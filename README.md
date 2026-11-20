# Spese di Casa

App self-hosted per registrare le spese di famiglia dal telefono, in pochi
secondi. Si installa come app (PWA) da Chrome su Android e raccoglie dati
puliti, da esportare in CSV a fine mese.

Gira su un Umbrel di casa e si raggiunge solo attraverso Tailscale: non è mai
esposta su internet.

## Cosa fa

- Inserimento rapido: importo, esercente (con suggerimenti), categoria, Salva.
- Data, «pagato da», metodo di pagamento e nota hanno valori predefiniti
  (oggi, chi è collegato, carta) e si cambiano con un tocco.
- Lista dei movimenti per mese, con modifica ed eliminazione.
- Entrate (stipendi, rimborsi, regali, vendite), separate dalle spese: in
  *Movimenti* l'interruttore «Spese | Entrate» passa da una lista all'altra,
  e «Nuova entrata» le registra con importo, categoria da una lista fissa,
  data, chi l'ha ricevuta e nota.
- Riepilogo mensile: spese del mese, entrate e differenza (entrate meno
  spese), un piccolo istogramma degli ultimi 6 mesi con entrate e spese
  affiancate e la differenza sotto ogni mese, poi grafico a ciambella e totale
  per categoria. Toccando una categoria si vedono le spese che la compongono.
- Spese ricorrenti (abbonamenti, bollette): alla scadenza compaiono come «da
  registrare» e si confermano con un tocco, cambiando l'importo se serve.
  Nulla viene registrato in automatico.
- Gestione di categorie ed esercenti (rinomina, disattiva, unisci i doppioni).
- Export CSV per mese o intervallo, in due formati: un file per le spese e
  uno per le entrate.
- Backup e ripristino dell'intero database.
- Due utenti con password propria, stessi dati per entrambi.

Nessuna chiamata esterna: niente CDN, font o telemetria. Tutto è servito dal
container.

## Come è organizzato

Il progetto vive in due repository pubblici su GitHub:

| Repository | Contenuto |
|---|---|
| `febio25/home-expenses` (questo) | Codice, test, `Dockerfile`, workflow che pubblica l'immagine |
| `febio25/umbrel-app-store` | Community App Store per Umbrel: scheda dell'app e `docker-compose.yml` |

L'immagine Docker viene costruita da GitHub Actions per `amd64` e `arm64` e
pubblicata su GitHub Container Registry come
`ghcr.io/febio25/home-expenses:<versione>`. Umbrel non costruisce nulla:
scarica l'immagine indicata nello store, fissata con il suo digest.

| Identificativo | Valore |
|---|---|
| ID dello store | `tallynest` |
| ID dell'app su Umbrel | `tallynest-expenses` |
| Porta dell'app su Umbrel | `8395` |
| Porta HTTPS su Tailscale | `8443` |

> L'account GitHub è `febio25`. `tallynest` è solo il prefisso dello store
> e dell'app su Umbrel: i due nomi sono indipendenti.

## Installazione su Umbrel

### 1. Pubblica il codice e l'immagine (una volta sola)

Serve un account GitHub (gratuito) e la GitHub CLI sul Mac. Con Homebrew:
`brew install gh`. In alternativa puoi usare GitHub Desktop.

1. Crea l'account su <https://github.com/signup> (fatto: `febio25`, accesso con Google).
2. Collega la CLI all'account: `gh auth login` (scegli GitHub.com, HTTPS,
   accesso dal browser).
3. Dalla cartella `home-expenses` crea il repository e carica il codice:

   ```bash
   cd home-expenses
   git init -b main
   git add .
   git commit -m "Spese di Casa 0.3.1"
   gh repo create home-expenses --public --source=. --remote=origin --push
   ```

4. Pubblica la versione con un tag. Il tag deve coincidere con
   `__version__` in `app/__init__.py`, altrimenti il workflow si ferma:

   ```bash
   git tag v0.3.1
   git push origin v0.3.1
   ```

5. Su GitHub, scheda **Actions** del repository, apri l'esecuzione
   «Release image». Dura alcuni minuti (la build per `arm64` è emulata).
   Alla fine il riepilogo mostra la riga da copiare, simile a:

   ```yaml
       image: ghcr.io/febio25/home-expenses:0.3.1@sha256:4f3c…
   ```

