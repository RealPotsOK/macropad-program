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

function Stop-RepoPythonProcesses {
    param(
        [string]$RepoRoot
    )

    if (-not $RepoRoot) {
        return
    }

    try {
        $normalizedRoot = [System.IO.Path]::GetFullPath($RepoRoot).TrimEnd('\')
    } catch {
        return
    }

    $targets = @()
    foreach ($process in (Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)) {
        if ($process.Name -notin @("python.exe", "pythonw.exe")) {
            continue
        }
        $commandLine = ""
        if ($null -ne $process.CommandLine) {
            $commandLine = [string]$process.CommandLine
        }
        $executablePath = ""
        if ($null -ne $process.ExecutablePath) {
            $executablePath = [string]$process.ExecutablePath
        }
        $matchesRoot = $false

        if ($commandLine -and $commandLine.IndexOf($normalizedRoot, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
            $matchesRoot = $true
        } elseif ($executablePath) {
            try {
                $fullExe = [System.IO.Path]::GetFullPath($executablePath)
                $venvScripts = Join-Path $normalizedRoot ".venv\Scripts"
                if ($fullExe.StartsWith($venvScripts, [System.StringComparison]::OrdinalIgnoreCase)) {
                    $matchesRoot = $true
                }
            } catch {
                $matchesRoot = $false
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

function Ensure-PyInstaller {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonPath
    )

    & $PythonPath -c "import PyInstaller" *> $null
    if ($LASTEXITCODE -eq 0) {
        return
    }

    Invoke-Checked -Command @($PythonPath, "-m", "pip", "install", "pyinstaller>=6.0")
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
$specFile = Join-Path $repoRoot "MacroPad Controller.spec"
$installDir = Join-Path $env:LOCALAPPDATA "MacroPad Controller"

Stop-MacroPadProcesses -Roots @($sourceDir, $installDir)
Stop-RepoPythonProcesses -RepoRoot $repoRoot

if (Test-Path $sourceDir) {
    Remove-Item -Path $sourceDir -Recurse -Force
}
New-Item -Path $distDir -ItemType Directory -Force | Out-Null
New-Item -Path $workDir -ItemType Directory -Force | Out-Null

try {
    Ensure-PyInstaller -PythonPath $Python
    Invoke-Checked -Command @(
        $Python,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        $distDir,
        "--workpath",
        $workDir,
        $specFile
    )
} finally {
    if (Test-Path $workDir) {
        Remove-Item -Path $workDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Packaged MacroPad Controller at $sourceDir"
