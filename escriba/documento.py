"""Configuración y renderizado de documentos."""

from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime
from pathlib import Path

FORMATOS_TRANSCRIPCION = {
    "bloques_hora": "Bloques con hora",
    "bloques": "Bloques sin hora",
    "corrido": "Texto corrido",
}
PAPELES = {"Carta": (21.59, 27.94), "A4": (21.0, 29.7), "Oficio": (21.59, 33.02)}
FUENTES = ["Calibri", "Arial", "Times New Roman", "Georgia", "Cambria", "Verdana", "Garamond"]


TIPOS = {
    "minuta": {
        "nombre": "Minuta de reunión",
        "corto": "Minuta",
        "titulo": "MINUTA DE REUNIÓN",
        "prefijo": "minuta",
        "personas": "Participantes",
        "cuerpo": "Desarrollo de la reunión",
        "ia": [
            ("temas", "Temas tratados"),
            ("acuerdos", "Acuerdos"),
            ("pendientes", "Pendientes y responsables"),
        ],
        "pedido": "de una reunión",
        "claves": 'las claves "temas" (temas tratados), "acuerdos" y "pendientes" (con responsable si se menciona)',
    },
    "clase": {
        "nombre": "Apuntes de clase",
        "corto": "Clase",
        "titulo": "Apuntes de clase",
        "prefijo": "clase",
        "personas": "Docente y curso",
        "cuerpo": "Desarrollo de la clase",
        "ia": [
            ("resumen", "Resumen de la clase"),
            ("conceptos", "Conceptos clave"),
            ("repaso", "Preguntas de repaso"),
        ],
        "pedido": "de una clase",
        "claves": 'las claves "resumen" (ideas principales), "conceptos" (términos o conceptos clave con su definición breve) y "repaso" (preguntas para estudiar)',
    },
    "transcripcion": {
        "nombre": "Transcripción para IA",
        "corto": "Para IA",
        "titulo": "Transcripción",
        "prefijo": "transcripcion",
        "personas": "Contexto",
        "cuerpo": "Transcripción",
        "ia": [("resumen", "Resumen")],
        "pedido": "de un video",
        "claves": 'la clave "resumen" (ideas principales)',
    },
}

FORMATOS_SALIDA = {
    "md": "Markdown (.md)",
    "docx": "Word (.docx)",
    "txt": "Texto plano (.txt)",
    "srt": "Subtítulos (.srt)",
    "json": "Datos (.json)",
}


@dataclass
class DocConfig:
    tipo: str = "minuta"

    titulo: str = "MINUTA DE REUNIÓN"
    organizacion: str = ""
    logo: str = ""
    lugar: str = ""
    fecha_modo: str = "video"
    participantes: str = ""

    datos: bool = True
    ver_participantes: bool = True
    secciones_ia: list = field(default_factory=lambda: ["temas", "acuerdos", "pendientes"])
    transcripcion: bool = True
    firmas: bool = False
    firmantes: str = "Elaboró; Revisó"
    formato_transcripcion: str = "bloques_hora"

    frontmatter: bool = False
    partir_palabras: int = 0

    fuente: str = "Calibri"
    tam: int = 11
    papel: str = "Carta"
    margen_cm: float = 2.5
    interlineado: float = 1.15
    color: str = "#1B2440"
    numeros_pagina: bool = True
    texto_pie: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, texto: str) -> "DocConfig":
        try:
            datos = json.loads(texto)
        except (TypeError, ValueError):
            return cls()
        if not isinstance(datos, dict):
            return cls()
        validos = {f.name for f in fields(cls)}
        c = cls(**{k: v for k, v in datos.items() if k in validos})
        if c.tipo not in TIPOS:
            c.tipo = "minuta"
        return c

    def lista_participantes(self) -> list[str]:
        return [x.strip() for x in self.participantes.splitlines() if x.strip()]

    def lista_firmantes(self) -> list[str]:
        return [x.strip() for x in self.firmantes.split(";") if x.strip()]

    @property
    def info(self) -> dict:
        return TIPOS[self.tipo]


