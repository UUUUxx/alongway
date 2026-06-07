param(
    [switch]$Stop,
    [Alias("skip-install")]
    [switch]$SkipInstall,
    [Alias("env")]
    [string]$EnvName = "alongway",
    [Alias("python")]
    [string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $Root "alongway_backend"
$AgentDir = Join-Path $Root "alongway_agent"
$FrontendDir = Join-Path $Root "alongway-frontend\alongway-demo"
$BackendRequirements = Join-Path $BackendDir "requirements.txt"
$AgentRequirements = Join-Path $AgentDir "requirements.txt"
$Ports = @(8000, 8001, 5173)
$Processes = @()

function Stop-PortProcess {
    param([int]$Port)

    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        $targetPid = $connection.OwningProcess
        if ($targetPid -and $targetPid -ne $PID) {
            $process = Get-Process -Id $targetPid -ErrorAction SilentlyContinue
            if ($process) {
                Write-Host "Stopping process on port $Port (PID $targetPid, $($process.ProcessName))"
                Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

function Stop-StartedProcesses {
    foreach ($process in $Processes) {
        if ($process -and -not $process.HasExited) {
            Write-Host "Stopping $($process.ProcessName) (PID $($process.Id))"
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

function Get-CondaCommand {
    $command = Get-Command conda -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "Cannot find conda. Please install Anaconda/Miniconda and make sure 'conda' is available in PATH."
    }
    return $command.Source
}

function Invoke-Conda {
    param([string[]]$Arguments)

    & $script:CondaCommand @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "conda $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

function Test-CondaEnv {
    param([string]$Name)

    $jsonText = & $script:CondaCommand env list --json
    if ($LASTEXITCODE -ne 0) {
        throw "conda env list failed with exit code $LASTEXITCODE"
    }
    $envList = $jsonText | ConvertFrom-Json
    foreach ($envPath in $envList.envs) {
        if ((Split-Path $envPath -Leaf) -eq $Name) {
            return $true
        }
    }
    return $false
}

function Ensure-CondaEnv {
    if (Test-CondaEnv -Name $EnvName) {
        Write-Host "Conda environment '$EnvName' already exists."
        return
    }

    Write-Host "Creating conda environment '$EnvName' with Python $PythonVersion..."
    Invoke-Conda -Arguments @("create", "-y", "-n", $EnvName, "python=$PythonVersion")
}

function Install-Requirements {
    if ($SkipInstall) {
        Write-Host "Skipping dependency install because -SkipInstall was provided."
        return
    }

    Write-Host "Installing backend requirements..."
    Invoke-Conda -Arguments @("run", "-n", $EnvName, "python", "-m", "pip", "install", "-r", $BackendRequirements)

    Write-Host "Installing agent requirements..."
    Invoke-Conda -Arguments @("run", "-n", $EnvName, "python", "-m", "pip", "install", "-r", $AgentRequirements)
}

function Invoke-CondaPython {
    param(
        [string]$WorkingDirectory,
        [string[]]$PythonArguments
    )

    Push-Location $WorkingDirectory
    try {
        $arguments = @("run", "-n", $EnvName, "python") + $PythonArguments
        Invoke-Conda -Arguments $arguments
    }
    finally {
        Pop-Location
    }
}

function Start-CondaPythonService {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string[]]$PythonArguments
    )

    Write-Host "Starting $Name..."
    $condaArgs = @("run", "-n", $EnvName, "python") + $PythonArguments

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $script:CondaCommand
    $psi.Arguments = ConvertTo-CommandLine -Arguments $condaArgs
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $false
    $psi.RedirectStandardError = $false

    $process = [System.Diagnostics.Process]::Start($psi)
    $script:Processes += $process
    Write-Host "$Name started (PID $($process.Id))"
}

function ConvertTo-CommandLine {
    param([string[]]$Arguments)

    $quoted = foreach ($arg in $Arguments) {
        if ($null -eq $arg) {
            '""'
        }
        elseif ($arg -match '[\s"]') {
            '"' + ($arg -replace '\\(?=\\*")', '$0$0' -replace '"', '\"') + '"'
        }
        else {
            $arg
        }
    }
    return ($quoted -join " ")
}

if ($Stop) {
    foreach ($port in $Ports) {
        Stop-PortProcess -Port $port
    }
    Write-Host "Along-way services stopped."
    exit 0
}

Write-Host "Along-way one-click launcher"
Write-Host "Root: $Root"
Write-Host "Conda env: $EnvName"
Write-Host ""

$script:CondaCommand = Get-CondaCommand

foreach ($port in $Ports) {
    $busy = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($busy) {
        Write-Host "Port $port is already in use. Run '.\start_alongway.ps1 -Stop' first, or close the existing service."
        exit 1
    }
}

try {
    Ensure-CondaEnv
    Install-Requirements

    Write-Host "Initializing backend seed data..."
    Invoke-CondaPython -WorkingDirectory $BackendDir -PythonArguments @("-m", "app.seed")

    Start-CondaPythonService `
        -Name "Backend http://127.0.0.1:8000" `
        -WorkingDirectory $BackendDir `
        -PythonArguments @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000")

    Start-CondaPythonService `
        -Name "Agent http://127.0.0.1:8001" `
        -WorkingDirectory $AgentDir `
        -PythonArguments @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001")

    Start-CondaPythonService `
        -Name "Frontend http://127.0.0.1:5173" `
        -WorkingDirectory $FrontendDir `
        -PythonArguments @("-m", "http.server", "5173", "--bind", "127.0.0.1")

    Write-Host ""
    Write-Host "All services are starting."
    Write-Host "Open: http://127.0.0.1:5173"
    Write-Host "Backend docs: http://127.0.0.1:8000/docs"
    Write-Host ""
    Write-Host "Keep this window open. Press Ctrl+C to stop all services."

    while ($true) {
        Start-Sleep -Seconds 1
        foreach ($process in $Processes) {
            if ($process.HasExited) {
                throw "A service exited unexpectedly (PID $($process.Id))."
            }
        }
    }
}
finally {
    Stop-StartedProcesses
}
