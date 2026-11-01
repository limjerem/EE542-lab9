param([switch]$Stop)
$ErrorActionPreference='Stop'
$labRoot=Split-Path -Parent $PSScriptRoot
$labWork=Join-Path $labRoot 'work'
$labLogs=Join-Path $labWork 'logs'
$labStateFile=Join-Path $labWork 'part2-tunnel-process.json'
$labSsh='C:\Windows\System32\OpenSSH\ssh.exe'
$labCurrent=$null
if(Test-Path -LiteralPath $labStateFile){
    $labState=Get-Content -LiteralPath $labStateFile -Raw | ConvertFrom-Json
    if($labState.provider -eq 'localhost.run'){
        $labCandidate=Get-Process -Id $labState.processId -ErrorAction SilentlyContinue
        if($labCandidate -and $labCandidate.ProcessName -eq 'ssh' -and $labCandidate.Path -eq $labSsh -and $labCandidate.StartTime.ToUniversalTime().Ticks.ToString() -eq $labState.startTicks){$labCurrent=$labCandidate}
    }
}
if($Stop){
    if($labCurrent){Stop-Process -Id $labCurrent.Id;Write-Output 'Stopped the Lab9 localhost.run tunnel.'}
    else{Write-Output 'No recorded Lab9 tunnel is running.'}
    if(Test-Path -LiteralPath $labStateFile){Remove-Item -LiteralPath $labStateFile}
    return
}
& (Join-Path $PSScriptRoot 'start_part1.ps1')
if($labCurrent){Write-Output ('Reusing Lab9 HTTPS tunnel: '+$labState.origin);return}
New-Item -ItemType Directory -Path $labLogs -Force | Out-Null
$labKnownHosts=Join-Path $labWork 'localhost-run-known-hosts'
# Service public host key recorded on the first connection; subsequent connections compare it strictly.
if(-not(Test-Path -LiteralPath $labKnownHosts)){
    'localhost.run ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILVqOuSMnyeGDVO1lG6EaG5In/dXABCchhmHKkuRU2s9' | Set-Content -LiteralPath $labKnownHosts -Encoding ascii
}
$labArguments=@('-T','-F','NUL','-o','StrictHostKeyChecking=yes','-o',('UserKnownHostsFile='+$labKnownHosts),'-o','GlobalKnownHostsFile=NUL','-o','HostKeyAlgorithms=ssh-ed25519','-o','BatchMode=yes','-o','PubkeyAuthentication=no','-o','PasswordAuthentication=no','-o','KbdInteractiveAuthentication=no','-o','IdentityAgent=none','-o','ConnectTimeout=15','-o','ServerAliveInterval=30','-o','ServerAliveCountMax=3','-o','ExitOnForwardFailure=yes','-R','80:127.0.0.1:8000','nokey@localhost.run','--','--output','json')
$labStdout=Join-Path $labLogs 'localhost-run.stdout.log'
$labStderr=Join-Path $labLogs 'localhost-run.stderr.log'
$labLaunched=Start-Process -FilePath $labSsh -ArgumentList $labArguments -WorkingDirectory $labRoot -WindowStyle Hidden -RedirectStandardOutput $labStdout -RedirectStandardError $labStderr -PassThru
$labOrigin=''
for($labAttempt=0;$labAttempt -lt 40;$labAttempt++){
    Start-Sleep -Milliseconds 500
    if(Test-Path -LiteralPath $labStdout){$labOrigin=[regex]::Match((Get-Content -LiteralPath $labStdout -Raw),'https://[a-z0-9]+\.lhr\.life').Value}
    if($labOrigin){break}
    $labLaunched.Refresh();if($labLaunched.HasExited){throw ('Tunnel failed. See '+$labStderr)}
}
if(-not $labOrigin){Stop-Process -Id $labLaunched.Id -ErrorAction SilentlyContinue;throw ('No tunnel URL received. See '+$labLogs)}
@{provider='localhost.run';origin=$labOrigin;processId=$labLaunched.Id;startTicks=$labLaunched.StartTime.ToUniversalTime().Ticks.ToString();target='http://127.0.0.1:8000'} | ConvertTo-Json | Set-Content -LiteralPath $labStateFile -Encoding utf8
& (Join-Path $labRoot 'groupchat_app_src\backend\.venv\Scripts\python.exe') -B (Join-Path $PSScriptRoot 'configure_part2.py') --url $labOrigin
if($LASTEXITCODE -ne 0){throw 'TWA origin configuration failed'}
Write-Output ('Lab9 HTTPS tunnel: '+$labOrigin)
Write-Output 'The origin has changed. Rebuild using Android Studio Generate APKs, then reinstall the APK.'
Write-Output 'Keep this computer and the tunnel running during the demo. Stop with scripts\start_part2_tunnel.ps1 -Stop.'
