# Shopify Store Cloner

Clona il contenuto di uno store Shopify (**SOURCE**) su un dev store
(**TARGET**): prodotti (varianti, immagini, tag, metafield), collezioni custom e
smart, pagine, blog + articoli, metafield shop, redirect URL e definizioni dei
metafield. Il **tema** si copia a parte con la Shopify CLI.

## Uso rapido

```bash
make
```

Al primo avvio crea `shopify_secrets.json`: **compilalo** con le tue credenziali
e rilancia `make`. Il Makefile gestisce automaticamente il venv e le dipendenze.

```jsonc
// shopify_secrets.json (gitignored)
{
  "CLIENT_ID":     "il-tuo-client-id",
  "CLIENT_SECRET": "shpss_...",
  "SOURCE_STORE":  "store-originale.myshopify.com",
  "TARGET_STORE":  "dev-store.myshopify.com"
}
```

> In alternativa puoi usare variabili d'ambiente:
> `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`, `SHOPIFY_SOURCE_STORE`,
> `SHOPIFY_TARGET_STORE`.

## Menu interattivo

Il menu permette di scegliere **cosa** clonare:

| Scelta | Cosa fa |
|---|---|
| **1 — Tutto** (consigliato) | Definizioni metafield, poi prodotti e contenuti |
| **2 — Solo definizioni metafield** | Solo la struttura GraphQL dei metafield |
| **3 — Solo prodotti e contenuti** | Prodotti, collezioni, pagine, blog, redirect |

E **come** autorizzare:

- **Manuale** (affidabile ovunque): lo script genera un link, tu lo apri nel
  browser, autorizzi e incolli l'URL di callback.
- **Automatico**: apre il browser e cattura il codice OAuth tramite un server
  locale su `http://localhost:3000`. Richiede che browser e script girino sulla
  stessa macchina e che la porta 3000 sia libera; se non lo è, ricade sul
  manuale.

Per i **prodotti** viene mostrato un menu di selezione raggruppato per
collezione (+ "senza collezione"), così puoi copiare solo quelli che vuoi
invece di tutti.

### Salvaguardia store di produzione

Prima di scrivere, se il TARGET **non** sembra un dev store (piano
`partner_test`, `staff`, `trial`, `sandbox`, `dev`), lo script mostra un avviso
e chiede una conferma esplicita (`CONFERMO`). Nessuna modifica viene eseguita
senza questa conferma.

## Prerequisiti

- **Python 3** e **make** (le dipendenze le gestisce `make` in un venv).
- **Un'app** nel [Shopify Partners Dashboard](https://partners.shopify.com),
  installata su **entrambi** gli store, con:
  - Il **Redirect URL** `http://localhost:3000/callback` nelle *Allowed
    redirection URLs*.
  - Gli scope: `read/write_products`, `read/write_content`,
    `read/write_metaobjects`, `read/write_metaobject_definitions`,
    `read/write_online_store_pages`, `read/write_themes`, `read/write_files`,
    `read/write_inventory`, `read/write_translations`, `read/write_locales`,
    `read/write_script_tags`, `read/write_shipping`, `read/write_customers`,
    `read/write_orders`.

## Clonare il tema

Il tema non viene clonato dagli script. Dalla cartella del tema originale, con
la Shopify CLI:

```bash
shopify theme push --store devstore.myshopify.com --unpublished --theme "Staging clone"
```

## Cose da fare a mano dopo la clonazione

1. **Tema** — vedi sopra.
2. **Menu di navigazione** — i link di navigazione non sono clonati: ricreali
   manualmente in *Online Store → Navigation*.
3. **Verifica metafield** — controlla le definizioni in
   *Settings → Custom data* del dev store.

## Struttura del progetto

| File | Descrizione |
|---|---|
| `clone_all.py` | Orchestratore interattivo — entry point di `make`. |
| `shopify_clone_manual.py` | Clona prodotti, collezioni, pagine, blog, metafield, redirect. |
| `clone_metafield_definitions.py` | Clona le definizioni dei metafield via GraphQL. |
| `config.py` | Carica le credenziali da env vars o `shopify_secrets.json`. |
| `shopify_secrets.example.json` | Template del file credenziali. |
| `Makefile` | `make` per avviare; `make clean` per ripulire venv e cache. |
| `requirements.txt` | Dipendenze Python (`requests>=2.28`). |
