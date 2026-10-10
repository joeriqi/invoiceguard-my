import datetime as dt
from decimal import Decimal as D

from invoiceguard.schema import Extracted, Line
from invoiceguard.validate import Context, validate


def good() -> Extracted:
    return Extracted(supplier_name="Acme Sdn Bhd", supplier_tin="C9123456789", supplier_id_type="BRN", supplier_id_value="123456789012",
                     invoice_number="INV-001", issue_date=dt.date(2026, 3, 1), currency="MYR", has_uin=True,
                     lines=[Line(quantity=D(2), unit_price=D("10.00"), tax_type="01", tax_rate=D(10), line_total=D("20.00")),
                            Line(quantity=D(1), unit_price=D("5.00"), tax_type="01", tax_rate=D(10), line_total=D("5.00"))],
                     subtotal=D("25.00"), tax_total=D("2.50"), total=D("27.50"))


def ctx(**kw):
    return Context(today=dt.date(2026, 10, 9), **kw)


def rules(inv, **kw):
    return {f.rule for f in validate(inv, ctx(**kw))}


def test_clean_invoice_passes():
    assert rules(good()) == set()


def test_v01_line_sum():
    i = good(); i.subtotal = D("30.00"); i.total = D("32.50")
    assert "V01" in rules(i)


def test_v02_total():
    i = good(); i.total = D("99.00")
    assert rules(i) == {"V02"}


def test_v03_line_calc():
    i = good(); i.lines[0].line_total = D("25.00"); i.subtotal = D("30.00"); i.total = D("32.50")
    assert rules(i) == {"V03"}


def test_v04_fx_needs_rate():
    i = good(); i.currency = "USD"
    assert "V04" in rules(i)
    i.exchange_rate = D("4.4")
    assert "V04" not in rules(i)


def test_v05_tin_cases():
    for bad in (None, "", "X123", "C91234"):
        i = good(); i.supplier_tin = bad
        assert "V05" in rules(i)
    i = good()
    assert "V05" in rules(i, tin_registry={"C9000000000"})      # unknown to (mock) registry
    assert "V05" not in rules(i, tin_registry={"C9123456789"})


def test_v06_tax_code():
    i = good(); i.lines[0].tax_type = "09"
    assert "V06" in rules(i)


def test_v07_high_value_is_warning():
    i = good(); i.subtotal = D("10000.00"); i.tax_total = D(0); i.total = D("10000.00")
    f = [x for x in validate(i, ctx()) if x.rule == "V07"]
    assert f and f[0].severity == "warning"


def test_v08_duplicate():
    c = ctx()
    assert not [f for f in validate(good(), c) if f.rule == "V08"]
    assert [f for f in validate(good(), c) if f.rule == "V08"]


def test_v09_future_date():
    i = good(); i.issue_date = dt.date(2026, 12, 1)
    assert "V09" in rules(i)


def test_v10_passport_length():
    i = good(); i.supplier_id_type = "PASSPORT"; i.supplier_id_value = "A" * 13
    assert "V10" in rules(i)
    i.supplier_id_value = "A" * 12
    assert "V10" not in rules(i)


def test_v11_info_only():
    i = good(); i.has_uin = False
    f = validate(i, ctx())
    assert [x.severity for x in f] == ["info"]


def test_line_rules_skipped_when_lines_not_extracted():
    i = good(); i.lines = None; i.subtotal = D("1.00")
    assert "V01" not in rules(i)
