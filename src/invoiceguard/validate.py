"""Deterministic validation engine. Rule metadata lives in config/rules.yaml. Rules marked verify=true
depend on regulatory facts that MUST be confirmed against LHDN guidelines / the MyInvois SDK."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal as D

import yaml

from .codes import CLASSIFICATION_CODES, CURRENCIES, MAX_PASSPORT_LEN, TAX_TYPES, TIN_RE
from .schema import Extracted
from .synth import ROOT

TOL = D("0.011")
RULES = {r["id"]: r for r in yaml.safe_load((ROOT / "config" / "rules.yaml").read_text(encoding="utf-8"))["rules"]}


@dataclass
class Finding:
    rule: str
    severity: str
    message: str
    field: str | None = None


@dataclass
class Context:
    today: date
    tin_registry: set[str] | None = None      # MOCK of the MyInvois TIN-validation API
    high_value_myr: D = D(10000)
    seen: set = field(default_factory=set)


def _f(rule, msg, fld=None):
    return Finding(rule, RULES[rule]["severity"], msg, fld)


def norm_no(s: str | None) -> str:
    return "".join(ch for ch in (s or "").upper() if ch.isalnum())


def validate(inv: Extracted, ctx: Context, only: set[str] | None = None) -> list[Finding]:
    out: list[Finding] = []
    on = (lambda r: True) if only is None else (lambda r: r in only)

    if on("V00"):
        for fld in ("invoice_number", "issue_date", "supplier_name", "total", "currency"):
            if getattr(inv, fld) in (None, ""):
                out.append(_f("V00", f"{fld} could not be read", fld))
    if inv.lines is not None:
        if on("V01") and inv.subtotal is not None and inv.lines and all(l.line_total is not None for l in inv.lines):
            if abs(sum(l.line_total for l in inv.lines) - inv.subtotal) > TOL:
                out.append(_f("V01", "Sum of line totals differs from subtotal", "subtotal"))
        if on("V03"):
            for i, l in enumerate(inv.lines, 1):
                if None not in (l.quantity, l.unit_price, l.line_total) and abs(l.quantity * l.unit_price - l.line_total) > TOL:
                    out.append(_f("V03", f"Line {i}: qty x unit price != line total", "lines"))
                    break
        if on("V06"):
            for i, l in enumerate(inv.lines, 1):
                if (l.tax_type and l.tax_type not in TAX_TYPES) or (l.classification_code and l.classification_code not in CLASSIFICATION_CODES):
                    out.append(_f("V06", f"Line {i}: tax/classification code not in code list", "lines"))
                    break
    if on("V02") and None not in (inv.subtotal, inv.tax_total, inv.total) and abs(inv.subtotal + inv.tax_total - inv.total) > TOL:
        out.append(_f("V02", "Subtotal + tax != total", "total"))
    if on("V04") and inv.currency:
        if inv.currency not in CURRENCIES:
            out.append(_f("V04", f"Unknown currency {inv.currency}", "currency"))
        elif inv.currency != "MYR" and not inv.exchange_rate:
            out.append(_f("V04", "Foreign currency without exchange rate", "exchange_rate"))
    if on("V05"):
        tin = inv.supplier_tin
        if not tin:
            out.append(_f("V05", "Supplier TIN missing", "supplier_tin"))
        elif not TIN_RE.match(tin):
            out.append(_f("V05", "Supplier TIN malformed", "supplier_tin"))
        elif ctx.tin_registry is not None and tin not in ctx.tin_registry:
            out.append(_f("V05", "TIN not found in registry (mock lookup)", "supplier_tin"))
    if on("V07"):
        t = None
        if inv.total is not None and inv.currency == "MYR":
            t = inv.total
        elif inv.total is not None and inv.exchange_rate:
            t = inv.total * inv.exchange_rate
        if t is not None and t >= ctx.high_value_myr:
            out.append(_f("V07", "Single transaction >= RM10,000: individual e-invoice, cannot be consolidated", "total"))
    if on("V08") and inv.invoice_number:
        key = (inv.supplier_tin or (inv.supplier_name or "").casefold(), norm_no(inv.invoice_number))
        if key in ctx.seen:
            out.append(_f("V08", "Duplicate supplier + invoice number", "invoice_number"))
        ctx.seen.add(key)
    if on("V09") and inv.issue_date and inv.issue_date > ctx.today:
        out.append(_f("V09", "Issue date is in the future", "issue_date"))
    if on("V10") and (inv.supplier_id_type or "").upper() == "PASSPORT" and len(inv.supplier_id_value or "") > MAX_PASSPORT_LEN:
        out.append(_f("V10", f"Passport ID longer than {MAX_PASSPORT_LEN} chars", "supplier_id_value"))
    if on("V11") and inv.has_uin is False:
        out.append(_f("V11", "No MyInvois UIN on document (supplier may not be e-invoicing)", None))
    return out
