"""Script para generar el archivo PDF de la Guía de Estudio y Defensa del TPFI.

Convierte 'docs/GUIA_ESTUDIO_TPFI.html' en 'docs/GUIA_ESTUDIO_TPFI.pdf' usando el
motor de renderizado de Microsoft Edge o Google Chrome en modo headless,
garantizando tipografia vectorial perfecta, saltos de pagina y colores.
"""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path


def find_browser() -> str | None:
    """Busca el ejecutable de Microsoft Edge o Google Chrome en Windows.

    Returns:
        Ruta absoluta al ejecutable del navegador o None si no se encuentra.
    """
    prog_x86 = os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")
    prog_64 = os.environ.get("PROGRAMFILES", "C:/Program Files")
    local_app = os.environ.get("LOCALAPPDATA", "")

    candidates = [
        # Microsoft Edge
        Path(prog_x86) / "Microsoft/Edge/Application/msedge.exe",
        Path(prog_64) / "Microsoft/Edge/Application/msedge.exe",
        Path(local_app) / "Microsoft/Edge/Application/msedge.exe",
        # Google Chrome
        Path(prog_64) / "Google/Chrome/Application/chrome.exe",
        Path(prog_x86) / "Google/Chrome/Application/chrome.exe",
        Path(local_app) / "Google/Chrome/Application/chrome.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def generate_pdf() -> int:
    """Convierte el archivo HTML de documentacion a formato PDF.

    Returns:
        Codigo de salida del proceso (0 para exito, 1 ante error).
    """
    base_dir = Path(__file__).resolve().parent
    html_path = base_dir / "docs" / "GUIA_ESTUDIO_TPFI.html"
    pdf_path = base_dir / "docs" / "GUIA_ESTUDIO_TPFI.pdf"

    if not html_path.is_file():
        print(f"[ERROR] No se encontro el archivo HTML en: {html_path}")
        return 1

    browser = find_browser()
    if browser:
        print(f"[*] Utilizando navegador para renderizar PDF: {browser}")
        cmd = [
            browser,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path}",
            str(html_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            if pdf_path.is_file() and pdf_path.stat().st_size > 0:
                print("\n[EXITO] PDF generado correctamente en:")
                print(f"  -> {pdf_path}")
                print(f"  Tamano: {pdf_path.stat().st_size / 1024:.1f} KB")
                return 0
        except Exception as err:
            print(f"[AVISO] Fallo la conversion headless: {err}")

    # Fallback: abrir en el navegador predeterminado para imprimir
    print("\n[INFO] Abriendo la guia en tu navegador web...")
    print("Para guardarla como PDF:")
    print("  1. Presiona Ctrl + P (Imprimir)")
    print("  2. En Destino selecciona 'Guardar como PDF'")
    print("  3. Guarda el archivo en docs/GUIA_ESTUDIO_TPFI.pdf")
    webbrowser.open(html_path.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(generate_pdf())
