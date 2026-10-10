"""EDA helpers shared by the notebook, Streamlit app and static dashboard."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .synth import ROOT


def load() -> pd.DataFrame:
    df = pd.read_csv(ROOT / "data" / "synthetic" / "invoices.csv", parse_dates=["issue_date"])
    df["injected_errors"] = df["injected_errors"].fillna("")
    df["month"] = df.issue_date.dt.strftime("%Y-%m")
    df["dom"] = df.issue_date.dt.day
    df["month_end"] = df.issue_date.dt.day >= df.issue_date.dt.days_in_month - 4
    df["foreign"] = df.currency != "MYR"
    return df


def kpis(df: pd.DataFrame) -> dict:
    return dict(
        n=len(df), suppliers=int(df.supplier_id.nunique()), value_myr=float(df.total_myr.sum()), median_myr=float(df.total_myr.median()),
        pct_high_value=float(df.high_value.mean()), n_value_unknown=int(df.total_myr.isna().sum()), pct_errors=float((df.injected_errors != "").mean()),
        pct_no_uin=float((~df.has_uin.astype(bool)).mean()), pct_foreign=float(df.foreign.mean()),
        pct_scanned_photo=float((df.quality != "digital").mean()), pct_month_end=float(df.month_end.mean()),
        mean_lines=float(df.n_lines.mean()), pct_multi_page=float((df.n_lines > 12).mean()))


def monthly(df):
    return df.groupby("month").agg(invoices=("invoice_id", "count"), value=("total_myr", "sum")).reset_index()


def dom(df):
    return df.groupby("dom").size().reindex(range(1, 32), fill_value=0).reset_index(name="invoices")


def value_hist(df, bins=14):
    x = np.log10(df.total_myr.dropna().clip(lower=1))  # NaN = foreign invoice without exchange rate
    h, e = np.histogram(x, bins=bins)
    return pd.DataFrame(dict(lo=10 ** e[:-1], hi=10 ** e[1:], n=h))


def error_prevalence(df):
    s = df.injected_errors[df.injected_errors != ""].str.split(",").explode().value_counts()
    return s.rename_axis("error").reset_index(name="n")


def supplier_pareto(df):
    c = df.supplier_id.value_counts().reset_index()
    c.columns = ["supplier", "n"]
    c["cum_share"] = c.n.cumsum() / c.n.sum()
    return c


def by_industry(df):
    return df.groupby("industry").agg(n=("invoice_id", "count"), median_myr=("total_myr", "median"),
                                      high_value=("high_value", "mean")).reset_index().sort_values("n", ascending=False)


def figures(df: pd.DataFrame) -> dict:
    import plotly.express as px
    T = "plotly_white"
    f = {}
    m = monthly(df)
    f["monthly_volume"] = px.bar(m, x="month", y="invoices", title="Invoices received per month", template=T)
    f["day_of_month"] = px.bar(dom(df), x="dom", y="invoices", template=T,
                               title="Arrival by day of month: month-end spike (consolidation crunch)")
    vh = value_hist(df)
    vh["bin"] = vh.apply(lambda r: f"{r.lo:,.0f}-{r.hi:,.0f}", axis=1)
    f["value_hist"] = px.bar(vh, x="bin", y="n", title="Invoice value (RM, log-spaced bins)", template=T)
    f["error_prevalence"] = px.bar(error_prevalence(df), x="n", y="error", orientation="h", template=T,
                                   title="Injected error types (ground truth)")
    f["quality_mix"] = px.pie(df, names="quality", hole=.45, title="Document quality mix", template=T)
    sp = supplier_pareto(df)
    f["supplier_pareto"] = px.line(sp, x=sp.index + 1, y="cum_share", markers=True, template=T,
                                   labels={"x": "Supplier rank", "cum_share": "Cumulative share"}, title="Supplier concentration")
    f["industry"] = px.bar(by_industry(df), x="n", y="industry", orientation="h", template=T, title="Invoices by industry")
    f["value_by_industry"] = px.box(df, x="industry", y="total_myr", log_y=True, template=T, title="Invoice value by industry (RM, log)")
    return f
