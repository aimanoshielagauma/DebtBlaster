$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Load optional KEY=VALUE settings for this scheduled task from .env.
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path -LiteralPath $envFile) {
    Get-Content -LiteralPath $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#=\s]+)\s*=\s*(.*?)\s*$') {
            $key = $Matches[1]
            $value = $Matches[2]
            if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Create the project virtual environment first. See README.md."
}
& $python manage.py schedule_reminders
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python manage.py process_reminders
exit $LASTEXITCODE
