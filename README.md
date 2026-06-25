# Shopify Store Cloner

Clona il contenuto di uno store Shopify (**SOURCE**) su un dev store
(**TARGET**): prodotti, collezioni, pagine, blog, metafield e relative
definizioni. Il **tema** si copia a parte con la Shopify CLI.

## Uso

```bash
make
```

Al primo avvio crea `shopify_secrets.json`: **compilalo** con le tue
credenziali e rilancia `make`. Tutto qui — `make` installa le dipendenze
(in un venv), e lancia il menu interattivo.

```jsonc
// shopify_secrets.json (gitignored)
{
  "CLIENT_ID":     "...",
  "CLIENT_SECRET": "shpss_...",
  "SOURCE_STORE":  "store-originale.myshopify.com",
  "TARGET_STORE":  "dev-store.myshopify.com"
}
```

> In alternativa al file puoi usare le variabili d'ambiente
> `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`, `SHOPIFY_SOURCE_STORE`,
> `SHOPIFY_TARGET_STORE`.

Il menu permette di scegliere **cosa** clonare (tutto / solo metafield /
solo contenuti) e **come** autorizzare:

- **Automatico** (consigliato): apre il browser e cattura il codice OAuth da
  un server locale su `http://localhost:3000`. Se non parte, ripiega sul
  manuale.
- **Manuale**: incolli l'URL di callback dal browser.

Per i **prodotti** mostra un menu di selezione raggruppato per collezione
(+ "senza collezione"), così copi solo quelli che vuoi invece di tutti.

Prima di scrivere, se il TARGET **non** sembra un dev store, lo script
chiede una **conferma esplicita** (`CONFERMO`).

## Prerequisiti

- **Python 3** e **make** (le dipendenze le gestisce `make` in un venv).
- **Un'app** nel [Dev Dashboard](https://partners.shopify.com), installata
  su **entrambi** gli store, con tutti gli scope read/write necessari e il
  **Redirect URL** `http://localhost:3000/callback` registrato negli
  *Allowed redirection URLs*.

## Il tema

Non viene clonato dagli script. Dalla cartella del tema originale, con la
Shopify CLI (sostituisci `devstore`):

```bash
shopify theme push --store devstore.myshopify.com --unpublished --theme "Staging clone"
```

## File

| File | Descrizione |
|---|---|
| `clone_all.py` | Orchestratore interattivo (entry point di `make`). |
| `shopify_clone_manual.py` | Clona prodotti, collezioni, pagine, blog, metafield, redirect. |
| `clone_metafield_definitions.py` | Clona le definizioni dei metafield (GraphQL). |
| `config.py` | Carica le credenziali da env vars o `shopify_secrets.json`. |
| `Makefile` | `make` per fare tutto; `make clean` per ripulire. |

> ⚠️ Il vecchio `CLIENT_SECRET` era committato in git: rimuoverlo dai file
> non lo toglie dalla history. **Rigeneralo** dal Dev Dashboard.
