# 04 · Deploy su PC sempre acceso (Windows / macOS / Linux)

Scegli questa strada se il PC dove lavori resta acceso. Niente Docker necessario.

## 1. FreeLLMAPI (app desktop)

1. Scarica l'installer da [Releases](https://github.com/tashfeenahmed/freellmapi/releases/latest)
   (Windows `.exe` Setup, macOS `.dmg` arm64/x64, Linux AppImage/.deb).
2. Avvia. Icona nel tray → **Open Dashboard** (http://127.0.0.1:31415). Nessuna password.
3. Tray → **Copy Key**: è la *unified key* `freellmapi-…` che userai ovunque.
4. Impostazioni → attiva l'avvio al login.
5. Pagina **Keys** → **Agent compatibility** → attiva **MCP**.
6. Aggiungi le key dei provider ([02](02-provider-e-account.md)).

L'app si aggiorna da sola e fa un backup del DB prima di ogni update. I dati stanno in
`%APPDATA%\FreeLLMAPI\` · `~/Library/Application Support/FreeLLMAPI/` · `~/.config/FreeLLMAPI/`.

Porta: **31415** (non 3001). Usala in tutti i comandi: `--url http://127.0.0.1:31415`.

## 2. Antigravity (facoltativo)

Prima leggi [08](08-sicurezza-e-rischi.md). Poi:

```bash
cp .env.example .env            # compila ANTIGRAVITY_PROXY_API_KEY, ANTIGRAVITY_WEBUI_PASSWORD, BRIDGE_API_KEY
npm install -g pm2 antigravity-claude-proxy@2.9.1
pm2 start deploy/pm2/ecosystem.config.cjs && pm2 save
```

- **Windows**: avvio automatico al login con
  `powershell -ExecutionPolicy Bypass -File deploy\windows\install-autostart.ps1`
- **macOS / Linux**: `pm2 startup` e lancia il comando che stampa.

Aggiungi gli account Google: apri http://localhost:8080 → **Add Account** (usa account secondari).
Controllo quote: `curl "http://localhost:8080/account-limits?format=table"`.

Poi in FreeLLMAPI: **Keys → Custom endpoint**
- Base URL: `http://127.0.0.1:3005/v1`
- API key: il valore di `BRIDGE_API_KEY`
- Modelli: `antigravity-claude-opus-4-6-thinking`, `antigravity-claude-sonnet-4-6-thinking`,
  `antigravity-gemini-3-pro` (o quelli che `curl -H "Authorization: Bearer $BRIDGE_API_KEY" http://127.0.0.1:3005/v1/models` elenca).
  Marca **Tools** e **Vision**.

## 3. Catena e verifica

```bash
python scripts/curator.py apply --dry-run
python scripts/curator.py apply
FREELLMAPI_API_KEY=freellmapi-... python scripts/doctor.py --url http://127.0.0.1:31415 --chat
```

Poi [06](06-claude-code-e-antigravity.md) per collegare Claude Code e Antigravity IDE.

## Consigli per un PC sempre acceso

- Disattiva sospensione/ibernazione quando è collegato alla corrente.
- Windows: escludi la cartella dati di FreeLLMAPI da OneDrive/sync.
- Vuoi usarlo da laptop o telefono? Installa [Tailscale](https://tailscale.com) su entrambi e usa
  l'IP Tailscale. Non aprire porte sul router di casa.
