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

function Stop-MacroPadProcesses {
    param(
        [string[]]$Roots
    )

    $normalizedRoots = @(
        $Roots |
        Where-Object { $_ } |
        ForEach-Object {
            try {
                [System.IO.Path]::GetFullPath($_).TrimEnd('\')
            } catch {
                $null
            }
        } |
        Where-Object { $_ }
    )

    if (-not $normalizedRoots.Count) {
        return
    }

    $targets = @()
    foreach ($process in (Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)) {
        if ($process.Name -ne "MacroPad Controller.exe") {
            continue
        }
        if (-not $process.ExecutablePath) {
            continue
        }
        $fullPath = [System.IO.Path]::GetFullPath($process.ExecutablePath)
        $matchesRoot = $false
        foreach ($root in $normalizedRoots) {
            if ($fullPath.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
                $matchesRoot = $true
                break
            }
        }
        if ($matchesRoot) {
            $targets += $process
        }
    }

    foreach ($process in $targets) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    }

    if ($targets) {
        Start-Sleep -Milliseconds 800
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
$iconPath = Join-Path $installDir "assets\MP_Icon.ico"

Stop-MacroPadProcesses -Roots @($sourceDir, $installDir)

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
if (Test-Path $iconPath) {
    $shortcut.IconLocation = "$iconPath,0"
} else {
    $shortcut.IconLocation = "$exePath,0"
}
$shortcut.Save()

Write-Host "Installed MacroPad Controller to $installDir"
Write-Host "Autostart enabled with $exePath --hidden"
Write-Host "Start menu shortcut created at $shortcutPath"
