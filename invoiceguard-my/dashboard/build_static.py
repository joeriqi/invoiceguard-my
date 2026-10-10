"""Builds dashboard/dist/index.html: one self-contained page (Chart.js from cdnjs) with all data embedded.
Every number is computed from data/ and reports/ - nothing is typed in."""
from __future__ import annotations

import base64
import io
import json
import random
from datetime import datetime
from pathlib import Path

import pandas as pd

from invoiceguard import eda, evaluate
from invoiceguard.schema import HEADER_FIELDS
from invoiceguard.synth import ROOT, load_corpus, load_params, make_suppliers
from invoiceguard.validate import RULES, norm_no

HERE = Path(__file__).resolve().parent
LABEL = {"A_ocr_regex": "A  OCR + regex", "A+_ocr_regex_rules": "A+  OCR + regex + rules", "B_llm_only": "B  LLM only",
         "C_invoiceguard": "C  InvoiceGuard (LLM + rules + router)", "C_invoiceguard_claude": "C  InvoiceGuard (real Claude)"}
SIMULATED = {"B_llm_only", "C_invoiceguard"}


def r(x, n=3):
    return None if x is None or pd.isna(x) else round(float(x), n)


LINE_KEYS = ("quantity", "unit_price", "tax_type", "line_total")
HDR = ("supplier_name", "supplier_tin", "supplier_id_type", "supplier_id_value", "invoice_number", "issue_date", "currency",
       "exchange_rate", "subtotal", "tax_total", "total", "has_uin")


def _thumb(inv_id: str, w: int = 280) -> str | None:
    f = ROOT / "data" / "synthetic" / "images" / f"{inv_id}_p1.png"
    if not f.exists():
        return None
    from PIL import Image
    im = Image.open(f).convert("L")
    im = im.crop((0, 0, im.width, int(im.height * 0.55)))      # invoices are top-heavy: keep the printed part
    im = im.resize((w, int(im.height * w / im.width)))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=42)
    return base64.b64encode(b.getvalue()).decode()


def _compact(d: dict) -> dict:
    out = {k: d.get(k) for k in HDR}
    out["lines"] = None if d.get("lines") is None else [{k: l.get(k) for k in LINE_KEYS} for l in d["lines"]]
    if d.get("field_confidence"):
        out["field_confidence"] = {k: round(v, 4) for k, v in d["field_confidence"].items()}
    return out


def _key(d: dict):
    if not d.get("invoice_number"):
        return None
    return f"{d.get('supplier_tin') or (d.get('supplier_name') or '').casefold()}|{norm_no(d['invoice_number'])}"


def inspector(P: dict) -> dict:
    """Per test invoice: extracted JSON per system, printed ground truth, stored decisions (the pipeline's output)."""
    corpus, ex = load_corpus(), evaluate.build_extractions(P)
    res = pd.read_csv(ROOT / "reports" / "results.csv").fillna("")
    sysmap = {"A": ("baseline", "A+_ocr_regex_rules"), "C": ("sim", "C_invoiceguard")}
    dumps = {k: {i: json.loads(e.model_dump_json()) for i, e in ex[v[0]].items()} for k, v in sysmap.items()}
    keys = {k: [_key(dumps[k][g["invoice_id"]]) for g in corpus] for k in sysmap}
    inv = []
    for idx, g in enumerate(corpus):
        if g["split"] != "test":
            continue
        rec = dict(id=g["invoice_id"], idx=idx, sup=g["supplier_name"], q=g["quality"], inj=g["injected_errors"], hv=g["high_value"],
                   gt=_compact(dict(g)), th=_thumb(g["invoice_id"]))
        for k, (_, name) in sysmap.items():
            r = res[(res.system == name) & (res.invoice_id == g["invoice_id"])].iloc[0]
            rec[k] = dict(ex=_compact(dumps[k][g["invoice_id"]]), dec=r.decision, rs=[x for x in r.reasons.split(",") if x], wrong=bool(r.wrong_auto))
        inv.append(rec)
    tins = sorted({s["tin"] for s in make_suppliers(random.Random(P["seed"]), P)})
    return dict(inv=inv, keys=keys, tins=tins, today=P["today"], thr=P["router"]["conf_threshold"])


