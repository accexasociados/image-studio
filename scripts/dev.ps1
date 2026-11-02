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

function Stop-StaleImageStudio {
    # Si la ventana anterior se cerró con la X (sin Ctrl+C), API, worker y web quedan vivos con el código
    # viejo. Dos workers se reparten la cola y el viejo falla con opciones que no conoce: se cierran antes.
    $venv = (Join-Path $backendRoot ".venv").ToLowerInvariant()
    $all = @(Get-CimInstance Win32_Process)
    $alive = @{}
    foreach ($p in $all) { $alive[[int]$p.ProcessId] = $true }
    $stale = [System.Collections.Generic.List[object]]::new()
    foreach ($p in $all) {
        $line = [string]$p.CommandLine
        if ($line -notmatch 'app\.queue\.worker|app\.main:app') { continue }
        $ours = $line.ToLowerInvariant().Contains($venv)
        # El lanzador del venv abre un python hijo sin la ruta del proyecto: se cierra solo si quedó huérfano.
        $orphan = -not $alive.ContainsKey([int]$p.ParentProcessId)
        if ($ours -or $orphan) { $stale.Add($p) }
    }
    foreach ($port in @(8090, 5180)) {
        $listeners = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
        foreach ($listener in $listeners) {
            $owner = $all | Where-Object { $_.ProcessId -eq $listener.OwningProcess } | Select-Object -First 1
            if ($null -ne $owner -and $owner.Name -in @("node.exe", "python.exe", "uvicorn.exe")) { $stale.Add($owner) }
        }
    }
    $ids = @($stale | ForEach-Object { [int]$_.ProcessId } | Sort-Object -Unique)
    if ($ids.Count -eq 0) { return }
    Write-Host "Cerrando $($ids.Count) proceso(s) de una ejecución anterior de Image Studio..."
    foreach ($id in $ids) {
        & taskkill.exe /PID $id /T /F 2>$null | Out-Null
    }
    Start-Sleep -Seconds 1
}

Stop-StaleImageStudio

# Fecha y hora además del PID: en la misma ventana de PowerShell el PID no cambia entre ejecuciones.
$logRoot = Join-Path ([System.IO.Path]::GetTempPath()) "image-studio-dev-$PID-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
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
    # El canal de avisos del navegador (SSE) nunca se cierra solo: sin tope, la recarga automática
    # se quedaba esperando para siempre y la API dejaba de responder. (El comentario va aquí arriba:
    # dentro de un comando partido con ` corta el comando y PowerShell pide los parámetros que faltan.)
    Start-ImageStudioProcess `
        -Name "api" `
        -Executable $uvicorn `
        -Arguments @("app.main:app", "--port", "8090", "--reload", "--timeout-graceful-shutdown", "3") `
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
