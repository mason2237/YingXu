# Elevate only the checksum-verified diagnostic executable, for one bounded capture.
param(
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [ValidateRange(30,600)][int]$Seconds = 240,
    [int]$TargetProcessId = 0
)
$ErrorActionPreference = 'Stop'
# Node may inherit a PowerShell 7 PSModulePath; load only Windows built-ins.
Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Utility/Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Management/Microsoft.PowerShell.Management.psd1') -ErrorAction Stop
$YingXuRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$YingXuCaptureDirectory = [IO.Path]::GetFullPath($OutputDirectory)
$YingXuAllowed = [IO.Path]::GetFullPath((Join-Path $YingXuRoot 'work/test-results')) + [IO.Path]::DirectorySeparatorChar
if (-not $YingXuCaptureDirectory.StartsWith($YingXuAllowed, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Capture output must stay inside this project work/test-results directory.'
}
$YingXuExecutable = Join-Path $YingXuRoot 'work/tools/PresentMon-2.6.0-x64.exe'
$YingXuDigest = (Get-FileHash -LiteralPath $YingXuExecutable -Algorithm SHA256).Hash.ToLowerInvariant()
if ($YingXuDigest -ne 'b2a706bc6ad475749e3b7e3409263aa1e6906d45bdcf993f6dbc0f660188f1af') {
    throw 'The PresentMon binary does not match the reviewed official release.'
}
New-Item -ItemType Directory -Path $YingXuCaptureDirectory -Force | Out-Null
$YingXuCsv = Join-Path $YingXuCaptureDirectory 'presentmon.csv'
if (Test-Path -LiteralPath $YingXuCsv) {throw 'Use a fresh capture directory; existing evidence must not be overwritten.'}
$YingXuSession = 'YingXuPresentation-' + [Guid]::NewGuid().ToString('N')
$YingXuTarget = @('--process_name','electron.exe')
if ($TargetProcessId -gt 0) {
    $YingXuTargetProcess = Get-Process -Id $TargetProcessId -ErrorAction Stop
    $YingXuElectron = [IO.Path]::GetFullPath((Join-Path $YingXuRoot 'work/tools/electron-45.0.0/electron.exe'))
    if (-not [String]::Equals($YingXuTargetProcess.Path, $YingXuElectron, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'The capture target must be this project Electron runtime.'
    }
    $YingXuTarget = @('--process_id',"$TargetProcessId")
}
$YingXuArguments = $YingXuTarget + @('--output_file',('"'+$YingXuCsv+'"'),
    '--no_console_stats','--qpc_time_ms','--v2_metrics','--write_display_metadata',
    '--timed',"$Seconds",'--terminate_after_timed','--session_name',$YingXuSession)
$YingXuRecord = [ordered]@{requestedAt=[DateTimeOffset]::Now.ToString('o');seconds=$Seconds;sha256=$YingXuDigest;
    session=$YingXuSession;csv=$YingXuCsv;targetProcessId=$TargetProcessId;permissionsChanged=$false;applicationElevated=$false}
try {
    $YingXuCapture = Start-Process -FilePath $YingXuExecutable -ArgumentList $YingXuArguments -Verb RunAs -WindowStyle Hidden -WorkingDirectory (Join-Path $env:WINDIR 'System32') -PassThru
    $YingXuRecord.processId = $YingXuCapture.Id
    $YingXuRecord.launched = $true
    $YingXuRecord | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $YingXuCaptureDirectory 'capture.json') -Encoding utf8
    $YingXuRecord | ConvertTo-Json -Compress
} catch {
    $YingXuRecord.launched = $false
    $YingXuRecord.error = $_.Exception.Message
    $YingXuRecord | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $YingXuCaptureDirectory 'capture.json') -Encoding utf8
    $YingXuRecord | ConvertTo-Json -Compress
    exit 2
}
