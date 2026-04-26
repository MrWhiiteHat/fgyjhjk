param(
    [int]$Port = 3000
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$frontendRoot = Join-Path $repoRoot "app/frontend"
Set-Location $frontendRoot

if (-not (Test-Path (Join-Path $frontendRoot "node_modules"))) {
    npm install
}

if ($Port -eq 3000) {
    npm run dev
} else {
    npx next dev -p $Port
}