def aplicar_tipo(c: DocConfig, tipo: str) -> DocConfig:
    t = TIPOS[tipo]
    base = dict(
        tipo=tipo,
        titulo=t["titulo"],
        datos=True,
        transcripcion=True,
        firmas=False,
        formato_transcripcion="bloques_hora",
        partir_palabras=0,
        secciones_ia=[k for k, _ in t["ia"]],
        ver_participantes=tipo != "transcripcion",
        frontmatter=tipo != "minuta",
    )
    if tipo == "transcripcion":
        base["secciones_ia"] = []
    return replace(c, **base)


@dataclass
class Minuta:
    archivo: str
    fecha: datetime
    duracion: str
    idioma: str
    prob: float
    bloques: list = field(default_factory=list)
    resumen: dict | None = None
    segmentos: list = field(default_factory=list)
    parte: tuple | None = None


def _hora(seg: float) -> str:
    seg = int(seg)
    return f"{seg // 3600:02d}:{seg % 3600 // 60:02d}:{seg % 60:02d}"


def _es_continuacion(m: Minuta) -> bool:
    return bool(m.parte and m.parte[0] > 1)


def _titulo(m: Minuta, c: DocConfig) -> str:
    return c.titulo + (f" (parte {m.parte[0]} de {m.parte[1]})" if m.parte else "")


def _datos(m: Minuta, c: DocConfig) -> list[tuple[str, str]]:
    filas = [("Fecha", m.fecha.strftime("%d/%m/%Y"))]
    if c.lugar:
        filas.append(("Lugar" if c.tipo == "minuta" else "Curso o lugar", c.lugar))
    filas += [
        ("Duración", m.duracion),
        ("Archivo de origen", m.archivo),
        ("Idioma detectado", f"{m.idioma} ({m.prob:.0%})"),
    ]
    return filas


def _secciones_ia(m: Minuta, c: DocConfig):
    res = m.resumen or {}
    out = []
    for clave, titulo in c.info["ia"]:
        if clave in c.secciones_ia:
            if m.resumen is None and c.tipo != "minuta":
                continue
            out.append((titulo, res.get(clave, []), m.resumen is None))
    return out


def _cuerpo_transcripcion(m: Minuta, c: DocConfig):
    if c.formato_transcripcion == "corrido":
        return [(None, " ".join(t for _, t in m.bloques))]
    con_hora = c.formato_transcripcion == "bloques_hora"
    return [(_hora(s) if con_hora else None, t) for s, t in m.bloques]


def _yaml(m: Minuta, c: DocConfig) -> list[str]:
    def q(x):
        return json.dumps(x, ensure_ascii=False)

    o = [
        "---",
        f"titulo: {q(c.titulo)}",
        f"tipo: {q(c.info['nombre'])}",
        f"fuente: {q(m.archivo)}",
        f"fecha: {m.fecha:%Y-%m-%d}",
        f"duracion: {q(m.duracion)}",
        f"idioma: {q(m.idioma)}",
    ]
    if c.organizacion:
        o.append(f"organizacion: {q(c.organizacion)}")
    if c.lugar:
        o.append(f"lugar: {q(c.lugar)}")
    if m.parte:
        o.append(f"parte: {m.parte[0]}/{m.parte[1]}")
    return o + ["---", ""]


