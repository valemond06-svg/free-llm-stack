# Aggiungi a ~/.bashrc o ~/.zshrc:   source /percorso/free-llm-stack/claude-code/aliases.sh
# Richiede: export FREELLMAPI_API_KEY=freellmapi-...   (meglio in un file non versionato)

FREE_LLM_STACK="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
export FREELLMAPI_URL="${FREELLMAPI_URL:-http://localhost:3001}"   # desktop app: http://127.0.0.1:31415

# Claude Code interamente su FreeLLMAPI (quando finisce il limite delle 5 ore).
alias claude-free='npx -y freellmapi launch --url "$FREELLMAPI_URL"'

# Claude Code direttamente sugli account Antigravity (Opus/Sonnet thinking). Rischio ban: vedi docs/08.
alias claude-antigravity='ANTHROPIC_BASE_URL=http://localhost:8080 ANTHROPIC_AUTH_TOKEN="${ANTIGRAVITY_PROXY_API_KEY:-test}" ANTHROPIC_MODEL=claude-opus-4-6-thinking command claude'

# Ricalibra la catena dopo nuove key/provider (prima mostra cosa cambierebbe).
alias llm-optimize='python3 "$FREE_LLM_STACK/scripts/curator.py" auto --dry-run && read -p "Applico? [y/N] " a && [ "$a" = y ] && python3 "$FREE_LLM_STACK/scripts/curator.py" auto'
alias llm-chain='python3 "$FREE_LLM_STACK/scripts/curator.py" report'
alias llm-doctor='python3 "$FREE_LLM_STACK/scripts/doctor.py" --url "$FREELLMAPI_URL"'
