# 🧾 InvoiceGuard MY

AI-assisted invoice intake and **MyInvois pre-submission validation** for Malaysian SMEs. It reads messy supplier invoices (PDF / scan /
phone photo), proposes structured JSON, checks it against deterministic e-invoicing rules, and routes only risky invoices to a human.

> **Prototype on synthetic data. Not tax or legal advice.** Regulatory rules are tagged `[VERIFY]` and must be confirmed against LHDN
> guidelines and the MyInvois SDK before real use.

**Live dashboard:** _add your hosted link here_ · **Narrative:** [business problem](docs/business_problem.md) → current process → bottleneck →
AI opportunity → solution → prototype → ROI → [roadmap](docs/roadmap.md)

## Results (held-out test split, 250 synthetic invoices)

| System | Basis | Field acc. | Critical-field exact | STP | Wrong auto-approvals |
|---|---|---|---|---|---|
| A  OCR + regex | **measured** (Tesseract) | 78.4% | 55.2% | 73.6% | 101 |
| A+ OCR + regex + rules | **measured** | 78.4% | 55.2% | 39.2% | 15 |
| B  LLM only | *simulated stand-in* | 97.8% | 85.6% | 100% | 130 |
| C  InvoiceGuard (LLM + rules + router) | *simulated stand-in* | 97.8% | 85.6% | 33.2% (60.1% on error-free docs) | **1** |

* A and A+ are real measurements. **B and C use `SimLLMExtractor`, a noise model with assumed error rates, not a real model run.**
  Replace them with measured numbers via `python -m invoiceguard.cli evaluate --extractor claude --limit 50` (needs an API key).
* The corpus is error-rich on purpose (35% injected errors, 14% invoices ≥ RM10,000 that policy sends to humans), so headline STP is low.
* The baseline's collapse on scans/photos depends on the degradation severity chosen in `synth.degrade`: read direction, not magnitude.
* **The one wrong auto-approval (IG-0075)** is a scanned invoice whose total was misread by RM0.01. That sits inside the RM0.011 rule tolerance, so
  every rule passed. Tolerance is a trade-off, and a self-consistent misread is the residual risk of any rules-based gate.
* Rules are only as strong as the extraction behind them: OCR+regex returns no line items, so line-based rules (V01/V03/V06) never fire.

## Dashboard

`dashboard/dist/index.html` is one self-contained page: **Overview & EDA · Evaluation · Review queue · Invoice inspector · ROI simulator.**
The **Invoice inspector** shows, for each test invoice, the extracted JSON next to what the document prints. You can **edit the JSON** and the
validation rules re-run in your browser, flipping the decision. The browser rules are tested against the Python engine on every test invoice
(`tests/test_dashboard_js.py`). Charts load Chart.js from cdnjs, so they need internet.

## 1 · Setup

**Three things are needed: Python packages (pip), plus Poppler and Tesseract (not pip packages).** `make doctor` checks all three and tells you exactly what is missing.

### Windows (PowerShell)
```powershell
# 1. Python 3.11+ from python.org (tick "Add python.exe to PATH"), then in the project folder:
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
python -m pip install -r requirements.txt

# 2. External tools (one-time). Examples; check the exact package names with `winget search` / `scoop search`:
#    Tesseract: install the UB Mannheim Windows build (winget search tesseract). If it is not on PATH, set TESSERACT_CMD to the full path of tesseract.exe
#    Poppler:   scoop install poppler   (or: conda install -c conda-forge poppler; or unzip a release and set POPPLER_BIN to its bin folder)

# 3. Check, then run (open a NEW terminal after installing tools so PATH refreshes; keep the venv active)
python -m invoiceguard.cli doctor
make all                                  # or the equivalent commands below if you do not have make
```
Always run `make` / `python` **in the same terminal where the venv is active**, otherwise `python` is a different interpreter and you get
`ModuleNotFoundError: No module named 'yaml'`.

