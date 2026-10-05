param(
    [string]$KeyFile = (Join-Path (Split-Path $PSScriptRoot -Parent | Split-Path -Parent) 'open router api key.txt'),
    [switch]$RunPaid
)
$ErrorActionPreference = 'Stop'
$geminiRepo = Split-Path $PSScriptRoot -Parent
$geminiContainer = 'uts-gemini-controller-20260930'
$geminiVolume = 'uts-gemini-dev20-20260930'
function Assert-DockerExit {
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed: $LASTEXITCODE" }
}
Push-Location $geminiRepo
try {
    docker info --format '{{.ServerVersion}} {{.OSType}}'; Assert-DockerExit
    docker build -f stage2/Dockerfile.gemini-laptop -t uts-gemini-controller:20260930 .; Assert-DockerExit
    $geminiExists = docker ps -aq --filter "name=^/$geminiContainer$"; Assert-DockerExit
    if (-not $geminiExists) {
        $geminiKeyPath = (Resolve-Path -LiteralPath $KeyFile).Path
        docker volume create $geminiVolume | Out-Null; Assert-DockerExit
        $geminiMount = docker volume inspect $geminiVolume --format '{{.Mountpoint}}'; Assert-DockerExit
        docker run -d --name $geminiContainer `
            --mount "type=volume,source=$geminiVolume,target=$geminiMount" `
            --mount "type=bind,source=$geminiRepo,target=/source,readonly" `
            --mount "type=bind,source=$geminiKeyPath,target=/run/openrouter-key,readonly" `
            --mount 'type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock' `
            --workdir "$geminiMount/repo" uts-gemini-controller:20260930
        Assert-DockerExit
        docker exec $geminiContainer python -c "import shutil; shutil.copytree('/source', '.', ignore=shutil.ignore_patterns('.git','.cache','.runtime','__pycache__'), dirs_exist_ok=True)"
        Assert-DockerExit
    }
    docker exec $geminiContainer python stage2/gemini_laptop_prepare.py; Assert-DockerExit
    docker exec $geminiContainer python stage2/gemini_laptop_qualify.py; Assert-DockerExit
    if ($RunPaid) {
        docker exec $geminiContainer python stage2/gemini_laptop_run.py; Assert-DockerExit
        $geminiDestination = Join-Path $geminiRepo 'stage2/results/gemini-dev20-laptop-20260930'
        New-Item -ItemType Directory -Force -Path $geminiDestination | Out-Null
        $geminiMount = docker volume inspect $geminiVolume --format '{{.Mountpoint}}'; Assert-DockerExit
        docker cp "${geminiContainer}:$geminiMount/repo/stage2/results/gemini-dev20-laptop-20260930/." $geminiDestination
        Assert-DockerExit
    }
} finally { Pop-Location }
