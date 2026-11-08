# Caricato dai profili PowerShell. Claude Code collega l'MCP una sola volta, all'avvio: se il
# terminale ripristinato lo lancia prima di FreeLLMAPI, l'MCP resta in ECONNREFUSED per tutta la
# sessione. Questo wrapper avvia FreeLLMAPI se serve e aspetta la porta prima di lanciare claude.

$FreeLlmStack = Split-Path -Parent $PSScriptRoot
if (-not $env:FREELLMAPI_EXE) { $env:FREELLMAPI_EXE = 'D:\AI\FreeLLMAPI-0.16.12-win\FreeLLMAPI.exe' }

function Test-FreeLlmPort {
    $client = New-Object System.Net.Sockets.TcpClient
    try { return $client.ConnectAsync('127.0.0.1', 31415).Wait(300) }
    catch { return $false }
    finally { $client.Dispose() }
}

function Wait-FreeLlm {
    if (Test-FreeLlmPort) { return }
    if (-not (Get-Process FreeLLMAPI -ErrorAction SilentlyContinue) -and (Test-Path $env:FREELLMAPI_EXE)) {
        Start-Process $env:FREELLMAPI_EXE
    }
    Write-Host 'Attendo FreeLLMAPI...' -ForegroundColor DarkGray
    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline) {
        if (Test-FreeLlmPort) { return }
        Start-Sleep -Milliseconds 500
    }
    Write-Host 'FreeLLMAPI non risponde: Claude parte senza MCP freellmapi.' -ForegroundColor Yellow
}

function claude {
    Wait-FreeLlm
    $real = Get-Command claude -CommandType Application, ExternalScript -ErrorAction Stop | Select-Object -First 1
    # Con $input vuoto la TUI perderebbe lo stdin: lo inoltriamo solo in una pipeline vera.
    if ($MyInvocation.ExpectingInput) { $input | & $real.Source @args } else { & $real.Source @args }
}

function llm-chain { python "$FreeLlmStack\scripts\curator.py" report }
function llm-doctor { python "$FreeLlmStack\scripts\doctor.py" --url http://127.0.0.1:31415 --chat }
