"""Windows-portability guards (the default text encoding there is a legacy code page, not UTF-8)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [*ROOT.glob("src/invoiceguard/*.py"), *ROOT.glob("dashboard/*.py"), *ROOT.glob("app/*.py"), *ROOT.glob("notebooks/*.py"), *[f for f in ROOT.glob("tests/*.py") if f.name != "test_portability.py"]]
IO = re.compile(r"\.(read_text|write_text)\(")


def test_every_text_read_and_write_names_its_encoding():
    bad = []
    for f in FILES:
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if IO.search(line) and "encoding=" not in line:        # all calls are single-line
                bad.append(f"{f.relative_to(ROOT)}:{n}")
    assert not bad, bad


def test_no_bare_subprocess_text_mode():
    """subprocess text mode without encoding= decodes with the Windows code page."""
    bad = [str(f.relative_to(ROOT)) for f in FILES if f.name != "tools.py" and re.search(r"subprocess\.run\(", f.read_text(encoding="utf-8"))]
    assert not bad, f"use tools.run_text instead: {bad}"


def test_external_tools_are_found_through_helper_not_bare_names():
    for f in (x for x in FILES if x.name != "tools.py"):
        txt = f.read_text(encoding="utf-8")
        assert not re.search(r'\[\s*"(pdftoppm|pdftotext|tesseract)"', txt), f.name


def test_missing_packages_give_a_readable_message_not_a_traceback():
    """Regression for 'ModuleNotFoundError: No module named yaml': simulate an interpreter with no third-party packages (-S)."""
    import os
    import sys

    from invoiceguard.tools import run_text
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    doc = run_text([sys.executable, "-S", "-m", "invoiceguard.cli", "doctor"], env=env, cwd=ROOT)
    assert doc.returncode == 1 and "MISSING" in doc.stdout and "pip install -r requirements.txt" in doc.stdout and "Traceback" not in doc.stderr
    gen = run_text([sys.executable, "-S", "-m", "invoiceguard.cli", "eda"], env=env, cwd=ROOT)
    assert gen.returncode != 0 and "pip install -r requirements.txt" in gen.stderr and "Traceback" not in gen.stderr
