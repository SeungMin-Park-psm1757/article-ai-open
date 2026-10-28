$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path .\.venv\Scripts\python.exe)) { throw '먼저 scripts/install.ps1을 실행하세요.' }
& .\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 18531 --server.headless true --server.fileWatcherType none
if ($LASTEXITCODE -ne 0) { throw '서버 시작 실패. 포트 충돌이나 오류를 확인하세요.' }
