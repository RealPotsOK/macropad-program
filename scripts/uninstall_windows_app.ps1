param()

$ErrorActionPreference = "Stop"

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

$installDir = Join-Path $env:LOCALAPPDATA "MacroPad Controller"
$repoRoot = Split-Path -Parent $PSScriptRoot
$distDir = Join-Path $repoRoot "dist\MacroPad Controller"
$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$shortcutPath = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\MacroPad Controller.lnk"

Stop-MacroPadProcesses -Roots @($installDir, $distDir)

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
