"""Evaluation: field accuracy, STP, wrong-auto-approve, error catch rate - per system, on the TEST split."""
from __future__ import annotations

import datetime as dt
import json
import random
from decimal import ROUND_HALF_UP
from decimal import Decimal as D
from pathlib import Path

import pandas as pd

from .extract import BaselineExtractor, SimLLMExtractor
from .route import route
from .schema import CRITICAL_FIELDS, HEADER_FIELDS, Extracted
from .synth import ERROR_TO_RULE, ROOT, load_corpus, load_params, make_suppliers
from .validate import Context, validate


def _n(v):
    if v is None or v == "":
        return None
    if isinstance(v, (D, float, int)):
        return str(D(str(v)).quantize(D("0.01"), ROUND_HALF_UP))
    if isinstance(v, dt.date):
        return v.isoformat()
    return "".join(ch for ch in str(v).casefold() if ch.isalnum())


def field_flags(gt: dict, ex: Extracted) -> dict[str, bool]:
    g = {"invoice_number": gt["invoice_number"], "issue_date": gt["issue_date"], "supplier_tin": gt["supplier_tin"] or None,
         "currency": gt["currency"], "total": gt["total"], "supplier_name": gt["supplier_name"],
         "subtotal": gt["subtotal"], "tax_total": gt["tax_total"]}
    out = {}
    for f in HEADER_FIELDS:
        a, b = g[f], getattr(ex, f)
        if f == "issue_date":
            a = dt.date.fromisoformat(a)
        elif f in ("total", "subtotal", "tax_total"):
            a = D(a)
        out[f] = _n(a) == _n(b)
    return out


def extract_all(extractor, corpus: list[dict]) -> dict[str, Extracted]:
    return {i["invoice_id"]: extractor.extract(i) for i in corpus}


POLICIES = {   # name -> (extractor key, rules, use_conf, route_enabled)
    "A_ocr_regex":         ("baseline", "V00-only", False, True),
    "A+_ocr_regex_rules":  ("baseline", "all", False, True),
    "B_llm_only":          ("sim", "none", False, False),
    "C_invoiceguard":      ("sim", "all", True, True),
    "C_invoiceguard_claude": ("claude", "all", True, True),
}


def run_policy(name: str, corpus: list[dict], ex_map: dict[str, Extracted], P: dict, registry: set[str]) -> pd.DataFrame:
    _, rules, use_conf, routed = POLICIES[name]
    ctx = Context(today=dt.date.fromisoformat(P["today"]), tin_registry=registry, high_value_myr=D(P["router"]["high_value_myr"]))
    rows = []
    for gt in corpus:
        if gt["invoice_id"] not in ex_map:
            continue
        ex = ex_map[gt["invoice_id"]]
        only = {"V00"} if rules == "V00-only" else (set() if rules == "none" else None)
        findings = validate(ex, ctx, only=only)
        if routed:
            decision, reasons, minconf = route(ex, findings, P["router"]["conf_threshold"], use_conf)
        else:
            decision, reasons, minconf = "auto_approve", [], 1.0
        fl = field_flags(gt, ex)
        crit_ok = all(fl[f] for f in CRITICAL_FIELDS)
        fired = sorted({f.rule for f in findings})
        exp_rules = sorted({ERROR_TO_RULE[e] for e in gt["injected_errors"]})
        rows.append(dict(
            invoice_id=gt["invoice_id"], split=gt["split"], system=name, quality=gt["quality"], layout=gt["layout"],
            language=gt["language"], industry=gt["industry"], decision=decision, reasons=",".join(reasons),
            fired=",".join(fired), minconf=round(minconf, 3), crit_ok=crit_ok, **{f"ok_{k}": v for k, v in fl.items()},
            injected=",".join(gt["injected_errors"]), high_value=gt["high_value"], should_review=gt["should_review"],
            rule_hit=bool(exp_rules) and all(r in fired for r in exp_rules),
            wrong_auto=(decision == "auto_approve") and (gt["should_review"] or not crit_ok)))
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for sysname, g in df.groupby("system", sort=False):
        auto = g[g.decision == "auto_approve"]
        err = g[g.injected != ""]
        clean_ok = g[(~g.should_review) & g.crit_ok]
        r = dict(system=sysname, n=len(g),
                 field_acc=g[[f"ok_{f}" for f in HEADER_FIELDS]].mean().mean(),
                 critical_exact=g.crit_ok.mean(), stp_rate=len(auto) / len(g),
                 wrong_auto_n=int(g.wrong_auto.sum()), wrong_auto_of_auto=(g.wrong_auto.sum() / len(auto)) if len(auto) else 0.0,
                 error_routed_to_review=(err.decision == "review").mean() if len(err) else None,
                 expected_rule_fired=err.rule_hit.mean() if len(err) else None,
                 unneeded_review=(clean_ok.decision == "review").mean() if len(clean_ok) else None,
                 stp_error_free_docs=(g[~g.should_review].decision == "auto_approve").mean())
        for f in HEADER_FIELDS:
            r[f"acc_{f}"] = g[f"ok_{f}"].mean()
        out.append(r)
    return pd.DataFrame(out)


def catch_by_error(df: pd.DataFrame) -> pd.DataFrame:
    e = df[df.injected != ""].copy()
    e["injected"] = e.injected.str.split(",")
    e = e.explode("injected")
    return (e.groupby(["system", "injected"]).agg(n=("invoice_id", "count"), routed=("decision", lambda s: (s == "review").mean()),
                                                   rule_fired=("rule_hit", "mean")).reset_index())


def run_all(extractions: dict[str, dict[str, Extracted]], P: dict | None = None) -> pd.DataFrame:
    P = P or load_params()
    corpus = load_corpus()
    registry = {s["tin"] for s in make_suppliers(random.Random(P["seed"]), P)}
    frames = []
    for name, (ek, *_rest) in POLICIES.items():
        if ek in extractions:
            frames.append(run_policy(name, corpus, extractions[ek], P, registry))
    return pd.concat(frames, ignore_index=True)


def build_extractions(P: dict, use_claude_limit: int | None = None) -> dict[str, dict[str, Extracted]]:
    corpus = load_corpus()
    ex = {"baseline": extract_all(BaselineExtractor(), corpus), "sim": extract_all(SimLLMExtractor(P["sim_llm"], P["seed"]), corpus)}
    cf = ROOT / "data" / "extractions_claude.json"
    if cf.exists():
        ex["claude"] = {k: Extracted.model_validate(v) for k, v in json.loads(cf.read_text(encoding="utf-8")).items()}
    return ex


def save_reports(df: pd.DataFrame, outdir: Path | None = None) -> None:
    outdir = outdir or ROOT / "reports"
    outdir.mkdir(exist_ok=True)
    df.to_csv(outdir / "results.csv", index=False)
    test = df[df.split == "test"]
    summarize(test).to_csv(outdir / "summary_test.csv", index=False)
    catch_by_error(test).to_csv(outdir / "catch_by_error_test.csv", index=False)