def render_md(m: Minuta, c: DocConfig) -> str:
    o = _yaml(m, c) if c.frontmatter else []
    cont = _es_continuacion(m)
    if c.organizacion and not cont:
        o += [f"**{c.organizacion}**", ""]
    o += [f"# {_titulo(m, c)}", ""]
    if c.datos and not cont:
        o += [f"- **{k}:** {v}" for k, v in _datos(m, c)] + [""]
    if c.ver_participantes and not cont:
        o += [f"## {c.info['personas']}", ""]
        o += [f"- {p}" for p in c.lista_participantes()] or ["_(completar)_"]
        o += [""]
    if not cont:
        for titulo, items, espacio in _secciones_ia(m, c):
            o += [f"## {titulo}", ""]
            o += [f"- {x}" for x in items] or ["_(completar)_" if espacio else "_No identificado._"]
            o += [""]
    if c.transcripcion:
        o += [f"## {c.info['cuerpo']}", ""]
        for hora, texto in _cuerpo_transcripcion(m, c):
            o += [f"**[{hora}]** {texto}" if hora else texto, ""]
    if c.firmas and not cont:
        o += ["---", ""] + [f"{n}: ______________________" for n in c.lista_firmantes()] + [""]
    if c.texto_pie:
        o += ["---", f"_{c.texto_pie}_", ""]
    return "\n".join(o)


def render_txt(m: Minuta, c: DocConfig) -> str:
    o = [_titulo(m, c).upper(), ""]
    if c.datos:
        o += [f"{k}: {v}" for k, v in _datos(m, c)] + [""]
    for titulo, items, _ in _secciones_ia(m, c):
        if items:
            o += [titulo.upper()] + [f"- {x}" for x in items] + [""]
    if c.transcripcion:
        o += [c.info["cuerpo"].upper(), ""]
        for hora, texto in _cuerpo_transcripcion(m, c):
            o += [f"[{hora}] {texto}" if hora else texto, ""]
    return "\n".join(o)


def _srt_ts(seg: float) -> str:
    ms = int(round(seg * 1000))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d},{ms % 1000:03d}"


def render_srt(m: Minuta) -> str:
    return "\n".join(
        f"{i}\n{_srt_ts(a)} --> {_srt_ts(b)}\n{t}\n" for i, (a, b, t) in enumerate(m.segmentos, 1)
    )


def render_json(m: Minuta, c: DocConfig) -> str:
    return json.dumps(
        {
            "titulo": c.titulo,
            "tipo": c.tipo,
            "fuente": m.archivo,
            "fecha": f"{m.fecha:%Y-%m-%d}",
            "duracion": m.duracion,
            "idioma": m.idioma,
            "resumen": m.resumen,
            "segmentos": [{"inicio": round(a, 2), "fin": round(b, 2), "texto": t} for a, b, t in m.segmentos],
        },
        ensure_ascii=False,
        indent=2,
    )


def partir(m: Minuta, palabras: int) -> list[Minuta]:
    if palabras <= 0 or not m.bloques:
        return [m]
    grupos, actual, n = [], [], 0
    for b in m.bloques:
        actual.append(b)
        n += len(b[1].split())
        if n >= palabras:
            grupos.append(actual)
            actual, n = [], 0
    if actual:
        grupos.append(actual)
    return [
        replace(m, bloques=g, parte=(i, len(grupos)) if len(grupos) > 1 else None)
        for i, g in enumerate(grupos, 1)
    ]


def _rgb(hex_color: str):
    from docx.shared import RGBColor

    h = hex_color.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _campo(par, instruccion: str):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    run = par.add_run()
    for tipo, texto in (("begin", None), (None, instruccion), ("end", None)):
        if tipo:
            e = OxmlElement("w:fldChar")
            e.set(qn("w:fldCharType"), tipo)
        else:
            e = OxmlElement("w:instrText")
            e.set(qn("xml:space"), "preserve")
            e.text = texto
        run._r.append(e)


def _sombrear(celda, color_hex: str):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), color_hex.lstrip("#"))
    celda._tc.get_or_add_tcPr().append(shd)


def _aclarar(hex_color: str, k=0.9) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return "%02X%02X%02X" % tuple(int(x + (255 - x) * k) for x in (r, g, b))


