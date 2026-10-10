"""InvoiceGuard MY - Streamlit app.  Run: streamlit run app/streamlit_app.py"""
from __future__ import annotations

import datetime as dt
import random
import sys
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from invoiceguard import eda, evaluate, roi  # noqa: E402
from invoiceguard.route import route  # noqa: E402
from invoiceguard.synth import load_corpus, load_params, make_suppliers  # noqa: E402
from invoiceguard.validate import RULES, Context, validate  # noqa: E402

st.set_page_config(page_title="InvoiceGuard MY", page_icon="🧾", layout="wide")
P = load_params()
SIM = {"B_llm_only", "C_invoiceguard"}


@st.cache_data
def data():
    df = eda.load()
    res = pd.read_csv(ROOT / "reports" / "results.csv").fillna("")
    summ = pd.read_csv(ROOT / "reports" / "summary_test.csv")
    catch = pd.read_csv(ROOT / "reports" / "catch_by_error_test.csv")
    return df, res, summ, catch


@st.cache_resource
def passes():
    """Recompute extractions + findings per invoice for the review UI (OCR text is cached on disk)."""
    corpus = load_corpus()
    ex = evaluate.build_extractions(P)
    reg = {s["tin"] for s in make_suppliers(random.Random(P["seed"]), P)}
    out = {}
    for name, (ek, rules, use_conf, routed) in evaluate.POLICIES.items():
        if ek not in ex or not routed:
            continue
        ctx = Context(today=dt.date.fromisoformat(P["today"]), tin_registry=reg)
        d = {}
        for g in corpus:
            e = ex[ek][g["invoice_id"]]
            f = validate(e, ctx, only={"V00"} if rules == "V00-only" else None)
            d[g["invoice_id"]] = (e, f, *route(e, f, P["router"]["conf_threshold"], use_conf))
        out[name] = d
    return {g["invoice_id"]: g for g in corpus}, out


df, res, summ, catch = data()
st.title("🧾 InvoiceGuard MY")
st.caption("AI-assisted invoice intake & MyInvois validation for Malaysian SMEs · **synthetic data** · "
           "A / A+ are *measured* (Tesseract + regex); B / C use a *simulated* LLM stand-in · not tax or legal advice")
tabs = st.tabs(["Overview & EDA", "Evaluation", "Review UI", "ROI simulator", "Live extraction (API key)"])

# ------------------------------------------------------------------ Overview
with tabs[0]:
    k = eda.kpis(df)
    c = st.columns(6)
    for col, (lab, v) in zip(c, [("Invoices", k["n"]), ("Suppliers", k["suppliers"]), ("Median RM", f"{k['median_myr']:,.0f}"),
                                 ("High-value ≥RM10k", f"{k['pct_high_value']:.0%}"), ("Last-5-days arrivals", f"{k['pct_month_end']:.0%}"),
                                 ("Scan/photo", f"{k['pct_scanned_photo']:.0%}")]):
        col.metric(lab, v)
    figs = eda.figures(df)
    a, b = st.columns(2)
    for i, name in enumerate(["monthly_volume", "day_of_month", "value_hist", "error_prevalence", "quality_mix", "supplier_pareto"]):
        (a if i % 2 == 0 else b).plotly_chart(figs[name], width="stretch")
    st.plotly_chart(figs["value_by_industry"], width="stretch")
    with st.expander("Data profile & raw table"):
        st.dataframe(df.drop(columns=["month_end"]).describe(include="all").T.astype(str))
        st.dataframe(df, width="stretch")

# ------------------------------------------------------------------ Evaluation
with tabs[1]:
    st.subheader("Held-out test split")
    t = summ.copy()
    t.insert(1, "basis", ["simulated" if s in SIM else "measured" for s in t.system])
    show = t[["system", "basis", "n", "field_acc", "critical_exact", "stp_rate", "stp_error_free_docs", "wrong_auto_n",
              "wrong_auto_of_auto", "error_routed_to_review"]]
    st.dataframe(show.style.format({c: "{:.1%}" for c in show.columns if show[c].dtype == float}), width="stretch")
    st.info("Wrong auto-approve = approved without human review although the document has an injected error, is ≥RM10k "
            "(policy), or a critical field was read wrongly. Target ≈ 0.")
    c1, c2 = st.columns(2)
    m = t.melt(id_vars="system", value_vars=["critical_exact", "stp_rate", "error_routed_to_review"])
    c1.plotly_chart(px.bar(m, x="system", y="value", color="variable", barmode="group", template="plotly_white",
                           title="Headline rates"), width="stretch")
    c2.plotly_chart(px.bar(t, x="system", y="wrong_auto_n", template="plotly_white", title="Wrong auto-approvals"), width="stretch")
    q = res[(res.split == "test")].groupby(["system", "quality"]).crit_ok.mean().reset_index()
    st.plotly_chart(px.bar(q, x="quality", y="crit_ok", color="system", barmode="group", template="plotly_white",
                           title="Critical-field exact match by document quality"), width="stretch")
    metric = st.radio("Injected-error metric", ["routed", "rule_fired"], horizontal=True)
    st.plotly_chart(px.bar(catch, x="injected", y=metric, color="system", barmode="group", template="plotly_white",
                           title="Handling of injected errors"), width="stretch")

