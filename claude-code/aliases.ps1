# Aggiungi al profilo PowerShell ($PROFILE):   . C:\percorso\free-llm-stack\claude-code\aliases.ps1
# Richiede la variabile utente FREELLMAPI_API_KEY (setx FREELLMAPI_API_KEY "freellmapi-...")

$FreeLlmStack = Split-Path -Parent $PSScriptRoot
if (-not $env:FREELLMAPI_URL) { $env:FREELLMAPI_URL = 'http://127.0.0.1:31415' }  # desktop app; server/Docker: http://localhost:3001

function claude-free { npx -y freellmapi launch --url $env:FREELLMAPI_URL @args }

function claude-antigravity {
    $env:ANTHROPIC_BASE_URL = 'http://localhost:8080'
    $env:ANTHROPIC_AUTH_TOKEN = if ($env:ANTIGRAVITY_PROXY_API_KEY) { $env:ANTIGRAVITY_PROXY_API_KEY } else { 'test' }
    $env:ANTHROPIC_MODEL = 'claude-opus-4-6-thinking'
    try { claude @args } finally { Remove-Item Env:ANTHROPIC_BASE_URL, Env:ANTHROPIC_AUTH_TOKEN, Env:ANTHROPIC_MODEL -ErrorAction SilentlyContinue }
}

function llm-optimize {
    python "$FreeLlmStack\scripts\curator.py" auto --dry-run
    if ((Read-Host 'Applico? [y/N]') -eq 'y') { python "$FreeLlmStack\scripts\curator.py" auto }
}
function llm-chain { python "$FreeLlmStack\scripts\curator.py" report }
function llm-doctor { python "$FreeLlmStack\scripts\doctor.py" --url $env:FREELLMAPI_URL }
