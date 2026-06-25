# Shopify Store Cloner
#
#   make          → fa tutto: dipendenze, file credenziali, e lancia l'app
#   make theme    → guida interattiva per shopify theme push sul dev store
#   make clean    → rimuove venv e file temporanei

VENV   := .venv
PYTHON := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip
STAMP  := $(VENV)/.installed

.DEFAULT_GOAL := run

.PHONY: run theme clean

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

theme: $(STAMP)
	@SOURCE=$$($(PYTHON) -c "import config; print(config.SOURCE_STORE)" 2>/dev/null); \
	TARGET=$$($(PYTHON) -c "import config; print(config.TARGET_STORE)" 2>/dev/null); \
	if [ -z "$$SOURCE" ] || [ -z "$$TARGET" ]; then \
		echo ""; \
		echo "  SOURCE_STORE o TARGET_STORE non configurati. Compila shopify_secrets.json."; \
		echo ""; \
		exit 1; \
	fi; \
	echo ""; \
	echo "  Origine:      $$SOURCE"; \
	echo "  Destinazione: $$TARGET"; \
	echo ""; \
	printf "  Pubblicare subito come tema attivo? (s/n) [n]: "; read PUB; \
	TMPDIR=$$(mktemp -d); \
	echo ""; \
	echo "  [1/2] Scegli il tema da copiare da $$SOURCE:"; \
	echo ""; \
	shopify theme pull --store "$$SOURCE" --path "$$TMPDIR"; \
	if [ $$? -ne 0 ]; then rm -rf "$$TMPDIR"; echo "  Errore nel pull. Esco."; exit 1; fi; \
	echo ""; \
	echo "  [2/2] Scegli il tema di destinazione su $$TARGET"; \
	echo "        (selezionane uno esistente oppure crea nuovo):"; \
	echo ""; \
	if [ "$$PUB" = "s" ] || [ "$$PUB" = "si" ] || [ "$$PUB" = "y" ] || [ "$$PUB" = "yes" ]; then \
		shopify theme push --store "$$TARGET" --path "$$TMPDIR"; \
	else \
		shopify theme push --store "$$TARGET" --path "$$TMPDIR" --unpublished; \
	fi; \
	rm -rf "$$TMPDIR"; \
	echo ""; \
	echo "  Tema copiato."

clean:
	rm -rf $(VENV) __pycache__ *.pyc
