# Aggiungi al profilo PowerShell ($PROFILE):   . C:\Dev\free-llm-stack\claude-code\aliases.ps1
# Richiede la variabile utente FREELLMAPI_API_KEY (setx FREELLMAPI_API_KEY "freellmapi-...")

$FreeLlmStack = Split-Path -Parent $PSScriptRoot
if (-not $env:FREELLMAPI_URL) { $env:FREELLMAPI_URL = 'http://100.119.96.109:3011' }  # VPS Tailscale default; fallback locale: 127.0.0.1:31415
if (-not $env:FREELLMAPI_API_KEY) { $env:FREELLMAPI_API_KEY = 'freellmapi-...' }

function claude-free {
    $env:ANTHROPIC_BASE_URL = $env:FREELLMAPI_URL
    $env:ANTHROPIC_AUTH_TOKEN = $env:FREELLMAPI_API_KEY
    $env:ANTHROPIC_API_KEY = $env:FREELLMAPI_API_KEY
    $oldOAuth = $env:CLAUDE_CODE_OAUTH_TOKEN
    $env:CLAUDE_CODE_OAUTH_TOKEN = ""
    try {
        claude @args
    } finally {
        Remove-Item Env:ANTHROPIC_BASE_URL, Env:ANTHROPIC_AUTH_TOKEN, Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
        $env:CLAUDE_CODE_OAUTH_TOKEN = $oldOAuth
    }
}

function claude-antigravity {
    $env:ANTHROPIC_BASE_URL = if ($env:ANTIGRAVITY_ANTHROPIC_URL) { $env:ANTIGRAVITY_ANTHROPIC_URL } else { 'http://127.0.0.1:8080' }
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
