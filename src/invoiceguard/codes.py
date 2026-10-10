"""Code lists. ILLUSTRATIVE subset - replace with the official MyInvois SDK code lists. [VERIFY]"""
import re

TAX_TYPES = {
    "01": "Sales Tax", "02": "Service Tax", "03": "Tourism Tax", "04": "High-Value Goods Tax",
    "05": "Sales Tax on Low Value Goods", "06": "Not Applicable", "E": "Tax exemption",
}
INVALID_TAX_CODES = ["09", "S", "00", "X1"]
CURRENCIES = {"MYR", "USD", "SGD", "EUR", "GBP", "CNY", "JPY", "THB", "IDR", "AUD"}
CLASSIFICATION_CODES = {"022"}  # "Others" only; extend from SDK
TIN_RE = re.compile(r"^C\d{10}$|^IG\d{11}$")  # [VERIFY] company / individual TIN shapes
MAX_PASSPORT_LEN = 12                          # [VERIFY] reported 24 Oct 2026 validation change
