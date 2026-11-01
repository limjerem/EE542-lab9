param([switch]$Stop,[switch]$Tunnel)
$ErrorActionPreference='Stop'
$labRoot=Split-Path -Parent $PSScriptRoot
$labWork=Join-Path $labRoot 'work'
$labLogs=Join-Path $labWork 'logs'
$labStateFile=Join-Path $labWork 'part4-process.json'
$labPython=Join-Path $labRoot '.venv\Scripts\python.exe'
New-Item -ItemType Directory -Force -Path $labLogs | Out-Null
if($Stop){
    if(Test-Path -LiteralPath $labStateFile){
        $labSaved=Get-Content -LiteralPath $labStateFile -Raw | ConvertFrom-Json
        $labProcess=Get-Process -Id $labSaved.processId -ErrorAction SilentlyContinue
        if($labProcess -and $labProcess.StartTime.ToUniversalTime().Ticks.ToString() -eq $labSaved.startTicks){Stop-Process -Id $labProcess.Id;Write-Output 'Stopped Part 4 website.'}
        Remove-Item -LiteralPath $labStateFile
    }
    return
}
if(-not(Test-Path -LiteralPath (Join-Path $labRoot 'local_artifacts\part4\corpus-state.json'))){throw 'Prepare the corpus with .venv\Scripts\python.exe -B -m part4.prepare first.'}
$labExisting=@(Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
$labReady=$false
if($labExisting.Count){
    try{$labReady=(Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/ads/health' -TimeoutSec 5).ready -eq $true}catch{}
    if(-not $labReady){
        $labOldFile=Join-Path $labWork 'part1-processes.json'
        if(-not(Test-Path -LiteralPath $labOldFile)){throw 'Port 8000 is occupied by an unrecorded service.'}
        $labOld=Get-Content -LiteralPath $labOldFile -Raw | ConvertFrom-Json
        $labEntry=@($labOld.services | Where-Object {$_.name -eq 'Website'})
        if($labEntry.Count -ne 1 -or $labExisting.Count -ne 1 -or $labExisting[0] -ne $labEntry[0].processId){throw 'Port 8000 does not match the recorded Lab9 website.'}
        $labProcess=Get-Process -Id $labExisting[0]
        if($labProcess.StartTime.ToUniversalTime().Ticks.ToString() -ne $labEntry[0].startTicks){throw 'The recorded website PID has been reused.'}
        Stop-Process -Id $labProcess.Id
        Write-Output 'Stopped the recorded Part 1 website to load the combined Part 4 application.'
    }
}
if(-not $labReady){
    $labProcess=Start-Process -FilePath $labPython -ArgumentList @('-B','-m','uvicorn','part4.app:app','--host','0.0.0.0','--port','8000') -WorkingDirectory $labRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $labLogs 'part4.stdout.log') -RedirectStandardError (Join-Path $labLogs 'part4.stderr.log') -PassThru
    for($labAttempt=0;$labAttempt -lt 60;$labAttempt++){
        Start-Sleep -Milliseconds 500
        try{$labReady=(Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/ads/health' -TimeoutSec 2).ready -eq $true}catch{}
        if($labReady){break}
        $labProcess.Refresh();if($labProcess.HasExited){break}
    }
    if(-not $labReady){throw ('Part 4 failed to start. See '+(Join-Path $labLogs 'part4.stderr.log'))}
    $labOwner=@(Get-NetTCPConnection -State Listen -LocalPort 8000 | Select-Object -ExpandProperty OwningProcess -Unique)
    if($labOwner.Count -ne 1){throw 'Could not identify the Part 4 website process.'}
    $labProcess=Get-Process -Id $labOwner[0]
    $labEntry=@{name='Website';processId=$labProcess.Id;startTicks=$labProcess.StartTime.ToUniversalTime().Ticks.ToString();port=8000;application='part4.app:app'}
    $labEntry | ConvertTo-Json | Set-Content -LiteralPath $labStateFile -Encoding utf8
    $labOldFile=Join-Path $labWork 'part1-processes.json'
    $labOthers=@();if(Test-Path -LiteralPath $labOldFile){$labOthers=@((Get-Content -LiteralPath $labOldFile -Raw | ConvertFrom-Json).services | Where-Object {$_.name -ne 'Website'})}
    @{services=@($labOthers)+@($labEntry)} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $labOldFile -Encoding utf8
}
Write-Output 'ADS Study Companion: http://localhost:8000/ads/'
if($Tunnel){
    & (Join-Path $PSScriptRoot 'start_part2_tunnel.ps1') -SkipWebsiteStart -SkipConfigure
    $labTunnel=Get-Content -LiteralPath (Join-Path $labWork 'part2-tunnel-process.json') -Raw | ConvertFrom-Json
    & $labPython -B (Join-Path $PSScriptRoot 'configure_part4.py') --url $labTunnel.origin
    if($LASTEXITCODE -ne 0){throw 'Part 4 Android configuration failed.'}
    Write-Output ('HTTPS application: '+$labTunnel.origin+'/ads/')
    Write-Output 'If this origin changed, build Generate APKs in Android Studio and reinstall the APK.'
}
