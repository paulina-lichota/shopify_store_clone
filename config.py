#!/usr/bin/env python3
"""
Configurazione condivisa — credenziali FUORI dal codice.
=========================================================
Le credenziali NON sono hardcoded negli script. Vengono lette, in ordine
di priorità, da:

  1. Variabili d'ambiente:
       SHOPIFY_CLIENT_ID
       SHOPIFY_CLIENT_SECRET
       SHOPIFY_SOURCE_STORE
       SHOPIFY_TARGET_STORE

  2. Un file locale `shopify_secrets.json` (GITIGNORED) accanto a questo
     file, con la forma:
       {
         "CLIENT_ID": "...",
         "CLIENT_SECRET": "shpss_...",
         "SOURCE_STORE": "origine.myshopify.com",
         "TARGET_STORE": "dev-store.myshopify.com"
       }
     Vedi shopify_secrets.example.json.

Se mancano dei valori, gli script lo segnalano ed escono.
"""

import os
import json

SECRETS_FILE = os.path.join(os.path.dirname(__file__), "shopify_secrets.json")

# Mappa: nome interno → variabile d'ambiente
_KEYS = {
    "CLIENT_ID":     "SHOPIFY_CLIENT_ID",
    "CLIENT_SECRET": "SHOPIFY_CLIENT_SECRET",
    "SOURCE_STORE":  "SHOPIFY_SOURCE_STORE",
    "TARGET_STORE":  "SHOPIFY_TARGET_STORE",
}


def _load():
    file_data = {}
    if os.path.exists(SECRETS_FILE):
        try:
            with open(SECRETS_FILE) as f:
                file_data = json.load(f)
        except Exception as e:
            print(f"  Attenzione: impossibile leggere {SECRETS_FILE}: {e}")
    out = {}
    for name, env in _KEYS.items():
        out[name] = (os.environ.get(env) or file_data.get(name) or "").strip()
    return out


_cfg = _load()

CLIENT_ID     = _cfg["CLIENT_ID"]
CLIENT_SECRET = _cfg["CLIENT_SECRET"]
SOURCE_STORE  = _cfg["SOURCE_STORE"]
TARGET_STORE  = _cfg["TARGET_STORE"]

# Valori segnaposto del template: vanno trattati come "non impostati".
_PLACEHOLDERS = ("il-tuo", "xxxx", "store-originale.myshopify.com",
                 "dev-store.myshopify.com")


def _is_set(name):
    v = _cfg[name]
    return bool(v) and not any(p in v for p in _PLACEHOLDERS)


def missing():
    """Ritorna la lista dei nomi di config mancanti o ancora segnaposto."""
    return [name for name in _KEYS if not _is_set(name)]


def require(exit_fn=None):
    """Verifica che tutte le credenziali ci siano; altrimenti spiega come
    impostarle ed esce (o chiama exit_fn)."""
    miss = missing()
    if not miss:
        return
    print("\n  CREDENZIALI MANCANTI:", ", ".join(miss))
    print("\n  Impostale in uno di questi modi:")
    print("    a) variabili d'ambiente:")
    for name in miss:
        print(f"         export {_KEYS[name]}=...")
    print(f"    b) file {os.path.basename(SECRETS_FILE)} "
          f"(vedi shopify_secrets.example.json)")
    if exit_fn:
        exit_fn()
    else:
        raise SystemExit(1)
