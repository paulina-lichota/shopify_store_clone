#!/usr/bin/env python3
"""
Shopify Store Cloner — Script Unico (Modalita' Manuale)
========================================================
Un unico script che:
  1. Ti genera i link di autorizzazione OAuth
  2. Tu li apri nel browser, autorizzi, e incolli il codice qui
  3. Lo script scambia il codice per un token permanente
  4. Clona tutto dallo store originale al dev store

Nessun server locale necessario. Niente SSL. Funziona sempre.

Cosa clona:
  - Prodotti (varianti, immagini, metafield, tag)
  - Collezioni custom (manuali) + prodotti associati
  - Collezioni smart (automatiche con regole)
  - Pagine
  - Blog + Articoli
  - Metafield a livello shop
  - Redirect URL

Prerequisiti:
  1. UN'UNICA APP nel Dev Dashboard
  2. App URL: http://localhost:3000 (o qualsiasi, non importa)
  3. Redirect URL: http://localhost:3000/callback
  4. Versione creata e rilasciata
  5. App installata su ENTRAMBI gli store
  6. pip install requests

Uso:
  1. Compila CLIENT_ID, CLIENT_SECRET, SOURCE_STORE, TARGET_STORE
  2. python shopify_clone.py
  3. Segui le istruzioni nel terminale
"""

import json
import sys
import time
import secrets
import requests
from urllib.parse import urlparse, parse_qs

# ═══════════════════════════════════════════════
# CONFIGURAZIONE
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
    "read_inventory", "write_inventory",
    "read_translations", "write_translations",
    "read_locales", "write_locales",
    "read_script_tags", "write_script_tags",
    "read_shipping", "write_shipping",
])

API_VERSION = "2025-01"
REDIRECT_URI = "http://localhost:3000/callback"

CLONE_PRODUCTS            = True
CLONE_CUSTOM_COLLECTIONS  = True
CLONE_SMART_COLLECTIONS   = True
CLONE_PAGES               = True
CLONE_BLOGS               = True
CLONE_REDIRECTS           = True
CLONE_SHOP_METAFIELDS     = True


# ═══════════════════════════════════════════════
# OAUTH MANUALE
# ═══════════════════════════════════════════════

def get_token_manual(store, label):
    """
    Flusso OAuth manuale:
    1. Genera URL di autorizzazione
    2. L'utente lo apre nel browser e autorizza
    3. Il browser va su localhost (che fallisce — ok!)
    4. L'utente copia l'URL dalla barra del browser
    5. Lo script estrae il codice e lo scambia per un token
    """
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
    print(f"\n  Dopo aver autorizzato, il browser dara' ERRORE (ERR_SSL o simile).")
    print(f"  E' NORMALE! Guarda la barra degli indirizzi del browser.")
    print(f"  L'URL conterra' qualcosa tipo:")
    print(f"  https://localhost:3000/callback?code=XXXXX&hmac=...&shop=...")
    print()

    # Chiedi all'utente: URL completo o solo il codice
    print("  Puoi incollare:")
    print("    - L'URL COMPLETO dalla barra del browser")
    print("    - Oppure SOLO il valore del parametro 'code'")
    print()

    user_input = input("  Incolla qui: ").strip()

    # Determina se e' un URL o solo il codice
    code = None
    if "code=" in user_input:
        # E' un URL, estrai il codice
        try:
            parsed = urlparse(user_input)
            params = parse_qs(parsed.query)
            code = params.get("code", [None])[0]

            # Verifica state se presente
            returned_state = params.get("state", [None])[0]
            if returned_state and returned_state != state:
                print("  ATTENZIONE: il parametro 'state' non corrisponde.")
                print("  Potrebbe essere un problema di sicurezza.")
                cont = input("  Continuare comunque? (s/n): ").strip().lower()
                if cont not in ("s", "si", "y", "yes"):
                    return None
        except Exception:
            # Proviamo a estrarre il codice con un metodo piu' grezzo
            for part in user_input.split("&"):
                if part.startswith("code=") or "code=" in part:
                    code = part.split("code=")[1].split("&")[0]
                    break
    else:
        # Assume sia solo il codice
        code = user_input

    if not code:
        print("  Errore: non riesco a trovare il codice nell'input.")
        return None

    print(f"  Codice trovato: {code[:10]}...")
    print(f"  Scambio il codice per un token permanente...")

    # Scambia codice per token
    url = f"https://{store}/admin/oauth/access_token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
    }

    try:
        resp = requests.post(url, data=payload)
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            print(f"  OK — Token permanente ottenuto per {store}")
            return token
        else:
            print(f"  ERRORE: {resp.status_code}")
            print(f"  {resp.text}")
            return None
    except Exception as e:
        print(f"  ERRORE: {e}")
        return None


