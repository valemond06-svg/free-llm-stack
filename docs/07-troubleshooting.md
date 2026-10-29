# 07 · Troubleshooting

Primo passo sempre: `python scripts/doctor.py --url URL` (con `FREELLMAPI_API_KEY` impostata).
Poi `python scripts/curator.py report`.

| Sintomo | Causa probabile | Soluzione |
|---|---|---|
| `claude mcp list`: freellmapi ✗ / `ECONNREFUSED` | FreeLLMAPI spento | Avvia l'app (tray) o `docker compose up -d`. Controlla la porta: desktop 31415, Docker 3001. |
| MCP risponde 403 | MCP disattivato | Dashboard → Keys → Agent compatibility → MCP on. |
| 401 su `/v1` o `/mcp` | Key sbagliata | Copia di nuovo la unified key (tray → Copy Key o Keys header). |
| La catena non segue l'ordine voluto | Profilo attivo con la sua catena | `curator.py apply` (scrive anche il profilo). Non modificare `fallback_config` a mano. |
| Dopo un update tornano centinaia di modelli nella catena | `auto_include_new_models` riattivato | Rilancia `curator.py apply`/`auto`. |
| Google: `429 Resource has been exhausted` | Quota del progetto finita | Più key da progetti diversi; la catena passa comunque al prossimo. |
| Google: `402 prepayment credits are depleted` | Progetto con fatturazione | Usa key da progetti **senza** billing. |
| UnoRouter: `403 consent_required` / `needs your consent for these providers` | Consenso provider non dato | Decisione dell'utente (i provider conservano/usano i prompt): o `scripts/unorouter_consent.py --grant` dopo il suo ok esplicito, o disattiva le key UnoRouter e rilancia `curator.py apply`. |
| Antigravity: `SUBSCRIPTION_REQUIRED` (403) | Modello non incluso negli account gratuiti (es. Sonnet 4.6, Gemini 2.5 Pro) | Disattiva quel modello custom in FreeLLMAPI; usa Opus 4.6 Thinking / Gemini 3 Flash. |
| Antigravity Gemini 3 Pro risponde "no longer available" con HTTP 200 | Falso successo: il fallback non scatta | Togli Gemini 3 Pro dalla catena. |
| MCP `freellmapi` ✗ dopo ogni riavvio del PC | App portatile (zip) senza avvio automatico | Collegamento a `FreeLLMAPI.exe` in `shell:startup`. |
| Bridge sotto pm2 non ascolta (nessun "listening" nei log) | Versione vecchia di `bridge/server.js` | Aggiorna il repo: ora riconosce l'avvio da pm2. |
| xKiro: `temporarily unavailable due to high demand` | Sovraccarico lato loro | Niente da fare; il fallback lo gestisce. |
| Zhipu: `429` (messaggio in cinese) | Sovraccarico / rate limit | Tenerlo in basso nella catena. |
| NVIDIA: `stream stalled 90000ms` | Modello molto lento | Normale ogni tanto; se frequente, abbassa Nemotron nella catena. |
| `fallback time budget expired` | Troppi modelli lenti di fila | Metti in alto modelli veloci (Gemini Flash, Groq). |
| Modelli Antigravity sempre in errore | Bridge o proxy giù, o nessun account | `curl URL_BRIDGE/health`; WebUI proxy → account validi? `account-limits`. |
| Bridge: `cannot reach Antigravity proxy` | Proxy non partito o URL errato | Docker: `UPSTREAM_URL=http://antigravity-proxy:8080`; nativo: `http://127.0.0.1:8080`. |
| Account Antigravity "needs re-auth" o sparito | Token revocato / ban | Rimuovi e riaggiungi; se è un ban vedi [08](08-sicurezza-e-rischi.md). |
| `curator.py`: `database not found` | Percorso DB diverso | `--db PATH`. Docker: `data/freellmapi/freeapi.db`. |
| `curator.py`: `attempt to write a readonly database` (Linux) | File del container | `sudo python3 scripts/curator.py ...` |
| `curator.py apply`: molti `[missing]` | Modelli rinominati/ritirati | Aggiorna `config/chain.json` coi nomi attuali (dashboard → Models) o usa `auto`. |
| Container FreeLLMAPI non raggiunge i provider | Rete/IPv6/proxy | Vedi "Providers unreachable" nella [guida install ufficiale](https://github.com/tashfeenahmed/freellmapi/blob/main/docs/en/install/01-install.md). |
| Password dashboard dimenticata (server) | — | "Forgot password?" → il codice è nei log: `docker compose logs freellmapi`. |

Log: app desktop → tray → **Open Logs Folder**; Docker → `docker compose logs -f <servizio>`;
pm2 → `pm2 logs`.
