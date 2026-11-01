param([switch]$Stop)
$ErrorActionPreference='Stop'
$labRoot=Split-Path -Parent $PSScriptRoot
$labState=Join-Path $labRoot 'work\part3-process.json'
if($Stop){
    if(Test-Path -LiteralPath $labState){
        $entry=Get-Content -LiteralPath $labState -Raw | ConvertFrom-Json
        $process=Get-Process -Id $entry.processId -ErrorAction SilentlyContinue
        if($process -and $process.StartTime.ToUniversalTime().Ticks.ToString() -eq $entry.startTicks){Stop-Process -Id $process.Id;Write-Output 'Stopped Lab9 Part 3.'}
        Remove-Item -LiteralPath $labState
    }
    return
}
$labPython=Join-Path $labRoot '.venv\Scripts\python.exe'
if(-not(Test-Path -LiteralPath $labPython)){throw 'Part 3 virtual environment is missing. See PART3.md.'}
$existing=Get-NetTCPConnection -State Listen -LocalPort 8501 -ErrorAction SilentlyContinue
if($existing){
    if(-not(Test-Path -LiteralPath $labState)){throw 'Port 8501 is occupied. No managed Lab9 Part 3 process is recorded.'}
    $entry=Get-Content -LiteralPath $labState -Raw | ConvertFrom-Json
    $running=Get-Process -Id $entry.processId -ErrorAction SilentlyContinue
    $owners=@($existing | Select-Object -ExpandProperty OwningProcess -Unique)
    if(-not $running -or $running.StartTime.ToUniversalTime().Ticks.ToString() -ne $entry.startTicks -or $owners.Count -ne 1 -or $owners[0] -ne $running.Id){throw 'Port 8501 belongs to another process.'}
    $health=Invoke-WebRequest 'http://127.0.0.1:8501/_stcore/health' -UseBasicParsing -TimeoutSec 5
    if($health.StatusCode -ne 200){throw 'Port 8501 is occupied by an unexpected service.'}
    Write-Output 'Part 3 is already running: http://127.0.0.1:8501'
    return
}
$labLogs=Join-Path $labRoot 'work\logs';New-Item -ItemType Directory -Path $labLogs -Force | Out-Null
$started=Start-Process -FilePath $labPython -WorkingDirectory $labRoot -WindowStyle Hidden -ArgumentList @('-B','-X','utf8','-m','streamlit','run','embedding/upload_app.py','--server.address','127.0.0.1','--server.port','8501','--server.headless','true','--browser.gatherUsageStats','false') -RedirectStandardOutput (Join-Path $labLogs 'part3.stdout.log') -RedirectStandardError (Join-Path $labLogs 'part3.stderr.log') -PassThru
$ready=$false
for($attempt=0;$attempt -lt 40;$attempt++){
    Start-Sleep -Milliseconds 500
    try{$health=Invoke-WebRequest 'http://127.0.0.1:8501/_stcore/health' -UseBasicParsing -TimeoutSec 2;if($health.StatusCode -eq 200){$ready=$true;break}}catch{}
    $started.Refresh();if($started.HasExited){throw 'Part 3 exited. See work\logs\part3.stderr.log.'}
}
if(-not $ready){throw 'Part 3 did not become ready. See work\logs.'}
$owners=@(Get-NetTCPConnection -State Listen -LocalPort 8501 | Select-Object -ExpandProperty OwningProcess -Unique)
if($owners.Count -ne 1){throw 'Could not identify the Part 3 listener.'}
$running=Get-Process -Id $owners[0]
@{processId=$running.Id;startTicks=$running.StartTime.ToUniversalTime().Ticks.ToString();url='http://127.0.0.1:8501';python=$labPython} | ConvertTo-Json | Set-Content -LiteralPath $labState -Encoding utf8
Write-Output 'Part 3 is running: http://127.0.0.1:8501'
