from decimal import Decimal as D

from invoiceguard.extract import ClaudeVisionExtractor, parse_text
from invoiceguard.roi import per_invoice, scenario
from invoiceguard.route import route
from invoiceguard.schema import Extracted
from invoiceguard.validate import Finding

SAMPLE = """Maju Teknik Sdn Bhd
Lot 1, Jalan Maju 2/3, Shah Alam
TIN: C9123456789
BRN No: 201901012345
TAX INVOICE                                      Invoice No: INV-2600123
                                                 Date: 14/03/2026
  1   Cloud hosting          2     100.00   02/6%     200.00
                                       Subtotal         RM 200.00
                                       Tax              RM 12.00
                                       Total            RM 212.00
"""


def test_parse_text_header_fields():
    e = parse_text(SAMPLE)
    assert (e.invoice_number, str(e.issue_date), e.supplier_tin, e.currency) == ("INV-2600123", "2026-03-14", "C9123456789", "MYR")
    assert (e.subtotal, e.tax_total, e.total) == (D("200.00"), D("12.00"), D("212.00"))
    assert e.lines is None


def test_router_rules():
    e = Extracted(field_confidence={"total": 0.95})
    assert route(e, [])[0] == "auto_approve"
    assert route(e, [Finding("V02", "error", "x")])[0] == "review"
    assert route(e, [Finding("V11", "info", "x")])[0] == "auto_approve"      # info never blocks
    assert route(Extracted(field_confidence={"total": 0.5}), [])[1] == ["LOW_CONF"]


def test_roi_matches_documented_example():
    p = dict(handling_min=8, rework_rate=.05, rework_min=20, hourly_cost=25, stp_rate=.7, spotcheck_min=.5, exception_min=4,
             new_rework_rate=.015, variable_cost=.10, fixed_monthly=390, implementation_cost=25000, volume=1000)
    pi = per_invoice(p)
    assert round(pi["baseline_min"], 2) == 9.0 and round(pi["saved_min"], 2) == 7.15 and round(pi["net_rm"], 2) == 2.88
    s = scenario(p)
    assert round(s["breakeven_volume"]) == 135 and 9.5 < s["payback_months"] < 10.5
    assert scenario(p, 300)["payback_months"] > 48


class _Block:
    type = "tool_use"
    input = {"invoice_number": "A-1", "issue_date": "2026-03-01", "total": 10.5, "currency": "MYR", "has_uin": True,
             "lines": [{"description": "x", "quantity": 1, "unit_price": 10.5, "line_total": 10.5}],
             "field_confidence": {"total": 0.9}}


class _Resp:
    content = [_Block()]
    usage = type("U", (), {"input_tokens": 100, "output_tokens": 20})()


class _FakeClient:
    class messages:   # noqa: N801
        @staticmethod
        def create(**kw):
            assert kw["tool_choice"]["name"] == "record_invoice"
            return _Resp()


def test_claude_extractor_with_fake_client(tmp_path):
    img = tmp_path / "x.png"; img.write_bytes(b"\x89PNG")
    ex = ClaudeVisionExtractor(client=_FakeClient(), model="test-model").extract_images([img])
    assert ex.total == D("10.5") and ex.lines[0].unit_price == D("10.5") and str(ex.issue_date) == "2026-03-01"
