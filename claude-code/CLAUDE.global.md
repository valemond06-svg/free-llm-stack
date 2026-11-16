# Hybrid Claude Code + FreeLLMAPI + Local Vulkan/CUDA

## Smart Multi-Tier Delegation & Agency Orchestrator

Quando affronti progetti o task, opera come **Lead Agency Orchestrator**:
Pianifica la scomposizione modulare e delega ogni sotto-task al tier ottimale:

### Tiers di Esecuzione:
1. **Tier 1 — Fast Cloud (`claude-free --fast`)**:
   - Modelli: Groq Llama-3.3-70B / Cerebras (<0.5s).
   - Task: Scaffolding iniziale, boilerplate, commit message, trasformazioni JSON/CSV, regex, formattazione.
2. **Tier 2 — Local Vulkan/CUDA (`claude-free --local` / PC Fisso `10.10.10.1` o Laptop `ai`)**:
   - Modelli: Qwen3.6-35B-A3B (65k context).
   - Task: Refactoring moduli singoli, unit test e mock, script di riorganizzazione, codice privato o sensibile.
   - Zero quote, costo zero, zero dipendenza da internet.
3. **Tier 3 — Elite Cloud (`claude-free --elite` o default)**:
   - Modelli: Qwen 3.8 Max (1M ctx), Nemotron 550B, Gemini Flash, Claude Sonnet mapping.
   - Task: Architettura distribuita, orchestrazione di sistema, refactoring multi-file critico, sicurezza e review.

### Regole Vincolanti:
- **Segretezza**: Mai inviare chiavi, token o credenziali in chiaro a provider terzi; mascherare sempre come `***`.
- **Gaming Laptop**: Durante sessioni di gioco (`GTA5.exe`), l'AI locale sul laptop rimane in standby; il carico locale va offloadato al PC Fisso via cavo o a FreeLLMAPI.
- **Integrità app-mezzi**: `app-mezzi` è aziendale e appartiene a Valentino. È severamente vietato modificarla o interagire con essa.
- **Chiusura del Lavoro**: Verificare sempre con test automatici e lint, aggiornare le memorie in `claude-context`, riscrivere `last-session-state.md` e sincronizzare il grafo con `rebuild-graph.ps1`.
