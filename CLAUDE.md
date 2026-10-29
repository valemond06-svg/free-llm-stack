# Istruzioni per l'agente AI: setup di free-llm-stack

Sei l'agente che installa questo stack **insieme all'utente**, sulla sua macchina. L'utente
potrebbe non essere esperto: spiega in parole semplici cosa fai e perché, un passo alla volta.
Parla nella lingua dell'utente (di default italiano).

Questo repo contiene solo infrastruttura: nessuna key, nessun DB. Leggi `README.md` e
`docs/01-architettura.md` prima di iniziare. Ogni fase sotto rimanda al doc con i dettagli.

## Regole

1. **Segreti**: non stampare, non scrivere nei file del repo e non committare mai key, password o
   la unified key. Le key dei provider le inserisce l'utente nella dashboard di FreeLLMAPI (o in
   `secrets/`, gitignored). Quando ti serve la unified key per un comando, chiedi all'utente di
   impostarla come variabile d'ambiente `FREELLMAPI_API_KEY` e usa la variabile, non il valore.
   Se l'utente incolla una key in chat, usala solo dove serve e ricordagli che è finita nel log.
2. **Account esterni**: registrazioni, login, OAuth Google, consensi nelle dashboard dei provider
   li fa l'utente nel browser. Tu dai il link e dici esattamente cosa cliccare, poi aspetti.
3. **Prima guarda, poi tocca**: prima di modificare `~/.claude/CLAUDE.md`, `~/.bashrc`, `$PROFILE`
   o la config MCP di Antigravity, leggili e mostra cosa aggiungerai. Aggiungi, non sovrascrivere.
4. **Verifica ogni fase** con `scripts/doctor.py` (o il controllo indicato) prima di passare oltre.
   Se un controllo fallisce, usa `docs/07-troubleshooting.md`; non andare avanti a tentativi.
5. **Antigravity** comporta un rischio concreto di ban dell'account Google
   (`docs/08-sicurezza-e-rischi.md`). Spiegalo all'utente con parole sue e fatti dare un sì
   esplicito prima di installarlo. Consiglia account secondari.
6. Usa `--dry-run` di `curator.py` e mostra il risultato prima di scrivere nel DB.
7. Comandi: usa la shell disponibile (bash su Linux/macOS, PowerShell su Windows). Python 3.10+
   e Node 20+ servono; se mancano, guida l'installazione.

## Fase 0 · Decisioni (chiedile tutte insieme, all'inizio)

- **Dove gira?** (a) questo PC, che resta acceso → `docs/04-pc-sempre-acceso.md`;
  (b) una VPS Linux → `docs/05-deploy-vps.md` (servono IP e accesso SSH; se sei su un altro PC,
  i comandi vanno eseguiti via `ssh`).
- **Antigravity sì/no?** (dopo aver spiegato il rischio).
- **Quali agenti collegare?** Claude Code (sempre), Antigravity IDE, altri.
- **Quali provider?** Proponi il "minimo per partire" di `docs/02-provider-e-account.md`
  (Google, NVIDIA, Groq, xKiro) e poi gli extra.

Riepiloga le scelte e il piano in 5–8 righe, poi procedi.

## Fase 1 · Prerequisiti

Controlla `git`, `python3`/`python`, `node -v` (≥ 20), e `docker` se VPS. Installa ciò che manca
(con conferma). Su VPS: firewall `ufw` con solo SSH aperto.

## Fase 2 · FreeLLMAPI

- PC: installer desktop da Releases, avvio al login, porta **31415**.
- VPS: `.env` da `.env.example` con `ENCRYPTION_KEY` generata (`openssl rand -hex 32`),
  `docker compose up -d`, porta **3001**, accesso alla dashboard via tunnel SSH.
  Fai salvare `ENCRYPTION_KEY` all'utente nel suo password manager.

Fai attivare **MCP** (Keys → Agent compatibility) e fai copiare la unified key.
Verifica: `python scripts/doctor.py --url <URL>` → "FreeLLMAPI is running" OK.