# ═══════════════════════════════════════════════
# HTTP CLIENT
# ═══════════════════════════════════════════════

class ShopifyClient:
    def __init__(self, store, token):
        self.base = f"https://{store}/admin/api/{API_VERSION}"
        self.headers = {
            "X-Shopify-Access-Token": token,
            "Content-Type": "application/json",
        }

    def _handle_rate_limit(self, resp):
        limit_header = resp.headers.get("X-Shopify-Shop-Api-Call-Limit", "0/40")
        try:
            used, total = map(int, limit_header.split("/"))
            if used >= total - 2:
                time.sleep(2)
            elif used >= total - 5:
                time.sleep(0.5)
        except ValueError:
            pass

    def get(self, path, params=None):
        url = f"{self.base}/{path}"
        resp = requests.get(url, headers=self.headers, params=params)
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", 2))
            print(f"    Pausa rate limit ({retry_after}s)...")
            time.sleep(retry_after)
            return self.get(path, params)
        self._handle_rate_limit(resp)
        resp.raise_for_status()
        return resp.json()

    def get_all(self, path, resource_key, params=None):
        if params is None:
            params = {}
        params.setdefault("limit", 250)
        all_items = []
        url = f"{self.base}/{path}"

        while url:
            resp = requests.get(url, headers=self.headers, params=params)
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", 2))
                print(f"    Pausa rate limit ({retry_after}s)...")
                time.sleep(retry_after)
                continue
            self._handle_rate_limit(resp)
            resp.raise_for_status()

            data = resp.json()
            items = data.get(resource_key, [])
            all_items.extend(items)

            url = None
            params = {}
            link_header = resp.headers.get("Link", "")
            for part in link_header.split(","):
                if 'rel="next"' in part:
                    url = part.split("<")[1].split(">")[0]
                    break

        return all_items

    def post(self, path, data):
        url = f"{self.base}/{path}"
        resp = requests.post(url, headers=self.headers, json=data)
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", 2))
            print(f"    Pausa rate limit ({retry_after}s)...")
            time.sleep(retry_after)
            return self.post(path, data)
        self._handle_rate_limit(resp)
        if resp.status_code >= 400:
            print(f"    WARN POST {path}: HTTP {resp.status_code}")
            try:
                err_str = json.dumps(resp.json(), indent=2)
                if len(err_str) > 400:
                    err_str = err_str[:400] + "..."
                print(f"      {err_str}")
            except Exception:
                print(f"      {resp.text[:400]}")
            return None
        return resp.json()


# ═══════════════════════════════════════════════
# METAFIELDS
# ═══════════════════════════════════════════════

def clone_metafields(source, target, src_path, tgt_path):
    try:
        metafields = source.get_all(f"{src_path}/metafields.json", "metafields")
    except Exception:
        return 0

    count = 0
    for mf in metafields:
        ns = mf.get("namespace", "")
        if ns.startswith("shopify--") or ns.startswith("global"):
            continue
        result = target.post(f"{tgt_path}/metafields.json", {"metafield": {
            "namespace": mf["namespace"],
            "key": mf["key"],
            "value": mf["value"],
            "type": mf["type"],
        }})
        if result:
            count += 1
    return count


# ═══════════════════════════════════════════════
# CLONAZIONE
# ═══════════════════════════════════════════════

