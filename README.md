# Spese di Casa

App self-hosted per registrare le spese di famiglia dal telefono, in pochi
secondi. Si installa come app (PWA) da Chrome su Android e raccoglie dati
puliti, da esportare in CSV a fine mese.

Gira su un Umbrel di casa e si raggiunge solo attraverso Tailscale: non è mai
esposta su internet.

## Cosa fa

- Inserimento rapido: importo, esercente (con suggerimenti), categoria, Salva.
  I suggerimenti degli esercenti seguono l'uso degli ultimi 90 giorni (dalla
  0.14.0); l'ordine dei pulsanti delle categorie si cambia in *Impostazioni →
  Categorie → Cambia l'ordine*.
- Categorie a icone (dalla 0.15.0): quattro per riga, in Nuova spesa, Nuova
  entrata, nelle modifiche e nelle ricorrenti. Il nome della categoria
  scelta è scritto accanto a «Categoria» sopra le icone, compare per un
  secondo e mezzo in un fumetto sopra l'icona toccata (anche quando la
  sceglie un esercente noto) e nel pulsante: «Salva in Ristoranti e bar».
  L'esercente scelto resta primo nella riga dei suggerimenti, colorato come
  la categoria; toccandolo di nuovo si toglie. Le icone delle categorie di
  spesa si scelgono in *Impostazioni → Categorie* (58 icone); quelle delle
  entrate sono fisse.
- Avvio immediato (dalla 0.14.0): utenti, categorie ed esercenti restano
  salvati sul telefono, quindi la schermata di inserimento compare subito,
  anche con Tailscale lento o spento, e l'importo si può scrivere; per
  salvare serve comunque il server (senza rete compare l'errore di sempre e
  i dati restano nel modulo). Le liste si aggiornano da sole appena il
  server risponde.
- Possibili doppioni (dalla 0.14.0): se esiste già una spesa con lo stesso
  importo, lo stesso giorno e lo stesso esercente (senza esercente: la
  stessa categoria), inserita da chiunque, la spesa si salva comunque e
  l'avviso diventa arancione, «Salvata, ma sembra un doppione: Nastia ha già
  registrato la stessa spesa alle 18:02», con il solito «Annulla».
- Data, «pagato da», metodo di pagamento e nota hanno valori predefiniti
  (oggi, chi è collegato, carta) e si cambiano con un tocco.
- Spese con data futura (dalla 0.12.0): una domiciliazione o una spesa già
  nota si inserisce in anticipo, fino a 12 mesi da oggi (data in «Cambia»).
  Conta subito nel suo mese (Movimenti, Riepilogo, istogramma, CSV) e porta
  l'etichetta «Prevista» finché non arriva il giorno; per correggerla si apre
  la spesa come sempre. Valgono ancora «non dopo oggi» le entrate, le date di
  Vinted e la registrazione di una spesa ricorrente. Dalla 0.18.0 anche
  *Esplora* le conta, con la riga «di cui previste dopo oggi». Se per la stessa spesa esiste anche un modello ricorrente, alla
  scadenza si tocca «Salta» invece di «Registra», per non averla due volte.
- *Movimenti → Spese* dalla 0.18.0 si apre sul **calendario del mese**
  (lunedì–domenica): sotto ogni giorno il totale in euro interi, i giorni
  futuri in grigio con le spese previste, oggi sottolineato. Il giorno
  scelto (all'apertura oggi; in un altro mese l'ultimo giorno con spese) si
  apre sotto come scontrino; un giorno vuoto offre «Aggiungi una spesa in
  questo giorno». La **lente** accanto al totale mostra il mese intero come
  scontrino, con la ricerca e i filtri; Indietro torna al calendario, e
  riaprendo Movimenti si parte sempre dal calendario. Le entrate restano
  una lista (busta paga).
- Calendario dalla 0.18.1: numeri dei giorni più grandi e importi con «€»
  («127 €»; dalle migliaia «1,2k €», «12k €», dal milione «1,2M €»). Ogni
  giorno ha la sua casella, su una scala di quattro verdi: il più tenue per
  i giorni senza spese, poi tre verdi sempre più pieni per le spese più
  alte del mese (rispetto al giorno più caro fino a oggi). Il giorno scelto
  è verde pieno. Le righe si completano con i giorni del mese prima e dopo,
  in grigio tratteggiato: toccandone uno si passa a quel mese, su quel
  giorno.
- Lista dei movimenti per mese, con modifica ed eliminazione. Dalla 0.16.0
  il mese è uno scontrino: una striscia sola con il bordo strappato sopra e
  sotto, ogni giorno aperto dal suo nome in maiuscolo tra due tratteggi e
  chiuso dal suo «Subtotale» (sempre, anche con una sola spesa). Lo stesso
  scontrino si usa per le spese di una categoria e per i risultati della
  ricerca, divisi per mese. Dalla 0.18.1, nella lente e nei risultati della
  ricerca, un giorno o un mese con una sola spesa si chiude senza
  «Subtotale» e senza riga: l'importo sarebbe lo stesso. Il giorno scelto
  nel calendario tiene il suo «Subtotale», come uno scontrino.
