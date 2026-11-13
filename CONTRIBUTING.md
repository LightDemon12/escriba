# Cómo colaborar

Gracias por interesarte en Escriba, que convierte videos en minutas, apuntes de clase y transcripciones para IA.

1. Abre un *issue* describiendo el problema o la idea antes de un cambio grande.
2. Crea una rama desde `main` y haz cambios pequeños y enfocados.
3. Instala las herramientas de desarrollo: `pip install -e ".[dev]"`.
4. Antes de abrir el *pull request* ejecuta `ruff check .` y `pytest`; ambos deben pasar.
5. Si cambias el contenido o el diseño del documento, agrega o actualiza pruebas en `tests/test_documento.py`.

## Estructura

- `escriba/core.py`: audio, transcripción en GPU y orquestación.
- `escriba/documento.py`: tipos de documento, configuración de diseño y renderizado (Markdown, Word, texto, SRT, JSON, vista previa).
- `escriba/gui.py`: interfaz gráfica (PySide6).
- `escriba/cli.py`: línea de comandos.

## Reportar errores

Incluye tu GPU, la versión del controlador (`nvidia-smi`), la versión de Python y el mensaje de error completo.
