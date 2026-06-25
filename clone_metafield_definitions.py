#!/usr/bin/env python3
"""
Shopify Metafield Definitions Cloner
=====================================
Companion dello script shopify_clone_manual.py

Copia le DEFINIZIONI dei metafield (non i valori) dallo store sorgente
al dev store. Usa GraphQL Admin API perche' le definizioni non sono
accessibili via REST.

Cosa copia:
  - Tutte le definizioni di metafield per: PRODUCT, PRODUCTVARIANT,
    COLLECTION, PAGE, BLOG, ARTICLE, CUSTOMER, ORDER, SHOP
  - Namespace, key, name, description, type, validations, pin,
    visibleToStorefrontApi

Cosa NON copia:
  - I valori (quelli li copia gia' il tuo script principale)
  - Le definizioni di sistema (namespace "shopify", "app--*", etc.)
  - I metaobject (sono un'altra cosa, se ti servono li aggiungiamo)

Prerequisiti:
  - Stessa app del tuo script principale (stessi CLIENT_ID / CLIENT_SECRET)
  - Scopes necessari: read_metaobject_definitions, write_metaobject_definitions
    (che hai gia' negli scopes del tuo script). Servono anche
    read_products, write_products (ci sono).
  - pip install requests

Uso:
  1. Compila SOURCE_STORE, TARGET_STORE, CLIENT_ID, CLIENT_SECRET
  2. python clone_metafield_definitions.py
  3. Autorizza su entrambi gli store (stesso flusso del tuo altro script)
"""

import sys
import time
import secrets
import json
import requests
from urllib.parse import urlparse, parse_qs

# ═══════════════════════════════════════════════
# CONFIGURAZIONE — IDENTICA AL TUO ALTRO SCRIPT
# ═══════════════════════════════════════════════

# Credenziali e store: caricati da config.py (env vars o shopify_secrets.json).
# NON inserire credenziali qui dentro.
import config
from config import CLIENT_ID, CLIENT_SECRET, SOURCE_STORE, TARGET_STORE

SCOPES = ",".join([
    "read_products", "write_products",
    "read_content", "write_content",
    "read_metaobjects", "write_metaobjects",
    "read_metaobject_definitions", "write_metaobject_definitions",
    "read_online_store_pages", "write_online_store_pages",
    "read_themes", "write_themes",
    "read_files", "write_files",
    "read_customers", "write_customers",
    "read_orders", "write_orders",
])

API_VERSION = "2025-01"
REDIRECT_URI = "http://localhost:3000/callback"

# Tipi di owner per cui cercare le definizioni
OWNER_TYPES = [
    "PRODUCT",
    "PRODUCTVARIANT",
    "COLLECTION",
    "PAGE",
    "BLOG",
    "ARTICLE",
    "CUSTOMER",
    "ORDER",
    "SHOP",
]


# ═══════════════════════════════════════════════
# OAUTH MANUALE (stesso flusso del tuo script)
# ═══════════════════════════════════════════════

def get_token_manual(store, label):
    state = secrets.token_hex(16)
    auth_url = (
        f"https://{store}/admin/oauth/authorize?"
        f"client_id={CLIENT_ID}"
        f"&scope={SCOPES}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state={state}"
    )

    print(f"\n  [{label}] Apri questo link nel browser:")
    print(f"\n  {auth_url}")
    print(f"\n  Il browser dara' errore su localhost. E' normale.")
    print(f"  Copia l'URL dalla barra degli indirizzi (o solo il parametro 'code').")
    print()

    user_input = input("  Incolla qui: ").strip()

    code = None
    if "code=" in user_input:
        try:
            parsed = urlparse(user_input)
            params = parse_qs(parsed.query)
            code = params.get("code", [None])[0]
        except Exception:
            for part in user_input.split("&"):
                if "code=" in part:
                    code = part.split("code=")[1].split("&")[0]
                    break
    else:
        code = user_input

    if not code:
        print("  Errore: codice non trovato.")
        return None

    url = f"https://{store}/admin/oauth/access_token"
    resp = requests.post(url, data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
    })
    if resp.status_code == 200:
        print(f"  OK — Token ottenuto per {store}")
        return resp.json().get("access_token")
    else:
        print(f"  ERRORE: {resp.status_code} — {resp.text}")
        return None


