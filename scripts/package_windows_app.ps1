param(
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

$distDir = Join-Path $repoRoot "dist"
$sourceDir = Join-Path $distDir "MacroPad Controller"
$workDir = Join-Path $env:TEMP ("MacroPadController-PyInstaller-" + [guid]::NewGuid().ToString("N"))
$launcher = Join-Path $repoRoot "scripts\windows_gui_launcher.py"
$srcDir = Join-Path $repoRoot "src"
$installDir = Join-Path $env:LOCALAPPDATA "MacroPad Controller"

Stop-MacroPadProcesses -Roots @($sourceDir, $installDir)

if (Test-Path $sourceDir) {
    Remove-Item -Path $sourceDir -Recurse -Force
}
New-Item -Path $distDir -ItemType Directory -Force | Out-Null
New-Item -Path $workDir -ItemType Directory -Force | Out-Null

try {
    Invoke-Checked -Command @($Python, "-m", "pip", "install", "-e", "${repoRoot}[build]")
    Invoke-Checked -Command @(
        $Python,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--windowed",
        "--onedir",
        "--name",
        "MacroPad Controller",
        "--distpath",
        $distDir,
        "--workpath",
        $workDir,
        "--paths",
        $srcDir,
        "--collect-submodules",
        "comtypes",
        "--collect-submodules",
        "pycaw",
        "--collect-submodules",
        "winsdk",
        $launcher
    )
} finally {
    if (Test-Path $workDir) {
        Remove-Item -Path $workDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Packaged MacroPad Controller at $sourceDir"
