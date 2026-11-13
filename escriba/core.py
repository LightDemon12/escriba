"""Transcripción y generación de documentos."""

from __future__ import annotations

import ctypes
import glob
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path

from .documento import (
    TIPOS,
    DocConfig,
    Minuta,
    partir,
    render_docx,
    render_json,
    render_md,
    render_srt,
    render_txt,
)


def _preload_cuda_libs():
    import importlib.util

    for pkg in ("nvidia.cublas", "nvidia.cudnn"):
        try:
            spec = importlib.util.find_spec(pkg)
        except ModuleNotFoundError:
            continue
        if not spec or not spec.submodule_search_locations:
            continue
        libs = glob.glob(os.path.join(list(spec.submodule_search_locations)[0], "lib", "*.so*"))
        for lib in sorted(libs):
            try:
                ctypes.CDLL(lib, mode=ctypes.RTLD_GLOBAL)
            except OSError:
                pass


_preload_cuda_libs()


class Cancelado(Exception):
    """El usuario canceló el proceso."""


def has_audio(path: Path) -> bool:
    r = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        return bool(json.loads(r.stdout or "{}").get("streams"))
    except json.JSONDecodeError:
        return False


def collect_inputs(paths, recursive=True):
    files = []
    for p in map(Path, paths):
        if p.is_dir():
            it = p.rglob("*") if recursive else p.glob("*")
            files += [f for f in sorted(it) if f.is_file() and not f.name.startswith(".")]
        elif p.is_file():
            files.append(p)
    return [f for f in files if has_audio(f)]


def extract_audio(src: Path, dst: Path):
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(src),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(dst),
        ],
        check=True,
    )


def fmt_ts(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def transcribe(
    model,
    audio: Path,
    language,
    block_secs=120,
    batch_size=1,
    beam_size=5,
    gpu_cap=100,
    on_progress=None,
    cancel=None,
    on_text=None,
):
    kw = dict(language=language, vad_filter=True, beam_size=beam_size, condition_on_previous_text=False)
    if batch_size > 1:
        from faster_whisper import BatchedInferencePipeline

        segments, info = BatchedInferencePipeline(model).transcribe(str(audio), batch_size=batch_size, **kw)
    else:
        segments, info = model.transcribe(str(audio), **kw)
    blocks, segs, cur_start, cur_text = [], [], None, []
    t_prev = time.monotonic()
    for seg in segments:
        if cancel is not None and cancel.is_set():
            raise Cancelado()
        if gpu_cap < 100:
            work = time.monotonic() - t_prev
            time.sleep(min(work * (100 / gpu_cap - 1), 5))
        t_prev = time.monotonic()
        if cur_start is None:
            cur_start = seg.start
        cur_text.append(seg.text.strip())
        segs.append((seg.start, seg.end, seg.text.strip()))
        if on_text:
            on_text(seg.start, seg.text.strip())
        if on_progress:
            on_progress(seg.end, info.duration)
        else:
            print(f"\r    {fmt_ts(seg.end)} / {fmt_ts(info.duration)}", end="", flush=True)
        if seg.end - cur_start >= block_secs:
            blocks.append((cur_start, " ".join(cur_text)))
            cur_start, cur_text = None, []
    if cur_text:
        blocks.append((cur_start, " ".join(cur_text)))
    if not on_progress:
        print()
    return info, blocks, segs


def resumir(blocks, tipo="minuta", modelo="claude-sonnet-5-5") -> dict:
    import anthropic

    info = TIPOS[tipo]
    claves = [k for k, _ in info["ia"]]
    texto = "\n".join(f"[{fmt_ts(s)}] {t}" for s, t in blocks)
    msg = anthropic.Anthropic().messages.create(
        model=modelo,
        max_tokens=4000,
        messages=[
            {
                "role": "user",
                "content": f"Con esta transcripción {info['pedido']} responde SOLO con un objeto JSON en español con "
                f"{info['claves']}, cada una una lista de textos breves. Usa solo lo que está en la "
                "transcripción; si no hay nada, devuelve una lista vacía.\n\n" + texto,
            }
        ],
    )
    raw = msg.content[0].text
    try:
        data = json.loads(raw[raw.index("{") : raw.rindex("}") + 1])
    except ValueError:
        data = {}
    return {k: [str(x) for x in data.get(k, [])] for k in claves}


def procesar(
    files,
    out_dir,
    modelo="large-v3-turbo",
    idioma=None,
    compute="float16",
    bloque=120,
    batch_size=1,
    beam_size=5,
    gpu_cap=100,
    device="cuda",
    gpu_index=0,
    resumen=False,
    formatos=("md", "docx"),
    doc: DocConfig | None = None,
    log=print,
    on_progress=None,
    on_file=None,
    cancel=None,
    on_stage=None,
    on_text=None,
):
    doc = doc or DocConfig()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stage = on_stage or (lambda *_: None)
    from faster_whisper import WhisperModel
    from faster_whisper.utils import download_model

    try:
        download_model(modelo, local_files_only=True)
    except Exception:
        stage("descarga")
        log(f"Descargando modelo {modelo} (solo la primera vez)...")
        download_model(modelo)
    stage("modelo")
    log(f"Cargando modelo {modelo} ({device}, {compute})...")
    model = WhisperModel(
        modelo, device=device, compute_type=compute, device_index=gpu_index if device == "cuda" else 0
    )
    creados = []
    for i, f in enumerate(files, 1):
        f = Path(f)
        if on_file:
            on_file(i, len(files), f)
        log(f"[{i}/{len(files)}] {f.name}")
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "audio.wav"
            stage("audio")
            extract_audio(f, wav)
            stage("transcribe")
            info, blocks, segs = transcribe(
                model, wav, idioma, bloque, batch_size, beam_size, gpu_cap, on_progress, cancel, on_text
            )
        stage("documento")
        minuta = Minuta(
            archivo=f.name,
            fecha=datetime.fromtimestamp(f.stat().st_mtime) if doc.fecha_modo == "video" else datetime.now(),
            duracion=fmt_ts(info.duration),
            idioma=info.language,
            prob=info.language_probability,
            bloques=blocks,
            segmentos=segs,
            resumen=resumir(blocks, doc.tipo) if resumen else None,
        )
        base = out_dir / f"{doc.info['prefijo']}_{f.stem}"
        creados += _escribir(base, minuta, doc, formatos)
        log(f"    -> {base}")
    return creados


def _escribir(base: Path, m: Minuta, doc: DocConfig, formatos) -> list[Path]:
    rutas = []
    if "md" in formatos:
        for p in partir(m, doc.partir_palabras):
            nombre = base.name + (f"_parte{p.parte[0]:02d}" if p.parte else "") + ".md"
            ruta = base.with_name(nombre)
            ruta.write_text(render_md(p, doc), encoding="utf-8")
            rutas.append(ruta)
    if "docx" in formatos:
        rutas.append(base.with_name(base.name + ".docx"))
        render_docx(m, doc, rutas[-1])
    if "txt" in formatos:
        rutas.append(base.with_name(base.name + ".txt"))
        rutas[-1].write_text(render_txt(m, doc), encoding="utf-8")
    if "srt" in formatos:
        rutas.append(base.with_name(base.name + ".srt"))
        rutas[-1].write_text(render_srt(m), encoding="utf-8")
    if "json" in formatos:
        rutas.append(base.with_name(base.name + ".json"))
        rutas[-1].write_text(render_json(m, doc), encoding="utf-8")
    return rutas
