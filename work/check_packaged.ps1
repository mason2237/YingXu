param([string]$Executable)
$ErrorActionPreference = 'Stop'
if (-not $Executable) {
    $Executable = Join-Path $PSScriptRoot '..\outputs\stage1\YingXuSubtitleOrganizer.exe'
}
$appExecutable = (Resolve-Path -LiteralPath $Executable).Path
$startedAt = Get-Date
$appProcess = Start-Process -FilePath $appExecutable -WindowStyle Hidden -PassThru
if ($appProcess.WaitForExit(5000)) {
    throw "Application exited during startup with code $($appProcess.ExitCode)"
}
$ownProcesses = @(Get-Process -Name 'YingXuSubtitleOrganizer' | Where-Object {
    $_.Path -eq $appExecutable -and $_.StartTime -ge $startedAt
})
$windowProcesses = @($ownProcesses | Where-Object { $_.MainWindowHandle -ne 0 })
if ($windowProcesses.Count -eq 0) {
    foreach ($entry in $ownProcesses) { Stop-Process -Id $entry.Id }
    throw 'No application window was detected.'
}
foreach ($entry in $windowProcesses) {
    Write-Output "Window started: $($entry.MainWindowTitle)"
    [void]$entry.CloseMainWindow()
}
if (-not $appProcess.WaitForExit(5000)) {
    foreach ($entry in $ownProcesses) {
        if (-not $entry.HasExited) { Stop-Process -Id $entry.Id }
    }
    throw 'Application did not close normally.'
}
Write-Output "PASS: packaged application opened its main window and closed normally."
