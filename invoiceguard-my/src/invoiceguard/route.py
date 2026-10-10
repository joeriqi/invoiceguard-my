"""Confidence + rules router. AI proposes, rules verify, humans decide."""
from __future__ import annotations

from .schema import Extracted
from .validate import Finding


def route(inv: Extracted, findings: list[Finding], conf_threshold: float = 0.80, use_conf: bool = True):
    reasons = sorted({f.rule for f in findings if f.severity in ("error", "warning")})
    minconf = min(inv.field_confidence.values()) if inv.field_confidence else 1.0
    if use_conf and minconf < conf_threshold:
        reasons.append("LOW_CONF")
    return ("review" if reasons else "auto_approve"), reasons, minconf
