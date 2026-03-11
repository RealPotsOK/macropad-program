param(
    [switch]$Build,
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Command
    )

    & $Command[0] $Command[1..($Command.Length - 1)]
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $($Command -join ' ')"
    }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) {
    $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $Python = $venvPython
    } else {
        $Python = "python"
    }
}

if ($Build -or -not (Test-Path (Join-Path $repoRoot "dist\MacroPad Controller\MacroPad Controller.exe"))) {
    Invoke-Checked -Command @(
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        (Join-Path $repoRoot "scripts\package_windows_app.ps1"),
        "-Python",
        $Python
    )
}

$sourceDir = Join-Path $repoRoot "dist\MacroPad Controller"
$installDir = Join-Path $env:LOCALAPPDATA "MacroPad Controller"
$exePath = Join-Path $installDir "MacroPad Controller.exe"
$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$shortcutPath = Join-Path $startMenuDir "MacroPad Controller.lnk"

if (Test-Path $installDir) {
    Remove-Item -Path $installDir -Recurse -Force
}

New-Item -Path $installDir -ItemType Directory -Force | Out-Null
Copy-Item -Path (Join-Path $sourceDir "*") -Destination $installDir -Recurse -Force
New-Item -Path $runKey -Force | Out-Null
New-ItemProperty -Path $runKey -Name "MacroPad Controller" -Value "`"$exePath`" --hidden" -PropertyType String -Force | Out-Null

New-Item -Path $startMenuDir -ItemType Directory -Force | Out-Null
$wshShell = New-Object -ComObject WScript.Shell
$shortcut = $wshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $installDir
$shortcut.Description = "MacroPad Controller"
$shortcut.IconLocation = $exePath
$shortcut.Save()

Write-Host "Installed MacroPad Controller to $installDir"
Write-Host "Autostart enabled with $exePath --hidden"
Write-Host "Start menu shortcut created at $shortcutPath"
