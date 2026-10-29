# 01 · Architettura

```
 Claude Code (abbonamento)            Antigravity IDE            altri agenti (Codex, Cline, OpenCode…)
   │  MCP: ask_freellmapi               │  MCP                      │  OpenAI /v1
   │  oppure `claude-free`              │                           │
   └───────────────┬────────────────────┴───────────────┬───────────┘
                   ▼                                    ▼
        ┌──────────────────────────────────────────────────────┐
        │  FreeLLMAPI  (router, catena `auto`, key cifrate)    │
        │  desktop :31415  ·  server/Docker :3001              │
        │  /v1 (OpenAI) · / (Anthropic) · /mcp · dashboard     │
        └───────┬───────────────────────────────┬──────────────┘
                │ provider gratuiti             │ custom provider (OpenAI)
                ▼                               ▼
   Google · NVIDIA · xKiro · Groq ·    antigravity-bridge :3005   ← questo repo (bridge/)
   UnoRouter · Zhipu · Mistral ·          │ OpenAI → Anthropic
   Cohere · …                             ▼
                                   antigravity-claude-proxy :8080  ← npm, multi-account Google
                                          │
                                          ▼
                                 Antigravity Cloud Code (Claude Opus/Sonnet thinking, Gemini Pro)
```

## I pezzi

| Pezzo | Cos'è | Da dove arriva |
|---|---|---|
| **FreeLLMAPI** | Router che mette 30+ provider gratuiti dietro un solo endpoint, con fallback automatico, rate limit per key, cache, MCP server. | [tashfeenahmed/freellmapi](https://github.com/tashfeenahmed/freellmapi) (app desktop o immagine Docker) |
| **Catena `auto`** | Lista ordinata di modelli che il router prova in sequenza quando chiedi `model="auto"`. Se uno dà 429/errore/timeout passa al successivo. | `config/chain.json` + `scripts/curator.py` |
| **curator.py** | Scrive la catena nel DB di FreeLLMAPI. `apply` = catena consigliata a mano. `auto` = la calcola da solo (filtri + punteggio + affidabilità reale dai log). | questo repo |
| **antigravity-claude-proxy** | Usa account Google con accesso Antigravity e li espone come API Anthropic. Bilancia tra più account. | npm [`antigravity-claude-proxy`](https://github.com/badri-s2001/antigravity-claude-proxy) |
| **antigravity-bridge** | FreeLLMAPI accetta solo provider OpenAI-compatibili; il proxy parla Anthropic. Il bridge traduce (messaggi, tool call, streaming, errori). | `bridge/` (zero dipendenze, testato) |
| **Integrazione Claude Code** | MCP `freellmapi` + regole di delega in `~/.claude/CLAUDE.md` + alias `claude-free`. | `claude-code/` |
| **Integrazione Antigravity IDE** | Lo stesso MCP `freellmapi` dentro l'agente di Antigravity. | `antigravity-ide/` |

## Due modi di usare Claude Code

1. **Ibrido (consigliato)**: Claude Code gira sul tuo abbonamento; i lavori pesanti ma semplici
   li delega via MCP (`ask_freellmapi`) ai modelli gratuiti. Risparmi la quota delle 5 ore.
2. **Tutto gratis** (`claude-free` = `npx freellmapi launch`): Claude Code parla direttamente con
   FreeLLMAPI come se fosse l'API Anthropic. Utile quando finisce il limite. Qualità inferiore.

Opzione extra: `claude-antigravity` punta Claude Code direttamente al proxy Antigravity (Opus vero),
senza passare da FreeLLMAPI. Stesso rischio account del proxy (vedi [08](08-sicurezza-e-rischi.md)).

## Dettaglio importante: profili

FreeLLMAPI ha i **profili** (catene con nome). Se un profilo è attivo — l'app desktop ha sempre
"Default" — il router usa la catena del profilo (`profile_models`), **non** `fallback_config`.
Uno script che scrive solo `fallback_config` non cambia niente. `curator.py` scrive entrambe e
spegne `auto_include_new_models` sul profilo attivo, altrimenti ogni sync del catalogo ci
riaggiunge centinaia di modelli. Dopo un aggiornamento del catalogo, rilancia `curator.py auto`.
