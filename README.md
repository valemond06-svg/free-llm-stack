# free-llm-stack

Stack pronto per usare **decine di modelli LLM gratuiti** dietro un solo endpoint, collegati a
**Claude Code** (in modalità ibrida con l'abbonamento) e all'**IDE Antigravity**, con
fallback automatico quando un provider finisce la quota.

- **FreeLLMAPI** fa da router: 30+ provider gratuiti, catena `auto` con fallback, key cifrate, server MCP.
- **Catena curata** di 22 modelli (Nemotron 3 Ultra, Qwen 3.8 Max, Gemini 3.x Flash, GLM 5.3…) e uno
  script che la ricalcola da solo quando aggiungi provider, usando anche l'affidabilità reale dai log.
- **Bridge Antigravity** (facoltativo): Claude Opus/Sonnet 4.6 thinking e Gemini Pro in cima alla catena.
- **Claude Code**: l'abbonamento si occupa del ragionamento, i lavori pesanti ma semplici vanno ai modelli gratis via MCP.
  Quando finisce il limite delle 5 ore, `claude-free` fa girare tutto su FreeLLMAPI.
- Gira su un **PC sempre acceso** o su una **VPS** (Docker, systemd o pm2).

Il repo contiene **solo infrastruttura**: nessuna key, nessun dato. Le tue key restano sulla tua macchina.

## Setup con il tuo agente AI (consigliato)

Clona il repo, aprilo con Claude Code (o un altro agente) e incolla il prompt di
[SETUP_PROMPT.md](SETUP_PROMPT.md). L'agente legge [CLAUDE.md](CLAUDE.md) e ti guida passo passo:
ti fa le domande giuste, installa, ti dice cosa cliccare per le registrazioni e verifica ogni fase.

## Setup manuale

| Passo | Guida |
|---|---|
| Come funziona | [docs/01-architettura.md](docs/01-architettura.md) |
| Quali provider e quanti account | [docs/02-provider-e-account.md](docs/02-provider-e-account.md) |
| Modelli consigliati e catena | [docs/03-modelli-e-catena.md](docs/03-modelli-e-catena.md) |
| Deploy su PC sempre acceso | [docs/04-pc-sempre-acceso.md](docs/04-pc-sempre-acceso.md) |
| Deploy su VPS | [docs/05-deploy-vps.md](docs/05-deploy-vps.md) |
| Claude Code e Antigravity IDE | [docs/06-claude-code-e-antigravity.md](docs/06-claude-code-e-antigravity.md) |
| Problemi comuni | [docs/07-troubleshooting.md](docs/07-troubleshooting.md) |
| **Sicurezza e rischi (leggere prima)** | [docs/08-sicurezza-e-rischi.md](docs/08-sicurezza-e-rischi.md) |

Avvio rapido su VPS con Docker:

```bash
cp .env.example .env && sed -i "s/^ENCRYPTION_KEY=.*/ENCRYPTION_KEY=$(openssl rand -hex 32)/" .env
docker compose up -d                          # + "--profile antigravity" per il bridge Antigravity
python3 scripts/doctor.py
```

## Struttura

```
CLAUDE.md / AGENTS.md          istruzioni per l'agente AI che fa il setup
SETUP_PROMPT.md                il prompt da incollare
docker-compose.yml             FreeLLMAPI + (profilo antigravity) proxy + bridge
.env.example                   variabili (segreti generati da te, mai committati)
bridge/                        adattatore OpenAI → Anthropic per Antigravity (Node, zero dipendenze, test)
scripts/curator.py             scrive la catena `auto` (apply / auto / report)
scripts/doctor.py              health check di tutto lo stack
config/chain.json              catena consigliata + regole del curator
config/freellmapi.config.example.json   config dichiarativa (key, endpoint custom)
claude-code/                   regole di delega per ~/.claude/CLAUDE.md, alias bash/PowerShell
antigravity-ide/               snippet MCP per l'IDE Antigravity
deploy/                        systemd, pm2, autostart Windows, Caddy, Dockerfile del proxy
docs/                          guide
```

## Comandi di tutti i giorni

```bash
llm-doctor      # tutto ok?
llm-chain       # che catena sta usando il router
llm-optimize    # ricalcola la catena dopo nuove key/provider
claude-free     # Claude Code interamente su modelli gratis
```

## Crediti

[FreeLLMAPI](https://github.com/tashfeenahmed/freellmapi) (MIT) ·
[antigravity-claude-proxy](https://github.com/badri-s2001/antigravity-claude-proxy) (MIT).
Questo repo li configura e li collega; non è affiliato a nessuno dei due.
Uso personale e sperimentale: i free tier non sono garantiti e i ToS dei provider restano validi.