## Fase 3 · Provider

Per ogni provider scelto: dai il link da `docs/02-provider-e-account.md`, l'utente crea la key e la
incolla nella dashboard (Keys). Ricorda le trappole note: Google senza fatturazione e key da
progetti diversi; **UnoRouter richiede di dare il consenso ai provider upstream** nella sua
dashboard; Cohere è una trial key.
**UnoRouter**: i suoi modelli `:free` richiedono un consenso legale ai provider upstream, che dichiarano di
conservare o usare i prompt per training. Spiegalo e chiedi un sì esplicito **prima** di eseguire
`scripts/unorouter_consent.py --grant`. Se l'utente rifiuta, disattiva le key UnoRouter (dashboard) e vai avanti.
Verifica: pallini verdi in Keys; `FREELLMAPI_API_KEY=… python scripts/doctor.py --url <URL>`.

## Fase 4 · Antigravity (solo se confermato)

- Esistono due proxy: `antigravity-claude-proxy` (API Anthropic, serve `bridge/`) oppure
  `frieser/antigravity-proxy` (API OpenAI, niente bridge; vedi `docs/04`, va legato a 127.0.0.1).
- PC: `.env` con i tre segreti generati, `npm i -g pm2 antigravity-claude-proxy@2.9.1`,
  `pm2 start deploy/pm2/ecosystem.config.cjs`, autostart (Windows: `deploy/windows/install-autostart.ps1`;
  macOS/Linux: `pm2 startup`).
- VPS: `docker compose --profile antigravity up -d`.
- L'utente aggiunge gli account Google dalla WebUI (`http://localhost:8080`, su VPS via tunnel,
  modalità Manual Authorization).
- In FreeLLMAPI: custom endpoint verso il bridge (`http://127.0.0.1:3005/v1` su PC,
  `http://antigravity-bridge:3005/v1` su Docker) con key `BRIDGE_API_KEY`, e i modelli elencati
  da `GET <bridge>/v1/models`, con Tools e Vision attivi.
Verifica: `doctor.py` → proxy, bridge e "bridge lists Antigravity models" OK.

## Fase 5 · Catena `auto`

`python scripts/curator.py report`, poi `apply --dry-run`, mostra, poi `apply`.
Se ci sono molti `[missing]`, proponi `auto --dry-run`. Spiega in 3 righe come leggere il report
(`docs/03-modelli-e-catena.md`).
Verifica: `doctor.py --chat` → "real completion via model=auto" OK.

## Fase 6 · Claude Code

`docs/06-claude-code-e-antigravity.md`:
1. `claude mcp add --scope user --transport http freellmapi <URL>/mcp --header "Authorization: Bearer $FREELLMAPI_API_KEY"`
   (su PowerShell `$env:FREELLMAPI_API_KEY`); verifica con `claude mcp list`.
2. Aggiungi `claude-code/CLAUDE.global.md` a `~/.claude/CLAUDE.md` con `<REPO>` sostituito.
3. Alias (`claude-code/aliases.sh` o `aliases.ps1`) nel profilo della shell.
L'MCP si carica alla prossima sessione di Claude Code: dillo all'utente.

## Fase 7 · Antigravity IDE e altri agenti (se scelti)

Snippet in `antigravity-ide/mcp_config.snippet.json`. Altri agenti: `npx freellmapi setup-<agente> --dry-run`.

## Fase 8 · Chiusura

- `doctor.py --chat` tutto OK.
- Riepilogo per l'utente: dove gira cosa, porte, come aggiornare, cosa fare quando aggiunge una
  key (`llm-optimize`), dove sono i backup, cosa tenere segreto.
- Ricordagli i comandi utili: `llm-doctor`, `llm-chain`, `llm-optimize`, `claude-free`.

## Se modifichi questo repo

- `bridge/`: Node ≥ 20, zero dipendenze. `cd bridge && npm test` deve restare verde.
- `scripts/`: solo libreria standard di Python.
- Mai aggiungere segreti, DB o dati in `data/`/`secrets/` al git.
