"""CLI: python -m invoiceguard.cli <generate|baseline|evaluate|eda|dashboard|all> [--extractor claude --limit N]"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Heavy imports are deliberately lazy so `doctor` works (and failures are readable) even when packages are missing.
ROOT = Path(__file__).resolve().parents[2]


def cmd_generate(_a=None):
    from .synth import build_corpus, load_params, render_all, save_corpus
    P = load_params()
    corpus = build_corpus(P)
    out = ROOT / "data" / "synthetic"
    save_corpus(corpus, out)
    t = time.time()
    render_all(corpus, out, P)
    print(f"generated {len(corpus)} invoices + PDFs/images in {time.time()-t:.0f}s -> {out}")


def cmd_baseline(_a=None):
    from .extract import get_text
    from .synth import load_corpus
    corpus = load_corpus()
    t = time.time()
    for i, inv in enumerate(corpus, 1):
        get_text(inv)
        if i % 25 == 0:
            print(f"  OCR/text {i}/{len(corpus)} ({time.time()-t:.0f}s)", flush=True)
    print("baseline text cache ready")


def cmd_claude(limit: int):
    from .extract import ClaudeVisionExtractor
    from .synth import load_corpus
    ex = ClaudeVisionExtractor()
    corpus = [i for i in load_corpus() if i["split"] == "test"][:limit]
    res = {}
    for inv in corpus:
        res[inv["invoice_id"]] = json.loads(ex.extract(inv).model_dump_json())
    (ROOT / "data" / "extractions_claude.json").write_text(json.dumps(res), encoding="utf-8")
    print(f"Claude extracted {len(res)} invoices; tokens: {ex.usage}")


def cmd_evaluate(a=None):
    from . import evaluate
    from .synth import load_params
    P = load_params()
    if a is not None and getattr(a, "extractor", None) == "claude":
        cmd_claude(a.limit)
    ex = evaluate.build_extractions(P)
    df = evaluate.run_all(ex, P)
    evaluate.save_reports(df)
    s = evaluate.summarize(df[df.split == "test"])
    import pandas as pd
    pd.set_option("display.width", 200)
    print(s[["system", "n", "field_acc", "critical_exact", "stp_rate", "wrong_auto_n", "wrong_auto_of_auto",
             "error_routed_to_review", "unneeded_review"]].round(3).to_string(index=False))


def cmd_eda(_a=None):
    from . import eda
    df = eda.load()
    figs = eda.figures(df)
    (ROOT / "reports" / "figures").mkdir(parents=True, exist_ok=True)
    for k, f in figs.items():
        f.write_html(ROOT / "reports" / "figures" / f"{k}.html", include_plotlyjs="cdn")
    (ROOT / "reports" / "eda_kpis.json").write_text(json.dumps(eda.kpis(df), indent=1), encoding="utf-8")
    print(json.dumps(eda.kpis(df), indent=1))


def cmd_dashboard(_a=None):
    sys.path.insert(0, str(ROOT / "dashboard"))
    import build_static
    build_static.main()


def cmd_doctor(_a=None):
    from . import tools
    if tools.doctor():
        raise SystemExit(1)


def cmd_pages(_a=None):
    """Build the dashboard and copy it to docs/index.html (GitHub Pages: Settings > Pages > main /docs). Cross-platform (no `cp`)."""
    import shutil
    cmd_dashboard()
    (ROOT / "docs").mkdir(exist_ok=True)
    shutil.copyfile(ROOT / "dashboard" / "dist" / "index.html", ROOT / "docs" / "index.html")
    print("copied to docs/index.html")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["doctor", "generate", "baseline", "evaluate", "eda", "dashboard", "pages", "all"])
    ap.add_argument("--extractor", choices=["sim", "claude"], default="sim")
    ap.add_argument("--limit", type=int, default=50)
    a = ap.parse_args()
    run = dict(doctor=cmd_doctor, generate=cmd_generate, baseline=cmd_baseline, evaluate=cmd_evaluate, eda=cmd_eda, dashboard=cmd_dashboard, pages=cmd_pages)
    from .tools import ToolMissing
    try:
        if a.cmd == "all":
            for c in ("doctor", "generate", "baseline", "evaluate", "eda", "dashboard"):
                print(f"\n== {c} ==")
                run[c](a)
        else:
            run[a.cmd](a)
    except ToolMissing as e:
        raise SystemExit(f"\nerror: {e}\nRun `python -m invoiceguard.cli doctor` for a full environment report.") from None
    except ModuleNotFoundError as e:
        raise SystemExit(f"\nerror: Python package '{e.name}' is not installed in THIS interpreter:\n  {sys.executable}\n"
                         f"Fix: activate your virtual environment, then run\n  {sys.executable} -m pip install -r requirements.txt\n"
                         f"Then check everything with:  python -m invoiceguard.cli doctor") from None
    except FileNotFoundError as e:
        raise SystemExit(f"\nerror: {e}\nRun the earlier pipeline stages first (`make all` runs them in order).") from None


if __name__ == "__main__":
    main()
