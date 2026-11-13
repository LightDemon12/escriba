"""Línea de comandos de Escriba."""

import argparse
import sys
from pathlib import Path

from . import __version__
from .core import collect_inputs, procesar
from .documento import FORMATOS_SALIDA, TIPOS, DocConfig, aplicar_tipo


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="escriba-cli",
        description="Convierte cualquier video en texto (minutas, apuntes de clase, transcripciones) usando la GPU.",
    )
    ap.add_argument("entradas", nargs="+", help="videos o carpetas")
    ap.add_argument("-o", "--salida", default="minutas", help="carpeta de salida")
    ap.add_argument(
        "-m",
        "--modelo",
        default="large-v3-turbo",
        help="tiny, base, small, medium, large-v3-turbo o large-v3",
    )
    ap.add_argument(
        "-l", "--idioma", default=None, help="código de idioma (es, en...); por defecto se detecta"
    )
    ap.add_argument("--compute", default="float16", help="float16 o int8_float16 (menos VRAM)")
    ap.add_argument("--lote", type=int, default=8, help="tamaño de lote (más alto = más rápido y más VRAM)")
    ap.add_argument("--bloque", type=int, default=120, help="segundos por bloque de la minuta")
    ap.add_argument("--cpu", action="store_true", help="usar la CPU en lugar de la GPU")
    ap.add_argument(
        "-t",
        "--tipo",
        choices=list(TIPOS),
        default="minuta",
        help="minuta, clase o transcripcion (para IA); ajusta secciones y títulos",
    )
    ap.add_argument(
        "-f", "--formatos", default="md,docx", help="separados por coma: " + ", ".join(FORMATOS_SALIDA)
    )
    ap.add_argument(
        "--partir", type=int, default=0, help="partir el .md en archivos de ~N palabras (para IA)"
    )
    ap.add_argument("--diseno", type=Path, help="archivo JSON con el diseño del documento")
    ap.add_argument(
        "--resumen", action="store_true", help="temas y acuerdos con Claude (requiere ANTHROPIC_API_KEY)"
    )
    ap.add_argument("--version", action="version", version=f"escriba {__version__}")
    a = ap.parse_args(argv)

    archivos = collect_inputs(a.entradas)
    if not archivos:
        sys.exit("No se encontraron archivos con audio o video.")
    if a.diseno:
        doc = DocConfig.from_json(a.diseno.read_text(encoding="utf-8"))
    else:
        doc = aplicar_tipo(DocConfig(), a.tipo)
    if a.partir:
        doc.partir_palabras = a.partir
    formatos = tuple(x.strip() for x in a.formatos.split(",") if x.strip() in FORMATOS_SALIDA)
    if not formatos:
        sys.exit("Indica al menos un formato válido en --formatos.")
    procesar(
        archivos,
        a.salida,
        a.modelo,
        a.idioma,
        a.compute,
        a.bloque,
        batch_size=a.lote,
        device="cpu" if a.cpu else "cuda",
        resumen=a.resumen,
        formatos=formatos,
        doc=doc,
    )


if __name__ == "__main__":
    main()
