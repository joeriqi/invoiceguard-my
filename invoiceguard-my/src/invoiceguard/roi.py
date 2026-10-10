"""ROI model: transparent, parameterised, conservative (direct handling labour only)."""
from __future__ import annotations

from copy import deepcopy


def per_invoice(p: dict) -> dict:
    base = p["handling_min"] + p["rework_rate"] * p["rework_min"]
    auto = p["stp_rate"] * p["spotcheck_min"] + (1 - p["stp_rate"]) * p["exception_min"] + p["new_rework_rate"] * p["rework_min"]
    saved = base - auto
    gross = saved * p["hourly_cost"] / 60
    return dict(baseline_min=base, automated_min=auto, saved_min=saved, gross_rm=gross, net_rm=gross - p["variable_cost"])


def scenario(p: dict, volume: float | None = None) -> dict:
    v = p["volume"] if volume is None else volume
    pi = per_invoice(p)
    monthly = v * pi["net_rm"] - p["fixed_monthly"]
    return dict(volume=v, **pi, monthly_net=monthly, annual_net=monthly * 12,
                payback_months=(p["implementation_cost"] / monthly) if monthly > 0 else None,
                breakeven_volume=(p["fixed_monthly"] / pi["net_rm"]) if pi["net_rm"] > 0 else None)


def sensitivity(p: dict, pct: float = 0.25) -> list[dict]:
    """Tornado: effect on monthly net benefit of moving each driver by +/- pct."""
    keys = ["volume", "handling_min", "hourly_cost", "stp_rate", "exception_min", "variable_cost", "fixed_monthly", "rework_rate"]
    out = []
    for k in keys:
        lo, hi = deepcopy(p), deepcopy(p)
        lo[k] *= 1 - pct
        hi[k] = min(hi[k] * (1 + pct), 0.99) if k == "stp_rate" else hi[k] * (1 + pct)
        out.append(dict(driver=k, low=scenario(lo)["monthly_net"], high=scenario(hi)["monthly_net"]))
    base = scenario(p)["monthly_net"]
    out.sort(key=lambda r: -abs(r["high"] - r["low"]))
    return [dict(base=base, **r) for r in out]