def build_data() -> dict:
    P = load_params()
    df = eda.load()
    res = pd.read_csv(ROOT / "reports" / "results.csv").fillna("")
    test = res[res.split == "test"]
    summ = pd.read_csv(ROOT / "reports" / "summary_test.csv")
    catch = pd.read_csv(ROOT / "reports" / "catch_by_error_test.csv")
    m, d, vh, ep, sp, ind = eda.monthly(df), eda.dom(df), eda.value_hist(df), eda.error_prevalence(df), eda.supplier_pareto(df), eda.by_industry(df)
    vh["lab"] = vh.apply(lambda x: f"{x.lo:,.0f}-{x.hi:,.0f}", axis=1)
    systems = []
    for _, s in summ.iterrows():
        systems.append(dict(id=s.system, label=LABEL.get(s.system, s.system), simulated=s.system in SIMULATED, n=int(s.n),
                            field_acc=r(s.field_acc), critical_exact=r(s.critical_exact), stp=r(s.stp_rate),
                            wrong_auto_n=int(s.wrong_auto_n), wrong_auto_rate=r(s.wrong_auto_of_auto),
                            err_routed=r(s.error_routed_to_review), unneeded=r(s.unneeded_review), stp_clean=r(s.stp_error_free_docs)))
    byq = {s: {q: r(g.crit_ok.mean()) for q, g in test[test.system == s].groupby("quality")} for s in test.system.unique()}
    errs = sorted(catch.injected.unique())
    cat = {s: [r(catch[(catch.system == s) & (catch.injected == e)].routed.mean()) for e in errs] for s in catch.system.unique()}
    rule = {s: [r(catch[(catch.system == s) & (catch.injected == e)].rule_fired.mean()) for e in errs] for s in catch.system.unique()}
    c = test[(test.system == "C_invoiceguard") & (test.decision == "review")].merge(
        df[["invoice_id", "supplier_name", "total_myr", "currency"]], on="invoice_id", how="left")
    c = c.sort_values("minconf").head(60)
    queue = [dict(id=x.invoice_id, supplier=x.supplier_name, total=r(x.total_myr, 0) if x.total_myr != "" else None, q=x.quality,
                  reasons=[k for k in x.reasons.split(",") if k], truth=x.injected.replace(",", ", ") or ("high value" if x.high_value else "clean"),
                  conf=r(x.minconf, 2)) for x in c.itertuples()]
    fa = {s: [r(summ[summ.system == s][f"acc_{f}"].iloc[0]) for f in HEADER_FIELDS] for s in summ.system}
    return dict(
        meta=dict(generated=datetime.now().strftime("%Y-%m-%d"), test_n=int(summ.n.max()), seed=P["seed"]),
        kpis=eda.kpis(df),
        monthly=dict(l=m.month.tolist(), n=m.invoices.tolist()),
        dom=d.invoices.tolist(),
        vhist=dict(l=vh.lab.tolist(), n=vh.n.tolist()),
        errs=dict(l=ep.error.tolist(), n=ep.n.tolist()),
        quality=df.quality.value_counts().to_dict(),
        pareto=dict(x=list(range(1, len(sp) + 1)), y=[round(v, 3) for v in sp.cum_share]),
        industry=dict(l=ind.industry.tolist(), n=ind.n.tolist()),
        systems=systems, fields=HEADER_FIELDS, field_acc=fa, acc_by_quality=byq,
        catch=dict(errors=errs, routed=cat, rule=rule), queue=queue,
        rules={k: v["name"] for k, v in RULES.items()},
        insp=inspector(P),
        roi=dict(P["roi"], measured_stp_clean=next((s["stp_clean"] for s in systems if s["id"] == "C_invoiceguard"), None)),
    )


def main():
    data = build_data()
    (ROOT / "reports" / "dashboard_data.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    tpl = (HERE / "template.html").read_text(encoding="utf-8")
    out = HERE / "dist"
    out.mkdir(exist_ok=True)
    html = tpl.replace("/*DATA*/null", json.dumps(data, separators=(",", ":")))
    (out / "index.html").write_text(html, encoding="utf-8")
    print(f"dashboard built: {out/'index.html'} ({len(html)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
