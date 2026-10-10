# %% [markdown]
# # 01 · Exploratory data analysis: InvoiceGuard MY
# Open in VS Code and click **Run Cell** / **Run All** (Jupyter extension, "# %%" cells). Also runs as a plain script.
#
# **Questions this notebook answers**
# 1. What does the invoice corpus look like (volume, value, quality, suppliers)?
# 2. Is the data internally consistent (integrity checks before any modelling)?
# 3. When does work arrive, and where is the bottleneck pressure?
# 4. Where does the *measured* OCR+regex baseline fail, and what does that imply for the AI design?
#
# > All invoices are **synthetic**. Patterns here describe the *evaluation corpus*, not Malaysian SMEs in general.

# %%
import sys
from pathlib import Path

ROOT = Path.cwd() if (Path.cwd() / "src").exists() else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402

from invoiceguard import eda  # noqa: E402

pd.set_option("display.width", 160)
FIG = ROOT / "reports" / "figures"
FIG.mkdir(parents=True, exist_ok=True)


def show(fig, name):
    fig.update_layout(template="plotly_white")
    fig.write_html(FIG / f"nb_{name}.html", include_plotlyjs="cdn")
    try:
        get_ipython  # noqa: B018  (defined inside Jupyter / VS Code interactive)
        fig.show()
    except NameError:
        pass


df = eda.load()
res = pd.read_csv(ROOT / "reports" / "results.csv").fillna("")
print(df.shape)
df.head(3).T

# %% [markdown]
# ## 1 · Data integrity checks (do these *before* trusting any chart)

# %%
checks = {
    "unique invoice_id": df.invoice_id.is_unique,
    "no nulls in key fields": df[["invoice_number", "issue_date", "supplier_name", "total", "currency"]].notna().all().all(),
    "dev+test = all": set(df.split) == {"dev", "test"},
    "dates inside range or future-injected": ((df.issue_date <= "2026-09-30") | df.injected_errors.str.contains("FUTURE_DATE")).all(),
    "foreign invoices without rate == injected FX errors": (
        (df.foreign & df.exchange_rate.isna()).sum() == df.injected_errors.str.contains("FX_NO_RATE").sum()),
    "duplicates == injected DUPLICATE": (
        df.duplicated(["supplier_id", "invoice_number"], keep="first").sum() == df.injected_errors.str.contains("DUPLICATE").sum()),
}
pd.Series(checks, name="passed").to_frame()

# %% [markdown]
# ## 2 · Corpus profile

# %%
pd.Series(eda.kpis(df)).round(3).to_frame("value")

# %%
show(px.histogram(df.dropna(subset=["total_myr"]), x="total_myr", log_x=True, nbins=30, color="quality",
                  title="Invoice value (RM, log scale)"), "value")
df.total_myr.describe(percentiles=[.1, .5, .9, .99]).round(0)

# %% [markdown]
# **Reading:** heavy right tail: a few large invoices carry most of the money, and the ones ≥ RM10,000 trigger the
# individual-e-invoice rule (cannot be consolidated, **[VERIFY]**). That is why they are routed to humans by *policy*,
# regardless of model confidence.

# %%
show(px.bar(eda.by_industry(df), x="industry", y="n", color="high_value", title="Industry mix (colour = share ≥ RM10k)"), "industry")
show(px.pie(df, names="quality", hole=.45, title="Document quality"), "quality")

# %% [markdown]
# ## 3 · Timing: where does the pressure come from?

# %%
d = eda.dom(df)
d["last5"] = d.dom >= 26
expected = d.invoices.sum() * 5 / 30
print(f"Share arriving on days 26-31: {d[d.last5].invoices.sum() / d.invoices.sum():.1%} (uniform would be ~{5/30:.0%}); the last-5-calendar-days KPI used in the dashboards is {eda.kpis(df)['pct_month_end']:.0%}")
show(px.bar(d, x="dom", y="invoices", color="last5", title="Arrivals by day of month"), "dom")