# ═══════════════════════════════════════════════
# GRAPHQL CLIENT
# ═══════════════════════════════════════════════

class GraphQLClient:
    def __init__(self, store, token):
        self.url = f"https://{store}/admin/api/{API_VERSION}/graphql.json"
        self.headers = {
            "X-Shopify-Access-Token": token,
            "Content-Type": "application/json",
        }

    def query(self, query_str, variables=None):
        payload = {"query": query_str}
        if variables:
            payload["variables"] = variables

        resp = requests.post(self.url, headers=self.headers, json=payload)

        if resp.status_code == 429:
            time.sleep(2)
            return self.query(query_str, variables)

        if resp.status_code >= 400:
            print(f"    HTTP {resp.status_code}: {resp.text[:300]}")
            return None

        data = resp.json()
        if "errors" in data:
            print(f"    GraphQL errors: {json.dumps(data['errors'], indent=2)[:400]}")
            return None

        # Rate limit cortese (cost-based)
        cost = data.get("extensions", {}).get("cost", {})
        if cost:
            avail = cost.get("throttleStatus", {}).get("currentlyAvailable", 1000)
            if avail < 100:
                time.sleep(1)

        return data.get("data")


# ═══════════════════════════════════════════════
# LOGICA
# ═══════════════════════════════════════════════

FETCH_QUERY = """
query GetDefinitions($ownerType: MetafieldOwnerType!, $after: String) {
  metafieldDefinitions(ownerType: $ownerType, first: 100, after: $after) {
    edges {
      cursor
      node {
        id
        name
        namespace
        key
        description
        type { name }
        ownerType
        pinnedPosition
        validations { name value type }
        access { storefront }
      }
    }
    pageInfo { hasNextPage }
  }
}
"""

CREATE_MUTATION = """
mutation CreateDefinition($definition: MetafieldDefinitionInput!) {
  metafieldDefinitionCreate(definition: $definition) {
    createdDefinition { id namespace key }
    userErrors { field message code }
  }
}
"""


def fetch_definitions(client, owner_type):
    """Scarica tutte le definizioni per un ownerType."""
    all_defs = []
    after = None
    while True:
        data = client.query(FETCH_QUERY, {"ownerType": owner_type, "after": after})
        if not data:
            break
        mdefs = data.get("metafieldDefinitions", {})
        edges = mdefs.get("edges", [])
        all_defs.extend([e["node"] for e in edges])
        if mdefs.get("pageInfo", {}).get("hasNextPage") and edges:
            after = edges[-1]["cursor"]
        else:
            break
    return all_defs


def is_system_definition(definition):
    """Filtra le definizioni di sistema / app che non vanno ricreate."""
    ns = definition.get("namespace", "")
    if ns.startswith("shopify"):
        return True
    if ns.startswith("app--"):
        return True
    return False


def create_definition(client, definition):
    """Ricrea una definizione sul target. Ritorna True se OK o gia' esistente."""
    input_def = {
        "name": definition["name"],
        "namespace": definition["namespace"],
        "key": definition["key"],
        "description": definition.get("description") or None,
        "type": definition["type"]["name"],
        "ownerType": definition["ownerType"],
    }

    # Validazioni (regex, min, max, choices, ecc.)
    validations = definition.get("validations") or []
    if validations:
        input_def["validations"] = [
            {"name": v["name"], "value": v["value"]}
            for v in validations if v.get("value") is not None
        ]

    # Pin (se era pinnato nell'admin del source)
    if definition.get("pinnedPosition") is not None:
        input_def["pin"] = True

    # Visibilita' storefront
    access = definition.get("access") or {}
    storefront_access = access.get("storefront")
    if storefront_access == "PUBLIC_READ":
        input_def["access"] = {"storefront": "PUBLIC_READ"}

    data = client.query(CREATE_MUTATION, {"definition": input_def})
    if not data:
        return False

    result = data.get("metafieldDefinitionCreate", {})
    errors = result.get("userErrors", [])

    if result.get("createdDefinition"):
        return True

    # Se e' gia' esistente, trattiamo come successo silenzioso
    for e in errors:
        if e.get("code") == "TAKEN":
            return True

    if errors:
        print(f"      userErrors: {json.dumps(errors, indent=2)[:400]}")
    return False


