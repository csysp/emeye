#!/usr/bin/env pwsh
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Windows task runner. Mirrors the Makefile target-for-target so the documented
# workflow is identical on every platform:
#
#   .\make.ps1 up
#   .\make.ps1 migrate
#   .\make.ps1 psql
#
# Every target is a thin wrapper over `docker compose`, exactly as in the
# Makefile. Docker Desktop remains the only prerequisite — no WSL, no make, no
# host Python.
#
# Target parity with the Makefile is enforced by scripts/check_task_parity.py
# in CI, so the two cannot silently diverge.

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Target = 'help',

    # Message for `revision`, e.g. .\make.ps1 revision -m "add bronze tables"
    [Alias('m')]
    [string]$Message
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

function Invoke-Compose {
    param([Parameter(ValueFromRemainingArguments)] [string[]]$Args)
    & docker compose @Args
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Invoke-App {
    param([Parameter(ValueFromRemainingArguments)] [string[]]$Args)
    Invoke-Compose run --rm app @Args
}

function Assert-Env {
    if (Test-Path '.env') { return }
    Copy-Item '.env.example' '.env'
    Write-Host ''
    Write-Host '  Created .env from .env.example.'
    Write-Host ''
    Write-Host '  Fill in these two before continuing — neither has a usable default:'
    Write-Host '    EMEYE_POSTGRES_PASSWORD   any non-empty string'
    Write-Host '    EMEYE_USER_AGENT          must carry a real contact address'
    Write-Host ''
    Write-Host '  Then re-run: .\make.ps1 up'
    Write-Host ''
    exit 1
}

function Get-EnvValue {
    param([string]$Key, [string]$Default)
    if (-not (Test-Path '.env')) { return $Default }
    $line = Select-String -Path '.env' -Pattern "^$Key=(.*)$" | Select-Object -First 1
    if ($null -eq $line) { return $Default }
    $value = $line.Matches[0].Groups[1].Value.Trim()
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value
}

function Show-Help {
    Write-Host ''
    Write-Host '  emeye task runner (Windows). Same targets as the Makefile.'
    Write-Host ''
    $targets = [ordered]@{
        'help'             = 'Show this help'
        'up'               = 'Start postgres and the app container'
        'down'             = 'Stop containers, keep data'
        'build'            = 'Rebuild the image'
        'migrate'          = 'Apply migrations (alembic upgrade head)'
        'revision'         = 'Autogenerate a migration: .\make.ps1 revision -m "message"'
        'downgrade'        = 'Roll back one migration'
        'shell'            = 'Bash shell in the app container'
        'psql'             = 'psql shell on the warehouse'
        'logs'             = 'Follow container logs'
        'ps'               = 'Show container status'
        'licenses'         = 'Check dependency license compatibility'
        'test'             = 'Run unit tests (no services, outbound network blocked)'
        'test-integration' = 'Run integration tests (needs a running postgres)'
        'lint'             = 'Run ruff and mypy'
        'clean'            = 'Remove containers and the app image, keep the database volume'
        'nuke'             = 'Remove containers AND all data volumes. Destroys the warehouse.'
    }
    foreach ($t in $targets.GetEnumerator()) {
        Write-Host ("  {0,-18} {1}" -f $t.Key, $t.Value)
    }
    Write-Host ''
}

function Invoke-AppNoDb {
    # EMEYE_WAIT_FOR_DB=0 skips the entrypoint's postgres wait: these need the
    # image, not the database, and would otherwise block for the full timeout.
    param([Parameter(ValueFromRemainingArguments)] [string[]]$Args)
    Invoke-Compose run --rm -e EMEYE_WAIT_FOR_DB=0 app @Args
}

switch ($Target.ToLower()) {
    'help' { Show-Help }

    'up' {
        Assert-Env
        Invoke-Compose up -d --build
        Write-Host 'up. next: .\make.ps1 migrate'
    }

    'down'  { Invoke-Compose down }
    'build' { Assert-Env; Invoke-Compose build }
    'ps'    { Invoke-Compose ps }
    'logs'  { Invoke-Compose logs -f }

    'migrate' { Assert-Env; Invoke-App alembic upgrade head }

    'revision' {
        Assert-Env
        if ([string]::IsNullOrWhiteSpace($Message)) {
            Write-Error 'usage: .\make.ps1 revision -m "message"'
            exit 1
        }
        Invoke-App alembic revision --autogenerate -m $Message
    }

    'downgrade' { Assert-Env; Invoke-App alembic downgrade -1 }

    'shell' { Assert-Env; Invoke-Compose exec app bash }

    'psql' {
        Assert-Env
        $user = Get-EnvValue 'EMEYE_POSTGRES_USER' 'emeye'
        $db   = Get-EnvValue 'EMEYE_POSTGRES_DB'   'emeye'
        Invoke-Compose exec postgres psql -U $user -d $db
    }

    'licenses' { Assert-Env; Invoke-App python scripts/check_licenses.py }

    'test' { Assert-Env; Invoke-AppNoDb pytest -m unit }

    'test-integration' { Assert-Env; Invoke-App pytest -m integration }

    'lint' {
        Assert-Env
        Invoke-AppNoDb ruff check .
        Invoke-AppNoDb ruff format --check .
        Invoke-AppNoDb mypy
    }

    'clean' { Invoke-Compose down --rmi local }

    'nuke' {
        Write-Host 'This deletes the warehouse volume permanently.'
        $answer = Read-Host "Type 'nuke' to confirm"
        if ($answer -ne 'nuke') { Write-Host 'aborted'; exit 1 }
        Invoke-Compose down -v --rmi local
    }

    default {
        Write-Error "unknown target '$Target'. Run .\make.ps1 help"
        exit 1
    }
}
