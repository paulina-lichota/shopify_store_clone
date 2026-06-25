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
- **Un'app Shopify** installata su **entrambi** gli store — vedi la sezione
  successiva se non l'hai ancora creata.

## Creare l'app Shopify (se non ce l'hai)

Lo script usa OAuth: ti serve un'app con `CLIENT_ID` e `CLIENT_SECRET`.
La si crea dalla **Shopify Dev Dashboard** — le custom app legacy nell'admin
sono deprecate e Shopify rimanda ora a questo ambiente.

1. Vai su **[https://dev.shopify.com/dashboard/](https://dev.shopify.com/dashboard/)**
   e accedi con il tuo account Shopify.
2. Clicca **Create app**, dai un nome (es. `shopify-cloner`).
3. In **Configuration → URLs** imposta:
   - **App URL**: `http://localhost:3000`
   - **Allowed redirection URLs**: `http://localhost:3000/callback`
4. In **Configuration → Admin API scopes** abilita tutti gli scope elencati
   sotto (read **e** write per ciascuno).
5. Salva. Vai in **API credentials** e copia **Client ID** (`CLIENT_ID`) e
   **Client secret** (`CLIENT_SECRET`).
6. Installa l'app su **entrambi** gli store (source e target): dal menu
   dell'app → **Install app** → seleziona lo store.

### Scope richiesti

```
products, content, metaobjects, metaobject_definitions,
online_store_pages, themes, files, inventory, translations,
locales, script_tags, shipping, customers, orders
```

## Clonare il tema

Il tema non viene clonato dagli script: va copiato a parte con la
**Shopify CLI**. La procedura completa è:

### 1. Installa la Shopify CLI (se non ce l'hai)

```bash
# macOS
brew tap shopify/shopify
brew install shopify-cli

# oppure con npm (multipiattaforma)
npm install -g @shopify/cli @shopify/theme
```

Verifica:

```bash
shopify version
```

### 2. Copia il tema con `make theme`

Usa il comando Make incluso nel progetto: scarica automaticamente il tema dallo
store sorgente in una cartella temporanea, lo carica sul dev store e poi pulisce.

```
$ make theme

  Origine:      store-originale.myshopify.com
  Destinazione: mio-devstore.myshopify.com

  Pubblicare subito come tema attivo? (s/n) [n]: n

  [1/2] Scegli il tema da copiare da store-originale.myshopify.com:

  # la CLI mostra la lista dei temi sorgente → selezioni con le frecce

  [2/2] Scegli il tema di destinazione su mio-devstore.myshopify.com
        (selezionane uno esistente oppure crea nuovo):

  # la CLI mostra la lista dei temi del dev store → selezioni o crei nuovo

  Tema copiato.
```

- **[1/2] Tema sorgente** — la Shopify CLI elenca tutti i temi dello store
  di origine (attivo, bozze, archiviati); selezioni con le frecce.
- **[2/2] Tema destinazione** — la CLI elenca i temi del dev store e offre
  anche l'opzione per creare un tema nuovo. Il flag `--theme "Nome"` non viene
  usato perché funziona solo su temi già esistenti e darebbe errore se il tema
  non c'è ancora.
- **Pubblicare subito** — `s` lo carica come tema attivo; `n` (default) lo
  carica come bozza non pubblicata.

La Shopify CLI aprirà il browser per autenticarti sullo store sorgente e poi su
quello di destinazione al primo utilizzo.

### 3. (Opzionale) Pubblica il tema in un secondo momento

Dall'admin del dev store: **Online Store → Themes → trova il tema →
Actions → Publish**.

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
