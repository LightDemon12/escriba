import json
from datetime import datetime

import pytest

from escriba.documento import (
    TIPOS,
    DocConfig,
    Minuta,
    aplicar_tipo,
    minuta_ejemplo,
    partir,
    render_docx,
    render_html,
    render_json,
    render_md,
    render_srt,
    render_txt,
)


def test_config_ida_y_vuelta():
    c = DocConfig(titulo="ACTA", firmas=True, color="#ff0000", secciones_ia=["temas"])
    assert DocConfig.from_json(c.to_json()) == c


def test_config_ignora_claves_desconocidas_y_json_roto():
    assert DocConfig.from_json('{"titulo": "X", "inventada": 1}').titulo == "X"
    assert DocConfig.from_json("no es json") == DocConfig()
    assert DocConfig.from_json("[1, 2]") == DocConfig()
    assert DocConfig.from_json('{"tipo": "raro"}').tipo == "minuta"


@pytest.mark.parametrize("tipo", list(TIPOS))
def test_aplicar_tipo_conserva_aspecto(tipo):
    c = aplicar_tipo(DocConfig(fuente="Arial", color="#123456"), tipo)
    assert c.tipo == tipo
    assert c.titulo == TIPOS[tipo]["titulo"]
    assert (c.fuente, c.color) == ("Arial", "#123456")


def test_md_respeta_secciones():
    m = minuta_ejemplo()
    md = render_md(m, DocConfig(secciones_ia=["temas"], transcripcion=False, titulo="ACTA"))
    assert "# ACTA" in md
    assert "Acuerdos" not in md
    assert "Desarrollo de la reunión" not in md
    assert "Temas tratados" in md


def test_minuta_sin_resumen_deja_espacios_pero_clase_no():
    m = Minuta("a.mp4", datetime(2026, 1, 2), "00:01:00", "es", 0.9, [(0, "hola")])
    assert "_(completar)_" in render_md(m, DocConfig())
    clase = render_md(m, aplicar_tipo(DocConfig(), "clase"))
    assert "Conceptos clave" not in clase
    assert "Desarrollo de la clase" in clase


def test_clase_con_resumen_usa_sus_secciones():
    md = render_md(minuta_ejemplo("clase"), aplicar_tipo(DocConfig(), "clase"))
    assert "## Conceptos clave" in md
    assert "Preguntas de repaso" in md
    assert "Acuerdos" not in md


def test_frontmatter_yaml():
    c = aplicar_tipo(DocConfig(organizacion='Mi "Org"'), "transcripcion")
    md = render_md(minuta_ejemplo(), c)
    assert md.startswith("---\n")
    assert 'organizacion: "Mi \\"Org\\""' in md
    assert not render_md(minuta_ejemplo(), DocConfig()).startswith("---")


def test_formatos_de_transcripcion():
    m = minuta_ejemplo()
    assert "**[00:02:00]**" in render_md(m, DocConfig(formato_transcripcion="bloques_hora"))
    assert "**[00:02:00]**" not in render_md(m, DocConfig(formato_transcripcion="bloques"))
    assert "proyecto. Se presentó" in render_md(m, DocConfig(formato_transcripcion="corrido"))


def test_partir_en_fragmentos():
    bloques = [(i * 10, "palabra " * 50) for i in range(10)]
    m = Minuta("a.mp4", datetime(2026, 1, 2), "00:10:00", "es", 1.0, bloques)
    partes = partir(m, 200)
    assert len(partes) > 1
    assert sum(len(p.bloques) for p in partes) == 10
    assert partes[0].parte == (1, len(partes))
    c = aplicar_tipo(DocConfig(), "transcripcion")
    assert "parte 2 de" in render_md(partes[1], c)
    assert partir(m, 0) == [m]


def test_txt_srt_json():
    m = minuta_ejemplo()
    m.segmentos = [(0.0, 2.5, "Hola"), (3661.2, 3663.0, "Adiós")]
    assert "MINUTA DE REUNIÓN" in render_txt(m, DocConfig())
    srt = render_srt(m)
    assert "1\n00:00:00,000 --> 00:00:02,500\nHola" in srt
    assert "01:01:01,200 --> 01:01:03,000" in srt
    datos = json.loads(render_json(m, DocConfig()))
    assert datos["segmentos"][1]["texto"] == "Adiós"


def test_docx_se_genera(tmp_path):
    for tipo in TIPOS:
        destino = tmp_path / f"{tipo}.docx"
        render_docx(minuta_ejemplo(tipo), aplicar_tipo(DocConfig(firmas=True, papel="A4"), tipo), destino)
        assert destino.stat().st_size > 1000


def test_logo_invalido_no_rompe(tmp_path):
    destino = tmp_path / "m.docx"
    render_docx(minuta_ejemplo(), DocConfig(logo=str(tmp_path / "no_existe.png")), destino)
    assert destino.exists()


def test_html_escapa_texto():
    html = render_html(minuta_ejemplo(), DocConfig(organizacion="Mi <Org>"))
    assert "Mi &lt;Org&gt;" in html
