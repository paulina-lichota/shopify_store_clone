#!/usr/bin/env python3
"""
Shopify Store Cloner — Orchestratore
=====================================
Un unico script interattivo che richiama gli altri due in ordine corretto:

  1. clone_metafield_definitions.py  → definizioni dei metafield (struttura)
  2. shopify_clone_manual.py         → prodotti, collezioni, pagine, blog,
                                       metafield shop, redirect

Vantaggio rispetto a lanciarli separatamente: l'autorizzazione OAuth viene
fatta UNA SOLA VOLTA per store (2 autorizzazioni totali invece di 4). Il
token ottenuto usa l'unione degli scope di entrambi gli script, quindi va
bene per tutte le operazioni.

Configurazione: si prende automaticamente da shopify_clone_manual.py
(CLIENT_ID, CLIENT_SECRET, SOURCE_STORE, TARGET_STORE, flag CLONE_*).
Compila la configurazione LI', non serve duplicarla qui.

Uso:
  python clone_all.py
"""

import os
import sys
import time
import socket
import secrets
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import requests

import shopify_clone_manual as manual
import clone_metafield_definitions as mf

# ═══════════════════════════════════════════════
# COLORI (ANSI) — attivi solo su terminale e se NO_COLOR non è impostato
# ═══════════════════════════════════════════════

_USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _c(text, code):
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def bold(t):   return _c(t, "1")
def cyan(t):   return _c(t, "1;36")
def green(t):  return _c(t, "1;32")
def yellow(t): return _c(t, "1;33")
def red(t):    return _c(t, "1;31")


def banner(title, color=cyan):
    line = "=" * 60
    print(color(f"\n{line}\n  {title}\n{line}"))


# ═══════════════════════════════════════════════
# CONFIG — credenziali caricate da config.py (env vars o shopify_secrets.json)
# ═══════════════════════════════════════════════

import config

CLIENT_ID     = config.CLIENT_ID
CLIENT_SECRET = config.CLIENT_SECRET
SOURCE_STORE  = config.SOURCE_STORE
TARGET_STORE  = config.TARGET_STORE

# Unione degli scope dei due script: il token autorizzato con questi va bene
# sia per le definizioni metafield (GraphQL) sia per il clone dei contenuti.
UNION_SCOPES = ",".join([
    "read_products", "write_products",
    "read_content", "write_content",
    "read_metaobjects", "write_metaobjects",
    "read_metaobject_definitions", "write_metaobject_definitions",
    "read_online_store_pages", "write_online_store_pages",
    "read_themes", "write_themes",
    "read_files", "write_files",
    "read_inventory", "write_inventory",
    "read_translations", "write_translations",
    "read_locales", "write_locales",
    "read_script_tags", "write_script_tags",
    "read_shipping", "write_shipping",
    "read_customers", "write_customers",
    "read_orders", "write_orders",
])


# Server OAuth locale: solo porta 3000. Se è occupata si usa il manuale.
# Il Redirect URL dell'app deve essere esattamente http://localhost:3000/callback.
SERVER_PORT  = 3000
REDIRECT_URI = f"http://localhost:{SERVER_PORT}/callback"


# ═══════════════════════════════════════════════
# OAUTH AUTOMATICO (server locale + browser)
# ═══════════════════════════════════════════════

class _OAuthResult:
    def __init__(self):
        self.token = None
        self.error = None
        self.done = threading.Event()


