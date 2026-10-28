param([string]$InstallPath = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'Stop'

if (-not $IsWindows -and $PSVersionTable.PSEdition -eq 'Core') {
    throw '이 진단 도구는 Windows에서 실행해야 합니다.'
}
if (-not (Test-Path -LiteralPath $InstallPath -PathType Container)) {
    throw '설치 경로가 존재하지 않습니다.'
}
$resolvedPath = (Resolve-Path -LiteralPath $InstallPath).Path
$driveName = [System.IO.Path]::GetPathRoot($resolvedPath)
$drive = [System.IO.DriveInfo]::new($driveName)
$os = Get-CimInstance Win32_OperatingSystem
$processors = @(Get-CimInstance Win32_Processor | ForEach-Object {
    [ordered]@{ name = $_.Name; logical_processors = $_.NumberOfLogicalProcessors }
})
$gpus = @(Get-CimInstance Win32_VideoController | ForEach-Object {
    [ordered]@{ name = $_.Name; driver_version = $_.DriverVersion }
})
$python = Get-Command py -ErrorAction SilentlyContinue
$result = [ordered]@{
    schema = 'article-ai-doctor/1'
    os = [ordered]@{ name = $os.Caption; version = $os.Version; architecture = $os.OSArchitecture }
    memory_bytes = [ordered]@{ total = [int64]$os.TotalVisibleMemorySize * 1024; available = [int64]$os.FreePhysicalMemory * 1024 }
    disk_bytes = [ordered]@{ free = $drive.AvailableFreeSpace; total = $drive.TotalSize }
    processors = $processors
    gpus = $gpus
    python_launcher_found = [bool]$python
    profile = 'UNVERIFIED'
    limitations = @('GPU VRAM, compute capability, backend and model compatibility are not measured.', 'No reference model configuration has been verified.')
}
$result | ConvertTo-Json -Depth 6
