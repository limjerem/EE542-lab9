param([switch]$Stop)
$ErrorActionPreference = 'Stop'
$labRoot = Split-Path -Parent $PSScriptRoot
$labWork = Join-Path $labRoot 'work'
$labLogs = Join-Path $labWork 'logs'
$labStateFile = Join-Path $labWork 'part1-processes.json'
New-Item -ItemType Directory -Force -Path $labLogs | Out-Null

if ($Stop) {
    if (-not (Test-Path -LiteralPath $labStateFile)) {
        Write-Output 'No managed Part 1 processes are recorded.'
        return
    }
    $labState = Get-Content -LiteralPath $labStateFile -Raw | ConvertFrom-Json
    foreach ($labEntry in $labState.services) {
        $labProcess = Get-Process -Id $labEntry.processId -ErrorAction SilentlyContinue
        if ($labProcess -and $labProcess.StartTime.ToUniversalTime().Ticks.ToString() -eq $labEntry.startTicks) {
            Stop-Process -Id $labProcess.Id
            Write-Output ('Stopped ' + $labEntry.name + ' (PID ' + $labProcess.Id + ').')
        }
    }
    Remove-Item -LiteralPath $labStateFile
    return
}

$labPython = Join-Path $labRoot 'groupchat_app_src\backend\.venv\Scripts\python.exe'
$labBackend = Join-Path $labRoot 'groupchat_app_src\backend'
$labRuntime = Join-Path $labRoot 'tools\llama.cpp\b12023'
$labLlama = Join-Path $labRuntime 'llama-server.exe'
$labModel = Join-Path $labRoot 'models\Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf'
foreach ($labRequired in @($labPython, $labLlama, $labModel)) {
    if (-not (Test-Path -LiteralPath $labRequired -PathType Leaf)) { throw ('Required file missing: ' + $labRequired) }
}
$labManaged = @()
if (Test-Path -LiteralPath $labStateFile) {
    $labManaged = @((Get-Content -LiteralPath $labStateFile -Raw | ConvertFrom-Json).services)
}
$labSpecifications = @(
    @{
        name='Llama'; port=8001; executable=$labLlama; directory=$labRuntime; log='llama';
        arguments=@('-m',('"' + $labModel + '"'),'--host','127.0.0.1','--port','8001','--ctx-size','4096','--parallel','1','-ngl','99','--threads','8','--alias','llama-3.1-8b-instruct','--n-predict','512');
        health='http://127.0.0.1:8001/health'
    },
    @{
        name='Website'; port=8000; executable=$labPython; directory=$labBackend; log='web';
        arguments=@('-B','-m','uvicorn','app:app','--host','0.0.0.0','--port','8000');
        health='http://127.0.0.1:8000/'
    }
)
foreach ($labSpec in $labSpecifications) {
    $labExisting = Get-NetTCPConnection -State Listen -LocalPort $labSpec.port -ErrorAction SilentlyContinue
    if ($labExisting) {
        $labResponse = Invoke-WebRequest -Uri $labSpec.health -UseBasicParsing -TimeoutSec 5
        if ($labResponse.StatusCode -ne 200) { throw ($labSpec.name + ' did not pass its health check.') }
        if ($labSpec.name -eq 'Llama') {
            if (($labResponse.Content | ConvertFrom-Json).status -ne 'ok') { throw 'Port 8001 is not the expected ready model server.' }
        } elseif ($labResponse.Content -notmatch 'Group Chat') { throw 'Port 8000 is not the expected Lab9 website.' }
        Write-Output ($labSpec.name + ' is already running on port ' + $labSpec.port + '.')
        continue
    }
    $labLaunched = Start-Process -FilePath $labSpec.executable -ArgumentList $labSpec.arguments -WorkingDirectory $labSpec.directory -WindowStyle Hidden -RedirectStandardOutput (Join-Path $labLogs ($labSpec.log + '.stdout.log')) -RedirectStandardError (Join-Path $labLogs ($labSpec.log + '.stderr.log')) -PassThru
    $labReady = $false
    for ($labAttempt = 0; $labAttempt -lt 60; $labAttempt++) {
        Start-Sleep -Milliseconds 500
        try {
            $labResponse = Invoke-WebRequest -Uri $labSpec.health -UseBasicParsing -TimeoutSec 2
            if ($labResponse.StatusCode -eq 200) { $labReady = $true; break }
        } catch { }
    }
    if (-not $labReady) { throw ($labSpec.name + ' failed to start. See ' + $labLogs) }
    $labOwner = @(Get-NetTCPConnection -State Listen -LocalPort $labSpec.port | Select-Object -ExpandProperty OwningProcess -Unique)
    if ($labOwner.Count -ne 1) { throw ('Cannot identify the process on port ' + $labSpec.port) }
    $labRunning = Get-Process -Id $labOwner[0]
    $labManaged = @($labManaged | Where-Object { $_.name -ne $labSpec.name }) + @(@{name=$labSpec.name;processId=$labRunning.Id;startTicks=$labRunning.StartTime.ToUniversalTime().Ticks.ToString();port=$labSpec.port})
    @{services=$labManaged} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $labStateFile -Encoding utf8
    Write-Output ($labSpec.name + ' started on port ' + $labSpec.port + '.')
}
Write-Output 'Open http://localhost:8000/ to use the chatbot.'