def render_docx(m: Minuta, c: DocConfig, destino: Path):
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt

    doc = Document()
    sec = doc.sections[0]
    ancho, alto = PAPELES.get(c.papel, PAPELES["Carta"])
    sec.page_width, sec.page_height = Cm(ancho), Cm(alto)
    sec.left_margin = sec.right_margin = sec.top_margin = sec.bottom_margin = Cm(c.margen_cm)

    def fuente(estilo, tam, negrita=False, color=None):
        estilo.font.name = c.fuente
        estilo.element.rPr.rFonts.set(qn("w:eastAsia"), c.fuente)
        estilo.font.size = Pt(tam)
        estilo.font.bold = negrita
        if color:
            estilo.font.color.rgb = _rgb(color)

    fuente(doc.styles["Normal"], c.tam)
    doc.styles["Normal"].paragraph_format.line_spacing = c.interlineado
    doc.styles["Normal"].paragraph_format.space_after = Pt(6)
    fuente(doc.styles["Title"], c.tam + 9, True, c.color)
    fuente(doc.styles["Heading 1"], c.tam + 3, True, c.color)
    doc.styles["Heading 1"].paragraph_format.space_before = Pt(14)

    if c.logo and Path(c.logo).is_file():
        try:
            doc.add_picture(c.logo, height=Cm(1.8))
        except Exception:
            pass
    if c.organizacion:
        p = doc.add_paragraph()
        r = p.add_run(c.organizacion)
        r.bold = True
        r.font.color.rgb = _rgb(c.color)
    doc.add_paragraph(_titulo(m, c), style="Title")

    cont = _es_continuacion(m)
    if c.datos and not cont:
        t = doc.add_table(rows=0, cols=2)
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for k, v in _datos(m, c):
            fila = t.add_row().cells
            fila[0].text, fila[1].text = k, v
            fila[0].paragraphs[0].runs[0].bold = True
            _sombrear(fila[0], _aclarar(c.color))
            fila[0].width, fila[1].width = Cm(4.5), Cm(ancho - 2 * c.margen_cm - 4.5)

    if c.ver_participantes and not cont:
        doc.add_heading(c.info["personas"], 1)
        lista = c.lista_participantes()
        for x in lista:
            doc.add_paragraph(x, style="List Bullet")
        if not lista:
            doc.add_paragraph("(completar)")

    if not cont:
        for titulo, items, espacio in _secciones_ia(m, c):
            doc.add_heading(titulo, 1)
            for x in items:
                doc.add_paragraph(x, style="List Bullet")
            if not items:
                doc.add_paragraph("(completar)" if espacio else "No identificado.")

    if c.transcripcion:
        doc.add_heading(c.info["cuerpo"], 1)
        for hora, texto in _cuerpo_transcripcion(m, c):
            p = doc.add_paragraph()
            if hora:
                r = p.add_run(f"[{hora}] ")
                r.bold = True
                r.font.color.rgb = _rgb(c.color)
            p.add_run(texto)
            p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    if c.firmas and c.lista_firmantes() and not cont:
        doc.add_paragraph()
        nombres = c.lista_firmantes()
        t = doc.add_table(rows=1, cols=len(nombres))
        for celda, n in zip(t.rows[0].cells, nombres):
            celda.text = "\n\n______________________________\n" + n
            for par in celda.paragraphs:
                par.alignment = WD_ALIGN_PARAGRAPH.CENTER

    pie = sec.footer.paragraphs[0]
    pie.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if c.texto_pie:
        pie.add_run(c.texto_pie + ("   |   " if c.numeros_pagina else ""))
    if c.numeros_pagina:
        pie.add_run("Página ")
        _campo(pie, "PAGE")
        pie.add_run(" de ")
        _campo(pie, "NUMPAGES")
    for r in pie.runs:
        r.font.size = Pt(max(c.tam - 2, 8))
        r.font.color.rgb = _rgb("#6B7390")
    doc.save(destino)


