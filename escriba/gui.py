#!/usr/bin/env python3
"""Interfaz gráfica de Escriba."""

import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QProcess,
    QRectF,
    QRunnable,
    QSettings,
    Qt,
    QThread,
    QThreadPool,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import core
from .documento import (
    FORMATOS_SALIDA,
    FORMATOS_TRANSCRIPCION,
    FUENTES,
    PAPELES,
    TIPOS,
    DocConfig,
    aplicar_tipo,
    minuta_ejemplo,
    render_html,
)

TINTA, PAPEL, HOJA = "#1B2440", "#F3F4F8", "#FFFFFF"
COBALTO, RESALTADOR = "#3B5BDB", "#FFD43B"
VERDE, ROJO, GRIS = "#2F9E6B", "#D6455D", "#7B84A0"

ICONOS = Path(__file__).parent / "iconos"


def pixmap_icono(nombre, color, tam=18):
    datos = (ICONOS / f"{nombre}.svg").read_text(encoding="utf-8").replace("currentColor", color)
    pm = QPixmap(tam * 2, tam * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    QSvgRenderer(datos.encode()).render(p)
    p.end()
    pm.setDevicePixelRatio(2)
    return pm


def icono(nombre, color=TINTA, tam=18):
    return QIcon(pixmap_icono(nombre, color, tam))


def pixmap_punto(color, tam=10):
    pm = QPixmap(tam * 2, tam * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(2, 2, tam * 2 - 4, tam * 2 - 4)
    p.end()
    pm.setDevicePixelRatio(2)
    return pm


MODELOS = ["tiny", "base", "small", "medium", "large-v3-turbo", "large-v3"]
VRAM_FP16 = {"tiny": 0.8, "base": 1.0, "small": 1.8, "medium": 3.8, "large-v3-turbo": 2.4, "large-v3": 4.0}
COMPUTE = ["float16", "int8_float16", "int8", "float32"]
COMPUTE_FACTOR = {"float16": 1.0, "int8_float16": 0.65, "int8": 0.6, "float32": 2.0}
IDIOMAS = [
    ("Autodetectar", None),
    ("Español", "es"),
    ("Inglés", "en"),
    ("Portugués", "pt"),
    ("Francés", "fr"),
    ("Alemán", "de"),
    ("Italiano", "it"),
]
PERFILES = {
    "Rápido": dict(modelo="small", compute="float16", batch=16, beam=1),
    "Equilibrado": dict(modelo="large-v3-turbo", compute="float16", batch=8, beam=5),
    "Máxima calidad": dict(modelo="large-v3", compute="int8_float16", batch=4, beam=5),
}
ETAPAS = [
    ("Modelo", ("descarga", "modelo")),
    ("Audio", ("audio",)),
    ("Transcripción", ("transcribe",)),
    ("Documento", ("documento",)),
]
TEXTO_ETAPA = {
    "descarga": "Descargando el modelo (solo la primera vez, unos 1,6 GB)",
    "modelo": "Cargando el modelo en la GPU",
    "audio": "Extrayendo el audio",
    "transcribe": "Transcribiendo",
    "documento": "Escribiendo el documento",
}

QSS = f"""
* {{ font-family: "Inter", "Noto Sans", "Ubuntu", "DejaVu Sans"; font-size: 13px; color: {TINTA}; }}
QWidget#raiz {{ background: {PAPEL}; }}
QWidget#lateral {{ background: {TINTA}; }}
QWidget#lateral QLabel {{ color: #C9CFE4; }}
QWidget#lateral QLabel#marca {{ color: white; font-size: 19px; font-weight: 700; }}
QLabel#marcaSub {{ color: #8E98BD; font-size: 12px; }}
QLabel#titulo {{ font-size: 20px; font-weight: 700; }}
QLabel#sub {{ color: {GRIS}; }}
QLabel#grupo {{ font-size: 14px; font-weight: 700; }}
QLabel#cifra {{ color: white; font-size: 15px; font-weight: 600; }}
QProgressBar#vram {{ background: #2B3558; border: none; border-radius: 4px; max-height: 8px; min-height: 8px; }}
QProgressBar#vram::chunk {{ background: {RESALTADOR}; border-radius: 4px; }}
QFrame#panel {{ background: {HOJA}; border-radius: 14px; }}
QFrame#tarjeta {{ background: {HOJA}; border-radius: 12px; border: 1px solid #E3E6F0; }}
QFrame#tarjeta[estado="activo"] {{ border: 2px solid {RESALTADOR}; }}
QFrame#tarjeta[estado="listo"] {{ border: 1px solid {VERDE}; }}
QFrame#tarjeta[estado="error"] {{ border: 1px solid {ROJO}; }}
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ background: transparent; }}
QListWidget::item:selected {{ background: transparent; }}
QPushButton {{ background: {HOJA}; border: 1px solid #D5D9E8; border-radius: 9px; padding: 8px 14px; font-weight: 600; }}
QPushButton:hover {{ border-color: {COBALTO}; color: {COBALTO}; }}
QPushButton:disabled {{ color: #A9AFC4; background: #ECEEF5; }}
QPushButton#primario {{ background: {COBALTO}; border: none; color: white; font-size: 15px; padding: 12px 22px; }}
QPushButton#primario:hover {{ background: #2F4CC0; color: white; }}
QPushButton#primario:disabled {{ background: #B7C2EE; color: white; }}
QPushButton#peligro {{ color: {ROJO}; }}
QPushButton#seg {{ border-radius: 9px; padding: 9px 6px; background: #ECEEF5; border: 1px solid #ECEEF5; }}
QPushButton#seg:checked {{ background: {TINTA}; color: white; border-color: {TINTA}; }}
QToolButton#quitar {{ border: none; color: #A9AFC4; font-size: 16px; padding: 4px 8px; }}
QToolButton#quitar:hover {{ color: {ROJO}; }}
QToolButton#avanzado {{ border: none; font-weight: 600; color: {COBALTO}; padding: 4px 0; }}
QComboBox, QSpinBox {{ background: {HOJA}; border: 1px solid #D5D9E8; border-radius: 8px; padding: 6px 8px; min-height: 20px; }}
QComboBox QAbstractItemView {{ background: {HOJA}; selection-background-color: {COBALTO}; selection-color: white; }}
QSlider::groove:horizontal {{ height: 6px; background: #E3E6F0; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {COBALTO}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {HOJA}; border: 2px solid {COBALTO}; width: 14px; height: 14px; margin: -6px 0; border-radius: 9px; }}
QLineEdit, QPlainTextEdit {{ background: {HOJA}; border: 1px solid #D5D9E8; border-radius: 8px; padding: 6px 8px; }}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {COBALTO}; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid #B8BEDA; background: {HOJA}; }}
QCheckBox::indicator:checked {{ background: {COBALTO}; border-color: {COBALTO}; }}
QTextBrowser#hoja {{ background: #FFFEFA; border: 1px solid #E6E2D3; border-radius: 12px; padding: 10px 14px;
    font-family: "Source Serif 4", "Noto Serif", "DejaVu Serif"; font-size: 14px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ width: 10px; background: transparent; }}
QScrollBar::handle:vertical {{ background: #CDD2E4; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


def fmt(sec):
    sec = int(sec)
    return (
        f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"
        if sec >= 3600
        else f"{sec // 60:02d}:{sec % 60:02d}"
    )


def tam(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}".replace(".", ",")
        n /= 1024


class Medidor(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(170, 170)
        self.valor = 0

    def set_valor(self, v):
        self.valor = max(0, min(100, v))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(14, 14, self.width() - 28, self.height() - 28)
        pen = QPen(QColor("#2B3558"), 12, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(r, 225 * 16, -270 * 16)
        pen.setColor(QColor(RESALTADOR))
        p.setPen(pen)
        p.drawArc(r, 225 * 16, int(-270 * 16 * self.valor / 100))
        p.setPen(QColor("white"))
        f = QFont(self.font())
        f.setPixelSize(34)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(0, 52, self.width(), 44), Qt.AlignCenter, f"{self.valor:.0f}%")
        f.setPixelSize(12)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor("#8E98BD"))
        p.drawText(QRectF(0, 94, self.width(), 20), Qt.AlignCenter, "uso de GPU")


class BarraResaltador(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(16)
        self.valor = 0.0
        self.indet = False
        self.fase = 0.0
        t = QTimer(self, interval=30, timeout=self._tick)
        t.start()

    def _tick(self):
        if self.indet:
            self.fase = (self.fase + 0.012) % 1.0
            self.update()

    def set_valor(self, v):
        self.valor, self.indet = v, False
        self.update()

    def set_indet(self):
        self.indet = True

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#E3E6F0"))
        p.drawRoundedRect(0, 3, w, h - 6, 5, 5)
        p.setBrush(QColor(RESALTADOR))
        if self.indet:
            seg = w * 0.28
            x = -seg + (w + seg) * self.fase
            p.setClipRect(0, 0, w, h)
            p.drawRoundedRect(QRectF(x, 1, seg, h - 2), 6, 6)
        elif self.valor > 0:
            fw = max(12, w * self.valor)
            path = QPainterPath()
            path.moveTo(4, 1)
            path.lineTo(fw, 1)
            path.lineTo(fw - 5, h - 1)
            path.lineTo(0, h - 1)
            path.closeSubpath()
            p.drawPath(path)


class Tarjeta(QFrame):
    quitar = Signal(object)

    def __init__(self, ruta):
        super().__init__()
        self.ruta = ruta
        self.progreso = 0.0
        self.setObjectName("tarjeta")
        self.setProperty("estado", "pendiente")
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 10, 10, 10)
        h.setSpacing(12)
        self.mini = QLabel()
        self.mini.setFixedSize(128, 72)
        self.mini.setAlignment(Qt.AlignCenter)
        self.mini.setStyleSheet("background:#E9ECF5; border-radius:8px; color:#9AA3C0; font-size:22px;")
        self.mini.setPixmap(pixmap_icono("video", "#9AA3C0", 26))
        h.addWidget(self.mini)
        v = QVBoxLayout()
        v.setSpacing(2)
        self.nombre = QLabel(Path(ruta).name)
        self.nombre.setStyleSheet("font-weight:700; font-size:14px;")
        self.nombre.setToolTip(ruta)
        self.meta = QLabel(f"{tam(Path(ruta).stat().st_size)}")
        self.meta.setObjectName("sub")
        self.estado = QLabel("En espera")
        self.estado.setObjectName("sub")
        v.addStretch()
        v.addWidget(self.nombre)
        v.addWidget(self.meta)
        v.addWidget(self.estado)
        v.addStretch()
        h.addLayout(v, 1)
        b = QToolButton()
        b.setObjectName("quitar")
        b.setIcon(icono("x", GRIS, 14))
        b.setToolTip("Quitar de la lista")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda: self.quitar.emit(self))
        h.addWidget(b, 0, Qt.AlignTop)
        self.setFixedHeight(94)

    def set_miniatura(self, png, dur):
        if png:
            pm = QPixmap()
            pm.loadFromData(png)
            self.mini.setPixmap(pm.scaled(128, 72, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        self.meta.setText(f"{fmt(dur)}, {tam(Path(self.ruta).stat().st_size)}" if dur else self.meta.text())

    def set_estado(self, e, texto):
        self.setProperty("estado", e)
        self.estado.setText(texto)
        color = {"activo": "#9A7B00", "listo": VERDE, "error": ROJO}.get(e, GRIS)
        self.estado.setStyleSheet(f"color:{color}; font-weight:600;")
        self.style().unpolish(self)
        self.style().polish(self)

    def set_progreso(self, v):
        self.progreso = v
        self.update()

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if self.property("estado") == "activo" and self.progreso > 0:
            p = QPainter(self)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(RESALTADOR))
            p.drawRoundedRect(
                QRectF(150, self.height() - 14, (self.width() - 190) * self.progreso, 5), 2.5, 2.5
            )


class _Senales(QObject):
    listo = Signal(object, bytes, float)


class CargaMiniatura(QRunnable):
    def __init__(self, tarjeta, senales):
        super().__init__()
        self.t, self.s = tarjeta, senales

    def run(self):
        png, dur = b"", 0.0
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", self.t.ruta],
                capture_output=True,
                text=True,
                timeout=20,
            )
            dur = float(r.stdout.strip() or 0)
            r = subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-ss",
                    str(min(3, dur / 2)),
                    "-i",
                    self.t.ruta,
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=256:-2",
                    "-f",
                    "image2pipe",
                    "-vcodec",
                    "png",
                    "-",
                ],
                capture_output=True,
                timeout=30,
            )
            png = r.stdout
        except Exception:
            pass
        self.s.listo.emit(self.t, png, dur)


class Etapa(QWidget):
    def __init__(self, texto):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 2, 0, 2)
        self.punto = QLabel()
        self.txt = QLabel(texto)
        h.addWidget(self.punto)
        h.addWidget(self.txt, 1)
        self.set_estado(0)

    def set_estado(self, e):
        col = {0: "#3A4670", 1: RESALTADOR, 2: "#6FD3A5"}[e]
        self.punto.setPixmap(pixmap_punto(col))
        self.txt.setStyleSheet(
            f"color:{'white' if e == 1 else '#8E98BD' if e == 0 else '#C9CFE4'};"
            f"font-weight:{'700' if e == 1 else '400'};"
        )


class Worker(QObject):
    log = Signal(str)
    progress = Signal(float, float)
    file = Signal(int, int, str)
    stage = Signal(str)
    text = Signal(float, str)
    done = Signal(list, str)

    def __init__(self, files, out_dir, opts):
        super().__init__()
        self.files, self.out_dir, self.opts = files, out_dir, opts
        self.cancel = threading.Event()

    def run(self):
        err, creados = "", []
        try:
            creados = core.procesar(
                self.files,
                self.out_dir,
                log=self.log.emit,
                on_progress=lambda a, b: self.progress.emit(a, b),
                on_file=lambda i, n, f: self.file.emit(i, n, f.name),
                on_stage=self.stage.emit,
                on_text=lambda s, t: self.text.emit(s, t),
                cancel=self.cancel,
                **self.opts,
            )
        except core.Cancelado:
            err = "Proceso cancelado."
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        self.done.emit([str(c) for c in creados], err)


class DisenoDialog(QDialog):
    def __init__(self, cfg: DocConfig, parent=None):
        super().__init__(parent)
        self.setObjectName("raiz")
        self.setWindowTitle("Diseño del documento")
        self.resize(1040, 700)
        self.cfg = cfg
        self._cargando = True
        raiz = QHBoxLayout(self)
        raiz.setSpacing(16)

        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFixedWidth(400)
        cont = QWidget()
        sc.setWidget(cont)
        v = QVBoxLayout(cont)
        v.setSpacing(12)

        def grupo(titulo):
            f = QFrame()
            f.setObjectName("panel")
            lay = QFormLayout(f)
            lay.setContentsMargins(16, 14, 16, 16)
            lay.setVerticalSpacing(9)
            t = QLabel(titulo)
            t.setObjectName("grupo")
            lay.addRow(t)
            v.addWidget(f)
            return lay

        g = grupo(f"Encabezado ({cfg.info['nombre'].lower()})")
        self.titulo = QLineEdit(cfg.titulo)
        g.addRow("Título", self.titulo)
        self.org = QLineEdit(cfg.organizacion)
        self.org.setPlaceholderText("Nombre de la institución")
        g.addRow("Organización", self.org)
        self.lugar = QLineEdit(cfg.lugar)
        g.addRow("Lugar", self.lugar)
        self.logo = QPushButton(
            icono("image-plus"), " " + (Path(cfg.logo).name if cfg.logo else "Elegir imagen")
        )
        self.logo.clicked.connect(self._pick_logo)
        self.logo_ruta = cfg.logo
        g.addRow("Logo", self.logo)
        self.fecha = QComboBox()
        self.fecha.addItem("Fecha del archivo de video", "video")
        self.fecha.addItem("Fecha de hoy", "hoy")
        self.fecha.setCurrentIndex(0 if cfg.fecha_modo == "video" else 1)
        g.addRow("Fecha", self.fecha)

        g = grupo("Qué incluye")
        self.chk, self.ia = {}, {}
        info = cfg.info
        filas = (
            [
                ("datos", "Datos generales (fecha, duración, archivo)", False),
                ("ver_participantes", info["personas"], False),
            ]
            + [(k, t, True) for k, t in info["ia"]]
            + [("transcripcion", info["cuerpo"], False), ("firmas", "Firmas", False)]
        )
        for clave, texto, es_ia in filas:
            c = QCheckBox(texto)
            if es_ia:
                c.setChecked(clave in cfg.secciones_ia)
                self.ia[clave] = c
            else:
                c.setChecked(getattr(cfg, clave))
                self.chk[clave] = c
            g.addRow(c)
        self.part = QPlainTextEdit(cfg.participantes)
        self.part.setPlaceholderText("Una línea por cada dato")
        self.part.setFixedHeight(80)
        g.addRow(info["personas"], self.part)
        self.firmantes = QLineEdit(cfg.firmantes)
        self.firmantes.setToolTip("Separados por punto y coma")
        g.addRow("Firmantes", self.firmantes)
        self.formato = QComboBox()
        for k, t in FORMATOS_TRANSCRIPCION.items():
            self.formato.addItem(t, k)
        self.formato.setCurrentIndex(list(FORMATOS_TRANSCRIPCION).index(cfg.formato_transcripcion))
        g.addRow("Transcripción", self.formato)

        g = grupo("Para usar con una IA")
        self.front = QCheckBox("Cabecera de datos (YAML) en el .md")
        self.front.setChecked(cfg.frontmatter)
        g.addRow(self.front)
        self.partir = QSpinBox()
        self.partir.setRange(0, 200000)
        self.partir.setSingleStep(1000)
        self.partir.setSpecialValueText("No partir")
        self.partir.setSuffix(" palabras")
        self.partir.setValue(cfg.partir_palabras)
        self.partir.setToolTip("Divide el .md en archivos para IA con límite de contexto")
        g.addRow("Partir .md", self.partir)

        g = grupo("Aspecto")
        self.fuente = QComboBox()
        self.fuente.addItems(FUENTES)
        self.fuente.setCurrentText(cfg.fuente)
        g.addRow("Letra", self.fuente)
        self.tam = QSpinBox()
        self.tam.setRange(8, 18)
        self.tam.setValue(cfg.tam)
        self.tam.setSuffix(" pt")
        g.addRow("Tamaño", self.tam)
        self.papel = QComboBox()
        self.papel.addItems(list(PAPELES))
        self.papel.setCurrentText(cfg.papel)
        g.addRow("Papel", self.papel)
        self.margen = QDoubleSpinBox()
        self.margen.setRange(1.0, 4.0)
        self.margen.setSingleStep(0.5)
        self.margen.setValue(cfg.margen_cm)
        self.margen.setSuffix(" cm")
        g.addRow("Márgenes", self.margen)
        self.interl = QDoubleSpinBox()
        self.interl.setRange(1.0, 2.0)
        self.interl.setSingleStep(0.05)
        self.interl.setValue(cfg.interlineado)
        g.addRow("Interlineado", self.interl)
        self.color = QPushButton(cfg.color)
        self.color_val = cfg.color
        self._pintar_color()
        self.color.clicked.connect(self._pick_color)
        g.addRow("Color de títulos", self.color)
        self.pagnum = QCheckBox("Numerar páginas")
        self.pagnum.setChecked(cfg.numeros_pagina)
        g.addRow(self.pagnum)
        self.pie = QLineEdit(cfg.texto_pie)
        self.pie.setPlaceholderText("Texto al pie de cada página")
        g.addRow("Pie", self.pie)
        v.addStretch()

        col = QVBoxLayout()
        col.addWidget(sc, 1)
        raiz.addLayout(col)

        der = QVBoxLayout()
        t = QLabel("Vista previa con datos de ejemplo")
        t.setObjectName("sub")
        der.addWidget(t)
        self.vista = QTextBrowser()
        self.vista.setStyleSheet(
            "background:white; border:1px solid #D5D9E8; border-radius:10px; padding:18px;"
        )
        der.addWidget(self.vista, 1)
        h = QHBoxLayout()
        b0 = QPushButton("Restablecer")
        b0.clicked.connect(self._reset)
        b1 = QPushButton("Cancelar")
        b1.clicked.connect(self.reject)
        b2 = QPushButton("Guardar diseño")
        b2.setObjectName("primario")
        b2.clicked.connect(self.accept)
        h.addWidget(b0)
        h.addStretch()
        h.addWidget(b1)
        h.addWidget(b2)
        der.addLayout(h)
        raiz.addLayout(der, 1)

        for w in (self.titulo, self.org, self.lugar, self.firmantes, self.pie):
            w.textChanged.connect(self.refrescar)
        for w in (self.fecha, self.formato, self.fuente, self.papel):
            w.currentIndexChanged.connect(self.refrescar)
        for w in (self.tam, self.margen, self.interl, self.partir):
            w.valueChanged.connect(self.refrescar)
        for w in list(self.chk.values()) + list(self.ia.values()) + [self.pagnum, self.front]:
            w.toggled.connect(self.refrescar)
        self.part.textChanged.connect(self.refrescar)
        self._cargando = False
        self.refrescar()

    def _pick_logo(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Logo", str(Path.home()), "Imágenes (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if f:
            self.logo_ruta = f
            self.logo.setText(" " + Path(f).name)
            self.refrescar()

    def _pintar_color(self):
        self.color.setStyleSheet(f"background:{self.color_val}; color:white; border:none;")
        self.color.setText(self.color_val)

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self.color_val), self, "Color de títulos")
        if c.isValid():
            self.color_val = c.name()
            self._pintar_color()
            self.refrescar()

    def _reset(self):
        d = aplicar_tipo(DocConfig(), self.cfg.tipo)
        self._cargando = True
        self.titulo.setText(d.titulo)
        self.org.setText(d.organizacion)
        self.lugar.setText(d.lugar)
        self.logo_ruta = ""
        self.logo.setText(" Elegir imagen")
        self.fecha.setCurrentIndex(0)
        for k, c in self.chk.items():
            c.setChecked(getattr(d, k))
        for k, c in self.ia.items():
            c.setChecked(k in d.secciones_ia)
        self.front.setChecked(d.frontmatter)
        self.partir.setValue(d.partir_palabras)
        self.part.setPlainText(d.participantes)
        self.firmantes.setText(d.firmantes)
        self.formato.setCurrentIndex(0)
        self.fuente.setCurrentText(d.fuente)
        self.tam.setValue(d.tam)
        self.papel.setCurrentText(d.papel)
        self.margen.setValue(d.margen_cm)
        self.interl.setValue(d.interlineado)
        self.color_val = d.color
        self._pintar_color()
        self.pagnum.setChecked(d.numeros_pagina)
        self.pie.setText(d.texto_pie)
        self._cargando = False
        self.refrescar()

    def resultado(self) -> DocConfig:
        return DocConfig(
            titulo=self.titulo.text() or "MINUTA DE REUNIÓN",
            organizacion=self.org.text(),
            logo=self.logo_ruta,
            lugar=self.lugar.text(),
            fecha_modo=self.fecha.currentData(),
            participantes=self.part.toPlainText(),
            firmantes=self.firmantes.text(),
            formato_transcripcion=self.formato.currentData(),
            fuente=self.fuente.currentText(),
            tam=self.tam.value(),
            papel=self.papel.currentText(),
            margen_cm=self.margen.value(),
            interlineado=self.interl.value(),
            color=self.color_val,
            numeros_pagina=self.pagnum.isChecked(),
            texto_pie=self.pie.text(),
            tipo=self.cfg.tipo,
            secciones_ia=[k for k, c in self.ia.items() if c.isChecked()],
            frontmatter=self.front.isChecked(),
            partir_palabras=self.partir.value(),
            **{k: c.isChecked() for k, c in self.chk.items()},
        )

    def refrescar(self, *_):
        if self._cargando:
            return
        self.vista.setHtml(render_html(minuta_ejemplo(self.cfg.tipo), self.resultado()))


class Ventana(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("raiz")
        self.setWindowTitle("Escriba")
        self.resize(1240, 800)
        self.setMinimumSize(1080, 700)
        self.setAcceptDrops(True)
        self.cfg = QSettings("escriba", "gui")
        self.thread = self.worker = None
        self.tarjetas = []
        self.activa = None
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(2)
        self.senales = _Senales()
        self.senales.listo.connect(lambda t, png, d: t.set_miniatura(png, d))
        self.vram_total = 6.0
        self.t0 = 0.0
        self._aplicando = False
        self._build()
        self._load()
        self._gpu_proc = QProcess(self)
        self._gpu_proc.finished.connect(self._gpu_leido)
        QTimer(self, interval=1500, timeout=self._poll_gpu).start()
        self._poll_gpu()
        self._refrescar_vacio()

    def _build(self):
        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        lat = QWidget()
        lat.setObjectName("lateral")
        lat.setFixedWidth(250)
        v = QVBoxLayout(lat)
        v.setContentsMargins(22, 26, 22, 22)
        m = QLabel("Escriba")
        m.setObjectName("marca")
        s = QLabel("Del video al texto, con tu GPU")
        s.setObjectName("marcaSub")
        v.addWidget(m)
        v.addWidget(s)
        v.addSpacing(18)
        self.medidor = Medidor()
        v.addWidget(self.medidor, 0, Qt.AlignHCenter)
        self.gpu_nombre = QLabel("GPU")
        self.gpu_nombre.setAlignment(Qt.AlignCenter)
        self.gpu_nombre.setWordWrap(True)
        v.addWidget(self.gpu_nombre)
        v.addSpacing(10)
        self.vram_lbl = QLabel("Memoria de video")
        v.addWidget(self.vram_lbl)
        from PySide6.QtWidgets import QProgressBar

        self.vram_bar = QProgressBar()
        self.vram_bar.setObjectName("vram")
        self.vram_bar.setTextVisible(False)
        self.vram_bar.setRange(0, 1000)
        v.addWidget(self.vram_bar)
        self.temp_lbl = QLabel("")
        v.addWidget(self.temp_lbl)
        v.addSpacing(18)
        self.velocidad = QLabel("")
        self.velocidad.setObjectName("cifra")
        v.addWidget(self.velocidad)
        self.eta = QLabel("")
        v.addWidget(self.eta)
        v.addStretch()
        self.etapas = []
        for nombre, _ in ETAPAS:
            e = Etapa(nombre)
            self.etapas.append(e)
            v.addWidget(e)
        raiz.addWidget(lat)

        cuerpo = QVBoxLayout()
        cuerpo.setContentsMargins(24, 22, 24, 20)
        cuerpo.setSpacing(14)
        raiz.addLayout(cuerpo, 1)

        arriba = QHBoxLayout()
        arriba.setSpacing(20)
        cuerpo.addLayout(arriba, 1)

        centro = QVBoxLayout()
        cab = QHBoxLayout()
        t = QLabel("Videos")
        t.setObjectName("titulo")
        self.contador = QLabel("")
        self.contador.setObjectName("sub")
        cab.addWidget(t)
        cab.addWidget(self.contador)
        cab.addStretch()
        for txt, ic, fn in (
            ("Agregar videos", "video", self.add_files),
            ("Carpeta", "folder-plus", self.add_folder),
            ("Vaciar", "trash", self.vaciar),
        ):
            b = QPushButton(icono(ic), " " + txt)
            b.setToolTip({"Carpeta": "Agregar todos los videos de una carpeta"}.get(txt, txt))
            b.clicked.connect(fn)
            cab.addWidget(b)
        centro.addLayout(cab)
        self.vacio = QLabel(
            "Arrastra aquí tus videos o una carpeta\n\nSirve cualquier formato: mp4, mkv, avi, mov, webm…"
        )
        self.vacio.setAlignment(Qt.AlignCenter)
        self.vacio.setStyleSheet(
            f"border:2px dashed #BFC6E0; border-radius:16px; color:{GRIS}; font-size:15px; background:rgba(255,255,255,0.5);"
        )
        centro.addWidget(self.vacio, 1)
        self.lista = QListWidget()
        self.lista.setSpacing(8)
        self.lista.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        centro.addWidget(self.lista, 1)
        arriba.addLayout(centro, 1)

        arriba.addWidget(self._panel_ajustes())

        cuerpo.addWidget(self._panel_hoja())

    def _panel_ajustes(self):
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFixedWidth(340)
        cont = QWidget()
        sc.setWidget(cont)
        v = QVBoxLayout(cont)
        v.setContentsMargins(0, 0, 6, 0)
        v.setSpacing(12)

        t = QLabel("Ajustes")
        t.setObjectName("titulo")
        v.addWidget(t)

        panel = QFrame()
        panel.setObjectName("panel")
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(16, 14, 16, 16)
        pv.setSpacing(10)
        lbl_t = QLabel("¿Qué quieres obtener?")
        lbl_t.setObjectName("grupo")
        pv.addWidget(lbl_t)
        seg = QHBoxLayout()
        seg.setSpacing(6)
        self.grupo_tipo = QButtonGroup(self)
        self.btn_tipo = {}
        for clave, info in TIPOS.items():
            b = QPushButton(info["corto"])
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setToolTip(info["nombre"])
            b.clicked.connect(lambda _, k=clave: self.elegir_tipo(k))
            self.grupo_tipo.addButton(b)
            self.btn_tipo[clave] = b
            seg.addWidget(b)
        pv.addLayout(seg)
        self.tipo_desc = QLabel("")
        self.tipo_desc.setObjectName("sub")
        self.tipo_desc.setWordWrap(True)
        pv.addWidget(self.tipo_desc)
        v.addWidget(panel)

        panel = QFrame()
        panel.setObjectName("panel")
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(16, 14, 16, 16)
        pv.setSpacing(10)
        lbl_t = QLabel("Calidad y velocidad")
        lbl_t.setObjectName("grupo")
        pv.addWidget(lbl_t)
        seg = QHBoxLayout()
        seg.setSpacing(6)
        self.grupo_perfil = QButtonGroup(self)
        self.btn_perfil = {}
        for nombre in list(PERFILES) + ["Personalizado"]:
            b = QPushButton(nombre if nombre != "Máxima calidad" else "Máxima")
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setToolTip(nombre)
            b.clicked.connect(lambda _, n=nombre: self.aplicar_perfil(n))
            self.grupo_perfil.addButton(b)
            self.btn_perfil[nombre] = b
            seg.addWidget(b)
        self.btn_perfil["Personalizado"].setText("Propio")
        pv.addLayout(seg)
        self.perfil_desc = QLabel("")
        self.perfil_desc.setObjectName("sub")
        self.perfil_desc.setWordWrap(True)
        pv.addWidget(self.perfil_desc)
        self.vram_est = QLabel("")
        pv.addWidget(self.vram_est)
        from PySide6.QtWidgets import QProgressBar

        self.vram_est_bar = QProgressBar()
        self.vram_est_bar.setObjectName("vram")
        self.vram_est_bar.setStyleSheet(
            f"QProgressBar#vram {{ background:#E3E6F0; }} QProgressBar#vram::chunk {{ background:{COBALTO}; }}"
        )
        self.vram_est_bar.setTextVisible(False)
        self.vram_est_bar.setRange(0, 1000)
        pv.addWidget(self.vram_est_bar)
        v.addWidget(panel)

        panel = QFrame()
        panel.setObjectName("panel")
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(16, 14, 16, 16)
        pv.setSpacing(8)
        lbl_t = QLabel("Idioma del audio")
        lbl_t.setObjectName("grupo")
        pv.addWidget(lbl_t)
        self.idioma = QComboBox()
        for n, c in IDIOMAS:
            self.idioma.addItem(n, c)
        pv.addWidget(self.idioma)
        lbl_t = QLabel("Guardar en")
        lbl_t.setObjectName("grupo")
        pv.addSpacing(6)
        pv.addWidget(lbl_t)
        self.out_btn = QPushButton(icono("folder"), " Elegir carpeta")
        self.out_btn.clicked.connect(self.pick_out)
        pv.addWidget(self.out_btn)
        self.chk_fmt = {k: QCheckBox(t) for k, t in FORMATOS_SALIDA.items()}
        self.chk_res = QCheckBox("Resumen con Claude (opcional)")
        self.chk_res.setToolTip("Requiere la variable ANTHROPIC_API_KEY")
        pv.addSpacing(6)
        lbl_t = QLabel("Formatos")
        lbl_t.setObjectName("grupo")
        pv.addWidget(lbl_t)
        for c in (*self.chk_fmt.values(), self.chk_res):
            pv.addWidget(c)
        pv.addSpacing(6)
        self.btn_diseno = QPushButton(icono("palette"), " Diseño del documento")
        self.btn_diseno.setToolTip("Elige qué secciones lleva el documento y cómo se ve")
        self.btn_diseno.clicked.connect(self.editar_diseno)
        pv.addWidget(self.btn_diseno)
        v.addWidget(panel)

        self.btn_av = QToolButton()
        self.btn_av.setObjectName("avanzado")
        self.btn_av.setText(" Ajustes avanzados")
        self.btn_av.setIcon(icono("chevron-right", COBALTO, 16))
        self.btn_av.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_av.setCheckable(True)
        self.btn_av.setCursor(Qt.PointingHandCursor)
        v.addWidget(self.btn_av)
        self.av = QFrame()
        self.av.setObjectName("panel")
        f = QFormLayout(self.av)
        f.setContentsMargins(16, 14, 16, 16)
        f.setVerticalSpacing(10)
        self.modelo = QComboBox()
        self.modelo.addItems(MODELOS)
        f.addRow("Modelo", self.modelo)
        self.device = QComboBox()
        self.device.addItems(["cuda", "cpu"])
        f.addRow("Dispositivo", self.device)
        self.gpu_idx = QSpinBox()
        self.gpu_idx.setRange(0, 7)
        f.addRow("GPU número", self.gpu_idx)
        self.compute = QComboBox()
        self.compute.addItems(COMPUTE)
        f.addRow("Precisión", self.compute)
        self.batch, self.batch_lbl = self._slider(1, 32, lambda x: f"{x}")
        f.addRow("Lote", self.batch)
        self.cap, self.cap_lbl = self._slider(10, 100, lambda x: f"{x}%")
        f.addRow("Tope de GPU", self.cap)
        self.beam = QSpinBox()
        self.beam.setRange(1, 10)
        f.addRow("Beam size", self.beam)
        self.bloque = QSpinBox()
        self.bloque.setRange(30, 900)
        self.bloque.setSingleStep(30)
        self.bloque.setSuffix(" s")
        f.addRow("Bloque", self.bloque)
        self.av.setVisible(False)
        v.addWidget(self.av)
        self.btn_av.toggled.connect(self._toggle_av)
        v.addStretch()

        for w in (self.modelo, self.compute):
            w.currentIndexChanged.connect(self._ajuste_manual)
        for w in (self.batch, self.beam):
            w.valueChanged.connect(self._ajuste_manual)
        for w in (self.modelo, self.compute, self.batch, self.device):
            if isinstance(w, QComboBox):
                w.currentIndexChanged.connect(self._actualizar_vram_est)
            else:
                w.valueChanged.connect(self._actualizar_vram_est)
        return sc

    def _slider(self, lo, hi, texto):
        cont = QWidget()
        h = QHBoxLayout(cont)
        h.setContentsMargins(0, 0, 0, 0)
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi)
        lbl = QLabel()
        lbl.setFixedWidth(38)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        s.valueChanged.connect(lambda x: lbl.setText(texto(x)))
        h.addWidget(s, 1)
        h.addWidget(lbl)
        cont.value = s.value
        cont.setValue = s.setValue
        cont.valueChanged = s.valueChanged
        return cont, lbl

    def _panel_hoja(self):
        p = QFrame()
        p.setObjectName("panel")
        p.setFixedHeight(220)
        v = QVBoxLayout(p)
        v.setContentsMargins(18, 14, 18, 16)
        v.setSpacing(8)
        cab = QHBoxLayout()
        self.etapa_lbl = QLabel("Listo para empezar")
        self.etapa_lbl.setObjectName("grupo")
        cab.addWidget(self.etapa_lbl, 1)
        self.btn_abrir = QPushButton(icono("folder-open"), " Abrir carpeta de salida")
        self.btn_abrir.clicked.connect(self.abrir_salida)
        self.btn_stop = QPushButton(icono("square", ROJO, 14), " Cancelar")
        self.btn_stop.setObjectName("peligro")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop)
        self.btn_go = QPushButton(icono("play", "#FFFFFF"), " Generar documentos")
        self.btn_go.setObjectName("primario")
        self.btn_go.clicked.connect(self.start)
        for b in (self.btn_abrir, self.btn_stop, self.btn_go):
            cab.addWidget(b)
        v.addLayout(cab)
        self.barra = BarraResaltador()
        v.addWidget(self.barra)
        self.hoja = QTextBrowser()
        self.hoja.setObjectName("hoja")
        self.hoja.setOpenExternalLinks(True)
        self.hoja.document().setMaximumBlockCount(600)
        self.hoja.setPlaceholderText("Aquí aparecerá el texto del video a medida que se transcribe.")
        v.addWidget(self.hoja, 1)
        return p

    def _toggle_av(self, on):
        self.av.setVisible(on)
        self.btn_av.setIcon(icono("chevron-down" if on else "chevron-right", COBALTO, 16))

    def _load(self):
        self._aplicando = True
        c = self.cfg
        self.modelo.setCurrentText(c.value("modelo", "large-v3-turbo"))
        self.device.setCurrentText(c.value("device", "cuda"))
        self.gpu_idx.setValue(int(c.value("gpu_idx", 0)))
        self.compute.setCurrentText(c.value("compute", "float16"))
        self.batch.setValue(int(c.value("batch", 8)))
        self.cap.setValue(int(c.value("cap", 100)))
        self.beam.setValue(int(c.value("beam", 5)))
        self.idioma.setCurrentIndex(int(c.value("idioma", 1)))
        self.bloque.setValue(int(c.value("bloque", 120)))
        activos = str(c.value("formatos", "md,docx")).split(",")
        for k, w in self.chk_fmt.items():
            w.setChecked(k in activos)
        self.chk_res.setChecked(c.value("res", "false") == "true")
        self.salida = c.value("out", "")
        self.diseno = DocConfig.from_json(c.value("diseno", ""))
        self._pintar_tipo()
        self._pintar_salida()
        self._aplicando = False
        self._detectar_perfil()
        self._actualizar_vram_est()

    def _save(self):
        c = self.cfg
        for k, w in (
            ("modelo", self.modelo.currentText()),
            ("device", self.device.currentText()),
            ("gpu_idx", self.gpu_idx.value()),
            ("compute", self.compute.currentText()),
            ("batch", self.batch.value()),
            ("cap", self.cap.value()),
            ("beam", self.beam.value()),
            ("idioma", self.idioma.currentIndex()),
            ("bloque", self.bloque.value()),
            ("formatos", ",".join(self.formatos())),
            ("res", str(self.chk_res.isChecked()).lower()),
            ("out", self.salida),
            ("diseno", self.diseno.to_json()),
        ):
            c.setValue(k, w)

    def aplicar_perfil(self, nombre):
        if nombre == "Personalizado":
            self.btn_av.setChecked(True)
            self.perfil_desc.setText("Ajusta modelo, lote y precisión en Ajustes avanzados.")
            return
        d = PERFILES[nombre]
        self._aplicando = True
        self.modelo.setCurrentText(d["modelo"])
        self.compute.setCurrentText(d["compute"])
        self.batch.setValue(d["batch"])
        self.beam.setValue(d["beam"])
        self._aplicando = False
        self._detectar_perfil()
        self._actualizar_vram_est()

    def _detectar_perfil(self):
        actual = dict(
            modelo=self.modelo.currentText(),
            compute=self.compute.currentText(),
            batch=self.batch.value(),
            beam=self.beam.value(),
        )
        sel = "Personalizado"
        for n, d in PERFILES.items():
            if d == actual:
                sel = n
        self.btn_perfil[sel].setChecked(True)
        self.perfil_desc.setText(
            {
                "Rápido": "Modelo pequeño y lotes grandes. Ideal para borradores.",
                "Equilibrado": "Buena precisión sin saturar la GPU. Recomendado.",
                "Máxima calidad": "El modelo más preciso. Más lento; cabe en 6 GB.",
                "Personalizado": "Combinación propia de modelo, lote y precisión.",
            }[sel]
        )

    def _ajuste_manual(self, *_):
        if not self._aplicando:
            self._detectar_perfil()

    def _actualizar_vram_est(self, *_):
        gb = (
            VRAM_FP16[self.modelo.currentText()] * COMPUTE_FACTOR[self.compute.currentText()]
            + 0.08 * self.batch.value()
        )
        usa = gb / self.vram_total
        self.vram_est.setText(
            f"Memoria de video estimada: {gb:.1f} de {self.vram_total:.0f} GB".replace(".", ",")
        )
        self.vram_est_bar.setValue(int(min(1, usa) * 1000))
        color = ROJO if usa > 0.92 else COBALTO
        self.vram_est_bar.setStyleSheet(
            f"QProgressBar#vram {{ background:#E3E6F0; }} QProgressBar#vram::chunk {{ background:{color}; }}"
        )
        if usa > 0.92:
            self.vram_est.setText(self.vram_est.text() + " (puede no caber: baja el lote o la precisión)")

    def _refrescar_vacio(self):
        n = len(self.tarjetas)
        self.vacio.setVisible(n == 0)
        self.lista.setVisible(n > 0)
        self.contador.setText(f"{n} archivo{'s' if n != 1 else ''}" if n else "")

    def _agregar(self, rutas):
        existentes = {t.ruta for t in self.tarjetas}
        for r in rutas:
            r = str(r)
            if r in existentes:
                continue
            t = Tarjeta(r)
            t.quitar.connect(self._quitar)
            it = QListWidgetItem()
            it.setSizeHint(t.sizeHint())
            self.lista.addItem(it)
            self.lista.setItemWidget(it, t)
            t._item = it
            self.tarjetas.append(t)
            self.pool.start(CargaMiniatura(t, self.senales))
        self._refrescar_vacio()

    def _quitar(self, t):
        if self.worker:
            return
        self.lista.takeItem(self.lista.row(t._item))
        self.tarjetas.remove(t)
        self._refrescar_vacio()

    def vaciar(self):
        if self.worker:
            return
        self.lista.clear()
        self.tarjetas.clear()
        self._refrescar_vacio()

    def add_files(self):
        fs, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar videos", str(Path.home()), "Todos los archivos (*)"
        )
        self._agregar(fs)

    def add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta con videos", str(Path.home()))
        if d:
            self._buscar([d])

    def _buscar(self, rutas):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._agregar(core.collect_inputs(rutas, True))
        finally:
            QApplication.restoreOverrideCursor()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        if not self.worker:
            self._buscar([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])

    def pick_out(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta de salida", self.salida or str(Path.home()))
        if d:
            self.salida = d
            self._pintar_salida()

    def _pintar_salida(self):
        if self.salida:
            self.out_btn.setIcon(icono("folder"))
            self.out_btn.setText(" " + Path(self.salida).name)
            self.out_btn.setToolTip(self.salida)
        else:
            self.out_btn.setText(" Elegir carpeta")

    def formatos(self):
        return [k for k, w in self.chk_fmt.items() if w.isChecked()]

    def elegir_tipo(self, clave):
        self.diseno = aplicar_tipo(self.diseno, clave)
        self._pintar_tipo()
        self._save()

    def _pintar_tipo(self):
        tipo = self.diseno.tipo
        self.btn_tipo[tipo].setChecked(True)
        self.tipo_desc.setText(
            {
                "minuta": "Acta de reunión con participantes, acuerdos y pendientes. Sale en Word y Markdown.",
                "clase": "Apuntes de clase con resumen, conceptos clave y preguntas de repaso.",
                "transcripcion": "Texto limpio en Markdown para pasárselo a una IA, con datos en la cabecera.",
            }[tipo]
        )

    def editar_diseno(self):
        d = DisenoDialog(self.diseno, self)
        if d.exec():
            self.diseno = d.resultado()
            self._save()

    def abrir_salida(self):
        if self.salida:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.salida))

    def start(self):
        if not self.tarjetas:
            return QMessageBox.information(
                self, "Faltan videos", "Arrastra videos o agrega una carpeta para empezar."
            )
        if not self.salida:
            self.pick_out()
            if not self.salida:
                return
        if not self.formatos():
            return QMessageBox.information(self, "Falta el formato", "Marca al menos un formato de salida.")
        self._save()
        opts = dict(
            modelo=self.modelo.currentText(),
            idioma=self.idioma.currentData(),
            compute=self.compute.currentText(),
            bloque=self.bloque.value(),
            batch_size=self.batch.value(),
            beam_size=self.beam.value(),
            gpu_cap=self.cap.value(),
            device=self.device.currentText(),
            gpu_index=self.gpu_idx.value(),
            resumen=self.chk_res.isChecked(),
            formatos=tuple(self.formatos()),
            doc=self.diseno,
        )
        for t in self.tarjetas:
            t.set_estado("pendiente", "En espera")
            t.set_progreso(0)
        self.activa = None
        self.worker = Worker([t.ruta for t in self.tarjetas], self.salida, opts)
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._progress)
        self.worker.file.connect(self._archivo)
        self.worker.stage.connect(self._etapa)
        self.worker.text.connect(self._texto)
        self.worker.log.connect(lambda s: None)
        self.worker.done.connect(self._done)
        self.btn_go.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.hoja.clear()
        self.barra.set_valor(0)
        self.velocidad.setText("")
        self.eta.setText("")
        self.thread.start()

    def stop(self):
        if self.worker:
            self.worker.cancel.set()
            self.etapa_lbl.setText("Cancelando")

    def _archivo(self, i, n, nombre):
        if self.activa is not None:
            self.activa.set_estado("listo", "Listo")
            self.activa.set_progreso(0)
        self.activa = self.tarjetas[i - 1]
        self.activa.set_estado("activo", "Procesando")
        self.lista.scrollToItem(self.activa._item)
        self.hoja.append(f"<p style='color:{GRIS}'><b>{nombre}</b> ({i} de {n})</p>")
        self.barra.set_valor(0)

    def _etapa(self, e):
        self.etapa_lbl.setText(TEXTO_ETAPA[e])
        idx = next(i for i, (_, es) in enumerate(ETAPAS) if e in es)
        for i, w in enumerate(self.etapas):
            w.set_estado(2 if i < idx else 1 if i == idx else 0)
        if e == "transcribe":
            self.t0 = time.monotonic()
            self.barra.set_valor(0)
        else:
            self.barra.set_indet()
        if self.activa is not None and e in ("audio", "transcribe", "documento"):
            self.activa.estado.setText(
                {
                    "audio": "Extrayendo audio",
                    "transcribe": "Transcribiendo",
                    "documento": "Escribiendo documento",
                }[e]
            )

    def _progress(self, cur, total):
        if not total:
            return
        f = cur / total
        self.barra.set_valor(f)
        if self.activa is not None:
            self.activa.set_progreso(f)
        dt = time.monotonic() - self.t0
        if dt > 3 and cur > 0:
            vel = cur / dt
            self.velocidad.setText(f"{vel:.1f}× tiempo real".replace(".", ","))
            self.eta.setText(f"Faltan unos {fmt((total - cur) / vel)}")
        self.etapa_lbl.setText(f"Transcribiendo: {fmt(cur)} de {fmt(total)}")

    def _texto(self, ini, txt):
        self.hoja.append(f"<span style='color:{GRIS}; font-size:11px'>{fmt(ini)}</span>&nbsp; {txt}")

    def _done(self, creados, err):
        self.thread.quit()
        self.thread.wait()
        self.worker = None
        self.btn_go.setEnabled(True)
        self.btn_stop.setEnabled(False)
        for w in self.etapas:
            w.set_estado(2 if not err else 0)
        if err:
            if self.activa is not None:
                self.activa.set_estado("error", err)
            self.etapa_lbl.setText(err)
            self.barra.set_valor(0)
            self.hoja.append(f"<p style='color:{ROJO}'><b>{err}</b></p>")
            if "cancelado" not in err.lower():
                QMessageBox.warning(self, "No se pudo terminar", err)
        else:
            if self.activa is not None:
                self.activa.set_estado("listo", "Listo")
                self.activa.set_progreso(0)
            self.barra.set_valor(1)
            self.etapa_lbl.setText(f"Listo: {len(creados)} archivo(s) generados")
            enlaces = "<br>".join(
                f"<a href='{QUrl.fromLocalFile(c).toString()}'>{Path(c).name}</a>" for c in creados
            )
            self.hoja.append(f"<p><b>Documentos generados</b><br>{enlaces}</p>")
        self.velocidad.setText("")
        self.eta.setText("")
        self.activa = None

    def _poll_gpu(self):
        if self._gpu_proc.state() == QProcess.NotRunning:
            self._gpu_proc.start(
                "nvidia-smi",
                [
                    "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
            )

    def _gpu_leido(self):
        try:
            filas = bytes(self._gpu_proc.readAllStandardOutput()).decode().splitlines()
            n, u, mu, mt, t = [x.strip() for x in filas[self.gpu_idx.value()].split(",")]
            self.medidor.set_valor(float(u))
            self.gpu_nombre.setText(n.replace("NVIDIA GeForce ", ""))
            self.vram_lbl.setText(
                f"Memoria de video: {float(mu) / 1024:.1f} de {float(mt) / 1024:.1f} GB".replace(".", ",")
            )
            self.vram_bar.setValue(int(1000 * float(mu) / float(mt)))
            self.temp_lbl.setText(f"{t} °C")
            nuevo = float(mt) / 1024
            if abs(nuevo - self.vram_total) > 0.1:
                self.vram_total = nuevo
                self._actualizar_vram_est()
        except Exception:
            self.gpu_nombre.setText("GPU NVIDIA no detectada")

    def closeEvent(self, e):
        self._save()
        if self.worker:
            self.worker.cancel.set()
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait(3000)
        super().closeEvent(e)


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(ICONOS / "escriba.svg")))
    app.setStyleSheet(QSS)
    w = Ventana()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
