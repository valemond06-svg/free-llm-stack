# 02 · Provider e account

I numeri sotto vengono dal setup di riferimento (ottobre 2026, ~460 richieste reali analizzate).
I free tier cambiano spesso: FreeLLMAPI aggiorna da solo il catalogo, ma ricontrolla le quote
sulla dashboard (pagina **Keys** e **Analytics**).

> **Termini di servizio.** Più key dentro lo *stesso* account (es. più progetti Google Cloud)
> è uso normale. Creare più *account* per moltiplicare un free tier viola i ToS di molti provider
> e può portare al blocco di tutti gli account. Decidi tu; nel dubbio resta su 1 account per provider.

## Cosa prendere (in ordine di priorità)

| # | Provider | Dove | Key nel setup di riferimento | Consiglio | Perché |
|---|---|---|---|---|---|
| 1 | **Google AI Studio** | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | 4 | **4–6 key da progetti diversi** | Il più veloce dei modelli forti (~6,5 s). Ma è il primo a finire la quota: 77 errori 429 su 183 richieste anche con 4 key. La quota è per progetto. **Non collegare la fatturazione**: un progetto con credito prepagato ha dato `402 credits depleted`. |
| 2 | **NVIDIA NIM** | [build.nvidia.com](https://build.nvidia.com) | 1 | 1–2 | Il più affidabile: 85% di successi. 40 RPM. Lento (~16 s) ma regge. Nemotron 3 Ultra 550B è il cavallo da tiro. |
| 3 | **xKiro** | sito ufficiale xKiro (verifica il dominio) | 4 | 1–2 | Qwen 3.8 Max: intelligenza top, 1M di contesto, ~5M token/giorno. Gli errori sono "high demand" lato loro: più key non aiutano. |
| 4 | **Groq** | [console.groq.com/keys](https://console.groq.com/keys) | 4 | 1–2 | Velocità LPU, ottimo per tool call in serie. 30 RPM. |
| 5 | **UnoRouter** | sito ufficiale UnoRouter (verifica il dominio) | 4 | 1 | GLM 5.3: IQ altissimo ma **1 RPM**. Nel setup di riferimento ha fallito il 100% delle volte per un `403 needs your consent for these providers`: **dalla dashboard UnoRouter va dato il consenso ai provider upstream** dei modelli `:free`. Fallo subito dopo aver creato la key. |
| 6 | **Zhipu / Z.ai** | [z.ai](https://z.ai) o [open.bigmodel.cn](https://open.bigmodel.cn) | 1 | 1 | GLM-4.7 Flash gratis, ma lento (~60 s) e spesso sovraccarico (429). Riserva. |
| 7 | **Mistral** | [console.mistral.ai](https://console.mistral.ai) | 1 | 1 | Mistral Code, 2 RPM. Chiusura catena. |
| 8 | **Cohere** | [dashboard.cohere.com/api-keys](https://dashboard.cohere.com/api-keys) | 1 | 1 | Trial key, poche chiamate al mese. Ultima spiaggia. |
| — | OpenRouter, Cloudflare, ElectronHub… | dalla dashboard | 0–1 | facoltativi | ElectronHub free: 100k token/mese, si esaurisce subito. OpenRouter `:free` utile come riserva extra. |
| ★ | **Antigravity** (account Google) | WebUI del proxy (`:8080`) | — | **2–3 account secondari**, mai quello principale | Claude Opus/Sonnet 4.6 thinking e Gemini Pro. Rischio ban concreto: vedi [08](08-sicurezza-e-rischi.md). Max 10 account nel proxy. |

## Minimo per partire

Google (2 key) + NVIDIA + Groq + xKiro. Bastano per una catena `auto` decente. Il resto si
aggiunge dopo; ogni volta: `python scripts/curator.py auto --dry-run`.

## Come aggiungere le key

- **Dashboard** (più semplice): pagina **Keys** → aggiungi → il pallino diventa verde dopo il test.
- **Da terminale**: `npx freellmapi keys add <platform>` (serve un token di sessione dashboard,
  vedi `npx freellmapi --help`).
- **Config dichiarativa** (server/Docker, ripetibile): `config/freellmapi.config.example.json` →
  copia in `secrets/freellmapi.config.json`, compila, metti `FREEAPI_CONFIG_PATH=/secrets/freellmapi.config.json`
  in `.env`, riavvia. È idempotente. Il file contiene key in chiaro: resta in `secrets/` (gitignored).

Dopo ogni modifica alle key: `python scripts/curator.py apply` (o `auto`).
