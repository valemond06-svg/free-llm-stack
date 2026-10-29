# Hybrid Claude Code + FreeLLMAPI

<!-- Incolla in ~/.claude/CLAUDE.md (regole globali). Sostituisci <REPO> con il percorso del repo free-llm-stack. -->

## Smart Delegation

Quando lavori con l'abbonamento Claude nativo, delega al tool MCP `ask_freellmapi`
(server `freellmapi`, `model="auto"`; `model="fusion"` per domande dove serve più di un parere)
i lavori ad alto consumo di token e a basso rischio:

1. Lettura e riassunto di file lunghi, log, documentazione (>500 righe)
2. Ricerca esplorativa e analisi di dipendenze (anche `web_search` dello stesso server)
3. Boilerplate: scaffolding, file di config, template CRUD
4. Bozze di unit test e mock
5. Trasformazioni di dati (JSON/CSV, pulizia, migrazioni di formato)
6. Script di riorganizzazione file (rename/move in batch)

Tieni i token nativi per: orchestrazione e decisioni di architettura, modifiche multi-file
critiche, debugging con stato complesso, review finale e sicurezza.

Regole:
- Il risultato di `ask_freellmapi` è una bozza di un modello più debole: verificalo prima di usarlo.
- Non mandare a FreeLLMAPI segreti, credenziali o dati personali: passa per provider terzi gratuiti.
- Se `freellmapi` non risponde, chiama `healthcheck`; se è giù, lavora in nativo e dillo.

## Manutenzione

Quando aggiungo provider o API key, o il catalogo FreeLLMAPI si aggiorna:
`python <REPO>/scripts/curator.py auto --dry-run`, mostrami il report, poi rilancia senza `--dry-run` se approvo.
Verifica generale: `python <REPO>/scripts/doctor.py`.
