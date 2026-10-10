"""Synthetic invoice corpus. Every entity is fictional. Ground truth = what the document *prints*
(including injected errors), so validation is expected to flag the injected problems."""
from __future__ import annotations

import copy
import datetime as dt
import json
import random
import string
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np
import yaml

from .codes import INVALID_TAX_CODES
from .tools import find_tool, run_text

D = Decimal
ROOT = Path(__file__).resolve().parents[2]


def q2(x) -> Decimal:
    return D(str(x)).quantize(D("0.01"), ROUND_HALF_UP)


def load_params() -> dict:
    return yaml.safe_load((ROOT / "config" / "params.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- vocab
INDUSTRIES = {
    "Office & stationery": dict(w=.14, mu=2.0, sig=.9, qty=(1, 60), tax="01", rates=[0, 10],
        en=["A4 paper 80gsm ream", "Ballpoint pens (box)", "Toner cartridge", "Filing folders", "Stapler set"],
        bm=["Kertas A4 80gsm rim", "Pen mata bulat (kotak)", "Katrij toner", "Fail folder", "Set pemati"]),
    "IT & software services": dict(w=.14, mu=5.0, sig=1.1, qty=(1, 12), tax="02", rates=[6, 8],
        en=["Cloud hosting monthly", "Software licence renewal", "Network maintenance", "Laptop repair", "Support retainer"],
        bm=["Hos awan bulanan", "Pembaharuan lesen perisian", "Penyelenggaraan rangkaian", "Baiki komputer riba", "Khidmat sokongan"]),
    "Logistics & freight": dict(w=.13, mu=4.3, sig=1.0, qty=(1, 20), tax="02", rates=[6, 8],
        en=["Local delivery trip", "Container haulage", "Air freight handling", "Warehouse storage", "Customs clearance"],
        bm=["Penghantaran tempatan", "Pengangkutan kontena", "Pengendalian kargo udara", "Penyimpanan gudang", "Pelepasan kastam"]),
    "Printing & packaging": dict(w=.12, mu=3.0, sig=1.0, qty=(50, 1000), tax="01", rates=[5, 10],
        en=["Corrugated box 5-ply", "Label printing", "Brochure A4 colour", "Bubble wrap roll", "Custom tape"],
        bm=["Kotak beralun 5-lapis", "Cetakan label", "Brosur A4 berwarna", "Gulungan bubble wrap", "Pita khas"]),
    "Food & catering": dict(w=.11, mu=2.5, sig=.9, qty=(5, 200), tax="02", rates=[6, 8],
        en=["Lunch box set", "Coffee break buffet", "Event catering package", "Mineral water carton", "Pastry tray"],
        bm=["Set kotak makan tengah hari", "Bufet rehat kopi", "Pakej katering acara", "Karton air mineral", "Dulang pastri"]),
    "Construction materials": dict(w=.12, mu=3.8, sig=1.1, qty=(10, 400), tax="01", rates=[5, 10],
        en=["Portland cement 50kg", "Steel rebar 12mm", "Ceramic floor tiles", "PVC pipe 4in", "Paint 20L pail"],
        bm=["Simen Portland 50kg", "Besi tetulang 12mm", "Jubin lantai seramik", "Paip PVC 4in", "Baldi cat 20L"]),
    "Cleaning & maintenance": dict(w=.13, mu=3.9, sig=.9, qty=(1, 30), tax="02", rates=[6, 8],
        en=["Monthly cleaning service", "Pest control visit", "Aircond servicing", "Lift maintenance", "Landscaping"],
        bm=["Perkhidmatan pembersihan bulanan", "Kawalan perosak", "Servis penyaman udara", "Penyelenggaraan lif", "Landskap"]),
    "Utilities & telco": dict(w=.11, mu=4.0, sig=.8, qty=(1, 6), tax="06", rates=[0],
        en=["Fibre broadband plan", "Mobile postpaid lines", "Leased line", "Water usage", "Electricity usage"],
        bm=["Pelan jalur lebar gentian", "Talian pascabayar", "Talian pajakan", "Penggunaan air", "Penggunaan elektrik"]),
}
P1 = ["Maju", "Bintang", "Sinar", "Teguh", "Harmoni", "Prima", "Nusantara", "Delta", "Cekap", "Mutiara",
      "Jaya", "Alam", "Sentosa", "Kasturi", "Rimba", "Pelangi", "Zenith", "Orion", "Lestari", "Wawasan"]
P2 = ["Teknik", "Logistik", "Pakej", "Digital", "Bekal", "Print", "Mesra", "Utama", "Global", "Resources"]
P3 = ["Sdn Bhd", "Enterprise", "Trading", "Sdn. Bhd.", "Resources", "PLT"]
CITIES = [("Shah Alam", "Selangor", "40000"), ("Petaling Jaya", "Selangor", "46000"), ("Kuala Lumpur", "WP KL", "50450"),
          ("Georgetown", "Penang", "10050"), ("Johor Bahru", "Johor", "80000"), ("Cyberjaya", "Selangor", "63000"),
          ("Ipoh", "Perak", "30000"), ("Kuching", "Sarawak", "93000")]
INV_FMTS = ["INV-{yy}{seq:05d}", "{p}/{yy}/{seq:04d}", "IV{seq:06d}", "{seq:07d}", "PI-{yy}-{seq:04d}"]

LABELS = {
    "en": dict(title="TAX INVOICE", inv_no=["Invoice No", "Invoice No.", "Inv No"], date=["Date", "Invoice Date"],
               tin=["TIN", "Tax ID"], sub=["Subtotal", "Sub-total"], tax=["Tax", "SST", "Service Tax"],
               total=["Total", "Grand Total", "Total Amount"], desc="Description", qty="Qty", price="Unit Price",
               amt="Amount", bill="Bill To"),
    "bm": dict(title="INVOIS CUKAI", inv_no=["No. Invois", "No Invois"], date=["Tarikh"], tin=["No. TIN"],
               sub=["Jumlah Kecil"], tax=["Cukai", "SST"], total=["Jumlah", "Jumlah Keseluruhan"],
               desc="Perihalan", qty="Kuantiti", price="Harga Seunit", amt="Jumlah", bill="Kepada"),
}
# 8 visual layouts
LAYOUTS = [
    dict(font="Helvetica", align="l", money="prefix", grid=False, datefmt="%d/%m/%Y", cur_line=False),
    dict(font="Times-Roman", align="c", money="plain", grid=True, datefmt="%Y-%m-%d", cur_line=True),
    dict(font="Courier", align="l", money="suffix", grid=False, datefmt="%d %b %Y", cur_line=False),
    dict(font="Helvetica", align="r", money="plain", grid=True, datefmt="%d/%m/%Y", cur_line=True),
    dict(font="Times-Roman", align="l", money="prefix", grid=False, datefmt="%d %b %Y", cur_line=False),
    dict(font="Courier", align="c", money="plain", grid=True, datefmt="%Y-%m-%d", cur_line=True),
    dict(font="Helvetica", align="c", money="suffix", grid=True, datefmt="%d/%m/%Y", cur_line=False),
    dict(font="Times-Roman", align="r", money="prefix", grid=False, datefmt="%Y-%m-%d", cur_line=False),
]
SYMBOL = {"MYR": "RM", "USD": "USD", "SGD": "SGD", "EUR": "EUR"}


# ---------------------------------------------------------------- suppliers
def make_suppliers(rng: random.Random, P: dict, n: int = 40) -> list[dict]:
    names, out = set(), []
    inds, wts = list(INDUSTRIES), [INDUSTRIES[i]["w"] for i in INDUSTRIES]
    for k in range(n):
        while True:
            nm = f"{rng.choice(P1)} {rng.choice(P2)} {rng.choice(P3)}"
            if nm not in names:
                names.add(nm)
                break
        lang = rng.choices(["en", "bm", "mixed"], [.6, .15, .25])[0]
        pick = lambda key, lang=lang: (rng.choice(LABELS[lang if lang != "mixed" else rng.choice(["en", "bm"])][key]))  # noqa: E731
        city = rng.choice(CITIES)
        foreign = k >= 6 and rng.random() < P["foreign_supplier_share"] * 1.3
        out.append(dict(
            supplier_id=f"S{k+1:02d}", name=nm, industry=rng.choices(inds, wts)[0], layout=rng.randrange(8),
            language=lang, tin="C9" + "".join(rng.choices(string.digits, k=9)),
            brn="".join(rng.choices(string.digits, k=12)), capable=rng.random() < P["einvoice_capable_share"],
            weight=1 / (k + 1) ** 0.9, fmt=rng.choice(INV_FMTS), prefix="".join(rng.choices(string.ascii_uppercase, k=2)),
            currency=rng.choice(["USD", "SGD", "EUR"]) if foreign else "MYR",
            address=f"Lot {rng.randint(1, 99)}, Jalan {rng.choice(P1)} {rng.randint(1, 9)}/{rng.randint(1, 20)}, "
                    f"{city[0]}, {city[2]} {city[1]}",
            lab=dict(title=LABELS["bm" if lang == "bm" else "en"]["title"], inv_no=pick("inv_no"), date=pick("date"),
                     tin=pick("tin"), sub=pick("sub"), tax=pick("tax"), total=pick("total"),
                     **{k2: LABELS["bm" if lang == "bm" else "en"][k2] for k2 in ("desc", "qty", "price", "amt", "bill")}),
        ))
    return out


# ---------------------------------------------------------------- invoices
def _date(rng, lo, hi):
    while True:
        m = rng.randint(lo.month, hi.month)
        first = dt.date(lo.year, m, 1)
        last = (dt.date(lo.year, m + 1, 1) - dt.timedelta(days=1)) if m < 12 else dt.date(lo.year, 12, 31)
        day = rng.randint(max(1, last.day - 4), last.day) if rng.random() < 0.40 else rng.randint(1, last.day)
        d = first.replace(day=day)
        if lo <= d <= hi:
            return d


def make_invoice(rng, np_rng, s: dict, lo, hi, P) -> dict:
    ind = INDUSTRIES[s["industry"]]
    n_lines = int(min(24, 1 + np_rng.geometric(0.35)))
    cur = s["currency"]
    rate = None if cur == "MYR" else q2({"USD": rng.uniform(4.2, 4.6), "SGD": rng.uniform(3.2, 3.5), "EUR": rng.uniform(4.8, 5.2)}[cur])
    rate = None if rate is None else D(str(round(float(rate), 4)))
    lines = []
    lang = s["language"]
    for _ in range(n_lines):
        use_bm = lang == "bm" or (lang == "mixed" and rng.random() < .5)
        idx = rng.randrange(len(ind["en"]))
        lo_q, hi_q = ind["qty"]
        qty = D(rng.randint(lo_q, max(lo_q, int(lo_q + (hi_q - lo_q) * rng.random() ** 3))))
        price_myr = float(np_rng.lognormal(ind["mu"], ind["sig"]))
        price = q2(price_myr / float(rate)) if rate else q2(price_myr)
        r = D(rng.choice(ind["rates"]))
        lt = q2(qty * price)
        lines.append(dict(description=(ind["bm"] if use_bm else ind["en"])[idx], quantity=str(qty), unit_price=str(price),
                          tax_type=ind["tax"], tax_rate=str(r), classification_code="022", line_total=str(lt)))
    sub = sum(D(x["line_total"]) for x in lines)
    tax = sum(q2(D(x["line_total"]) * D(x["tax_rate"]) / 100) for x in lines)
    total = sub + tax
    q = rng.choices(["digital", "scanned", "photo"], [P["quality_mix"][k] for k in ("digital", "scanned", "photo")])[0]
    return dict(supplier_id=s["supplier_id"], supplier_name=s["name"], industry=s["industry"], layout=s["layout"],
                language=lang, quality=q, supplier_tin=s["tin"], supplier_id_type="BRN", supplier_id_value=s["brn"],
                invoice_number="", issue_date=_date(rng, lo, hi).isoformat(), currency=cur,
                exchange_rate=None if rate is None else str(rate), lines=lines, subtotal=str(sub), tax_total=str(tax),
                total=str(total), has_uin=s["capable"],
                uin="".join(rng.choices(string.ascii_uppercase + string.digits, k=26)) if s["capable"] else None,
                injected_errors=[])


ERROR_WEIGHTS = {"TOTAL_MISMATCH": 3, "LINE_SUM_MISMATCH": 2, "LINE_CALC_ERROR": 2, "MISSING_TIN": 3, "BAD_TIN_FORMAT": 2,
                 "BAD_TAX_CODE": 2, "FX_NO_RATE": 0, "OVERLENGTH_ID": 1, "FUTURE_DATE": 1}
ERROR_TO_RULE = {"TOTAL_MISMATCH": "V02", "LINE_SUM_MISMATCH": "V01", "LINE_CALC_ERROR": "V03", "MISSING_TIN": "V05",
                 "BAD_TIN_FORMAT": "V05", "BAD_TAX_CODE": "V06", "FX_NO_RATE": "V04", "OVERLENGTH_ID": "V10",
                 "FUTURE_DATE": "V09", "DUPLICATE": "V08"}


def inject(inv: dict, kind: str, rng, today: dt.date) -> bool:
    if kind == "FX_NO_RATE" and inv["currency"] == "MYR":
        return False
    if kind == "TOTAL_MISMATCH":
        inv["total"] = str(D(inv["total"]) + q2(rng.choice([-1, 1]) * rng.uniform(1, 80)))
    elif kind == "LINE_SUM_MISMATCH":
        inv["subtotal"] = str(D(inv["subtotal"]) + q2(rng.uniform(5, 200)))
        inv["total"] = str(D(inv["subtotal"]) + D(inv["tax_total"]))
    elif kind == "LINE_CALC_ERROR":
        ln = rng.choice(inv["lines"])
        ln["line_total"] = str(D(ln["line_total"]) + q2(rng.uniform(3, 60)))
        inv["subtotal"] = str(sum(D(x["line_total"]) for x in inv["lines"]))
        inv["total"] = str(D(inv["subtotal"]) + D(inv["tax_total"]))
    elif kind == "MISSING_TIN":
        inv["supplier_tin"] = ""
    elif kind == "BAD_TIN_FORMAT":
        inv["supplier_tin"] = rng.choice(["C9" + inv["supplier_tin"][2:6], "X" + inv["supplier_tin"][1:], inv["supplier_tin"] + "7"])
    elif kind == "BAD_TAX_CODE":
        rng.choice(inv["lines"])["tax_type"] = rng.choice(INVALID_TAX_CODES)
    elif kind == "FX_NO_RATE":
        inv["exchange_rate"] = None
    elif kind == "OVERLENGTH_ID":
        inv["supplier_id_type"] = "PASSPORT"
        inv["supplier_id_value"] = "".join(rng.choices(string.ascii_uppercase + string.digits, k=rng.randint(13, 16)))
    elif kind == "FUTURE_DATE":
        inv["issue_date"] = (today + dt.timedelta(days=rng.randint(5, 60))).isoformat()
    inv["injected_errors"].append(kind)
    return True


def total_myr(inv: dict) -> float | None:
    if inv["currency"] == "MYR":
        return float(inv["total"])
    return float(D(inv["total"]) * D(inv["exchange_rate"])) if inv["exchange_rate"] else None


def build_corpus(P: dict | None = None) -> list[dict]:
    P = P or load_params()
    rng, np_rng = random.Random(P["seed"]), np.random.default_rng(P["seed"])
    lo, hi = dt.date.fromisoformat(P["date_range"][0]), dt.date.fromisoformat(P["date_range"][1])
    today = dt.date.fromisoformat(P["today"])
    sups = make_suppliers(rng, P)
    n_dup = round(P["duplicate_share"] * P["n_invoices"])
    base = []
    for _ in range(P["n_invoices"] - n_dup):
        s = rng.choices(sups, [x["weight"] for x in sups])[0]
        base.append(make_invoice(rng, np_rng, s, lo, hi, P))
    base.sort(key=lambda x: x["issue_date"])
    seq: dict[str, int] = {}
    sm = {s["supplier_id"]: s for s in sups}
    for inv in base:  # chronological invoice numbers per supplier
        s = sm[inv["supplier_id"]]
        seq[s["supplier_id"]] = seq.get(s["supplier_id"], rng.randint(1, 400)) + rng.randint(1, 4)
        inv["invoice_number"] = s["fmt"].format(yy=inv["issue_date"][2:4], seq=seq[s["supplier_id"]], p=s["prefix"])
    # inject errors
    kinds, wts = [k for k, w in ERROR_WEIGHTS.items() if w], [w for w in ERROR_WEIGHTS.values() if w]
    n_err = round(P["error_rate"] * P["n_invoices"]) - n_dup
    fx_pool = [i for i, b in enumerate(base) if b["currency"] != "MYR"]
    fx_idx = rng.sample(fx_pool, min(7, len(fx_pool)))
    for i in fx_idx:
        inject(base[i], "FX_NO_RATE", rng, today)
    pool = [i for i in range(len(base)) if i not in set(fx_idx)]
    idxs = rng.sample(pool, n_err - len(fx_idx))
    for i in idxs:
        want = 1 if rng.random() < .85 else 2
        tries = 0
        while len(base[i]["injected_errors"]) < want and tries < 20:
            tries += 1
            k = rng.choices(kinds, wts)[0]
            arith = {"TOTAL_MISMATCH", "LINE_SUM_MISMATCH", "LINE_CALC_ERROR"}
            if k not in base[i]["injected_errors"] and not (k in arith and arith & set(base[i]["injected_errors"])):
                inject(base[i], k, rng, today)
    clean = [i for i in range(len(base)) if not base[i]["injected_errors"] and base[i]["issue_date"] < "2026-09-01"]
    dups = []
    for i in rng.sample(clean, n_dup):
        c = copy.deepcopy(base[i])
        c["issue_date"] = (dt.date.fromisoformat(c["issue_date"]) + dt.timedelta(days=rng.randint(3, 20))).isoformat()
        c["injected_errors"] = ["DUPLICATE"]
        c["quality"] = rng.choices(["digital", "scanned", "photo"], [.6, .28, .12])[0]
        dups.append(c)
    allinv = sorted(base + dups, key=lambda x: (x["issue_date"], x["supplier_id"]))
    dev = set(rng.sample(range(len(allinv)), P["dev_size"]))
    for i, inv in enumerate(allinv):
        inv["invoice_id"] = f"IG-{i+1:04d}"
        inv["split"] = "dev" if i in dev else "test"
        inv["total_myr"] = total_myr(inv)
        inv["high_value"] = bool(inv["total_myr"] is not None and inv["total_myr"] >= P["router"]["high_value_myr"])
        inv["n_lines"] = len(inv["lines"])
        inv["should_review"] = bool(inv["injected_errors"]) or inv["high_value"]
    return allinv


# ---------------------------------------------------------------- rendering
def money(x, cur, style):
    s = f"{D(x):,.2f}"
    sym = SYMBOL.get(cur, cur)
    return {"plain": s, "prefix": f"{sym} {s}", "suffix": f"{s} {cur}"}[style]


def render_pdf(inv: dict, sup: dict, path: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    lay, lab = LAYOUTS[inv["layout"]], sup["lab"]
    W, H = A4
    c = canvas.Canvas(str(path), pagesize=A4)
    fn, fb = lay["font"], lay["font"] + ("-Bold" if lay["font"] != "Times-Roman" else "-Bold")
    if fn == "Times-Roman":
        fb = "Times-Bold"
    cur = inv["currency"]
    d = dt.date.fromisoformat(inv["issue_date"]).strftime(lay["datefmt"])
    x0 = {"l": 40, "c": W / 2, "r": W - 40}[lay["align"]]

    def t(x, y, s, bold=False, size=9, right=False, center=False):
        c.setFont(fb if bold else fn, size)
        (c.drawRightString if right else c.drawCentredString if center else c.drawString)(x, y, s)

    def head(y):
        for i, s in enumerate([inv["supplier_name"], sup["address"]]):
            fnt = (lay["align"] == "r", lay["align"] == "c")
            t(x0, y, s, bold=i == 0, size=13 if i == 0 else 8, right=fnt[0], center=fnt[1])
            y -= 16 if i == 0 else 12
        if inv["supplier_tin"]:
            t(x0, y, f"{lab['tin']}: {inv['supplier_tin']}", right=lay["align"] == "r", center=lay["align"] == "c")
            y -= 12
        t(x0, y, f"{inv['supplier_id_type']} No: {inv['supplier_id_value']}", size=8, right=lay["align"] == "r", center=lay["align"] == "c")
        return y - 24

    y = head(H - 50)
    t(40, y, lab["title"], bold=True, size=14)
    t(W - 40, y, f"{lab['inv_no']}: {inv['invoice_number']}", right=True, bold=True)
    y -= 16
    t(W - 40, y, f"{lab['date']}: {d}", right=True)
    if lay["cur_line"]:
        y -= 12
        t(W - 40, y, f"Currency: {cur}", right=True)
    if inv["exchange_rate"]:
        y -= 12
        t(W - 40, y, f"Exchange Rate: 1 {cur} = {inv['exchange_rate']} MYR", right=True, size=8)
    t(40, y, f"{lab['bill']}: SYNTHETIC BUYER SDN BHD", size=9)
    y -= 12
    t(40, y, "TIN: C9999999999", size=8)
    if inv["uin"]:
        y -= 12
        t(40, y, f"e-Invoice UIN: {inv['uin']}", size=7)
    y -= 26
    cols = [(40, False), (62, False), (320, True), (395, True), (455, False), (W - 40, True)]
    heads = ["#", lab["desc"], lab["qty"], lab["price"], "Tax", lab["amt"]]

    def table_head(y):
        if lay["grid"]:
            c.rect(36, y - 4, W - 72, 15)
        for (x, r), h in zip(cols, heads):
            t(x, y, h, bold=True, size=8, right=r)
        return y - 18

    y = table_head(y)
    for i, ln in enumerate(inv["lines"], 1):
        if y < 150:
            c.setFont(fn, 6)
            c.drawString(40, 20, "SYNTHETIC - NOT A REAL INVOICE")
            c.showPage()
            y = table_head(H - 60)
        vals = [str(i), ln["description"][:44], ln["quantity"], f"{D(ln['unit_price']):,.2f}",
                f"{ln['tax_type']}/{ln['tax_rate']}%", f"{D(ln['line_total']):,.2f}"]
        for (x, r), v in zip(cols, vals):
            t(x, y, v, size=8, right=r)
        if lay["grid"]:
            c.line(36, y - 4, W - 36, y - 4)
        y -= 14
    y -= 8
    for lbl, val, bold in [(lab["sub"], inv["subtotal"], False), (lab["tax"], inv["tax_total"], False), (lab["total"], inv["total"], True)]:
        t(400, y, lbl, bold=bold)
        t(W - 40, y, money(val, cur, lay["money"]), bold=bold, right=True)
        y -= 14
    c.setFont(fn, 6)
    c.drawString(40, 20, "SYNTHETIC - NOT A REAL INVOICE")
    c.save()


def degrade(img, quality: str, rng: random.Random):
    import io

    from PIL import Image, ImageEnhance, ImageFilter
    img = img.convert("L")
    ang = rng.uniform(-1.5, 1.5) if quality == "scanned" else rng.uniform(-3.5, 3.5)
    img = img.rotate(ang, expand=True, fillcolor=255, resample=Image.BICUBIC)
    img = img.filter(ImageFilter.GaussianBlur(rng.uniform(.5, .9) if quality == "scanned" else rng.uniform(.9, 1.5)))
    img = ImageEnhance.Contrast(img).enhance(.85 if quality == "scanned" else .65)
    a = np.asarray(img, dtype=np.float32)
    a += np.random.default_rng(rng.randrange(10**6)).normal(0, 6 if quality == "scanned" else 13, a.shape)
    if quality == "photo":
        a *= np.linspace(1.0, .72, a.shape[1])[None, :]
    img = Image.fromarray(np.clip(a, 0, 255).astype("uint8"))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=55 if quality == "scanned" else 38)
    return Image.open(io.BytesIO(buf.getvalue())).convert("L")


def render_all(corpus: list[dict], out: Path, P: dict) -> None:
    import tempfile

    from PIL import Image
    sups = {s["supplier_id"]: s for s in make_suppliers(random.Random(P["seed"]), P)}
    (out / "pdf").mkdir(parents=True, exist_ok=True)
    (out / "images").mkdir(parents=True, exist_ok=True)
    for inv in corpus:
        pdf = out / "pdf" / f"{inv['invoice_id']}.pdf"
        render_pdf(inv, sups[inv["supplier_id"]], pdf)
        with tempfile.TemporaryDirectory() as td:
            r = run_text([find_tool("pdftoppm"), "-r", "110", "-png", str(pdf), f"{td}/p"])
            if r.returncode:
                raise RuntimeError(f"pdftoppm failed on {pdf.name}: {r.stderr.strip()[:200]}")
            pages = sorted(Path(td).glob("p*.png"))
            rng = random.Random(f"{P['seed']}-{inv['invoice_id']}")
            for k, p in enumerate(pages):
                with Image.open(p) as src:      # close the handle: Windows cannot delete an open file in the temp dir
                    im = src.copy()
                im = im if inv["quality"] == "digital" else degrade(im, inv["quality"], rng)
                im.save(out / "images" / f"{inv['invoice_id']}_p{k+1}.png")
                if k == 0:  # small committed thumbnail for the review UI when deployed
                    th = im.convert("L")
                    th = th.resize((520, int(th.height * 520 / th.width)))
                    (ROOT / "data" / "thumbs").mkdir(parents=True, exist_ok=True)
                    th.save(ROOT / "data" / "thumbs" / f"{inv['invoice_id']}_p1.jpg", quality=55)


def save_corpus(corpus: list[dict], out: Path) -> None:
    import pandas as pd
    out.mkdir(parents=True, exist_ok=True)
    (out / "invoices.json").write_text(json.dumps(corpus, indent=1, default=str), encoding="utf-8")
    flat = pd.DataFrame([{k: (",".join(v) if k == "injected_errors" else v) for k, v in i.items() if k != "lines"} for i in corpus])
    flat.to_csv(out / "invoices.csv", index=False)


def load_corpus(out: Path | None = None) -> list[dict]:
    out = out or ROOT / "data" / "synthetic"
    return json.loads((out / "invoices.json").read_text(encoding="utf-8"))