class _OAuthHandler(BaseHTTPRequestHandler):
    """Cattura il callback OAuth su /callback e scambia il codice."""
    result = None
    expected_state = None

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self._respond(404, "Not found")
            return

        params = parse_qs(parsed.query)
        if params.get("state", [None])[0] != self.expected_state:
            self._respond(400, "Errore: state non valido (possibile CSRF)")
            self.result.error = "State mismatch"
            self.result.done.set()
            return

        code = params.get("code", [None])[0]
        shop = params.get("shop", [None])[0]
        if not code:
            self._respond(400, "Errore: nessun codice ricevuto")
            self.result.error = "No code"
            self.result.done.set()
            return

        token = self._exchange_code(shop, code)
        if token:
            self._respond(200,
                f"<h2>Autorizzazione completata per {shop}</h2>"
                "<p>Token ottenuto. Puoi chiudere questa finestra "
                "e tornare al terminale.</p>")
            self.result.token = token
        else:
            self._respond(500, "Errore nello scambio del codice")
            self.result.error = "Token exchange failed"
        self.result.done.set()

    def _exchange_code(self, shop, code):
        try:
            resp = requests.post(
                f"https://{shop}/admin/oauth/access_token",
                data={"client_id": CLIENT_ID,
                      "client_secret": CLIENT_SECRET,
                      "code": code},
            )
            if resp.status_code == 200:
                return resp.json().get("access_token")
            print(f"  Errore token exchange: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"  Errore: {e}")
        return None

    def _respond(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            f"<html><body style='font-family:sans-serif;padding:40px'>"
            f"{body}</body></html>".encode())

    def log_message(self, *args):
        pass  # silenzia i log HTTP


def get_token_server(store, label, redirect_uri):
    """Apre il browser e attende il callback sul server locale già avviato."""
    state = secrets.token_hex(16)
    auth_url = (
        f"https://{store}/admin/oauth/authorize?"
        f"client_id={CLIENT_ID}&scope={UNION_SCOPES}"
        f"&redirect_uri={redirect_uri}&state={state}"
    )

    result = _OAuthResult()
    _OAuthHandler.result = result
    _OAuthHandler.expected_state = state

    print(f"\n  [{label}] Apro il browser per autorizzare {store}...")
    print(f"  (Se non si apre, copia questo link a mano:)\n  {auth_url}")
    try:
        webbrowser.open(auth_url)
    except Exception:
        print("  Impossibile aprire il browser automaticamente.")

    print(f"  In attesa dell'autorizzazione (timeout 5 min)...")
    result.done.wait(timeout=300)
    if result.token:
        print(f"  OK — Token ottenuto per {store}")
        return result.token
    print(f"  ERRORE — {result.error or 'Timeout'}")
    return None


def check_config():
    config.require(exit_fn=lambda: sys.exit(1))


# Valori del campo `plan_name` (REST shop.json) tipici di store NON di
# produzione, su cui è sicuro scrivere.
DEV_PLAN_HINTS = (
    "partner_test",   # development store creato dai Partner
    "staff",          # staff / staff business
    "trial",          # trial
    "sandbox",        # sandbox
    "dev",            # development preview
)


def confirm_target_is_dev(target_token):
    """Controlla che il TARGET sia un dev store. Se non lo sembra, chiede una
    conferma esplicita prima di scrivere su uno store potenzialmente live.
    Ritorna True se si può procedere."""
    try:
        shop = manual.ShopifyClient(TARGET_STORE, target_token).get("shop.json")["shop"]
    except Exception as e:
        print(f"\n  Impossibile leggere le info del target ({e}).")
        risp = input("  Procedere comunque? (scrivi 'si' per continuare): ").strip().lower()
        return risp in ("s", "si", "y", "yes")

    plan = (shop.get("plan_name") or "").lower()
    display = (shop.get("plan_display_name") or "").lower()
    is_dev = any(h in plan for h in DEV_PLAN_HINTS) or \
        any(k in display for k in ("developer", "development", "trial", "partner", "staff"))

    print(f"\n  Target: {shop.get('name')}  —  piano: "
          f"{shop.get('plan_display_name') or plan or 'sconosciuto'}")

    if is_dev:
        return True

    print(red("\n  " + "!" * 56))
    print(red("  ATTENZIONE: il TARGET non sembra un development store."))
    print(red(f"  Dominio:  {TARGET_STORE}"))
    print(red(f"  Piano:    {shop.get('plan_display_name') or plan or 'sconosciuto'}"))
    print(red("  La clonazione SCRIVE dati (prodotti, collezioni, pagine...) su"))
    print(red("  questo store. Se è uno store di PRODUZIONE potresti alterarlo."))
    print(red("  " + "!" * 56))
    risp = input(
        "\n  Sei sicuro di voler scrivere su questo store? "
        "(scrivi 'CONFERMO' per procedere): "
    ).strip()
    return risp == "CONFERMO"


def _port_is_free(port):
    """Sonda dual-stack: prova a connettersi alla porta su IPv4 (127.0.0.1) e
    IPv6 (::1). Se una connessione riesce, qualcuno è in ascolto → occupata."""
    for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        try:
            with socket.socket(family, socket.SOCK_STREAM) as s:
                s.settimeout(0.2)
                if s.connect_ex((host, port)) == 0:
                    return False
        except OSError:
            pass  # famiglia non disponibile (es. niente IPv6): ignora
    return True


def authorize_both_stores(method):
    """OAuth una sola volta per store, con l'unione degli scope.
    method='auto' → server locale + browser; 'manual' → copia-incolla."""
    # Forza il flusso OAuth manuale a richiedere TUTTI gli scope necessari.
    manual.SCOPES = UNION_SCOPES

    banner("AUTORIZZAZIONE (una sola volta per store)")

    if method == "auto" and not _port_is_free(SERVER_PORT):
        print(f"\n  Porta {SERVER_PORT} occupata → passo alla modalità manuale.")
        method = "manual"

    if method == "auto":
        try:
            server = HTTPServer(("127.0.0.1", SERVER_PORT), _OAuthHandler)
        except OSError as e:
            print(f"\n  Impossibile usare la porta {SERVER_PORT} ({e}) "
                  "→ passo alla modalità manuale.")
        else:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            print(f"  Server locale avviato su {REDIRECT_URI}")
            try:
                source_token = get_token_server(SOURCE_STORE, "ORIGINE", REDIRECT_URI)
                target_token = get_token_server(TARGET_STORE, "DEV STORE", REDIRECT_URI)
            finally:
                server.shutdown()
                server.server_close()
            if not source_token or not target_token:
                print("  Autorizzazione automatica fallita. Esco.")
                sys.exit(1)
            return source_token, target_token

    # Manuale
    print(bold("\n  --- Store ORIGINALE ---"))
    source_token = manual.get_token_manual(SOURCE_STORE, "ORIGINE")
    if not source_token:
        print("  Impossibile ottenere il token per l'origine. Esco.")
        sys.exit(1)

    print(bold("\n  --- Dev Store ---"))
    target_token = manual.get_token_manual(TARGET_STORE, "DEV STORE")
    if not target_token:
        print("  Impossibile ottenere il token per il dev store. Esco.")
        sys.exit(1)

    return source_token, target_token


def run_metafield_definitions(source_token, target_token):
    banner("STEP 1/2 — DEFINIZIONI METAFIELD")

    source = mf.GraphQLClient(SOURCE_STORE, source_token)
    target = mf.GraphQLClient(TARGET_STORE, target_token)

    test = source.query("{ shop { name } }")
    if not test:
        print("  Errore: impossibile connettersi al source (GraphQL).")
        return
    print(f"  Source OK: {test['shop']['name']}")
    test = target.query("{ shop { name } }")
    if not test:
        print("  Errore: impossibile connettersi al target (GraphQL).")
        return
    print(f"  Target OK: {test['shop']['name']}")

    start = time.time()
    mf.clone_all_definitions(source, target)
    print(f"  Definizioni completate in {int(time.time() - start)}s")


def select_products(source):
    """Mostra un menu di selezione prodotti raggruppati per collezione
    (+ 'senza collezione') e ritorna la lista dei prodotti scelti. None se
    si annulla; lista vuota se selezione vuota."""
    print("\n  Carico collezioni e prodotti dello store sorgente...")
    custom = source.get_all("custom_collections.json", "custom_collections")
    smart = source.get_all("smart_collections.json", "smart_collections")
    all_products = source.get_all("products.json", "products")
    all_ids = {p["id"] for p in all_products}

    # Membership prodotti per ogni collezione (custom + smart).
    groups = []          # [(titolo, set_id_prodotti)]
    in_any = set()
    for coll in custom + smart:
        cid = coll["id"]
        prods = source.get_all("products.json", "products",
                               params={"collection_id": cid})
        ids = {p["id"] for p in prods}
        groups.append((coll["title"], ids))
        in_any |= ids
    no_coll = all_ids - in_any

    # Menu
    print(bold(f"\n  Da quali collezioni copiare i prodotti? "
               f"({len(all_products)} prodotti totali)"))
    print("    0) TUTTI i prodotti")
    for i, (title, ids) in enumerate(groups, 1):
        print(f"    {i}) {title} ({len(ids)})")
    print(f"    s) Senza collezione ({len(no_coll)})")
    raw = input("\n  Indici separati da virgola (Invio = tutti, q = salta): "
                ).strip().lower()

    if raw == "q":
        return None
    if not raw or raw == "0":
        print(f"  Selezionati tutti i {len(all_products)} prodotti.")
        return all_products

    selected = set()
    for tok in (t.strip() for t in raw.split(",")):
        if tok == "s":
            selected |= no_coll
        elif tok.isdigit() and 1 <= int(tok) <= len(groups):
            selected |= groups[int(tok) - 1][1]
        elif tok:
            print(f"  (ignoro '{tok}': non valido)")

    chosen = [p for p in all_products if p["id"] in selected]
    print(f"  Selezionati {len(chosen)} prodotti.")
    return chosen


def run_content(source_token, target_token):
    banner("STEP 2/2 — PRODOTTI E CONTENUTI")

    source = manual.ShopifyClient(SOURCE_STORE, source_token)
    target = manual.ShopifyClient(TARGET_STORE, target_token)

    try:
        src = source.get("shop.json")["shop"]
        tgt = target.get("shop.json")["shop"]
        print(f"  Origine: {src['name']}  →  Target: {tgt['name']}")
    except Exception as e:
        print(f"  Errore connessione: {e}")
        return

    start = time.time()
    pid_map = {}
    if manual.CLONE_PRODUCTS:
        selected = select_products(source)
        if selected is None:
            print("  Prodotti saltati.")
        elif not selected:
            print("  Nessun prodotto selezionato: salto.")
        else:
            pid_map = manual.clone_products(source, target, products=selected)
    if manual.CLONE_CUSTOM_COLLECTIONS:
        manual.clone_custom_collections(source, target, pid_map)
    if manual.CLONE_SMART_COLLECTIONS:
        manual.clone_smart_collections(source, target)
    if manual.CLONE_PAGES:
        manual.clone_pages(source, target)
    if manual.CLONE_BLOGS:
        manual.clone_blogs(source, target)
    if manual.CLONE_REDIRECTS:
        manual.clone_redirects(source, target)
    if manual.CLONE_SHOP_METAFIELDS:
        manual.clone_shop_metafields(source, target)

    elapsed = time.time() - start
    print(f"\n  Contenuti completati in {int(elapsed // 60)}m {int(elapsed % 60)}s")


def menu():
    banner("SHOPIFY STORE CLONER — ORCHESTRATORE")
    print(f"\n  Origine:      {green(SOURCE_STORE)}")
    print(f"  Destinazione: {yellow(TARGET_STORE)}")
    print(bold("\n  Cosa vuoi clonare?"))
    print("    1) Tutto: definizioni metafield, poi prodotti/contenuti  [consigliato]")
    print("    2) Solo le definizioni dei metafield")
    print("    3) Solo prodotti e contenuti")
    print("    q) Esci")

    choice = input("\n  Scelta [1]: ").strip().lower() or "1"
    if choice == "q":
        sys.exit(0)
    if choice not in ("1", "2", "3"):
        print("  Scelta non valida.")
        sys.exit(1)

    print(bold("\n  Come vuoi autorizzare gli store?"))
    print("    1) Manuale: apri il link, autorizza, incolla qui l'URL  [affidabile]")
    print("    2) Automatico: un server locale su :3000 cattura il codice da solo")
    print("       (solo se script e browser sono sulla STESSA macchina e la")
    print("        porta 3000 è libera; altrimenti si usa il manuale)")
    m = input("\n  Scelta [1]: ").strip() or "1"
    method = "auto" if m == "2" else "manual"
    return choice, method


def main():
    check_config()
    choice, method = menu()

    conferma = input("\n  Procedere con l'autorizzazione e la clonazione? (s/n): ").strip().lower()
    if conferma not in ("s", "si", "y", "yes"):
        print("  Annullato.")
        sys.exit(0)

    source_token, target_token = authorize_both_stores(method)

    # Salvaguardia: non scrivere su uno store di produzione senza conferma.
    if not confirm_target_is_dev(target_token):
        print("  Annullato: nessuna modifica effettuata sul target.")
        sys.exit(0)

    if choice in ("1", "2"):
        run_metafield_definitions(source_token, target_token)
    if choice in ("1", "3"):
        run_content(source_token, target_token)

    banner("FATTO", color=green)
    print(bold("\n  Da fare a mano:"))
    print("  1. Tema: shopify theme push --store <dev>.myshopify.com "
          "--unpublished --theme \"Staging clone\"")
    print("  2. Menu di navigazione: ricreali a mano")
    print("  3. Verifica le definizioni in Settings → Custom data del dev store")


if __name__ == "__main__":
    main()