- Ricerca nei movimenti (dalla 0.9.0): la barra sotto «Spese | Entrate» cerca
  in tutti i mesi, senza badare a maiuscole e accenti, in esercente, nota,
  categoria, importo («12,50») e titolo dell'articolo Vinted collegato (per
  le entrate: categoria, nota, importo e articolo). I risultati sono
  raggruppati per mese, con totale e numero; una spesa si apre come sempre e
  Indietro torna ai risultati. La × torna alla lista del mese. Dalla 0.14.0
  i risultati arrivano 100 alla volta («Mostra altre 100» in fondo), mentre
  i totali in cima e quelli di ogni mese contano sempre tutti i risultati.
  Dalla 0.18.0 la ricerca delle spese è nella lente, con i **filtri a
  pillole** sotto la barra: Categoria, Chi (ha pagato), Metodo, Periodo
  (questo mese, ultimi 3 mesi, quest'anno, anno scorso) ed Etichetta. Si
  sceglie dal basso; la pillola attiva diventa verde con il valore e la ×.
  I filtri si combinano tra loro e con il testo, funzionano anche senza
  testo e restano nell'indirizzo (Indietro li ritrova).
- **Etichette** (dalla 0.18.0): una parola che comincia con # nella nota di
  una spesa («Cena #vacanze-2026») la raggruppa con le altre spese dello
  stesso scopo, di qualsiasi categoria. Maiuscole e accenti non contano.
  Nelle liste le etichette sono pillole sotto la spesa: toccandone una si
  vedono tutte le spese con quell'etichetta e il loro totale. Scrivendo # nella
  nota l'app propone le etichette già usate. Nessun campo nuovo nel database:
  vivono nella nota, quindi anche nel CSV, e il testo dell'export le spiega.
- Entrate (stipendi, rimborsi, regali, vendite, buoni pasto), separate dalle
  spese: in *Movimenti* l'interruttore «Spese | Entrate» passa da una lista
  all'altra, e «Nuova entrata» le registra con importo, categoria da una
  lista fissa, data, chi l'ha ricevuta e nota. Dalla 0.16.0 le entrate del
  mese sono impaginate come una busta paga: in alto periodo, numero di
  entrate e ricorrenti ancora *attese* nel mese; poi la tabella Data |
  Voce | Importo, dalla più recente; in fondo il «Totale entrate» e la parte
  in buoni pasto. Le categorie sono nell'ordine Stipendio, Buoni pasto,
  Vinted, Rimborsi, Regali, Vendite, Altro.
- Riepilogo mensile, rivisto nella 0.18.0. In cima il **bilancio** del mese
  in un riquadro, come su un registro: Entrate (con «di cui buoni pasto»),
  Spese con il segno meno, «Differenza finora»; nel mese in corso poi le
  entrate ricorrenti ancora attese (lo stipendio di fine mese) e «A fine
  mese», con la doppia sottolineatura. Un mese passato finisce con la sua
  «Differenza». Toccando Entrate o Spese si apre la lista del mese in
  Movimenti. Sotto, l'**istogramma** di 6 mesi con entrate e spese
  affiancate e solo i nomi dei mesi: toccando un mese tutta la pagina passa
  a quel mese; le colonne restano ferme finché il mese mostrato è tra loro.
  Poi l'interruttore **Spese | Entrate** per ciambella e categorie: una
  categoria di spesa apre le sue spese; una categoria di entrata apre la
  busta paga del mese con le sue righe evidenziate (la × toglie l'evidenza).
  La vecchia schermata *Riepilogo → Entrate* non c'è più. Dalla 0.18.1 il
  numero dei movimenti è sulla stessa riga della voce, tra parentesi
  («Entrate (4)», «Spese (35)»), con le voci e il totale finale più grandi.
- *Esplora* (dalla 0.9.0), dal link sotto l'istogramma: i totali di un mese,
  di un anno, degli ultimi 6 mesi o di due date a scelta, con le frecce per
  andare avanti e indietro. Dalla 0.18.0 conta anche le spese previste dopo
  oggi e arriva ai mesi in cui ce ne sono. Solo totali (entrate, spese con i buoni pasto in
  evidenza, differenza) e le date di riferimento: niente movimenti né
  categorie. C'è anche per Vinted, con vendite, spese Vinted, differenza e
  guadagno sugli articoli venduti nel periodo.
- Buoni pasto: si registrano come entrata della categoria *Buoni pasto*
  (per esempio il totale caricato nel mese, anche come entrata ricorrente),
  mentre gli acquisti pagati con i buoni restano normali spese, per intero.
  Nel riepilogo la parte in buoni è indicata sotto le entrate e, nell'istogramma,
  in verde più chiaro in cima alla colonna delle entrate.
- Spese ed entrate ricorrenti (abbonamenti, bollette, stipendi): alla
  scadenza compaiono come «da registrare» e si confermano con un tocco,
  cambiando l'importo se serve. Nulla viene registrato in automatico.
  Si gestiscono da *Impostazioni → Ricorrenti*; il promemoria compare in
  Nuova spesa e, per le entrate, anche nella lista delle entrate.
  Frequenze: ogni mese, 2, 3, 4 (dalla 0.17.0) o 6 mesi, ogni anno.
- Dalla 0.17.0 in cima a *Ricorrenti* il riquadro **Quanto costano**: le
  spese ricorrenti attive (con il segno −) e le entrate ricorrenti attive
  (con il +) al mese e all'anno, in euro interi. Una spesa ogni 2 mesi conta
  metà al mese, una annuale un dodicesimo; le sospese non contano. Una
  ricorrente può avere l'**importo variabile** (bollette, stipendio con
  straordinari): l'importo salvato è una stima, scritta con «circa», e i
  totali che la contengono hanno «~». Alla scadenza l'importo si corregge
  come sempre. Le scadenze vicine sono scritte a parole: «domani», «tra 5
  giorni», «scaduta 3 giorni fa» (fino a due settimane, poi la data).
- Sezione *Vinted* (dalla 0.8.0), nella barra in basso: un articolo per ogni
  cosa messa in vendita, comprata per rivenderla o già di casa, con una foto
  facoltativa (miniatura nella lista, tocco per vederla grande). L'articolo
  non contiene importi: punta alla spesa d'acquisto (categoria *Vinted*) e
  all'entrata della vendita (categoria di entrata *Vinted*), che restano
  normali movimenti e finiscono nei rispettivi CSV. Il guadagno è vendita
  meno acquisto; per le cose già di casa, l'intera vendita. In *Vinted →
  Riepilogo*, rivisto nella 0.18.1 come il Riepilogo di casa: il bilancio
  del mese in un riquadro (Vendite e Spese Vinted con il numero tra
  parentesi, «di cui acquisti» e «di cui extra» quando ci sono entrambi,
  Differenza con la doppia sottolineatura; toccando Vendite si aprono gli
  articoli venduti), l'istogramma degli ultimi 6 mesi (toccando un mese
  tutta la pagina passa a quel mese) con il link a *Esplora*, dove c'è il
  guadagno sugli articoli venduti in un mese, un anno, 6 mesi o due date a
  scelta, e il conteggio dell'anno rispetto alle soglie DAC7 (indicativo). Gli acquisti personali fatti su
  Vinted restano spese della loro categoria (Abbigliamento, Casa e utenze…);
  i costi extra (buste, spedizioni) sono spese *Vinted* senza articolo.
- *Vinted*, dalla 0.10.0: un articolo nuovo resta **da pubblicare** finché
  non lo segni come pubblicato su Vinted («Segna come pubblicato», un tocco:
  oggi; la data si corregge dalla scheda). «In vendita da …» conta da quel
  giorno. In cima alla lista quattro filtri a icona con il numero: da
  pubblicare (clessidra, dalla 0.16.0), in vendita (negozio), venduti
  (moneta), tutti (pila, ritirati compresi). La ricerca guarda tutti gli
  articoli. Dalla 0.18.1 la barra di ricerca compare solo quando serve: la
  **lente** in alto, accanto al nome, la apre sotto «Articoli | Riepilogo»;
  la lente di nuovo, o la ×, la svuota e la chiude.
- **Ribasso a scalini** (dalla 0.19.0): se un articolo in vendita resta
  invenduto, l'app propone di abbassarne il prezzo un gradino alla volta,
  fino al minimo e mai sotto, arrotondato al mezzo euro per difetto. Non lo
  cambia mai da sola: il prezzo si cambia prima su Vinted, poi si conferma
  nell'app. Il **piano base** è −10% ogni 14 giorni, contati dalla
  pubblicazione e poi dall'ultimo cambio di prezzo; ogni articolo può avere
  un piano suo, proposto da Claude nella risposta (riga `RIBASSO`) o scritto
  a mano (una % o un importo, ogni quanti giorni), oppure «Niente ribasso».
  Nella scheda, sotto *Su Vinted*, la sezione **Ribasso** mostra il piano
  con «Cambia» e il prossimo gradino; quando tocca, un riquadro giallo
  propone «Ribassa a X €», «Salta N giorni» (rimanda di un giro) o «Altro
  prezzo». In cima alla lista Vinted la riga gialla «N articoli da
  ribassare · Vedi ›» apre solo quelli. Al minimo l'articolo resta un giro
  intero a quel prezzo; se è ancora invenduto chiede di decidere:
  «Rivaluta con Claude» (la richiesta riporta i prezzi già fatti e il
  piano), «Ritira dalla vendita» o «Lascia così» (nessun altro promemoria
  finché il prezzo non cambia). Senza minimo il ribasso non parte: la
  scheda chiede di impostarlo.
- Scheda dell'articolo (dalla 0.16.0): accanto alla foto, alti quanto lei,
  il titolo (fino a quattro righe, poi «…»; toccandolo si rinomina) e i
  prezzi (prezzo su Vinted e pagato; da venduto, prezzo di vendita e
  guadagno). La matita sulla foto apre «Cambia foto · Togli foto»; toccando
  la foto la si vede grande. Lo stato («In vendita da 4 giorni») è accanto
  al titolo *Su Vinted*.
- *Annunci con Claude* (0.10.0, rivisti nella 0.11.0): nella scheda
  dell'articolo tre passi (dettagli, «Condividi con Claude», «Incolla
  risposta»); la risposta incollata riempie titolo, descrizione, prezzo e
  minimo, poi l'annuncio pronto si copia su Vinted. L'app non chiama Claude
  né altri servizi: vedi [Annunci Vinted con
  Claude](#annunci-vinted-con-claude).
- *Impostazioni* si apre dall'icona a ingranaggio in alto a destra, accanto
  al nome, nelle schermate Nuova spesa, Movimenti, Riepilogo e Vinted.
- Gestione di categorie ed esercenti (rinomina, disattiva, unisci i doppioni).
  Dalla 0.15.0 ogni categoria ha un solo pulsante, «Modifica»: nome, icona
  e «Disattiva categoria» nella stessa finestra.
  Dalla 0.11.0 *Impostazioni → Esercenti* ha la ricerca (senza maiuscole e
  accenti) e i **possibili doppioni**: nomi uguali a meno di maiuscole,
  accenti, punteggiatura e sigle (srl, spa…), un nome dentro l'altro («Lidl»
  e «Lidl via Roma») o una lettera di differenza («Esselunga» ed
  «Eselunga»). Per ogni coppia «Unisci» (scegli il nome da tenere) oppure
  «Non sono doppioni», che vale per entrambi e non la ripropone più.
  La categoria *Vinted* serve alla sezione: si può rinominare ma non
  disattivare né eliminare.
