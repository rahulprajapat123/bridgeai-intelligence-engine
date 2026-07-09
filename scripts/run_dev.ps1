$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
if (-not (Test-Path ".venv")) {
  python -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install -e .[dev]
.\.venv\Scripts\research-intel.exe init-db
.\.venv\Scripts\python.exe -m research_intel.run_server --reload --host 127.0.0.1 --port 8000
