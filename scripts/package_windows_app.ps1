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

if (Test-Path $sourceDir) {
    Remove-Item -Path $sourceDir -Recurse -Force -ErrorAction SilentlyContinue
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
        $launcher
    )
} finally {
    if (Test-Path $workDir) {
        Remove-Item -Path $workDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Packaged MacroPad Controller at $sourceDir"
