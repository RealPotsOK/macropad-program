param()

$ErrorActionPreference = "Stop"

$installDir = Join-Path $env:LOCALAPPDATA "MacroPad Controller"
$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$shortcutPath = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\MacroPad Controller.lnk"

if (Test-Path $installDir) {
    Remove-Item -Path $installDir -Recurse -Force
}

if (Get-ItemProperty -Path $runKey -Name "MacroPad Controller" -ErrorAction SilentlyContinue) {
    Remove-ItemProperty -Path $runKey -Name "MacroPad Controller" -ErrorAction SilentlyContinue
}

if (Test-Path $shortcutPath) {
    Remove-Item -Path $shortcutPath -Force
}

Write-Host "Uninstalled MacroPad Controller."