6. Controlla che l'immagine sia pubblica: dal tuo profilo GitHub apri
   **Packages → home-expenses**. Se è indicata come privata: **Package
   settings → Change visibility → Public**. Umbrel non può scaricare
   immagini private. Verifica dal Mac, senza credenziali:

   ```bash
   docker logout ghcr.io
   docker pull ghcr.io/febio25/home-expenses:0.3.1
   ```

### 2. Pubblica lo store

1. Nella cartella `umbrel-app-store`, in
   `tallynest-expenses/docker-compose.yml`, sostituisci la riga `image:` con
   quella copiata al punto 5 (resta un segnaposto `REPLACE_WITH_DIGEST…`
   finché non lo fai, e l'installazione fallirebbe).
2. Crea il repository dello store:

   ```bash
   cd ../umbrel-app-store
   git init -b main
   git add .
   git commit -m "Tallynest App Store con Spese di Casa 0.3.1"
   gh repo create umbrel-app-store --public --source=. --remote=origin --push
   ```

La struttura è quella del template ufficiale
[getumbrel/umbrel-community-app-store](https://github.com/getumbrel/umbrel-community-app-store):
`umbrel-app-store.yml` alla radice e una cartella per app con
`umbrel-app.yml` e `docker-compose.yml`.

### 3. Aggiungi lo store e installa l'app

1. Su Umbrel apri l'**App Store** dal dock.
2. Menu **⋯** in alto a destra → **Community App Stores**.
3. Incolla `https://github.com/febio25/umbrel-app-store` e premi
   **Add**, poi **Open** accanto a «Tallynest».
4. Installa **Spese di Casa**.

Fonte: guida Umbrel «Adding a community app store»,
<https://umbrel.com/support/apps/how-to-add-a-community-app-store>.

### 4. Primo avvio

Apri l'app dal dashboard di Umbrel (`http://umbrel.local:8395`) e completa la
configurazione: nome e password per te e per Nastia (almeno 8 caratteri,
inserite due volte). Fallo subito dopo l'installazione: finché la
configurazione non è completata, chiunque raggiunga l'Umbrel può farla al
posto tuo.

**Login di Umbrel disattivato per questa app.** Il `docker-compose.yml` dello
store imposta `PROXY_AUTH_ADD: "false"`: così Nastia non deve conoscere la
password di Umbrel, e l'app installata sul telefono non si trova davanti la
schermata di accesso di Umbrel. L'accesso resta protetto dal login dell'app
(password con hash scrypt, blocco dopo 5 tentativi). È la stessa impostazione
che usa l'app ufficiale Vaultwarden; la guida ufficiale di packaging la
descrive in `getumbrel/umbrel-apps`, file
`.agents/skills/umbrel-package-app/SKILL.md`, sezione «app_proxy». In umbrelOS
2.0 esiste anche l'interruttore per singola app «Require Umbrel login»: se
nelle impostazioni dell'app risulta acceso, spegnilo.

**Cookie di sessione.** Su Umbrel l'app usa `SPESE_COOKIE_SECURE=auto`: il
cookie è `Secure` quando la richiesta arriva in HTTPS, e il login funziona
anche aprendo l'app in HTTP dal dashboard di Umbrel. Con `true` il login da
`http://umbrel.local:8395` fallirebbe senza spiegazioni.

## HTTPS con Tailscale

Chrome installa la PWA come app solo da un indirizzo HTTPS con un certificato
valido. Tailscale Serve lo fornisce dentro la tailnet: l'app resta
raggiungibile solo dai dispositivi collegati alla tua tailnet.

Prerequisito: l'app **Tailscale** installata sull'Umbrel e collegata al tuo
account.

### 1. Abilita MagicDNS e i certificati HTTPS

1. Apri la console di amministrazione di Tailscale,
   <https://login.tailscale.com/admin/dns>.
2. Abilita **MagicDNS** se non è già attivo.
3. In **HTTPS Certificates** scegli **Enable HTTPS** e conferma.

Nota sulla riservatezza: i certificati finiscono nei registri pubblici di
Certificate Transparency, con il nome della macchina e il nome della tailnet
(es. `umbrel.tail1234.ts.net`). L'accesso resta comunque limitato alla
tailnet. Se il nome della macchina contiene informazioni personali,
rinominala prima, dalla pagina **Machines** della console.

Fonte: Tailscale, «Enabling HTTPS»,
<https://tailscale.com/docs/how-to/set-up-https-certificates>.

### 2. Esponi l'app con `tailscale serve`

1. Su Umbrel: **Settings → Advanced settings → Terminal → App**, scegli
   **Tailscale**.
2. Scrivi:

   ```bash
   tailscale serve --bg --https=8443 http://127.0.0.1:8395
   ```

3. Controlla:

   ```bash
   tailscale serve status
   ```

   Deve mostrare un indirizzo come
   `https://umbrel.<tailnet>.ts.net:8443` che punta a
   `http://127.0.0.1:8395`.

Perché funziona e perché questi valori:

- L'app Tailscale di Umbrel usa la rete dell'host (`network_mode: host` nel
  suo `docker-compose.yml`). umbrelOS 2.0 apre la porta di ogni app anche su
  `127.0.0.1` proprio per questi casi, e solo in IPv4: per questo il comando
  usa `127.0.0.1` e non `localhost`, che potrebbe essere risolto in IPv6
  (`::1`), dove non risponde nessuno. Fonte: sorgenti di umbrelOS,
  `packages/umbreld/source/modules/lan-ingress/lan-ingress.ts` nel
  repository `getumbrel/umbrel`.
- Tailscale Serve segnala all'app che la richiesta è arrivata in HTTPS
  (`X-Forwarded-Proto: https`) e umbrelOS lo inoltra: il cookie di sessione
  sul telefono è quindi `Secure`.
- `--bg` salva la regola nella configurazione di Tailscale, che Umbrel tiene
  nella cartella dati dell'app Tailscale: la regola sopravvive ai riavvii.
- `8443` e non `443`: sull'indirizzo Tailscale dell'Umbrel la porta 443 serve
  il dashboard di Umbrel, e una regola su 443 la occuperebbe.
- La prima apertura può richiedere qualche secondo: Tailscale ottiene il
  certificato da Let's Encrypt.

Per togliere la regola: `tailscale serve --https=8443 off`. Per cancellarle
tutte: `tailscale serve reset`.

Fonte: Tailscale, «tailscale serve command»,
<https://tailscale.com/docs/reference/tailscale-cli/serve>.

### 3. Prova dal Mac

Con Tailscale attivo sul Mac apri `https://umbrel.<tailnet>.ts.net:8443`. Il
lucchetto di Chrome deve indicare una connessione sicura, senza avvisi.

## Installazione sui telefoni

Ripeti questi passi sul telefono di Fabio e su quello di Nastia.

### 1. Tailscale su Android

1. Installa **Tailscale** dal Play Store e accedi.
   - Sul telefono di Nastia puoi usare il tuo account Tailscale, oppure
     invitarla nella tua tailnet dalla pagina **Users** della console, così
     ha un accesso suo che puoi revocare.
2. Attiva la connessione nell'app Tailscale.

### 2. Tailscale come VPN sempre attiva

1. **Impostazioni → Rete e Internet → VPN**. Sui Samsung: **Impostazioni →
   Connessioni → Altre impostazioni di connessione → VPN**. Se non trovi la
   voce, cerca «VPN» nelle Impostazioni.
2. Tocca l'ingranaggio accanto a **Tailscale** e attiva **VPN sempre attiva**.
3. Lascia **spento** «Blocca connessioni senza VPN»: se Tailscale si
   disconnette, il telefono resterebbe senza internet.
4. Consiglio: in **Impostazioni → App → Tailscale → Batteria** scegli
   «Senza restrizioni», per evitare che Android sospenda la connessione.

Fonte: Guida di Android, «Connettersi a una rete privata virtuale (VPN)»,
<https://support.google.com/android/answer/9089766>. I nomi delle voci
variano da un produttore all'altro.

### 3. Installa l'app da Chrome

1. Apri Chrome e vai su `https://umbrel.<tailnet>.ts.net:8443`.
2. Accedi con il tuo nome e la tua password.
3. Menu **⋮** → **Installa app**. Se vedi invece **Aggiungi a schermata
   Home**, toccalo e poi scegli **Installa**.
4. Controlla:
   - l'icona «Spese» compare nel cassetto delle app;
   - aprendola parte a schermo intero, senza barra degli indirizzi, sulla
     schermata Nuova spesa;
   - la pressione lunga sull'icona mostra **Nuova spesa** e **Movimenti**.

L'accesso dura 90 giorni e si rinnova a ogni utilizzo.

Se Chrome offre solo «Aggiungi a schermata Home» senza «Installa», di solito
l'indirizzo non è HTTPS valido o il service worker non si è registrato:
ricarica la pagina una volta e riprova.

## Aggiornamento

### Su Umbrel

Esempio con la versione `0.5.0`.

1. Nel repository `home-expenses` la versione in `app/__init__.py`
   (`__version__`) deve essere quella nuova. Fai commit e push.
2. Crea e invia il tag:

   ```bash
   git tag v0.5.0 && git push origin v0.5.0
   ```

3. In **Actions** apri l'esecuzione «Release image» e, alla fine, copia la
   riga `image: …@sha256:…` dal riepilogo.
4. Nel repository `umbrel-app-store` sostituisci la riga con un comando
   (incollandola a mano con TextEdit si può perdere l'andata a capo). Incolla
   la riga copiata tra gli apici di `LINE`:

   ```bash
   cd umbrel-app-store
   LINE='image: ghcr.io/febio25/home-expenses:0.5.0@sha256:INCOLLA_QUI'
   sed -i '' "s|^    image: ghcr.io/febio25/home-expenses:.*|    ${LINE}|" tallynest-expenses/docker-compose.yml
   grep -n -A1 "image:" tallynest-expenses/docker-compose.yml
   ```

   L'ultimo comando deve mostrare la riga nuova seguita da
   `user: "1000:1000"` sulla riga successiva. (`sed -i ''` è la forma del
   Mac; su Linux si scrive `sed -i`.)
5. In `tallynest-expenses/umbrel-app.yml` aggiorna `version:` e
   `releaseNotes:`, poi commit e push.
6. Su Umbrel l'aggiornamento compare nell'App Store; installalo da lì.

Il database è in `${APP_DATA_DIR}/data` e non viene toccato. All'avvio l'app
applica da sola le eventuali modifiche allo schema. Le app installate sui
telefoni si aggiornano alla seconda apertura dopo l'aggiornamento del server.

Consiglio: scarica un backup dall'app prima di aggiornare.

### In locale

```bash
git pull
docker compose up -d --build
```

## Backup e ripristino

- **Backup:** *Impostazioni → Backup e ripristino → Scarica backup*. È un unico
  file SQLite (`spese-backup-AAAAMMGG-HHMM.db`) con tutti i dati (spese,
  entrate, ricorrenti, categorie, esercenti), compresi gli utenti e le loro
  password in forma protetta (hash). Conservalo in un posto sicuro. I backup
  delle versioni precedenti si ripristinano: le tabelle aggiunte dopo
  (ricorrenti, entrate) vengono create vuote.
- **Ripristino:** stessa schermata, *Ripristina da file…*. Sostituisce tutti i
  dati con quelli del file, utenti e password compresi. L'app controlla che il
  file sia un backup integro prima di toccare qualcosa e salva una copia dei
  dati sostituiti nella cartella dati (`pre-restore-*.db`, ultime 3).
- Dopo un ripristino valgono utenti e sessioni del backup: può essere
  necessario accedere di nuovo.
- **Backup di Umbrel:** se li attivi in umbrelOS, includono anche la cartella
  dati dell'app (`spese.db`). Il backup dall'app resta il modo più semplice
  per avere una copia da conservare altrove o da ripristinare su un'altra
  installazione.

Per una nuova installazione: completa il primo avvio con password provvisorie,
poi ripristina il backup.

### Passare dai test sul Mac a Umbrel

Scarica un backup dall'app sul Mac, installa l'app su Umbrel, completa il
primo avvio con password provvisorie e ripristina il backup. Utenti e
password diventano quelli dei test.

## Password dimenticata e blocco dei tentativi

- **Blocco:** dopo 5 password sbagliate in 5 minuti per lo stesso nome,
  l'accesso viene rifiutato con «Troppi tentativi sbagliati». Si sblocca da
  solo entro 5 minuti dal primo errore; anche un riavvio dell'app azzera
  subito il conteggio.
- **Una persona ha dimenticato la password:** l'altra la reimposta da
  *Impostazioni → Account → «… ha dimenticato la password»*, senza conoscere
  quella vecchia.
- **Nessuno riesce ad accedere su Umbrel:** **Settings → Advanced settings →
  Terminal → App**, scegli **Spese di Casa** e scrivi:

  ```bash
  python -m app.cli list-users
  python -m app.cli reset-password fabio
  ```

  Il comando chiede la nuova password due volte, senza mostrarla, e chiude
  tutte le sessioni di quell'utente. Il terminale dell'app si apre dentro il
  container principale dell'app (fonte: guida Umbrel «Using the built-in
  Terminal»).
- **Nessuno riesce ad accedere in locale:** nella cartella del progetto,

  ```bash
  docker compose exec spese python -m app.cli list-users
  docker compose exec spese python -m app.cli reset-password fabio
  ```

Sul telefono, il pulsante «Mostra» accanto al campo password permette di
controllare cosa si sta scrivendo (utile con la correzione automatica della
tastiera).

## Avvio in locale con docker-compose (test)

Serve Docker con il plugin Compose.

```bash
docker compose up -d --build
```

Poi apri <http://localhost:8080>. Per fermare: `docker compose down` (i dati
restano nel volume `spese-di-casa_spese-data`).

Il `docker-compose.yml` fissa il nome del progetto a `spese-di-casa`: se la
cartella prima si chiamava così, il volume con i dati dei test è lo stesso
anche ora che si chiama `home-expenses`.

### Con Portainer

*Stacks → Add stack → Web editor*: incolla il contenuto di
`docker-compose.yml`, togli le righe `build: .` e `image: spese-di-casa:local`
e togli il commento dalla riga `image: ghcr.io/febio25/home-expenses:…`.
Così Portainer usa l'immagine pubblicata e non deve costruire nulla.

In alternativa, *Stacks → Add stack → Repository* con l'URL di questo
repository e *Compose path* `docker-compose.yml`: Portainer costruisce
l'immagine dal `Dockerfile`.

### Prova dal telefono in rete locale

Sulla stessa rete Wi-Fi puoi aprire `http://<ip-del-computer>:8080` da Chrome
sul telefono per provare l'interfaccia. Senza HTTPS Chrome non propone
l'installazione come app e non attiva il service worker.

## Configurazione

Variabili d'ambiente del container. I valori predefiniti vanno bene nella
maggior parte dei casi.

| Variabile | Predefinito | Significato |
|---|---|---|
| `SPESE_DATA_DIR` | `/data` | Cartella del database (`spese.db`). Va montata su un volume. |
| `SPESE_COOKIE_SECURE` | `true` | `true`: cookie di sessione sempre `Secure` (dietro HTTPS). `auto`: `Secure` solo se la richiesta arriva in HTTPS (header `X-Forwarded-Proto` o schema della richiesta). `false`: mai (solo per test). Su Umbrel e in locale si usa `auto`. |
| `SPESE_SESSION_DAYS` | `90` | Durata della sessione, rinnovata a ogni utilizzo. |

Il container ascolta sulla porta `8080` e gira come utente `1000:1000`.

## Export CSV

Da *Impostazioni → Esporta CSV*, per mese o per intervallo di date.

Colonne: `data` (AAAA-MM-GG), `importo`, `categoria`, `esercente`, `nota`,
`pagato_da`, `metodo_pagamento` (Carta, Contanti, Altro), `inserito_da`,
`creato_il` (data e ora UTC in formato ISO 8601, es. `2026-11-13T16:30:43Z`).

| Formato | Separatore | Decimali | Codifica | Pensato per |
|---|---|---|---|---|
| Standard | virgola | punto (`12.50`) | UTF-8 | analisi con un assistente AI, script |
| Excel italiano | punto e virgola | virgola (`12,50`) | UTF-8 con BOM | doppio clic in Excel |

L'esercente è facoltativo: se manca, la colonna resta vuota.

### Entrate

Stessa schermata, scegliendo *Entrate*: un file a parte
(`entrate_<mese>.csv`, `entrate_<mese>_excel.csv`), negli stessi due formati.
Il CSV delle spese non cambia.

Colonne: `data` (AAAA-MM-GG), `importo`, `categoria` (Stipendio, Rimborsi,
Regali, Vendite, Altro), `nota`, `ricevuto_da`, `inserito_da`, `creato_il`
(UTC, ISO 8601).

La lista delle categorie di entrata è fissa (in `app/schemas.py`,
`INCOME_CATEGORIES`): per cambiarla serve una nuova versione dell'app.

## API

Il frontend usa solo l'API REST JSON sotto `/api/v1`. Lo schema OpenAPI è su
`/api/openapi.json` (importabile in Postman, Insomnia, Swagger Editor). La
pagina interattiva `/docs` di FastAPI è disattivata perché carica risorse da un
CDN.

- Autenticazione: `POST /api/v1/auth/login` imposta il cookie di sessione. Lo
  stesso token è accettato come `Authorization: Bearer <token>`, per una futura
  app nativa.
- Le richieste di scrittura autenticate con il cookie devono avere l'header
  `X-Requested-With` (protezione CSRF).
- Gli importi si inviano come testo (`"12,50"` o `"12.50"`) e tornano come
  interi in centesimi (`amount_cents`).
- `POST /api/v1/expenses` accetta un `client_uuid`: ripetere la richiesta con lo
  stesso valore non crea doppioni.
- `GET /api/v1/expenses` filtra per `month=AAAA-MM` (oppure `from` e `to`) e
  per `category_id`: per esempio `?month=2026-11&category_id=3` restituisce
  le spese che compongono quel totale del riepilogo.
- Spese ricorrenti: `GET/POST /api/v1/recurring`, `PATCH/DELETE
  /api/v1/recurring/{id}`, `POST /api/v1/recurring/{id}/register` (crea la spesa
  e sposta la scadenza) e `POST /api/v1/recurring/{id}/skip`. Entrambe chiedono
  `due_date` uguale alla scadenza attuale: se l'altra persona l'ha già
  registrata la risposta è 409, senza doppioni.
- Entrate: `GET/POST /api/v1/incomes` (filtri `month`, oppure `from` e `to`;
  `client_uuid` come per le spese), `GET/PATCH/DELETE /api/v1/incomes/{id}` e
  `GET /api/v1/incomes/categories` (la lista fissa: `salary`, `refund`,
  `gift`, `sale`, `other`, con i nomi in italiano). Export:
  `GET /api/v1/export/incomes.csv`, con gli stessi filtri e formati di
  `/export.csv`.
- Riepilogo: `GET /api/v1/summary?month=AAAA-MM` restituisce le spese
  (`total_cents`, `by_category`), le entrate (`income_cents`, `income_count`)
  e `balance_cents` (entrate meno spese). `GET /api/v1/summary/trend?month=AAAA-MM&months=6`
  restituisce i totali di entrate e spese di ogni mese della finestra (da 1 a
  24 mesi, il più vecchio per primo), anche quelli vuoti.

## Sviluppo

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt

# avvio senza Docker
SPESE_DATA_DIR=./data SPESE_COOKIE_SECURE=auto uvicorn app.main:app --reload --port 8080

# test
pytest
```

Le icone si rigenerano con `python scripts/make_icons.py`.

### Struttura

```
app/
  main.py          avvio, file statici, header di sicurezza
  config.py        variabili d'ambiente
  db.py            connessioni SQLite e migrazioni
  security.py      password (scrypt), sessioni, autenticazione
  money.py         conversione degli importi in centesimi
  dates.py         intervalli di date
  schemas.py       modelli JSON dell'API
  migrations/      schema del database (file SQL numerati)
  cli.py           strumenti di recupero (reimpostazione password)
  routers/         endpoint: auth, expenses, incomes, recurring, categories,
                   merchants, summary, export, backup
  static/          frontend (HTML, CSS, JavaScript, manifest, service worker)
tests/             test automatici (pytest)
scripts/           generazione delle icone
.github/workflows/ pubblicazione dell'immagine su GHCR (release.yml)
Dockerfile
docker-compose.yml test in locale e Portainer
```
