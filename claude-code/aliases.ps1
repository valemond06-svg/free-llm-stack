# Aggiungi al profilo PowerShell ($PROFILE):   . C:\Dev\free-llm-stack\claude-code\aliases.ps1
# Claude-Free Smart Multi-Provider & Agency Orchestrator

$FreeLlmStack = Split-Path -Parent $PSScriptRoot

if (-not $env:FREELLMAPI_API_KEY -or $env:FREELLMAPI_API_KEY -eq 'freellmapi-...') {
    $userKey = [System.Environment]::GetEnvironmentVariable('FREELLMAPI_API_KEY', 'User')
    if ($userKey -and $userKey -ne 'freellmapi-...') {
        $env:FREELLMAPI_API_KEY = $userKey
    } elseif (Test-Path "$env:USERPROFILE\.config\free-llm-stack\api-key.bak") {
        $env:FREELLMAPI_API_KEY = (Get-Content "$env:USERPROFILE\.config\free-llm-stack\api-key.bak" | Select-String -Pattern '^freellmapi-[0-9a-f]{32,}' | Select-Object -First 1).Line.Trim()
    } else {
        $env:FREELLMAPI_API_KEY = 'freellmapi-cc65ebfe697a3ec347fe49caa397e12c33d576fcae39b726'
    }
}

$script:FissoKey = "61e25408bc484a99f8141347eaa6bad2742b5cb94aa21bda564828fd3b55fc81"

function claude-free {
    param([Parameter(ValueFromRemainingArguments=$true)]$ArgsList)
    $env:ANTHROPIC_BASE_URL = 'http://100.119.96.109:3011'
    $env:ANTHROPIC_AUTH_TOKEN = $env:FREELLMAPI_API_KEY
    $env:ANTHROPIC_API_KEY = $env:FREELLMAPI_API_KEY
    $oldOAuth = $env:CLAUDE_CODE_OAUTH_TOKEN
    $env:CLAUDE_CODE_OAUTH_TOKEN = ""
    Remove-Item Env:ANTHROPIC_MODEL -ErrorAction SilentlyContinue
    try {
        claude @ArgsList
    } finally {
        Remove-Item Env:ANTHROPIC_BASE_URL, Env:ANTHROPIC_AUTH_TOKEN, Env:ANTHROPIC_API_KEY, Env:ANTHROPIC_MODEL -ErrorAction SilentlyContinue
        $env:CLAUDE_CODE_OAUTH_TOKEN = $oldOAuth
    }
}

function claude-local {
    param([Parameter(ValueFromRemainingArguments=$true)]$ArgsList)
    
    # Prova prima il cavo diretto Gigabit 10.10.10.1:8080 (2ms)
    $cableOk = $false
    try {
        $res = Invoke-WebRequest -Uri "http://10.10.10.1:8080/v1/models" -Headers @{ Authorization = "Bearer $($script:FissoKey)" } -TimeoutSec 1 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($res.StatusCode -in 200, 401) { $cableOk = $true }
    } catch {}

    if ($cableOk) {
        $env:ANTHROPIC_BASE_URL = 'http://10.10.10.1:8080'
        Write-Host "[claude-free] Collegato a PC Fisso Vulkan via cavo diretto (10.10.10.1:8080)" -ForegroundColor Green
    } else {
        $env:ANTHROPIC_BASE_URL = 'http://100.83.194.37:8080'
        Write-Host "[claude-free] Collegato a PC Fisso Vulkan via Tailscale (100.83.194.37:8080)" -ForegroundColor Cyan
    }

    $env:ANTHROPIC_AUTH_TOKEN = $script:FissoKey
    $env:ANTHROPIC_API_KEY = $script:FissoKey
    $oldOAuth = $env:CLAUDE_CODE_OAUTH_TOKEN
    $env:CLAUDE_CODE_OAUTH_TOKEN = ""
    Remove-Item Env:ANTHROPIC_MODEL -ErrorAction SilentlyContinue
    try {
        claude @ArgsList
    } finally {
        Remove-Item Env:ANTHROPIC_BASE_URL, Env:ANTHROPIC_AUTH_TOKEN, Env:ANTHROPIC_API_KEY, Env:ANTHROPIC_MODEL -ErrorAction SilentlyContinue
        $env:CLAUDE_CODE_OAUTH_TOKEN = $oldOAuth
    }
}

function claude-fisso {
    param([Parameter(ValueFromRemainingArguments=$true)]$ArgsList)
    claude-local @ArgsList
}

function claude-fast {
    param([Parameter(ValueFromRemainingArguments=$true)]$ArgsList)
    $env:ANTHROPIC_BASE_URL = 'http://100.119.96.109:3011'
    $env:ANTHROPIC_AUTH_TOKEN = $env:FREELLMAPI_API_KEY
    $env:ANTHROPIC_API_KEY = $env:FREELLMAPI_API_KEY
    $env:ANTHROPIC_MODEL = 'claude-haiku-4-5'
    $oldOAuth = $env:CLAUDE_CODE_OAUTH_TOKEN
    $env:CLAUDE_CODE_OAUTH_TOKEN = ""
    Write-Host "[claude-free] Modalita FAST attiva (Groq/Cerebras Haiku)" -ForegroundColor Yellow
    try {
        claude @ArgsList
    } finally {
        Remove-Item Env:ANTHROPIC_BASE_URL, Env:ANTHROPIC_AUTH_TOKEN, Env:ANTHROPIC_API_KEY, Env:ANTHROPIC_MODEL -ErrorAction SilentlyContinue
        $env:CLAUDE_CODE_OAUTH_TOKEN = $oldOAuth
    }
}

function claude-elite {
    param([Parameter(ValueFromRemainingArguments=$true)]$ArgsList)
    $env:ANTHROPIC_BASE_URL = 'http://100.119.96.109:3011'
    $env:ANTHROPIC_AUTH_TOKEN = $env:FREELLMAPI_API_KEY
    $env:ANTHROPIC_API_KEY = $env:FREELLMAPI_API_KEY
    $env:ANTHROPIC_MODEL = 'claude-sonnet-4-5'
    $oldOAuth = $env:CLAUDE_CODE_OAUTH_TOKEN
    $env:CLAUDE_CODE_OAUTH_TOKEN = ""
    Write-Host "[claude-free] Modalita ELITE attiva (Qwen 3.8 Max / Nemotron 550B / Gemini Flash)" -ForegroundColor Magenta
    try {
        claude @ArgsList
    } finally {
        Remove-Item Env:ANTHROPIC_BASE_URL, Env:ANTHROPIC_AUTH_TOKEN, Env:ANTHROPIC_API_KEY, Env:ANTHROPIC_MODEL -ErrorAction SilentlyContinue
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
function llm-doctor { python "$FreeLlmStack\scripts\doctor.py" --url (if ($env:FREELLMAPI_URL) { $env:FREELLMAPI_URL } else { 'http://100.119.96.109:3011' }) }
