PY ?= python
export PYTHONPATH := src

.PHONY: setup doctor data baseline eval eda dashboard app test lint all pages

# setup installs into the ACTIVE interpreter: activate your virtual environment first.
setup:
	$(PY) -m pip install -r requirements.txt

# doctor checks Python packages plus Poppler and Tesseract, and says exactly what is missing.
doctor:
	$(PY) -m invoiceguard.cli doctor

data:
	$(PY) -m invoiceguard.cli generate

baseline:
	$(PY) -m invoiceguard.cli baseline

eval:
	$(PY) -m invoiceguard.cli evaluate

eda:
	$(PY) -m invoiceguard.cli eda

dashboard:
	$(PY) -m invoiceguard.cli dashboard

app:
	streamlit run app/streamlit_app.py

test:
	$(PY) -m pytest -q

lint:
	ruff check src tests app dashboard notebooks

all: doctor data baseline eval eda dashboard test

# Publish with GitHub Pages: Settings > Pages > Branch main, folder /docs
pages:
	$(PY) -m invoiceguard.cli pages