- Export CSV per mese o intervallo, in due formati: un file per le spese e
  uno per le entrate; più un file con tutti gli articoli Vinted, e dalla
  0.15.0 *Tutto*. Ogni export si scarica o, dal telefono, si condivide con
  il testo che lo accompagna: vedi [Export CSV](#export-csv).
- Backup e ripristino dell'intero database, foto degli articoli comprese;
  dalla 0.14.0 anche copie automatiche sull'Umbrel (vedi [Backup e
  ripristino](#backup-e-ripristino)).
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
   - la pressione lunga sull'icona mostra **Nuova spesa**, **Movimenti** e
     **Vinted**.

L'accesso dura 90 giorni e si rinnova a ogni utilizzo.

Se Chrome offre solo «Aggiungi a schermata Home» senza «Installa», di solito
l'indirizzo non è HTTPS valido o il service worker non si è registrato:
ricarica la pagina una volta e riprova.

## Aggiornamento

### Su Umbrel

Esempio con la versione `0.9.0`.

1. Nel repository `home-expenses` la versione in `app/__init__.py`
   (`__version__`) deve essere quella nuova. Fai commit e push.
2. Crea e invia il tag:

   ```bash
   git tag v0.9.0 && git push origin v0.9.0
   ```

3. Quando in **Actions** l'esecuzione «Release image» è finita in verde
   (2–3 minuti), leggi il digest dell'immagine dal registro:

   ```bash
   TOKEN=$(curl -s "https://ghcr.io/token?scope=repository:febio25/home-expenses:pull" | sed -E 's/.*"token":"([^"]+)".*/\1/')
   DIGEST=$(curl -sI -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json" https://ghcr.io/v2/febio25/home-expenses/manifests/0.9.0 | grep -i docker-content-digest | awk '{print $2}' | tr -d '\r')
   echo "$DIGEST"
   ```

   Deve comparire `sha256:` seguito da 64 caratteri: è il digest dell'indice
   multi-arch, quello che serve a Umbrel. Se non compare nulla, l'immagine
   non è pubblicata. Non usare il digest dei file tra gli «Artifacts» del
   workflow: è un file di build, non l'immagine.
4. Nella stessa finestra del Terminale, nel repository `umbrel-app-store`
   sostituisci la riga con un comando (incollandola a mano con TextEdit si
   può perdere l'andata a capo):

   ```bash
   cd umbrel-app-store
   LINE="image: ghcr.io/febio25/home-expenses:0.9.0@${DIGEST}"
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
Le novità del manifest (per esempio la scorciatoia **Vinted** della 0.8.0)
arrivano quando Chrome aggiorna l'app installata. Da Chrome 144 non c'è più
il limite di un controllo al giorno (fonte: Chrome for Developers, «A better
way to update your web apps»); con versioni precedenti può volerci fino a un
giorno. Se dopo qualche apertura la scorciatoia non compare: chiudi l'app,
apri `about://webapks` in Chrome, tocca **Update** sotto l'app, poi aprila e
chiudila una volta; di solito in pochi minuti lo stato diventa «Successful»
(fonte: web.dev, «How Chrome handles updates to the web app manifest»).

Dalla 0.7.0 alla 0.8.0, al primo avvio: se esiste già una categoria di spesa
chiamata «Vinted» (fatta a mano, maiuscole e minuscole non contano) diventa
la categoria della sezione, con le sue spese, e viene riattivata se era
disattivata; altrimenti viene creata. Le spese già registrate lì restano
come sono e si collegano agli articoli da *Nuovo articolo → Scegli una spesa
già registrata*; le vendite già registrate in *Vendite* si collegano da
*Segna come venduto → Scegli un'entrata già registrata* e passano alla
categoria di entrata *Vinted*.

Dalla 0.9.0 alla 0.10.0, al primo avvio: gli articoli già inseriti restano
*In vendita*, con la data di messa in vendita che avevano (quella
dell'acquisto, o il giorno in cui erano stati aggiunti); se un articolo non
era ancora su Vinted, dalla sua scheda *Su Vinted → Modifica → Non ancora
pubblicato*, oppure correggi la data. Foto, acquisti e vendite non cambiano.
Gli articoli nuovi partono *Da pubblicare*.

Dalla 0.18.1 alla 0.19.0, al primo avvio, il database passa dallo schema 10
all'11 (prima l'app ne salva una copia, *Prima di un aggiornamento*): gli
articoli Vinted ricevono i campi del ribasso, vuoti per tutti, cioè con il
piano base. Gli articoli in vendita da più di 14 giorni allo stesso prezzo
e sopra il minimo compaiono subito tra quelli da ribassare. La 0.18.1
funziona anche sul database della 0.19.0 (verificato: i campi vengono
ignorati); un backup della 0.19.0 però non si ripristina sulla 0.18.1.

Dalla 0.18.0 alla 0.18.1 il database non cambia (schema 10, invariato):
cambiano solo l'aspetto di calendario, scontrini, Riepilogo e Vinted.
Tornare alla 0.18.0 resta possibile, anche con un backup fatto dalla 0.18.1.

Dalla 0.17.0 alla 0.18.0 il database non cambia (schema 10, invariato):
cambiano Movimenti (calendario, lente, filtri, etichette), Riepilogo ed
Esplora. Tornare alla 0.17.0 resta possibile, anche con un backup fatto
dalla 0.18.0; le etichette restano nelle note come testo.

Dalla 0.16.0 alla 0.17.0, al primo avvio, il database passa dallo schema 9
al 10 (prima l'app ne salva una copia, *Prima di un aggiornamento*): spese
ed entrate ricorrenti ricevono il campo «Importo variabile», spento per
tutte. Per segnare una bolletta o uno stipendio variabile: *Ricorrenti →*
la voce *→ Importo variabile*. La 0.16.0 funziona anche sul database della
0.17.0 (verificato: il campo viene ignorato); un backup della 0.17.0 però
non si ripristina sulla 0.16.0.

Dalla 0.15.0 alla 0.16.0 il database non cambia (schema 9, invariato):
cambia solo la grafica, più l'ordine e due icone delle categorie di entrata
(Vinted con l'etichetta, Vendite con banconota e moneta). Tornare alla
0.15.0 resta possibile, anche con un backup fatto dalla 0.16.0.

Dalla 0.14.0 alla 0.15.0, al primo avvio, il database passa dallo schema 8
al 9 (prima l'app ne salva una copia, *Prima di un aggiornamento*): ogni
categoria di spesa riceve il campo dell'icona. Le dieci categorie iniziali
e *Vinted* hanno subito la loro icona, riconosciute dal nome originale; una
categoria rinominata o creata a mano mostra l'icona generica (quattro forme)
finché non se ne sceglie una in *Impostazioni → Categorie → Modifica*. Un
backup della 0.15.0 non si ripristina sulla 0.14.0; un backup vecchio si
ripristina sulla 0.15.0 e riceve le icone nello stesso modo. Per tornare
alla 0.14.0 serve la copia *Prima di un aggiornamento* o un backup fatto
prima.

Dalla 0.13.0 alla 0.14.0 il database non cambia (schema invariato): tornare
alla 0.13.0 resta possibile. Al primo avvio le copie lasciate dai ripristini
(`pre-restore-*.db`) passano nella cartella `snapshots` della cartella dati,
dove da ora finiscono anche le copie automatiche. La prima copia del giorno
si fa all'avvio (o entro un'ora, su un'installazione nuova appena configurata).
Dalla 0.14.0, prima di applicare un aggiornamento che cambia il database,
l'app ne salva una copia (*Prima di un aggiornamento*).

Dalla 0.12.0 alla 0.13.0 il database non cambia (solo l'interfaccia della
scheda Vinted). Dalla 0.11.0 alla 0.12.0 il database non cambia (schema invariato): cambiano
solo le regole sulla data delle spese. Un backup della 0.12.0 si ripristina
anche sulla 0.11.0, ma le spese con data futura resterebbero lì, senza
etichetta e senza raggiungerle dai mesi successivi.

Dalla 0.10.0 alla 0.11.0, al primo avvio il database aggiunge solo la
tabella delle coppie di esercenti segnate come «Non sono doppioni» (vuota):
articoli, annunci ed esercenti non cambiano. Dopo l'aggiornamento conviene
aggiungere la skill «annunci-vinted» al proprio account Claude (vedi
[Annunci Vinted con Claude](#annunci-vinted-con-claude)).

Consiglio: scarica un backup dall'app prima di aggiornare.

### In locale

```bash
git pull
docker compose up -d --build
```

## Backup e ripristino

- **Backup:** *Impostazioni → Backup e ripristino → Scarica backup*. È un unico
  file SQLite (`spese-backup-AAAAMMGG-HHMM.db`) con tutti i dati (spese,
  entrate, ricorrenti, categorie, esercenti, articoli Vinted con le foto),
  compresi gli utenti e le loro password in forma protetta (hash). Conservalo
  in un posto sicuro. I backup delle versioni precedenti si ripristinano: le
  tabelle aggiunte dopo (spese ricorrenti, entrate, entrate ricorrenti,
  articoli Vinted) vengono create vuote e la categoria *Vinted* viene adottata
  o creata come all'aggiornamento. Un backup fatto con la 0.8.0 non si
  ripristina sulle versioni precedenti: l'app lo rifiuta con «Il backup viene
  da una versione più recente dell'app». Lo stesso vale per un backup della
  0.10.0 (annunci e storico dei prezzi) e della 0.11.0 (esercenti segnati
  come «Non sono doppioni») sulle versioni precedenti.
- **Dimensioni:** le foto sono salvate nel database, ridotte dal telefono a
  1200 pixel sul lato lungo (JPEG, al massimo 3 MB l'una) più una miniatura:
  il backup cresce con il numero di foto. Il ripristino accetta file fino a
  512 MB.
- **Ultimo backup scaricato** (dalla 0.14.0): sotto il testo della sezione,
  data, ora e chi l'ha scaricato (vale per entrambi i telefoni). In rosso se
  manca o ha più di 30 giorni. Il file prende il nome con l'ora del
  telefono.
- **Ripristino:** stessa schermata, *Ripristina da file…*. Sostituisce tutti i
  dati con quelli del file, utenti e password compresi. L'app controlla che il
  file sia un backup integro prima di toccare qualcosa e salva una copia dei
  dati sostituiti (*Prima di un ripristino*, ultime 3).
- **Copie automatiche sull'Umbrel** (dalla 0.14.0), nella cartella
  `snapshots` della cartella dati: una al giorno (le ultime 7), una prima di
  ogni aggiornamento che cambia il database (ultime 3) e una prima di ogni
  ripristino (ultime 3). Sono fatte con l'API di backup di SQLite, quindi
  coerenti anche mentre l'app scrive. Compaiono in fondo alla sezione con
  data, tipo e dimensione, ognuna con «Ripristina» (stessi controlli del
  ripristino da file; i dati sostituiti diventano a loro volta una copia,
  quindi un ripristino sbagliato si annulla allo stesso modo). Proteggono da
  errori, ripristini sbagliati e aggiornamenti andati male, **non** da un
  guasto del disco dell'Umbrel: per quello serve il backup scaricato o i
  Backup di umbrelOS. Occupano spazio: con molte foto Vinted ogni copia pesa
  quanto il database.
- Dopo un ripristino valgono utenti e sessioni del backup: può essere
  necessario accedere di nuovo.
- **Backup di umbrelOS:** da *Settings → Backups* umbrelOS fa backup
  automatici cifrati (ogni ora) verso un altro Umbrel, un NAS o un disco
  USB (fonte: guida Umbrel «Backing up your data»). Includono la cartella
  dati dell'app, quindi anche le copie automatiche, che sono coerenti per
  costruzione. Il backup dall'app resta il modo più semplice per avere una
  copia da conservare altrove o da ripristinare su un'altra installazione.

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

Nella variante *Excel italiano*, dalla 0.14.0, un esercente o una nota che
inizia con `=`, `+`, `-` o `@` (per esempio «-10% saldi») prende un
apostrofo davanti: per Excel è il segno «questo è testo» e nella cella non
si vede. Senza, Excel lo leggerebbe come una formula (`#NOME?`). Gli importi
restano numeri e il formato *Standard*, quello per l'AI, non cambia mai.

### Scarica o Condividi, e *Tutto* (dalla 0.15.0)

Ogni export (Spese, Entrate, Articoli Vinted, Tutto) ha due pulsanti:

- **Scarica**: i file vanno nella cartella Download. La conferma ha
  «Copia testo», che copia negli appunti il testo che accompagna i file.
- **Condividi** (solo dal telefono, dall'indirizzo di Tailscale): copia il
  testo negli appunti e apre il menu Condividi di Android con i file. Si
  sceglie l'app (Claude, Drive, Gmail…), si allegano i file e si incolla il
  testo. Testo e file vanno separati perché molte app, quando ricevono un
  file, ignorano il testo. Da `http://umbrel.local:8395` o da un computer
  il pulsante non c'è: Chrome condivide i file solo in HTTPS, e il CSV è tra
  i tipi che accetta. Il backup (`.db`) non è tra questi: si scarica soltanto.

*Tutto* (fino alla 0.14.0 *Per Claude*) sono le spese e le entrate del
periodo e tutti gli articoli Vinted, in file separati (un file senza righe
viene saltato), nel formato scelto.

Il testo dice cosa contengono i file, numero di righe e totali da usare
come controllo (spese, entrate, buoni pasto, differenza; per Vinted gli
articoli per stato, pagato, venduto e guadagno) e le convenzioni dell'app
che le colonne da sole non dicono: buoni pasto come entrata e acquisti fatti
con i buoni tra le spese, categoria *Vinted*, spese con data futura
(previste), formato *Excel italiano*.

L'app non manda nulla a nessuno: la condivisione è un gesto verso un'altra
app. Non è verificato che l'app Claude per Android accetti i CSV dal menu
Condividi, né che la chat aperta così finisca in un progetto: in quel caso
si scarica e si allegano i file nel progetto delle analisi. La prima volta
Chrome può chiedere il permesso di scaricare più file («Consenti»). Se gli
appunti non sono disponibili compare una finestra con il testo da copiare a
mano.

### Entrate

Stessa schermata, scegliendo *Entrate*: un file a parte
(`entrate_<mese>.csv`, `entrate_<mese>_excel.csv`), negli stessi due formati.
Il CSV delle spese non cambia.

Colonne: `data` (AAAA-MM-GG), `importo`, `categoria` (Stipendio, Rimborsi,
Regali, Vendite, Vinted, Altro, Buoni pasto), `nota`, `ricevuto_da`,
`inserito_da`, `creato_il` (UTC, ISO 8601).

La lista delle categorie di entrata è fissa (in `app/schemas.py`,
`INCOME_CATEGORIES`): per cambiarla serve una nuova versione dell'app.

### Articoli Vinted

Stessa schermata, scegliendo *Articoli Vinted*: un file con tutti gli
articoli, senza scelta del periodo (`vinted_articoli.csv`,
`vinted_articoli_excel.csv`), negli stessi due formati.

Colonne: `articolo`, `stato` (Da pubblicare, In vendita, Venduto,
Ritirato), `data_acquisto` e `prezzo_acquisto` (vuoti per le cose già di
casa), `data_vendita` e `prezzo_vendita` (vuoti finché non è venduto),
`guadagno` (vendita meno acquisto; per le cose già di casa l'intera vendita;
vuoto finché non è venduto), `giorni_in_vendita` (dalla pubblicazione su
Vinted alla vendita o a oggi; vuoto per gli articoli ritirati e per quelli
mai pubblicati), `nota`, `inserito_da`, `creato_il` (UTC, ISO 8601). Dalla
0.10.0, in coda: `data_pubblicazione`, `tipo` (Abbigliamento, Borsa, Libro,
Altro), `marca`, `taglia`, `condizioni`, `prezzo_partenza` (il prezzo
dell'annuncio il giorno della pubblicazione), `prezzo_attuale`,
`prezzo_minimo`, `cambi_prezzo` (quante volte il prezzo è cambiato dopo la
pubblicazione). Dalla 0.19.0, in coda: `ribasso` (il piano, «−10% ogni 14
giorni», «Niente ribasso») e `ribasso_scelto_da` (base, Claude, a mano). Le
colonne precedenti non cambiano posizione.

Gli importi degli articoli sono anche nei CSV di spese ed entrate, con
categoria *Vinted*: il file degli articoli aggiunge il legame tra acquisto e
vendita, non altri soldi.

## Annunci Vinted con Claude

Dalla 0.10.0 l'app aiuta a scrivere l'annuncio di un articolo con Claude,
**a mano**: prepara la richiesta e legge la risposta, ma non chiama Claude
né altri servizi (nessuna chiave, nessuna chiamata esterna). La
pubblicazione su Vinted resta sempre manuale.

Nella scheda dell'articolo il riquadro *Annuncio* segue la vita
dell'articolo (0.11.0):

1. **Compila i dettagli** (passo 1): «Aggiungi dettagli» apre la schermata
   *Dettagli*. Il tipo (Abbigliamento, Borsa, Libro, Altro) decide i campi:
   marca, taglia, stato, colore e materiale, misure, difetti; per i libri
   autore, editore e anno. «Prezzi simili visti su Vinted» (es. «20, 25,
   18») dà a Claude un riferimento vero per il prezzo. Il passo è compiuto
   con tipo, stato e marca (autore per i libri; solo lo stato per «Altro»);
   gli altri passi funzionano anche senza. Si possono compilare anche in
   *Nuovo articolo* → «Aggiungi dettagli per l'annuncio».
2. **Chiedi a Claude** (passo 2), «Condividi con Claude»:
   - **con la foto:** l'app copia la richiesta negli appunti e apre il menu
     Condividi con la sola foto (l'app Claude per Android, ricevendo testo
     e foto insieme, tiene solo la foto). Scegli Claude; nella chat tieni
     premuto nel campo del messaggio, scegli **Incolla** e invia. Dalla
     0.13.0 l'avviso «Richiesta copiata…» compare in alto, dove il menu
     Condividi non lo copre;
   - **senza foto:** il menu Condividi riceve direttamente la richiesta.

   «Copia solo la richiesta» copia il testo senza condividere nulla.
3. Claude risponde nel formato fisso (TITOLO, DESCRIZIONE, PREZZO, MINIMO,
   RIBASSO dalla 0.19.0, VERIFICA): copia la risposta con il pulsante copia
   sotto il messaggio.
4. **Incolla la risposta** (passo 3): si apre la schermata *Annuncio* con
   titolo, descrizione, prezzo e minimo già compilati, più un avviso giallo
   con le cose da controllare (non viene salvato). Correggi e **Salva
   annuncio**. Se la risposta non è nel formato, tutto il testo finisce nella
   descrizione e i prezzi restano vuoti. Se negli appunti c'è ancora la
   richiesta, l'app lo dice e apre la casella in cui incollare. «Oppure
   scrivi l'annuncio tu» apre la stessa schermata vuota. Dalla 0.19.0, se
   la risposta ha la riga RIBASSO («10% ogni 14 giorni», «2 € ogni 7
   giorni», «niente»), sotto i prezzi compare «Ribasso: … (proposto da
   Claude)» e il piano si salva con l'annuncio; senza la riga, o con una
   riga che l'app non sa leggere (lo dice l'avviso giallo), l'articolo
   tiene il piano che aveva.
5. **Annuncio pronto:** il riquadro mostra titolo, descrizione e prezzo, ognuno
   con «Copia», e il promemoria per Vinted. Pubblichi a mano su Vinted, poi
   **Segna come pubblicato**: il prezzo di quel giorno diventa il prezzo di
   partenza. «Chiedi di nuovo» ripropone i passi. Dalla 0.13.0 la riga
   **Dettagli dell'articolo** (chiusa: tipo, marca, taglia, stato in una
   riga) si apre con «Mostra ▾» e mostra tutti i dettagli compilati (anche
   misure, difetti, prezzi simili) con «Modifica dettagli», senza passare
   da «Chiedi di nuovo».
6. **In vendita:** in cima il prezzo su Vinted con «Cambia» (lo storico dei
   prezzi finisce nel CSV: `prezzo_partenza`, `cambi_prezzo`), poi titolo e
   descrizione con «Copia» e «Non si vende? Chiedi a Claude un prezzo
   nuovo»: la richiesta dice da quanti giorni e a che prezzo è in vendita,
   e dalla 0.19.0 anche i prezzi già fatti, il minimo e il ribasso attuale.
   Anche qui c'è la riga *Dettagli dell'articolo*. Venduto o ritirato: resta
   solo il testo, se c'è, con i dettagli da rivedere (senza modifica).

Il **titolo dell'annuncio** parte dal nome dell'articolo: finché non salvi un
titolo diverso (di solito quello di Claude), «Copia» copia il nome, e se
rinomini l'articolo cambia anche lui.

Appunti, condivisione e lettura degli appunti funzionano solo in HTTPS,
cioè dall'indirizzo Tailscale. Da `http://umbrel.local:8395` l'app mostra il
testo da copiare a mano e una casella in cui incollare la risposta. La prima
volta che tocchi «Incolla risposta» Chrome può chiedere il permesso di
leggere gli appunti; se lo neghi, l'app apre la casella in cui incollare.

### Le regole per Claude: richiesta e skill «annunci-vinted»

Dalla 0.11.0 la richiesta dell'app basta da sola: contiene i dati, le regole
di stile (titolo come frase naturale, descrizione in prosa da 1 a 4 frasi,
niente hashtag, elenchi o emoji, un esempio da un annuncio di Nastia), le
regole del prezzo e il formato della risposta (`app/vinted_listing.py`).

Le stesse regole, più dettagliate (titoli d'esempio, libri, richieste di
modifica nella stessa chat), stanno nella skill
[`skills/annunci-vinted/SKILL.md`](skills/annunci-vinted/SKILL.md). Claude la
usa da solo in qualsiasi chat, anche in quella aperta con «Condividi», e la
si può cambiare senza una nuova versione dell'app. Per aggiungerla:

1. Su claude.ai: *Impostazioni → Capacità*, attiva «Esecuzione del codice e
   creazione di file» (serve alle skill).
2. Comprimi la cartella `skills/annunci-vinted` in un file ZIP (o usa quello
   consegnato con la versione) e caricalo da *Personalizza → Skill → + →
   Carica una skill*.
3. Ogni persona la aggiunge al **proprio** account Claude: se Nastia usa un
   account suo, la carica anche lei. Senza skill la richiesta funziona
   comunque.

Il formato della risposta deve restare **identico** nella richiesta e nella
skill, altrimenti «Incolla risposta» non riconosce le parti. Con la 0.19.0
la skill aggiunge la riga RIBASSO subito dopo MINIMO: va ricaricata (stessi
passi). La 0.18 ignora quella riga senza errori, perché legge solo il primo
numero di MINIMO; per questo RIBASSO non va mai dopo VERIFICA. Il Progetto
claude.ai «Annunci Vinted» suggerito dalla 0.10.0 non serve più: una chat
aperta con «Condividi» non entra in un Progetto.

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
  le spese che compongono quel totale del riepilogo. Dalla 0.9.0 anche `q`
  (al massimo 80 caratteri): testo cercato senza maiuscole né accenti in
  esercente, nota, categoria e titolo dell'articolo Vinted collegato, oppure
  un importo esatto («12,50»); combinabile con gli altri filtri, senza di
  loro cerca in tutti i mesi. `GET /api/v1/incomes` accetta lo stesso `q`
  (categoria, nota, articolo, importo).
- Spese ricorrenti: `GET/POST /api/v1/recurring`, `PATCH/DELETE
  /api/v1/recurring/{id}`, `POST /api/v1/recurring/{id}/register` (crea la spesa
  e sposta la scadenza) e `POST /api/v1/recurring/{id}/skip`. Entrambe chiedono
  `due_date` uguale alla scadenza attuale: se l'altra persona l'ha già
  registrata la risposta è 409, senza doppioni.
- Entrate: `GET/POST /api/v1/incomes` (filtri `month`, oppure `from` e `to`;
  `client_uuid` come per le spese), `GET/PATCH/DELETE /api/v1/incomes/{id}` e
  `GET /api/v1/incomes/categories` (la lista fissa: `salary`, `refund`,
  `gift`, `sale`, `vinted`, `other`, `meal_voucher`, con i nomi in
  italiano). Export:
  `GET /api/v1/export/incomes.csv`, con gli stessi filtri e formati di
  `/export.csv`.
- Entrate ricorrenti: stessi endpoint e stesse regole delle spese ricorrenti
  sotto `/api/v1/recurring-incomes` (`GET/POST`, `GET/PATCH/DELETE /{id}`,
  `POST /{id}/register` che crea l'entrata e sposta la scadenza, `POST
  /{id}/skip`), con `category` e `received_by_user_id` al posto di categoria,
  esercente e metodo di pagamento.
- Riepilogo: `GET /api/v1/summary?month=AAAA-MM` restituisce le spese
  (`total_cents`, `by_category`), le entrate (`income_cents`, `income_count`,
  `voucher_cents`: la parte nella categoria `meal_voucher`) e `balance_cents`
  (entrate meno spese). `GET /api/v1/summary/incomes?month=AAAA-MM` restituisce
  le entrate del mese per categoria (`total_cents`, `income_count`,
  `by_category`, dalla più grande). `GET /api/v1/summary/trend?month=AAAA-MM&months=6`
  restituisce i totali di entrate (con `voucher_cents`) e spese di ogni mese
  della finestra (da 1 a 24 mesi, il più vecchio per primo), anche quelli vuoti.
  `GET /api/v1/summary/period?from=AAAA-MM-GG&to=AAAA-MM-GG` (0.9.0, per
  *Esplora*) restituisce i totali di un periodo qualsiasi, estremi compresi:
  `income_cents`, `income_count`, `voucher_cents`, `expense_cents`,
  `expense_count`, `balance_cents`.
- Vinted (0.8.0), sotto `/api/v1/vinted`: `GET/POST /items` (filtro
  `status`: `listed`, `sold`, `withdrawn`; `client_uuid` come per le spese),
  `GET/PATCH/DELETE /items/{id}` (la PATCH cambia titolo, nota e ritiro;
  la DELETE elimina anche la spesa e l'entrata collegate), `POST
  /items/{id}/purchase` e `POST /items/{id}/sale` (creano la spesa o
  l'entrata, oppure collegano una già registrata con `expense_id` o
  `income_id`), `DELETE /items/{id}/sale` (annulla la vendita eliminando
  l'entrata), `PUT/DELETE /items/{id}/photo` (JPEG in base64, già ridotto
  dal client) e `GET /items/{id}/photo` e `/photo/thumb`, `GET
  /unlinked-expenses` e `/unlinked-incomes` (cosa si può collegare), `GET
  /summary?month=AAAA-MM`, `/summary/trend?month=AAAA-MM&months=6` e, dalla
  0.9.0, `/summary/period?from=&to=` (le cifre del riepilogo del mese su un
  periodo qualsiasi). Le
  spese e le entrate collegate riportano `vinted_item_id` e
  `vinted_item_title`; la loro categoria non si può cambiare. Le categorie
  hanno `system_key` (`vinted` per quella della sezione, altrimenti `null`).
  Export: `GET /api/v1/export/vinted.csv`, con gli stessi formati di
  `/export.csv` e senza filtri di data.
- Vinted dalla 0.10.0: stato `unlisted` (da pubblicare; anche come filtro
  `status`) e `listed_on` facoltativo (il giorno della pubblicazione su
  Vinted; `POST /items` senza `listed_on` crea un articolo da pubblicare,
  `PATCH` con `listed_on: null` lo riporta lì). `POST` e `PATCH /items`
  accettano anche i dettagli (`kind`, `brand`, `size`, `condition`,
  `color_material`, `measurements`, `book_author`, `book_publisher_year`,
  `defects`, `similar_prices`) e l'annuncio (`listing_title`,
  `listing_description`, `price`, `min_price` come testo, «22,50»); ogni
  articolo restituisce `details` e `listing`, con `price_changes` (il prezzo
  il giorno della pubblicazione, poi ogni cambio). `GET /listing/options`
  (tipi con i loro campi, stati con le parole di Vinted), `GET
  /items/{id}/listing-request` (il testo da mandare a Claude) e `POST
  /listing/parse` (legge la risposta incollata, senza salvare nulla).
- Dalla 0.11.0: `listing.effective_title` (il titolo da mettere su Vinted:
  quello dell'annuncio o, se manca, il nome dell'articolo); `POST
  /listing/parse` risponde 422 se riceve la richiesta stessa invece della
  risposta; l'acquisto di un articolo non ha più «Vinted» come esercente
  predefinito. Esercenti: `GET /api/v1/merchants/duplicates` (coppie di nomi
  che si assomigliano: `reason` `same`, `contained` o `similar`, con
  `reason_name` in italiano; prima l'esercente con più spese), `POST
  /api/v1/merchants/{id}/distinct` con `{other_id}` («Non sono doppioni») e
  `DELETE /api/v1/merchants/{id}/distinct/{other_id}` (annulla).
- Dalla 0.14.0:
  - `GET /api/v1/expenses` e `GET /api/v1/incomes` accettano `limit` (da 1 a
    500) e `offset`: una pagina della lista. `GET
    /api/v1/summary/search/expenses?q=…` e `/summary/search/incomes?q=…`
    restituiscono numero e totale di tutti i risultati di una ricerca, anche
    mese per mese (`count`, `total_cents`, `months`).
  - `POST /api/v1/expenses` restituisce anche `possible_duplicates`: le
    spese con lo stesso importo e lo stesso giorno, dello stesso esercente
    (senza esercente: della stessa categoria). La spesa è salvata comunque.
  - `GET /api/v1/merchants`: ogni esercente ha `recent_count` (spese degli
    ultimi 90 giorni) e la lista è ordinata prima per quello.
  - `PUT /api/v1/categories/order` con `{ids: [...]}`: tutte le categorie,
    attive e no, nel nuovo ordine (409 se l'elenco non corrisponde).
  - `GET /api/v1/summary?month=…` ha anche `expected_income_cents` ed
    `expected_incomes`: le entrate ricorrenti attive con la prossima
    scadenza nel mese, non ancora registrate.
  - `GET /api/v1/backups` (`last_download` e `copies`, le copie sul server
    dalla più recente) e `POST /api/v1/backups/{name}/restore`.
  - `GET /api/v1/export/brief` (filtri `month`, oppure `from` e `to`):
    `files` (nome e indirizzo dei CSV standard del periodo) e `text` (il
    testo da mandare con i file a un assistente AI). Dalla 0.15.0 anche
    `what` (`expenses`, `incomes`, `vinted` o `all`, predefinito; `vinted`
    senza periodo) e `format` (`standard` o `excel_it`).
- Dalla 0.15.0:
  - `GET /api/v1/categories/icons` → `{icons, default}`: le icone che una
    categoria di spesa può avere. Ogni categoria ha `icon` (il nome; quella
    predefinita, `category`, se non è stata scelta); `POST` e `PATCH
    /api/v1/categories` accettano `icon` (422 se non è nell'elenco).
  - `GET /api/v1/incomes/categories`: ogni voce ha anche `icon` (fissa).
  - Le immagini delle icone sono Tabler Icons copiate nell'interfaccia
    (`app/static/js/category-icons.js`); l'API dà solo i nomi.
- Dalla 0.17.0: spese ed entrate ricorrenti hanno `is_variable` (`POST`,
  `PATCH`, risposte). `GET /api/v1/summary/recurring` → `{expenses,
  incomes}`, ciascuno con `count`, `month_cents`, `year_cents` e
  `has_variable`: quanto valgono al mese e all'anno i modelli attivi.
- Dalla 0.18.0:
  - `GET /api/v1/expenses` e `GET /api/v1/summary/search/expenses` accettano
    gli stessi filtri: `category_id`, `paid_by_user_id`, `payment_method`,
    `tag` («vacanze» o «#vacanze»: le spese con quell'etichetta nella nota),
    `from` e `to`. Per i totali della ricerca `q` non è più obbligatorio.
  - `GET /api/v1/tags`: le etichette delle note delle spese (`tag`, `count`,
    `total_cents`, `last_date`), dalla usata più di recente.
  - `GET /api/v1/summary/period` ha anche `planned_cents` e `planned_count`:
    la parte delle spese del periodo con data dopo oggi.
- Dalla 0.18.1: `GET /api/v1/vinted/summary` ha anche `purchase_cents` e
  `extra_cents`, gli importi delle spese Vinted del mese divisi tra acquisti
  di articoli e costi extra (accanto a `purchase_count` ed `extra_count`).
- Dalla 0.19.0 (ribasso):
  - ogni articolo Vinted ha `markdown`: `plan` (`kind` `pct`, `eur` o `none`,
    `amount` in percento o in centesimi, `days`, `source` `base`, `claude` o
    `manual`, `text` come lo scrive l'app), `state` (`inactive`, `off`,
    `no_minimum`, `waiting`, `due`, `at_minimum`, `review`, `settled`),
    `since` (ultimo cambio di prezzo), `due_on`, `next_price_cents`, `steps`
    (i gradini che restano, il minimo per ultimo).
  - `PATCH /api/v1/vinted/items/{id}` accetta `markdown`: `{"plan": "base"}`,
    `{"plan": "none"}` oppure `{"plan": "pct" | "eur", "amount": "10" |
    "2,50", "days": 14, "source": "claude" | "manual"}` (da 1% a 50%, da
    0,50 €, ogni 1–90 giorni; altrimenti 422).
  - `POST /api/v1/vinted/items/{id}/markdown/skip` («Salta»: il gradino si
    rimanda di un giro da oggi; 409 se non c'è niente da saltare) e
    `POST /api/v1/vinted/items/{id}/markdown/settle` («Lascia così» al
    minimo; 409 se l'articolo non è al minimo).
  - `POST /api/v1/vinted/listing/parse` restituisce anche `markdown` (il piano
    della riga RIBASSO, se leggibile) e `markdown_text` (la riga com'è
    scritta).

## Sviluppo

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt

# avvio senza Docker
SPESE_DATA_DIR=./data SPESE_COOKIE_SECURE=auto uvicorn app.main:app --reload --port 8080

# test del server
pytest

# test dell'interfaccia (dalla 0.14.0): Chrome a misura di telefono
python -m playwright install chromium
pytest tests_ui
```

I test dell'interfaccia (`tests_ui/`) avviano l'app su una porta libera con
una cartella dati vuota e la usano in Chrome a 360 e 320 pixel: inserimento
e «Annulla», apertura senza rete, doppioni, ricerca a pagine, entrate
attese, ordine delle categorie, backup, export per Claude, filtro iniziale
di Vinted, schermate principali senza elementi fuori schermo né errori in
console. Il workflow di rilascio li esegue insieme ai test del server prima
di pubblicare l'immagine. Per usare un Chrome già installato:
`SPESE_UI_CHROME=/percorso/di/chrome pytest tests_ui`. Playwright è una
dipendenza solo di sviluppo: non entra nell'immagine.

Le icone si rigenerano con `python scripts/make_icons.py`.

### Struttura

```
app/
  main.py          avvio, file statici, header di sicurezza
  config.py        variabili d'ambiente
  db.py            connessioni SQLite e migrazioni
  security.py      password (scrypt), sessioni, autenticazione
  money.py         conversione degli importi in centesimi
  validation.py    controlli comuni (importo, categoria, utente, nota)
  copies.py        copie automatiche del database e ultimo backup scaricato
  export_brief.py  testo da mandare con i CSV a un assistente AI
  text.py          ricerca: testo senza maiuscole e accenti
  tags.py          etichette #parola nelle note delle spese (0.18.0)
  vinted_listing.py  annunci Vinted: richiesta per Claude e lettura della risposta
  vinted_markdown.py ribasso a scalini: piani, gradini e stato di un articolo (0.19.0)
  merchant_duplicates.py  possibili doppioni tra gli esercenti
  dates.py         intervalli di date
  schemas.py       modelli JSON dell'API
  vinted_schemas.py  modelli JSON della sezione Vinted (dalla 0.17.0)
  migrations/      schema del database (file SQL numerati)
  cli.py           strumenti di recupero (reimpostazione password)
  routers/         endpoint: auth, expenses, incomes, recurring,
                   recurring_incomes, categories, merchants, summary,
                   tags, vinted, vinted_photos, vinted_summary, export, backup
  static/          frontend (HTML, CSS, JavaScript, manifest, service worker)
tests/             test automatici del server (pytest)
tests_ui/          test dell'interfaccia in Chrome (Playwright)
skills/            skill «annunci-vinted» da caricare su claude.ai
scripts/           generazione delle icone
.github/workflows/ pubblicazione dell'immagine su GHCR (release.yml)
Dockerfile
docker-compose.yml test in locale e Portainer
```
