"""Oracle test: validating the *ground truth* must flag every injected error with its expected rule."""
import datetime as dt
from decimal import Decimal as D

from invoiceguard.evaluate import _n
from invoiceguard.schema import Extracted, Line
from invoiceguard.synth import ERROR_TO_RULE, build_corpus, load_params
from invoiceguard.validate import Context, validate


def to_extracted(g: dict) -> Extracted:
    return Extracted(
        supplier_name=g["supplier_name"], supplier_tin=g["supplier_tin"] or None, supplier_id_type=g["supplier_id_type"],
        supplier_id_value=g["supplier_id_value"], invoice_number=g["invoice_number"], issue_date=dt.date.fromisoformat(g["issue_date"]),
        currency=g["currency"], exchange_rate=D(g["exchange_rate"]) if g["exchange_rate"] else None, has_uin=g["has_uin"],
        subtotal=D(g["subtotal"]), tax_total=D(g["tax_total"]), total=D(g["total"]),
        lines=[Line(quantity=D(x["quantity"]), unit_price=D(x["unit_price"]), tax_type=x["tax_type"], tax_rate=D(x["tax_rate"]),
                    classification_code=x["classification_code"], line_total=D(x["line_total"])) for x in g["lines"]])


def test_determinism():
    P = load_params()
    a, b = build_corpus(P), build_corpus(P)
    assert [x["invoice_number"] for x in a] == [x["invoice_number"] for x in b]


def test_oracle_catches_every_injected_error_and_nothing_else():
    P = load_params()
    corpus = build_corpus(P)
    import random

    from invoiceguard.synth import make_suppliers
    reg = {s["tin"] for s in make_suppliers(random.Random(P["seed"]), P)}
    ctx = Context(today=dt.date.fromisoformat(P["today"]), tin_registry=reg)
    for g in corpus:
        fired = {f.rule for f in validate(to_extracted(g), ctx) if f.severity == "error"}
        expected = {ERROR_TO_RULE[e] for e in g["injected_errors"]}
        assert expected <= fired, (g["invoice_id"], expected, fired)
        assert fired <= expected, f"false alarm on {g['invoice_id']}: {fired - expected}"


def test_split_sizes_and_leak_free_ids():
    P = load_params()
    c = build_corpus(P)
    assert len(c) == P["n_invoices"]
    assert sum(x["split"] == "dev" for x in c) == P["dev_size"]
    assert len({x["invoice_id"] for x in c}) == len(c)


def test_normaliser():
    assert _n("INV-001") == _n("inv 001") and _n(D("1.005")) == "1.01"