| `make` target | Equivalent (any OS, no make needed) |
|---|---|
| `make doctor` | `python -m invoiceguard.cli doctor` |
| `make all` | `python -m invoiceguard.cli all` then `python -m pytest -q` |
| `make pages` | `python -m invoiceguard.cli pages` |
| `make app` | `streamlit run app/streamlit_app.py` |

### macOS / Linux
```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
sudo apt-get install -y tesseract-ocr poppler-utils       # macOS: brew install tesseract poppler
make doctor && make all                                   # data -> OCR baseline -> evaluate -> EDA -> dashboard -> tests (~5 min)
make app                                                  # Streamlit app at http://localhost:8501
make pages                                                # build the dashboard and copy it to docs/index.html for GitHub Pages
```
In VS Code: open the folder, pick the `.venv` interpreter (Ctrl+Shift+P, "Python: Select Interpreter"), accept the recommended extensions.

**Reproducibility:** a fresh clone with a new virtualenv reproduces the committed `reports/*.csv` and `docs/index.html` byte for byte. If a future library release ever
changes something, install with `-c constraints-tested.txt`. The *measured* OCR baseline depends on the Tesseract and Poppler versions, so tiny differences on another
machine are possible; `doctor` prints your versions (verified here with Poppler 24.02 and Tesseract 5.3.4).

## 2 · Repo map

```
config/params.yaml      all assumptions (seed, mix, simulator, router, ROI)      config/rules.yaml  rule catalogue
src/invoiceguard/       synth · extract · validate · route · evaluate · roi · eda · cli
notebooks/01_eda.py     EDA as VS Code "# %%" cells (also runs as a script)
app/streamlit_app.py    EDA · evaluation · human review UI · ROI simulator · live extraction
dashboard/              build_static.py + template.html -> dist/index.html
tests/                  rule unit tests · oracle test · ROI/extractor/router tests · JS-vs-Python parity test
docs/                   business_problem.md · roadmap.md · evidence_log.csv
```

## 3 · Pipeline

`generate` (300 invoices, 8 layouts, EN/BM, noise, injected errors, fixed seed, 50 dev / 250 test) → `baseline` (pdftotext / Tesseract cache) →
`evaluate` (4 systems) → `eda` → `dashboard`. Tune only on **dev**; report only **test**. A clean rebuild reproduces identical results.

## 4 · Validation rules (`config/rules.yaml`)

V00 unreadable field · V01 Σlines = subtotal · V02 subtotal + tax = total · V03 qty × price = line · V04 currency / FX rate · V05 TIN present, well-formed,
known (lookup is a **mock** of the MyInvois TIN API) · V06 tax code list · V07 ≥ RM10,000 · V08 duplicate · V09 future date · V10 passport ID ≤ 12 · V11 no UIN.
Code lists in `codes.py` are an **illustrative subset**; replace them from the SDK.

## 5 · Tests

`make test`: 26 tests. The **oracle test** validates the ground truth and requires every injected error to fire exactly its expected rule with zero false
alarms. The **parity test** (needs Node and a built dashboard) checks the browser rules against Python on 500 invoice-system pairs.

## 6 · Real extractor

```bash
cp .env.example .env     # add ANTHROPIC_API_KEY; model name via INVOICEGUARD_MODEL (check the current model list)
python -m invoiceguard.cli evaluate --extractor claude --limit 50    # synthetic invoices only
```
Adds `C_invoiceguard_claude` (measured) to results and dashboards. Expect lower catch rates than the simulator.

## 7 · Hosting

* **Static dashboard:** `make pages`, push, then Settings ▸ Pages ▸ Branch `main`, folder `/docs`. Or drop `dashboard/dist/index.html` into Netlify Drop.
* **Streamlit:** Streamlit Community Cloud (main file `app/streamlit_app.py`) or Docker (`docker build -t invoiceguard . && docker run -p 8501:8501 invoiceguard`).

## 8 · Honest limits

Synthetic data only · simulator ≠ real model · TIN lookup mocked · code lists illustrative · ROI inputs are assumptions · regulatory facts (dates, RM10,000
rule, penalties, the reported 24 Oct 2026 validation change) are `[VERIFY]` items · no client results are claimed.
