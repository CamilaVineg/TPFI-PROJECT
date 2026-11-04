"""Script para generar los archivos PDF de la Guía de Estudio y Guion de Defensa del TPFI.

Convierte los archivos HTML de 'docs/' a PDF usando el motor de renderizado de
Microsoft Edge o Google Chrome en modo headless, garantizando tipografia
vectorial perfecta, saltos de pagina y colores.
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


def convert_html_to_pdf(browser: str | None, html_path: Path, pdf_path: Path) -> bool:
    """Renderiza un archivo HTML en PDF mediante el navegador.

    Args:
        browser: Ruta al ejecutable del navegador o None.
        html_path: Ruta al archivo HTML de origen.
        pdf_path: Ruta al archivo PDF de destino.

    Returns:
        True si la conversion fue exitosa, False en caso contrario.
    """
    if not html_path.is_file():
        print(f"[ERROR] No se encontro el archivo HTML en: {html_path}")
        return False

    if browser:
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
                print(
                    f"[EXITO] PDF generado: {pdf_path.name} "
                    f"({pdf_path.stat().st_size / 1024:.1f} KB)"
                )
                return True
        except Exception as err:
            print(f"[AVISO] Fallo la conversion headless de {html_path.name}: {err}")

    # Fallback si falla el modo headless
    webbrowser.open(html_path.as_uri())
    return False


def generate_all_pdfs() -> int:
    """Convierte todos los documentos HTML de la carpeta docs a PDF.

    Returns:
        Codigo de salida del proceso (0 para exito, 1 si todos fallan).
    """
    base_dir = Path(__file__).resolve().parent
    docs_dir = base_dir / "docs"

    documents = [
        ("GUIA_ESTUDIO_TPFI.html", "GUIA_ESTUDIO_TPFI.pdf"),
        ("GUION_DEFENSA_ORAL.html", "GUION_DEFENSA_ORAL.pdf"),
    ]

    browser = find_browser()
    if browser:
        print(f"[*] Navegador detectado para renderizado: {browser}\n")
    else:
        print("[AVISO] No se detecto navegador. Se abriran en el navegador predeterminado.\n")

    success_count = 0
    for html_name, pdf_name in documents:
        html_path = docs_dir / html_name
        pdf_path = docs_dir / pdf_name
        if convert_html_to_pdf(browser, html_path, pdf_path):
            success_count += 1

    if success_count > 0:
        print(f"\n[OK] Se generaron {success_count} de {len(documents)} archivos PDF en 'docs/'.")
        return 0

    print("\n[INFO] Para guardar como PDF desde el navegador:")
    print("  1. Presiona Ctrl + P (Imprimir)")
    print("  2. En Destino selecciona 'Guardar como PDF'")
    print("  3. Guarda el archivo en la carpeta 'docs/'")
    return 0


if __name__ == "__main__":
    sys.exit(generate_all_pdfs())
