# Shopify Store Cloner
#
#   make          → fa tutto: dipendenze, file credenziali, e lancia l'app
#   make clean    → rimuove venv e file temporanei

VENV   := .venv
PYTHON := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip
STAMP  := $(VENV)/.installed

.DEFAULT_GOAL := run

.PHONY: run clean

run: $(STAMP)
	@if [ ! -f shopify_secrets.json ]; then \
		cp shopify_secrets.example.json shopify_secrets.json; \
		echo ""; \
		echo "  Creato shopify_secrets.json — compilalo con le tue credenziali,"; \
		echo "  poi rilancia:  make"; \
		echo ""; \
	else \
		$(PYTHON) clone_all.py; \
	fi

# Dipendenze nel venv (reinstalla solo se requirements.txt cambia)
$(STAMP): requirements.txt
	@test -d $(VENV) || python3 -m venv $(VENV)
	@$(PIP) install --upgrade pip >/dev/null
	@$(PIP) install -q -r requirements.txt
	@touch $(STAMP)

clean:
	rm -rf $(VENV) __pycache__ *.pyc