def render_html(m: Minuta, c: DocConfig) -> str:
    e = html.escape
    h = [f"<body style=\"font-family:'{c.fuente}',sans-serif; font-size:{c.tam}pt; color:#222;\">"]
    if c.organizacion:
        h.append(f"<p style='color:{c.color}'><b>{e(c.organizacion)}</b></p>")
    h.append(f"<h1 style='color:{c.color}; font-size:{c.tam + 8}pt; margin:2px 0 8px'>{e(c.titulo)}</h1>")
    if c.datos:
        h.append("<table cellspacing='0' cellpadding='4' width='100%' style='border:1px solid #ccc'>")
        for k, v in _datos(m, c):
            h.append(
                f"<tr><td bgcolor='#{_aclarar(c.color)}' width='28%'><b>{e(k)}</b></td><td>{e(v)}</td></tr>"
            )
        h.append("</table>")

    def titulo(t):
        h.append(f"<h2 style='color:{c.color}; font-size:{c.tam + 2}pt; margin:12px 0 4px'>{e(t)}</h2>")

    def items(lst, vacio):
        if lst:
            h.append("<ul>" + "".join(f"<li>{e(x)}</li>" for x in lst) + "</ul>")
        else:
            h.append(f"<p style='color:#888'>{vacio}</p>")

    if c.ver_participantes:
        titulo(c.info["personas"])
        items(c.lista_participantes(), "(completar)")
    for t, lst, espacio in _secciones_ia(m, c):
        titulo(t)
        items(lst, "(completar)" if espacio else "No identificado.")
    if c.transcripcion:
        titulo(c.info["cuerpo"])
        for hora, texto in _cuerpo_transcripcion(m, c):
            pre = f"<b style='color:{c.color}'>[{hora}]</b> " if hora else ""
            h.append(f"<p align='justify'>{pre}{e(texto)}</p>")
    if c.firmas and c.lista_firmantes():
        celdas = "".join(
            f"<td align='center'><br><br>______________<br>{e(n)}</td>" for n in c.lista_firmantes()
        )
        h.append(f"<table width='100%'><tr>{celdas}</tr></table>")
    pie = " | ".join(x for x in (c.texto_pie, "Página 1 de 1" if c.numeros_pagina else "") if x)
    if pie:
        h.append(f"<p align='center' style='color:#888; font-size:{max(c.tam - 3, 7)}pt'>{e(pie)}</p>")
    h.append("</body>")
    return "".join(h)


def minuta_ejemplo(tipo: str = "minuta") -> Minuta:
    if tipo == "clase":
        return Minuta(
            archivo="clase_fisica_03.mp4",
            fecha=datetime(2026, 11, 10, 10, 30),
            duracion="01:10:00",
            idioma="es",
            prob=0.99,
            bloques=[
                (0, "Hoy vamos a ver la segunda ley de Newton y su relación con la fuerza neta."),
                (120, "La aceleración es proporcional a la fuerza e inversamente proporcional a la masa."),
            ],
            resumen={
                "resumen": ["La fuerza neta produce aceleración", "F = m a"],
                "conceptos": ["Fuerza neta: suma vectorial de todas las fuerzas"],
                "repaso": ["¿Qué ocurre con la aceleración si se duplica la masa?"],
            },
        )
    return Minuta(
        archivo="reunion_equipo.mp4",
        fecha=datetime(2026, 11, 10, 10, 30),
        duracion="00:42:15",
        idioma="es",
        prob=0.99,
        bloques=[
            (0, "Buenos días a todos. Iniciamos revisando el avance del proyecto."),
            (120, "Se presentó el presupuesto y se acordó enviarlo para su aprobación."),
        ],
        resumen={
            "temas": ["Avance del proyecto", "Presupuesto"],
            "acuerdos": ["Enviar el presupuesto para aprobación"],
            "pendientes": ["Juan: enviar el informe el viernes"],
            "resumen": ["Revisión del avance y del presupuesto"],
        },
    )