def clone_products(source, target, products=None):
    print("\n--- PRODOTTI ---")
    # Se `products` è passato (lista già filtrata) la si usa; altrimenti tutti.
    if products is None:
        products = source.get_all("products.json", "products")
    print(f"  Da copiare: {len(products)} prodotti")
    product_id_map = {}

    for i, product in enumerate(products, 1):
        print(f"  [{i}/{len(products)}] {product['title']}", end="", flush=True)

        new_product = {
            "title": product["title"],
            "body_html": product.get("body_html"),
            "vendor": product.get("vendor"),
            "product_type": product.get("product_type"),
            "handle": product.get("handle"),
            "tags": product.get("tags", ""),
            "status": product.get("status", "active"),
            "template_suffix": product.get("template_suffix"),
        }

        if product.get("variants"):
            new_product["variants"] = [{
                "title": v.get("title"),
                "price": v.get("price"),
                "compare_at_price": v.get("compare_at_price"),
                "sku": v.get("sku"),
                "barcode": v.get("barcode"),
                "weight": v.get("weight"),
                "weight_unit": v.get("weight_unit"),
                "inventory_management": v.get("inventory_management"),
                "inventory_policy": v.get("inventory_policy"),
                "requires_shipping": v.get("requires_shipping"),
                "taxable": v.get("taxable"),
                "option1": v.get("option1"),
                "option2": v.get("option2"),
                "option3": v.get("option3"),
            } for v in product["variants"]]

        if product.get("options"):
            new_product["options"] = [
                {"name": opt["name"], "values": opt.get("values", [])}
                for opt in product["options"]
            ]

        if product.get("images"):
            new_product["images"] = []
            for img in product["images"]:
                img_data = {"src": img["src"]}
                if img.get("alt"): img_data["alt"] = img["alt"]
                if img.get("position"): img_data["position"] = img["position"]
                new_product["images"].append(img_data)

        result = target.post("products.json", {"product": new_product})
        if result and "product" in result:
            new_id = result["product"]["id"]
            old_id = product["id"]
            product_id_map[old_id] = new_id

            mf = clone_metafields(source, target,
                f"products/{old_id}", f"products/{new_id}")
            vmf = 0
            if product.get("variants") and result["product"].get("variants"):
                for old_v, new_v in zip(product["variants"],
                                         result["product"]["variants"]):
                    vmf += clone_metafields(source, target,
                        f"products/{old_id}/variants/{old_v['id']}",
                        f"products/{new_id}/variants/{new_v['id']}")

            extra = ""
            if mf: extra += f" +{mf}mf"
            if vmf: extra += f" +{vmf}vmf"
            print(f" OK{extra}")
        else:
            print(" ERRORE")

    print(f"  Totale: {len(product_id_map)}/{len(products)}")
    return product_id_map


def clone_custom_collections(source, target, product_id_map):
    print("\n--- COLLEZIONI MANUALI ---")
    collections = source.get_all("custom_collections.json", "custom_collections")
    print(f"  Trovate {len(collections)}")

    for i, coll in enumerate(collections, 1):
        print(f"  [{i}/{len(collections)}] {coll['title']}", end="", flush=True)

        new_coll = {
            "title": coll["title"],
            "body_html": coll.get("body_html"),
            "handle": coll.get("handle"),
            "sort_order": coll.get("sort_order"),
            "template_suffix": coll.get("template_suffix"),
            "published": coll.get("published", True),
        }
        if coll.get("image"):
            new_coll["image"] = {"src": coll["image"]["src"]}
            if coll["image"].get("alt"):
                new_coll["image"]["alt"] = coll["image"]["alt"]

        result = target.post("custom_collections.json", {"custom_collection": new_coll})
        if result and "custom_collection" in result:
            new_cid = result["custom_collection"]["id"]
            old_cid = coll["id"]
            clone_metafields(source, target,
                f"collections/{old_cid}", f"collections/{new_cid}")

            collects = source.get_all("collects.json", "collects",
                params={"collection_id": old_cid})
            pc = 0
            for c in collects:
                npid = product_id_map.get(c["product_id"])
                if npid:
                    r = target.post("collects.json", {"collect": {
                        "product_id": npid, "collection_id": new_cid}})
                    if r: pc += 1
            print(f" OK ({pc} prodotti)")
        else:
            print(" ERRORE")