def clone_all_definitions(source, target):
    print("\n" + "=" * 60)
    print("  CLONAZIONE DEFINIZIONI METAFIELD")
    print("=" * 60)

    total_cloned = 0
    total_failed = 0
    total_skipped = 0

    for owner in OWNER_TYPES:
        print(f"\n--- {owner} ---")
        defs = fetch_definitions(source, owner)
        if not defs:
            print("  Nessuna definizione.")
            continue

        user_defs = [d for d in defs if not is_system_definition(d)]
        system_count = len(defs) - len(user_defs)
        print(f"  Trovate {len(defs)} ({system_count} di sistema → skip, "
              f"{len(user_defs)} da clonare)")

        for i, d in enumerate(user_defs, 1):
            label = f"{d['namespace']}.{d['key']} ({d['type']['name']})"
            print(f"  [{i}/{len(user_defs)}] {label}", end="", flush=True)
            ok = create_definition(target, d)
            if ok:
                print("  OK")
                total_cloned += 1
            else:
                print("  FALLITO")
                total_failed += 1

    print("\n" + "=" * 60)
    print(f"  RISULTATO: {total_cloned} clonate, {total_failed} fallite")
    print("=" * 60)


# ═══════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  CLONE METAFIELD DEFINITIONS")
    print("=" * 60)
    print(f"\n  Origine:      {SOURCE_STORE}")
    print(f"  Destinazione: {TARGET_STORE}")

    config.require(exit_fn=lambda: sys.exit(1))

    print("\n  --- Autenticazione Store ORIGINALE ---")
    source_token = get_token_manual(SOURCE_STORE, "ORIGINE")
    if not source_token:
        sys.exit(1)

    print("\n  --- Autenticazione Dev Store ---")
    target_token = get_token_manual(TARGET_STORE, "DEV STORE")
    if not target_token:
        sys.exit(1)

    source = GraphQLClient(SOURCE_STORE, source_token)
    target = GraphQLClient(TARGET_STORE, target_token)

    # Verifica connessione con query minima
    test = source.query("{ shop { name } }")
    if not test:
        print("  Errore: impossibile connettersi al source.")
        sys.exit(1)
    print(f"\n  Source OK: {test['shop']['name']}")

    test = target.query("{ shop { name } }")
    if not test:
        print("  Errore: impossibile connettersi al target.")
        sys.exit(1)
    print(f"  Target OK: {test['shop']['name']}")

    conferma = input("\n  Procedere con la clonazione delle definizioni? (s/n): ").strip().lower()
    if conferma not in ("s", "si", "y", "yes"):
        print("  Annullato.")
        sys.exit(0)

    start = time.time()
    clone_all_definitions(source, target)
    elapsed = time.time() - start
    print(f"\n  Tempo: {int(elapsed)}s")

    print("\n  PROSSIMI PASSI:")
    print("  1. Verifica in Settings → Custom data del dev store")
    print("  2. Se i VALORI dei metafield erano gia' stati copiati dallo")
    print("     script principale, ora il tema dovrebbe riconoscerli")
    print("     automaticamente (le definizioni fanno il 'match' sui")
    print("     namespace.key esistenti).")
    print("  3. Se qualche definizione e' fallita, controlla i userErrors")
    print("     sopra — di solito e' un type non supportato o validation.")


if __name__ == "__main__":
    main()
