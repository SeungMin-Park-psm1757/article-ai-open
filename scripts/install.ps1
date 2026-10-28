$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Python 3.12를 설치하고 py 명령을 사용할 수 있게 설정하세요.' }
$marker = '.venv\article-ai-owner.txt'
if (Test-Path -LiteralPath '.venv') {
    if ((Get-Item -LiteralPath '.venv' -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw '연결된 .venv 경로는 변경하지 않습니다.'
    }
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf) -or (Get-Content -LiteralPath $marker -Raw).Trim() -ne 'article-ai-venv/1') {
        throw '기존 .venv의 소유권을 확인할 수 없어 변경하지 않았습니다. 별도의 빈 설치 폴더를 사용하세요.'
    }
} else {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw '가상환경 생성 실패. .venv를 확인하세요.' }
    Set-Content -LiteralPath $marker -Value 'article-ai-venv/1' -Encoding ascii
}
& .\.venv\Scripts\python.exe -m pip install -r requirements-windows-base.lock
if ($LASTEXITCODE -ne 0) { throw '의존성 설치 실패' }
Write-Host '설치 완료. scripts/start.ps1을 실행하세요.'
