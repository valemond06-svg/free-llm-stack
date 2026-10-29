# 03 · Modelli consigliati e catena `auto`

## La catena consigliata

È in `config/chain.json` (con il motivo di ogni posizione). In breve:

| Pos | Modello | Provider | Note |
|---|---|---|---|
| 1–3 | Claude Opus 4.6 Thinking → Claude Sonnet 4.6 Thinking → Gemini 3 Pro | Antigravity (bridge) | Solo se Antigravity è attivo; altrimenti vengono saltati. |
| 4 | Nemotron 3 Ultra 550B | NVIDIA | Il più affidabile. |
| 5–6 | Qwen3.8 Max → Qwen3.8 Omni Flash | xKiro | IQ top, 1M contesto; Omni ha la visione. |
| 7–9 | Gemini 3.7 → 3.6 → 3.5 Flash | Google | Veloci, quota per modello. |
| 10 | Qwen3.8 27B | Groq | Velocità LPU. |
| 11–12 | GLM 5.3 → GLM 5.3 Flash | UnoRouter | IQ alto ma 1 RPM: **mai** nelle prime posizioni. |
| 13–14 | Qwen3.7 Max → Qwen3.6 Plus | xKiro | Stessa quota di xKiro. |
| 15 | Poolside Laguna XS 2.1 | NVIDIA | Specialista coding. |
| 16 | GLM-4.7 Flash | Zhipu | Lento, riserva. |
| 17–18 | Gemini Flash (latest) → Gemini 3.8 Flash | Google | Il 3.8 è forte ma lento. |
| 19 | GPT-OSS 120B | Groq | Veloce per script. |
| 20 | Mistral Medium 3.5 | xKiro | Visione + tool. |
| 21–22 | Mistral Code → Command A Reasoning | Mistral, Cohere | Chiusura. |

I nomi dei modelli cambiano. `curator.py apply` segnala come `[missing]` quelli che non esistono
più nel catalogo: sostituiscili in `chain.json` con il successore (dashboard → Models).

## Le regole (usate da `curator.py auto`)

1. **Gatekeeper** — scarta subito:
   - modelli senza **tool calling** (rompono gli agenti di coding);
   - modelli non-chat: guard/safety/moderation/parse/translate/fim/tts/whisper/voxtral/embedding/robotics/rerank/ocr;
   - intelligenza bassa (`intelligence_rank > 90`; nel DB rank basso = migliore);
   - varianti lite/mini (Flash-Lite, Ministral 3B/8B/14B, GPT-OSS 20B) che consumano la stessa quota dei modelli forti.
2. **Anti-cannibalizzazione** — per ogni provider tiene solo i 4 migliori (+1 con visione se c'è):
   i modelli dello stesso provider spesso condividono il budget mensile.
3. **Posizionamento** — punteggio = intelligenza 55% + **affidabilità reale** 25% (successi negli
   ultimi 14 giorni dai log di FreeLLMAPI) + velocità 20%, +8 se contesto ≥ 1M, +5 se ≥ 256K.
   Modelli con RPM ≤ 2 o molto lenti non entrano mai nelle prime 5 posizioni (bloccherebbero
   le tool call consecutive degli agenti).
4. I modelli Antigravity sono **fissati in cima** (`rules.pinned_top`).

Tutte le soglie sono in `chain.json → rules`.

## Comandi

```bash
python scripts/curator.py report            # la catena che il router usa DAVVERO adesso
python scripts/curator.py apply --dry-run   # anteprima della catena consigliata
python scripts/curator.py apply             # la applica (fa prima un backup del DB)
python scripts/curator.py auto --dry-run    # anteprima della catena calcolata
python scripts/curator.py auto              # la applica
```

`--db PATH` o `FREELLMAPI_DB_PATH` se il DB non è nel posto standard. Con Docker il DB è in
`data/freellmapi/freeapi.db` (su Linux serve `sudo`: il file è dell'utente `node` del container).

**Quando rilanciare:** dopo aver aggiunto/rimosso key o provider, dopo un aggiornamento del
catalogo (FreeLLMAPI lo sincronizza da solo), o se `report` mostra modelli che falliscono sempre.

## Strategia di routing

`priority` (la catena in ordine) è quella che usiamo. FreeLLMAPI ne ha altre (`balanced`,
`smartest`, `fastest`, `reliable`) selezionabili dalla dashboard o dall'MCP (`set_routing_strategy`).
Con `fusion` più modelli rispondono e uno sintetizza: utile per domande difficili, consuma di più.
