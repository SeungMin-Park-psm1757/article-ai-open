$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path .\.venv\Scripts\python.exe) -or -not (Test-Path .\.venv\article-ai-owner.txt) -or ((Get-Item -LiteralPath '.venv' -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -or (Get-Content .\.venv\article-ai-owner.txt -Raw).Trim() -ne 'article-ai-venv/1') { throw '관리되는 가상환경이 없습니다. 먼저 scripts/install.ps1을 실행하세요.' }
& .\.venv\Scripts\python.exe -m pip install -r requirements-windows-ai.lock
if ($LASTEXITCODE -ne 0) { throw '의미 검색 의존성 설치 실패' }
Write-Host '의존성을 설치했습니다. 모델 아티팩트는 별도로 다운로드해야 합니다.'