# ------------------------------------------------------------------ Review UI
with tabs[2]:
    gts, ps = passes()
    sysname = st.selectbox("System", list(ps), index=list(ps).index("C_invoiceguard") if "C_invoiceguard" in ps else 0)
    only_review = st.checkbox("Only invoices routed to human review", True)
    ids = [i for i, v in ps[sysname].items() if gts[i]["split"] == "test" and (v[2] == "review" or not only_review)]
    inv_id = st.selectbox("Invoice", ids)
    g, (e, finds, decision, reasons, minconf) = gts[inv_id], ps[sysname][inv_id]
    left, right = st.columns([1, 1])
    img = next((p for p in (ROOT / "data" / "synthetic" / "images" / f"{inv_id}_p1.png", ROOT / "data" / "thumbs" / f"{inv_id}_p1.jpg") if p.exists()), None)
    if img:
        left.image(str(img), caption=f"{inv_id} · {g['quality']} · layout {g['layout']} · {g['language']}")
    else:
        left.warning("Run `make data` to render invoice images")
    right.markdown(f"**Decision:** `{decision}` · min confidence {minconf:.2f} · reasons: {', '.join(reasons) or '-'}")
    for f in finds:
        icon = {"error": "🟥", "warning": "🟧", "info": "ℹ️"}[f.severity]
        right.markdown(f"{icon} **{f.rule}** {RULES[f.rule]['name']}: {f.message}")
    rows = []
    for fld in ["supplier_name", "supplier_tin", "invoice_number", "issue_date", "currency", "subtotal", "tax_total", "total"]:
        truth, got = g[fld], getattr(e, fld)
        ok = evaluate._n(D(truth) if fld in ("subtotal", "tax_total", "total") else (dt.date.fromisoformat(truth) if fld == "issue_date" else (truth or None))) == evaluate._n(got)
        rows.append(dict(field=fld, printed_on_document=truth, extracted=str(got), match="✅" if ok else "❌",
                         confidence=round(e.field_confidence.get(fld, float("nan")), 2)))
    right.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    right.caption(f"Ground truth injected errors: {g['injected_errors'] or 'none'} · high value: {g['high_value']}")
    right.button("✅ Approve (demo)")
    right.button("✏️ Send back to supplier (demo)")

# ------------------------------------------------------------------ ROI
with tabs[3]:
    base = dict(P["roi"])
    meas = summ[summ.system == "C_invoiceguard"].stp_error_free_docs.iloc[0]
    st.caption(f"Default STP = simulated rate on error-free documents ({meas:.0%}); planning assumption in config is {base['stp_rate']:.0%}.")
    c1, c2 = st.columns(2)
    with c1:
        p = dict(base)
        p["volume"] = st.slider("Invoices / month", 50, 5000, int(base["volume"]), 50)
        p["handling_min"] = st.slider("Manual minutes / invoice", 2.0, 20.0, float(base["handling_min"]), .5)
        p["hourly_cost"] = st.slider("Staff cost RM/hour", 10, 60, int(base["hourly_cost"]))
        p["stp_rate"] = st.slider("Straight-through rate", 0.0, 0.95, float(round(meas, 2)), .01)
        p["exception_min"] = st.slider("Exception minutes / invoice", 1.0, 12.0, float(base["exception_min"]), .5)
        p["implementation_cost"] = st.slider("Build cost RM", 5000, 80000, int(base["implementation_cost"]), 1000)
        p["fixed_monthly"] = st.slider("Run cost RM/month", 100, 1500, int(base["fixed_monthly"]), 10)
    s = roi.scenario(p)
    with c2:
        a, b, c = st.columns(3)
        a.metric("Net RM / invoice", f"{s['net_rm']:.2f}")
        b.metric("Net benefit / month", f"RM {s['monthly_net']:,.0f}")
        c.metric("Payback (months)", "never" if s["payback_months"] is None else f"{s['payback_months']:.1f}")
        st.metric("Break-even volume", "-" if s["breakeven_volume"] is None else f"{s['breakeven_volume']:,.0f} invoices/month")
        vols = list(range(0, 3001, 100))
        st.plotly_chart(px.line(x=vols, y=[roi.scenario(p, v)["monthly_net"] for v in vols], template="plotly_white",
                                labels={"x": "Invoices/month", "y": "Net benefit/month (RM)"}, title="Break-even curve"), width="stretch")
        sens = pd.DataFrame(roi.sensitivity(p))
        sens["swing"] = sens.high - sens.low
        st.plotly_chart(px.bar(sens, y="driver", x="swing", orientation="h", template="plotly_white",
                               title="Sensitivity: swing in monthly net benefit for ±25% change"), width="stretch")

# ------------------------------------------------------------------ Live extraction
with tabs[4]:
    st.write("Upload an invoice image (PNG/JPG) to run the **real** vision extractor → validation → router. "
             "Requires `ANTHROPIC_API_KEY` in `.env`. Use synthetic invoices only.")
    up = st.file_uploader("Invoice image", type=["png", "jpg", "jpeg"])
    if up and st.button("Extract & validate"):
        import os
        import tempfile

        if not os.getenv("ANTHROPIC_API_KEY"):
            st.error("Set ANTHROPIC_API_KEY first (see .env.example).")
        else:
            from invoiceguard.extract import ClaudeVisionExtractor
            with tempfile.NamedTemporaryFile(suffix=Path(up.name).suffix, delete=False) as tf:
                tf.write(up.getvalue())
            ex = ClaudeVisionExtractor().extract_images([Path(tf.name)])
            ctx = Context(today=dt.date.fromisoformat(P["today"]))
            fl = validate(ex, ctx)
            dec, why, mc = route(ex, fl, P["router"]["conf_threshold"])
            st.image(up)
            st.json(ex.model_dump(mode="json"))
            st.write(f"**Decision: {dec}** · reasons: {why} · min confidence {mc:.2f}")
            for f in fl:
                st.write(f"- {f.severity.upper()} {f.rule}: {f.message}")
