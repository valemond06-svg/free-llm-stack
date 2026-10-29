# 06 · Collegare Claude Code e Antigravity IDE

`URL` = `http://127.0.0.1:31415` (app desktop) oppure `http://localhost:3001` (Docker/server,
o l'IP Tailscale della VPS). `KEY` = la unified key `freellmapi-…`.

## Claude Code

### A. MCP (modalità ibrida, consigliata)

```bash
claude mcp add --scope user --transport http freellmapi URL/mcp \
  --header "Authorization: Bearer KEY"
claude mcp list            # deve mostrare: freellmapi ... ✓ Connected
```

Se risponde 403: l'MCP è spento → dashboard **Keys → Agent compatibility → MCP**.

Tool che ottieni: `ask_freellmapi`, `list_models`, `healthcheck`, `provider_health`,
`provider_list`, `usage_summary`, `quota_outlook`, `routing_info`, `set_routing_strategy`,
`cache_stats`, `compression_stats`, `clear_cache`, `web_search`.

### B. Regole di delega

Copia `claude-code/CLAUDE.global.md` in fondo a `~/.claude/CLAUDE.md` (crealo se non c'è) e
sostituisci `<REPO>` con il percorso del repo. Così Claude Code manda in automatico i lavori
pesanti/semplici ai modelli gratuiti e tiene la quota per il resto.

### C. Alias

- bash/zsh: aggiungi `source /percorso/free-llm-stack/claude-code/aliases.sh` a `~/.bashrc` / `~/.zshrc`
- PowerShell: aggiungi `. C:\percorso\free-llm-stack\claude-code\aliases.ps1` a `$PROFILE`

Imposta la key come variabile d'ambiente utente (mai dentro file del repo):
`export FREELLMAPI_API_KEY=...` in `~/.bashrc`, oppure `setx FREELLMAPI_API_KEY "..."` su Windows.

| Alias | Cosa fa |
|---|---|
| `claude-free` | Claude Code interamente su FreeLLMAPI (`npx freellmapi launch`). Per quando finisce il limite. La key non viene scritta su disco. |
| `claude-antigravity` | Claude Code direttamente sul proxy Antigravity (Opus 4.6 thinking). |
| `llm-optimize` | `curator.py auto` con anteprima e conferma. |
| `llm-chain` | Mostra la catena attiva. |
| `llm-doctor` | Health check. |

In alternativa ad `claude-free`: `npx freellmapi setup-claude --url URL --profile free` crea un
profilo Claude Code dedicato (fa backup della config prima di scrivere; prova con `--dry-run`).

## Antigravity IDE

Pannello Agent → menu **…** → **MCP Servers** → **Manage MCP Servers** → **View raw config**.
Unisci il blocco di `antigravity-ide/mcp_config.snippet.json` dentro `mcpServers`, metti URL e KEY
veri, salva, premi refresh. L'agente di Antigravity ora vede gli stessi tool `freellmapi`.

## Altri agenti

FreeLLMAPI ha un generatore per ognuno (Codex, Cline, Continue, Aider, OpenCode, Goose, Qwen Code,
Roo, Kilo, Crush…): `npx freellmapi setup-<agente> --url URL --api-key KEY --dry-run`.
Gli agenti OpenAI vogliono `URL/v1`; Claude Code vuole la radice `URL`.
