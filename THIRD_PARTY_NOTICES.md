# Avisos de terceros

Escriba es software MIT (ver [LICENSE](LICENSE)). Este repositorio solo incluye código propio y los iconos
indicados abajo. Las dependencias, los modelos y los programas externos se instalan o descargan en el equipo
de cada usuario y se rigen por sus propias licencias. Esta tabla es informativa; la licencia que vale es la
de cada proyecto.

## Incluido en este repositorio

| Elemento | Licencia | Detalle |
|---|---|---|
| Iconos de `escriba/iconos/` (excepto `escriba.svg`) | ISC y MIT | [Lucide](https://lucide.dev), basado en Feather. Textos completos en [`escriba/iconos/LICENSE-lucide.txt`](escriba/iconos/LICENSE-lucide.txt) |
| `escriba/iconos/escriba.svg` | MIT | Icono propio de Escriba |
| Capturas de `docs/` | MIT | Capturas de la propia interfaz con videos de prueba generados con ffmpeg |

El programa no incluye tipografías. La interfaz usa las que haya en el sistema, y los documentos Word solo
nombran la fuente elegida sin incrustarla.

## Dependencias directas de Python

| Paquete | Licencia | Notas |
|---|---|---|
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | MIT | Motor de transcripción; incluye el modelo de detección de voz Silero VAD (MIT) |
| [CTranslate2](https://github.com/OpenNMT/CTranslate2) | MIT | Inferencia en GPU y CPU |
| [PyAV](https://github.com/PyAV-Org/PyAV) | BSD-3-Clause | Sus ruedas incluyen librerías de FFmpeg (LGPL) |
| [python-docx](https://github.com/python-openxml/python-docx) | MIT | Genera los archivos .docx |
| [PySide6](https://doc.qt.io/qtforpython-6/) y shiboken6 | LGPL-3.0, GPL-2.0 o GPL-3.0 (doble licencia) | Interfaz gráfica; se usa bajo LGPL-3.0 |
| [anthropic](https://github.com/anthropics/anthropic-sdk-python) | Apache-2.0 | Solo con el extra `resumen` |
| nvidia-cublas-cu12, nvidia-cudnn-cu12 | Licencia propietaria de NVIDIA | Bibliotecas CUDA que se instalan desde PyPI; no se redistribuyen aquí |

## Dependencias transitivas

Revisadas con `pip-licenses` sobre el entorno completo. Ninguna usa GPL ni AGPL sin alternativa más permisiva.

- **MIT, BSD, Apache-2.0, PSF, ISC:** numpy, lxml, PyYAML, onnxruntime, protobuf, flatbuffers, huggingface_hub, tokenizers,
  hf-xet, fsspec, filelock, packaging, click, httpx, anyio, h11, idna, pydantic, jiter, typing-extensions y demás.
- **tqdm:** MPL-2.0 y MIT. La MPL-2.0 aplica a nivel de archivo y Escriba no modifica tqdm.
- **nvidia-cuda-nvrtc-cu12:** licencia propietaria de NVIDIA, instalada como dependencia de las bibliotecas CUDA.

## Programas externos

- **FFmpeg** (LGPL o GPL según la compilación): lo instala el sistema (`apt install ffmpeg`) y Escriba lo
  invoca como programa independiente.

## Modelos de transcripción

Se descargan de Hugging Face al usarlos y no forman parte de este repositorio. Los modelos por defecto son
conversiones a CTranslate2 de [Whisper](https://github.com/openai/whisper) y están publicados bajo licencia
MIT (`Systran/faster-whisper-*`, `mobiuslabsgmbh/faster-whisper-large-v3-turbo`). Si usas otro modelo,
revisa su licencia.

## PySide6 y la LGPL

Escriba usa PySide6 sin modificarlo y como biblioteca instalada aparte, lo que es compatible con la LGPL-3.0.
Si distribuyes un ejecutable empaquetado (por ejemplo con PyInstaller), debes cumplir las obligaciones de la
LGPL: incluir el aviso y el texto de la licencia, y permitir reemplazar la biblioteca.

## Marcas

NVIDIA, CUDA y RTX son marcas de NVIDIA Corporation. Whisper es un proyecto de OpenAI. Claude es una marca
de Anthropic. Qt es una marca de The Qt Company. Escriba es un proyecto independiente que no está afiliado
ni respaldado por ninguna de estas empresas; los nombres se usan solo para describir compatibilidad.