def clone_smart_collections(source, target):
    print("\n--- COLLEZIONI SMART ---")
    collections = source.get_all("smart_collections.json", "smart_collections")
    print(f"  Trovate {len(collections)}")

    for i, coll in enumerate(collections, 1):
        print(f"  [{i}/{len(collections)}] {coll['title']}", end="", flush=True)

        new_coll = {
            "title": coll["title"],
            "body_html": coll.get("body_html"),
            "handle": coll.get("handle"),
            "sort_order": coll.get("sort_order"),
            "template_suffix": coll.get("template_suffix"),
            "published": coll.get("published", True),
            "disjunctive": coll.get("disjunctive", False),
        }
        if coll.get("rules"):
            new_coll["rules"] = [
                {"column": r["column"], "relation": r["relation"],
                 "condition": r["condition"]}
                for r in coll["rules"]
            ]
        if coll.get("image"):
            new_coll["image"] = {"src": coll["image"]["src"]}

        result = target.post("smart_collections.json", {"smart_collection": new_coll})
        if result and "smart_collection" in result:
            clone_metafields(source, target,
                f"collections/{coll['id']}",
                f"collections/{result['smart_collection']['id']}")
            print(" OK")
        else:
            print(" ERRORE")


def clone_pages(source, target):
    print("\n--- PAGINE ---")
    pages = source.get_all("pages.json", "pages")
    print(f"  Trovate {len(pages)}")

    for i, page in enumerate(pages, 1):
        print(f"  [{i}/{len(pages)}] {page['title']}", end="", flush=True)
        new_page = {
            "title": page["title"],
            "body_html": page.get("body_html"),
            "handle": page.get("handle"),
            "author": page.get("author"),
            "template_suffix": page.get("template_suffix"),
            "published": page.get("published_at") is not None,
        }
        result = target.post("pages.json", {"page": new_page})
        if result and "page" in result:
            clone_metafields(source, target,
                f"pages/{page['id']}", f"pages/{result['page']['id']}")
            print(" OK")
        else:
            print(" ERRORE")


def clone_blogs(source, target):
    print("\n--- BLOG E ARTICOLI ---")
    blogs = source.get_all("blogs.json", "blogs")
    print(f"  Trovati {len(blogs)} blog")

    for blog in blogs:
        print(f"  Blog: {blog['title']}")
        result = target.post("blogs.json", {"blog": {
            "title": blog["title"],
            "handle": blog.get("handle"),
            "commentable": blog.get("commentable", "no"),
            "template_suffix": blog.get("template_suffix"),
        }})
        if not result or "blog" not in result:
            print("    Errore creazione blog")
            continue

        new_bid = result["blog"]["id"]
        old_bid = blog["id"]
        clone_metafields(source, target, f"blogs/{old_bid}", f"blogs/{new_bid}")

        articles = source.get_all(f"blogs/{old_bid}/articles.json", "articles")
        print(f"    {len(articles)} articoli")

        for j, art in enumerate(articles, 1):
            print(f"    [{j}/{len(articles)}] {art['title']}", end="", flush=True)
            new_art = {
                "title": art["title"],
                "body_html": art.get("body_html"),
                "author": art.get("author"),
                "handle": art.get("handle"),
                "tags": art.get("tags", ""),
                "summary_html": art.get("summary_html"),
                "template_suffix": art.get("template_suffix"),
                "published": art.get("published_at") is not None,
            }
            if art.get("image"):
                new_art["image"] = {"src": art["image"]["src"]}
                if art["image"].get("alt"):
                    new_art["image"]["alt"] = art["image"]["alt"]

            ar = target.post(f"blogs/{new_bid}/articles.json", {"article": new_art})
            if ar and "article" in ar:
                clone_metafields(source, target,
                    f"articles/{art['id']}", f"articles/{ar['article']['id']}")
                print(" OK")
            else:
                print(" ERRORE")


