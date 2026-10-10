"""Locate external command-line tools (Poppler: pdftoppm/pdftotext, and Tesseract) on any OS, and report clearly when missing.
These are not pip packages. On Windows the installers often do NOT add them to PATH, so common install locations are searched too."""
from __future__ import annotations

import glob
import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

ENV_OVERRIDE = {"tesseract": "TESSERACT_CMD"}          # full path to the executable
POPPLER_ENV = "POPPLER_BIN"                            # folder containing pdftoppm / pdftotext

HINT = {
    "tesseract": ("Tesseract OCR is not installed or not on PATH. Windows: install the UB Mannheim build (try `winget search tesseract`), then either "
                  "reopen the terminal or set TESSERACT_CMD to the full path of tesseract.exe. macOS: `brew install tesseract`. "
                  "Ubuntu: `sudo apt-get install tesseract-ocr`."),
    "poppler": ("Poppler (pdftoppm / pdftotext) is not installed or not on PATH. Windows: `scoop install poppler`, or "
                "`conda install -c conda-forge poppler`, or unzip a Poppler release and set POPPLER_BIN to its bin folder (or add it to PATH). "
                "macOS: `brew install poppler`. Ubuntu: `sudo apt-get install poppler-utils`."),
}


class ToolMissing(RuntimeError):
    pass


def _candidates(name: str) -> list[str]:
    exe = name + (".exe" if os.name == "nt" else "")
    home, local = Path.home(), os.environ.get("LOCALAPPDATA", "")
    out: list[str] = []
    if name == "tesseract":
        out += [r"C:\Program Files\Tesseract-OCR", r"C:\Program Files (x86)\Tesseract-OCR", str(Path(local) / "Programs" / "Tesseract-OCR")]
    else:
        out += [os.environ.get(POPPLER_ENV, ""), str(Path(sys.prefix) / "Library" / "bin"), str(home / "scoop" / "apps" / "poppler" / "current" / "Library" / "bin"),
                str(home / "scoop" / "apps" / "poppler" / "current" / "bin")]
        for pat in (r"C:\Program Files\poppler*\Library\bin", r"C:\Program Files\poppler*\bin", r"C:\poppler*\Library\bin", r"C:\poppler*\bin",
                    str(home / "poppler*" / "Library" / "bin"), str(home / "Downloads" / "poppler*" / "Library" / "bin")):
            out += glob.glob(pat)
    return [str(Path(d) / exe) for d in out if d]


def find_tool(name: str) -> str:
    env = os.environ.get(ENV_OVERRIDE.get(name, ""), "")
    if env and Path(env).exists():
        return env
    found = shutil.which(name)
    if found:
        return found
    for c in _candidates(name):
        if Path(c).exists():
            return c
    raise ToolMissing(HINT["tesseract" if name == "tesseract" else "poppler"])


def run_text(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    """subprocess with explicit UTF-8 (never the Windows locale code page)."""
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def _version(path: str, arg: str) -> str:
    r = run_text([path, arg])
    return ((r.stdout or r.stderr).strip().splitlines() or ["?"])[0]


def doctor() -> int:
    """Print an environment report. Exit code 1 if anything required is missing."""
    bad = 0
    print(f"Python {sys.version.split()[0]} at {sys.executable}")
    if sys.prefix == getattr(sys, "base_prefix", sys.prefix):
        print("  note: no virtual environment is active. That is fine only if you installed requirements into THIS interpreter.")
    print("\nPython packages (pip install -r requirements.txt):")
    for mod, pip in [("yaml", "pyyaml"), ("pandas", "pandas"), ("numpy", "numpy"), ("pydantic", "pydantic"), ("PIL", "pillow"),
                     ("reportlab", "reportlab"), ("plotly", "plotly")]:
        try:
            m = importlib.import_module(mod)
            print(f"  ok       {pip:<10} {getattr(m, '__version__', '')}")
        except ImportError:
            print(f"  MISSING  {pip:<10}  -> run:  {sys.executable} -m pip install -r requirements.txt")
            bad = 1
    print("\nExternal tools (not pip packages):")
    for name, arg in [("pdftoppm", "-v"), ("pdftotext", "-v"), ("tesseract", "--version")]:
        try:
            p = find_tool(name)
            print(f"  ok       {name:<10} {p}  [{_version(p, arg)}]")
        except ToolMissing as e:
            print(f"  MISSING  {name:<10} {e}")
            bad = 1
    print("\nOptional: node (only for the dashboard JS parity test):", shutil.which("node") or "not found (that test will be skipped)")
    print("\nResult:", "READY" if not bad else "NOT READY: fix the MISSING items above, then run `make doctor` again")
    return bad
