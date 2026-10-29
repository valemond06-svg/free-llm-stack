# 05 · Deploy su VPS (Ubuntu/Debian, 24/7)

Basta una VPS piccola: FreeLLMAPI usa ~40 MB di RAM a riposo. 1 vCPU / 1 GB va bene
(Hetzner, Oracle Free Tier ARM, Contabo…). L'immagine è amd64 + arm64.

## 1. Preparazione

```bash
sudo apt update && sudo apt install -y git python3 curl openssl ufw
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

# firewall: solo SSH. Nessuna porta del stack va aperta al pubblico.
sudo ufw allow OpenSSH && sudo ufw enable
```

## 2. Stack

```bash
git clone <URL-DI-QUESTO-REPO> ~/free-llm-stack && cd ~/free-llm-stack
cp .env.example .env
sed -i "s/^ENCRYPTION_KEY=.*/ENCRYPTION_KEY=$(openssl rand -hex 32)/" .env
# se usi Antigravity, genera anche questi tre:
for v in ANTIGRAVITY_PROXY_API_KEY ANTIGRAVITY_WEBUI_PASSWORD BRIDGE_API_KEY; do
  sed -i "s/^$v=.*/$v=$(openssl rand -hex 24)/" .env; done
chmod 600 .env

docker compose up -d                          # solo FreeLLMAPI
docker compose --profile antigravity up -d    # + proxy Antigravity e bridge
docker compose ps
```

**Salva `ENCRYPTION_KEY` in un password manager.** Senza, le key nel DB sono perse.

## 3. Accedere alle dashboard (dal tuo PC)

Tutto ascolta solo su `127.0.0.1` della VPS. Usa un tunnel SSH:

```bash
ssh -L 3001:127.0.0.1:3001 -L 8080:127.0.0.1:8080 utente@ip-vps
```

Poi sul tuo PC: http://localhost:3001 (FreeLLMAPI) e http://localhost:8080 (account Antigravity).
Al primo accesso FreeLLMAPI chiede di creare email + password (o usa `admin` nella config
dichiarativa). Login Google sul proxy da remoto: modalità **Manual Authorization** nella WebUI
(copi l'URL OAuth, autorizzi sul tuo PC, incolli il codice).

Alternativa comoda e sicura: **Tailscale** sulla VPS e sui tuoi dispositivi, poi
`HOST_BIND=<ip-tailscale>` in `.env`.

## 4. Configurazione

1. Dashboard → **Keys**: aggiungi key provider, copia la unified key, attiva **MCP**.
2. Se usi Antigravity: aggiungi gli account nella WebUI del proxy, poi in FreeLLMAPI
   **Keys → Custom endpoint** con Base URL `http://antigravity-bridge:3005/v1` (nome del servizio
   Docker, non localhost) e key = `BRIDGE_API_KEY`. Modelli come in [04](04-pc-sempre-acceso.md).
   Oppure usa la config dichiarativa (`config/freellmapi.config.example.json`).
3. Catena: `sudo python3 scripts/curator.py apply` (il DB è in `data/freellmapi/`, di proprietà
   dell'utente del container).
4. Verifica: `FREELLMAPI_API_KEY=... python3 scripts/doctor.py --chat`.

## 5. Usarla dai tuoi PC

Claude Code sul tuo PC deve raggiungere la VPS. Due opzioni:
- **Tailscale** (consigliato): `http://<ip-tailscale-vps>:3001/mcp`.
- **Tunnel SSH fisso**: `ssh -N -L 3001:127.0.0.1:3001 utente@ip-vps` (con `autossh` per tenerlo su).

Esposizione pubblica con dominio + HTTPS: possibile con `deploy/caddy/Caddyfile`, ma FreeLLMAPI è
single-user e protetto solo dalla unified key: fallo solo se sai cosa stai facendo.

## Manutenzione

```bash
docker compose pull && docker compose up -d     # aggiornare FreeLLMAPI
docker compose --profile antigravity build --pull && docker compose --profile antigravity up -d
docker compose logs -f freellmapi
```

Backup: FreeLLMAPI ha backup cifrati (dashboard → Backups, oppure `FREEAPI_DB_BACKUP_PATH`
in `.env`). In più, copia periodicamente `data/` e `.env` fuori dalla VPS.

## Senza Docker

`deploy/systemd/` contiene unit per FreeLLMAPI da sorgente, proxy e bridge. Crea un utente `llm`,
metti il repo in `/opt/free-llm-stack`, adatta i percorsi, poi
`sudo systemctl enable --now freellmapi antigravity-proxy antigravity-bridge`.