def clone_redirects(source, target):
    print("\n--- REDIRECT ---")
    redirects = source.get_all("redirects.json", "redirects")
    print(f"  Trovati {len(redirects)}")
    count = 0
    for r in redirects:
        result = target.post("redirects.json", {"redirect": {
            "path": r["path"], "target": r["target"]}})
        if result: count += 1
    print(f"  Totale: {count}/{len(redirects)}")


def clone_shop_metafields(source, target):
    print("\n--- METAFIELD SHOP ---")
    metafields = source.get_all("metafields.json", "metafields")
    metafields = [m for m in metafields
                  if not m.get("namespace", "").startswith("shopify--")]
    print(f"  Trovati {len(metafields)} (esclusi quelli di sistema)")
    count = 0
    for m in metafields:
        result = target.post("metafields.json", {"metafield": {
            "namespace": m["namespace"], "key": m["key"],
            "value": m["value"], "type": m["type"],
        }})
        if result: count += 1
    print(f"  Totale: {count}/{len(metafields)}")


# ═══════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  SHOPIFY STORE CLONER (Modalita' Manuale)")
    print("=" * 60)
    print(f"\n  Origine:      {SOURCE_STORE}")
    print(f"  Destinazione: {TARGET_STORE}")

    config.require(exit_fn=lambda: sys.exit(1))

    # ── OAUTH ──
    print("\n" + "=" * 60)
    print("  FASE 1: AUTORIZZAZIONE")
    print("=" * 60)

    print("\n  --- Store ORIGINALE ---")
    source_token = get_token_manual(SOURCE_STORE, "ORIGINE")
    if not source_token:
        print("  Impossibile ottenere il token. Esco.")
        sys.exit(1)

    print("\n  --- Dev Store ---")
    target_token = get_token_manual(TARGET_STORE, "DEV STORE")
    if not target_token:
        print("  Impossibile ottenere il token. Esco.")
        sys.exit(1)

    # ── VERIFICA ──
    print("\n" + "=" * 60)
    print("  FASE 2: VERIFICA")
    print("=" * 60)

    source = ShopifyClient(SOURCE_STORE, source_token)
    target = ShopifyClient(TARGET_STORE, target_token)

    try:
        src = source.get("shop.json")["shop"]
        tgt = target.get("shop.json")["shop"]
        print(f"\n  Origine: {src['name']}")
        print(f"  Target:  {tgt['name']}")
    except Exception as e:
        print(f"  Errore connessione: {e}")
        sys.exit(1)

    # ── CLONAZIONE ──
    print("\n" + "=" * 60)
    print("  FASE 3: CLONAZIONE")
    print("=" * 60)

    conferma = input("\n  Procedere con la clonazione? (s/n): ").strip().lower()
    if conferma not in ("s", "si", "y", "yes"):
        print("  Annullato.")
        sys.exit(0)

    start = time.time()
    pid_map = {}

    if CLONE_PRODUCTS:
        pid_map = clone_products(source, target)
    if CLONE_CUSTOM_COLLECTIONS:
        clone_custom_collections(source, target, pid_map)
    if CLONE_SMART_COLLECTIONS:
        clone_smart_collections(source, target)
    if CLONE_PAGES:
        clone_pages(source, target)
    if CLONE_BLOGS:
        clone_blogs(source, target)
    if CLONE_REDIRECTS:
        clone_redirects(source, target)
    if CLONE_SHOP_METAFIELDS:
        clone_shop_metafields(source, target)

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"  COMPLETATO in {int(elapsed // 60)}m {int(elapsed % 60)}s")
    print(f"{'=' * 60}")
    print("\n  Da fare a mano:")
    print("  1. Tema: scarica dall'originale, carica sul dev store")
    print("  2. Menu navigazione: ricreali a mano")
    print("  3. Controlla gli handle prodotti per Bubble")


if __name__ == "__main__":
    main()
