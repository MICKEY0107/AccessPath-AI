<#
.SYNOPSIS
  One entry point for running, demonstrating and testing AccessPath AI on Windows.

.EXAMPLE
  ./scripts/dev.ps1 setup      # first time: .env, containers, database, demo
  ./scripts/dev.ps1 demo       # refresh the demo account, journeys and reports
  ./scripts/dev.ps1 test       # full test suite in the container
  ./scripts/dev.ps1 lint       # ruff
  ./scripts/dev.ps1 check      # what is set up and what is not
  ./scripts/dev.ps1 benchmark  # Gate 1 benchmark with the scripted plans
  ./scripts/dev.ps1 logs       # follow the worker log
  ./scripts/dev.ps1 stop       # stop the containers (data is kept)
#>
# A plain script (no param block), so arguments such as -v or -k reach pytest unchanged.
$Command = if ($args.Count -gt 0) { [string]$args[0] } else { "help" }
$Rest = if ($args.Count -gt 1) { @($args[1..($args.Count - 1)]) } else { @() }

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

function Invoke-Step([string]$Title, [scriptblock]$Body) {
  Write-Host "`n== $Title" -ForegroundColor Cyan
  $global:LASTEXITCODE = 0
  & $Body
  if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "Step failed: $Title" }
}

function New-Secret([int]$Bytes = 36) {
  $buffer = New-Object byte[] $Bytes
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buffer)
  return ([Convert]::ToBase64String($buffer) -replace '[+/=]', 'x')
}

function Initialize-Env {
  if (Test-Path ".env") { Write-Host ".env already exists; keeping it."; return }
  $text = Get-Content ".env.example" -Raw
  $text = $text -replace 'DJANGO_SECRET_KEY=.*', "DJANGO_SECRET_KEY=$(New-Secret 48)"
  $text = $text -replace 'POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=$(New-Secret 18)"
  Set-Content ".env" $text -NoNewline
  Write-Host "Created .env with a random secret key and database password. Add AI keys there later (optional)."
}

function Wait-Web {
  # Windows PowerShell 5.1 turns a native command's stderr into an error under "Stop".
  $ErrorActionPreference = "Continue"
  for ($i = 0; $i -lt 30; $i++) {
    docker compose exec -T web python manage.py check 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { return }
    Start-Sleep -Seconds 2
  }
}

switch ($Command) {
  "setup" {
    Invoke-Step "Create .env" { Initialize-Env }
    # --renew-anon-volumes refreshes the image's virtual environment (test tools included).
    Invoke-Step "Build and start the containers" { docker compose up -d --build --renew-anon-volumes }
    Wait-Web
    Invoke-Step "Apply the database schema" { docker compose exec -T web python manage.py migrate }
    Invoke-Step "Install axe-core (optional page rules)" {
      docker compose exec -T web python manage.py install_axe_core
      if ($LASTEXITCODE -ne 0) { Write-Host "axe-core could not be downloaded; the keyboard checks still run."; $global:LASTEXITCODE = 0 }
    }
    Invoke-Step "Prepare the demo" { docker compose exec -T web python manage.py demo_setup @Rest }
    Invoke-Step "Check the setup" { docker compose exec -T web python manage.py check_setup }
    Write-Host "`nOpen http://127.0.0.1:8000/ and sign in with the demo account above." -ForegroundColor Green
  }
  "start" { Invoke-Step "Start the containers" { docker compose up -d } }
  "demo" { Invoke-Step "Prepare the demo" { docker compose exec -T web python manage.py demo_setup @Rest } }
  "test" {
    Invoke-Step "Run the tests" {
      docker compose exec -T -e DJANGO_SETTINGS_MODULE=config.settings.test web python -m pytest -q @Rest
    }
  }
  "lint" { Invoke-Step "Ruff" { docker compose exec -T web python -m ruff check . @Rest } }
  "check" { Invoke-Step "Check the setup" { docker compose exec -T web python manage.py check_setup } }
  "benchmark" {
    $arguments = if ($Rest.Count) { $Rest } else { @("--provider", "fixture", "--repeat", "1") }
    Invoke-Step "Benchmark" { docker compose exec -T worker python manage.py run_benchmark @arguments }
  }
  "logs" { docker compose logs -f worker }
  "stop" { Invoke-Step "Stop the containers" { docker compose stop } }
  default {
    Write-Host "Usage: ./scripts/dev.ps1 <setup|start|demo|test|lint|check|benchmark|logs|stop> [arguments]"
    Write-Host "  setup      first time: .env, containers, database, axe-core, demo"
    Write-Host "  demo       refresh the demo account, journeys and reports (demo --password <p>)"
    Write-Host "  test       full test suite in the container (test tests/test_rules.py -k preset)"
    Write-Host "  lint       ruff"
    Write-Host "  check      what is set up and what is not"
    Write-Host "  benchmark  Gate 1 benchmark (default: scripted plans)"
    Write-Host "  logs/stop  follow the worker log / stop the containers"
  }
}
