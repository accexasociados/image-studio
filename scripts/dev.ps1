[CmdletBinding()]
param(
    [switch] $Check
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot "backend"
$webRoot = Join-Path $projectRoot "web"
$uvicorn = Join-Path $backendRoot ".venv\Scripts\uvicorn.exe"
$python = Join-Path $backendRoot ".venv\Scripts\python.exe"
$vite = Join-Path $webRoot "node_modules\.bin\vite.cmd"

foreach ($requiredPath in @($uvicorn, $python, $vite)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Falta '$requiredPath'. Completa la instalación indicada en README.md."
    }
}

$npmCommand = Get-Command "npm.cmd" -ErrorAction Stop
if ($Check) {
    Write-Host "Entorno de desarrollo listo: backend, worker y web tienen sus ejecutables."
    exit 0
}

$logRoot = Join-Path ([System.IO.Path]::GetTempPath()) "image-studio-dev-$PID"
New-Item -ItemType Directory -Path $logRoot -ErrorAction Stop | Out-Null
$processes = [System.Collections.Generic.List[object]]::new()

function Start-ImageStudioProcess {
    param(
        [Parameter(Mandatory)] [string] $Name,
        [Parameter(Mandatory)] [string] $Executable,
        [Parameter(Mandatory)] [string[]] $Arguments,
        [Parameter(Mandatory)] [string] $WorkingDirectory
    )

    $stdout = Join-Path $logRoot "$Name.stdout.log"
    $stderr = Join-Path $logRoot "$Name.stderr.log"
    $process = Start-Process `
        -FilePath $Executable `
        -ArgumentList $Arguments `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -WindowStyle Hidden `
        -PassThru
    $processes.Add([pscustomobject]@{
            Name = $Name
            Process = $process
            StandardOutput = $stdout
            StandardError = $stderr
        })
}

try {
    Start-ImageStudioProcess `
        -Name "api" `
        -Executable $uvicorn `
        -Arguments @("app.main:app", "--port", "8090", "--reload") `
        -WorkingDirectory $backendRoot
    Start-ImageStudioProcess `
        -Name "worker" `
        -Executable $python `
        -Arguments @("-m", "app.queue.worker") `
        -WorkingDirectory $backendRoot
    Start-ImageStudioProcess `
        -Name "web" `
        -Executable $npmCommand.Source `
        -Arguments @("run", "dev") `
        -WorkingDirectory $webRoot

    Write-Host "Image Studio está iniciando."
    Write-Host "Web:     http://localhost:5180"
    Write-Host "API:     http://localhost:8090/api/v1"
    Write-Host "Swagger: http://localhost:8090/docs"
    Write-Host "Logs:    $logRoot"
    Write-Host "Presiona Ctrl+C para cerrar API, worker y web."

    while ($true) {
        foreach ($entry in $processes) {
            if ($entry.Process.HasExited) {
                throw "El proceso '$($entry.Name)' terminó con código $($entry.Process.ExitCode). Revisa '$($entry.StandardError)'."
            }
        }
        Start-Sleep -Seconds 1
    }
}
finally {
    Write-Host "Cerrando procesos de Image Studio..."
    foreach ($entry in $processes) {
        if (-not $entry.Process.HasExited) {
            & taskkill.exe /PID $entry.Process.Id /T /F 2>$null | Out-Null
        }
    }
    Write-Host "Procesos cerrados. Los logs se conservan en '$logRoot'."
}