# %%
df["weekday"] = df.issue_date.dt.day_name()
show(px.bar(df.groupby("weekday").size().reindex(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]).reset_index(name="n"),
            x="weekday", y="n", title="Arrivals by weekday"), "weekday")

# %% [markdown]
# **Reading:** a month-end spike. During the relaxation period consolidated e-invoices are due within 7 days of month-end
# (**[VERIFY]**), so the same people who key invoices also face the compliance deadline in the same week.
#
# ## 4 · Suppliers

# %%
sp = eda.supplier_pareto(df)
print(f"Top 5 suppliers = {sp.cum_share.iloc[4]:.0%} of invoices; top 10 = {sp.cum_share.iloc[9]:.0%}")
show(px.line(sp, y="cum_share", markers=True, title="Supplier concentration (cumulative share)"), "pareto")

# %% [markdown]
# **Reading:** concentrated suppliers → supplier-specific layouts repeat. Opportunity: per-supplier extraction hints and a
# supplier master (TIN, MSIC, tax defaults) that makes validation sharper over time.
#
# ## 5 · Where the measured baseline fails (OCR + regex)

# %%
test = res[(res.split == "test") & (res.system == "A_ocr_regex")].copy()
fields = [c for c in test.columns if c.startswith("ok_")]
print("Baseline exact-match by field (test):")
print(test[fields].mean().round(3).sort_values())

# %%
byq = test.groupby("quality")[fields + ["crit_ok"]].mean().round(2)
byq

# %%
show(px.bar(byq.reset_index().melt(id_vars="quality", value_vars=fields), x="variable", y="value", color="quality",
            barmode="group", title="Baseline accuracy by field and document quality"), "baseline_by_quality")

# %%
by_layout = test.groupby("layout").crit_ok.agg(["mean", "count"]).round(2)
by_lang = test.groupby("language").crit_ok.agg(["mean", "count"]).round(2)
display_df = pd.concat({"layout": by_layout, "language": by_lang})
display_df

# %% [markdown]
# **Reading:** the regex baseline gets all five critical fields right on ~88% of clean digital PDFs, ~12% of scans and 0% of phone
# photos. Layout and language effects are second-order.
#
# **Caveat:** how harsh the scan/photo degradation is (blur, noise, skew) is a parameter *I* chose in `synth.degrade`. The
# direction of the gap is the finding; its magnitude is not a claim about real-world scans. Digital quality is the dominant driver, so a vision model (reads pixels, not OCR text) is the
# natural upgrade, consistent with recent benchmarks that find native image input beats parse-to-text pipelines
# (Berghaus et al., arXiv 2509.04469).
#
# ## 6 · What the baseline *cannot* do: validation needs line items

# %%
c = pd.read_csv(ROOT / "reports" / "catch_by_error_test.csv")
piv = c[c.system.isin(["A_ocr_regex", "A+_ocr_regex_rules"])].pivot(index="injected", columns="system", values="rule_fired").round(2)
piv

# %% [markdown]
# **Reading:** even *with* the rules engine, the regex baseline fires the expected rule 0% of the time for line-based errors
# (`LINE_CALC_ERROR`, `LINE_SUM_MISMATCH`, `BAD_TAX_CODE`) because it never extracts line items. Structured line extraction is
# therefore the capability that unlocks validation: the concrete **AI opportunity**.
#
# ## 7 · Findings → design decisions
# | Finding | Design decision |
# |---|---|
# | ~47% of invoices arrive in the last 5 days of the month | Prioritise throughput and an exception queue sorted by risk |
# | Baseline fails on photos (0% critical-field match) | Vision-first extraction, not OCR-first |
# | Line-based errors invisible without line items | Extract line items; run V01/V03/V06 |
# | ≥RM10k invoices are ~14% of volume | Policy-based human review above threshold |
# | Wrong auto-approvals are the costly failure | Route on rules **and** confidence; report wrong-auto-approve as the headline safety metric |
