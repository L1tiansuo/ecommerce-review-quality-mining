param([switch]$Reinstall)
$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force runtime | Out-Null
# 仅本地开发模式使用文件型H2。Docker部署始终使用MySQL。
$bundled=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies'
$python=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if(!(Test-Path $python)){
  $base=Join-Path $bundled 'python\python.exe'
  if(!(Test-Path $base)){$base=(Get-Command python -ErrorAction Stop).Source}
  & $base -m venv .venv
  if($LASTEXITCODE){throw '创建Python虚拟环境失败，请安装Python3.10以上版本。'}
}
if($Reinstall -or !(Test-Path runtime/dependencies.ready)){
  & $python -m pip install -r requirements-dev.txt
  if($LASTEXITCODE){throw '依赖安装失败，请检查网络与Python版本。'}
  Set-Content runtime/dependencies.ready 'installed'
}
$java=(Get-Command java -ErrorAction SilentlyContinue).Source
if(!$java){$java='C:\Program Files\JetBrains\PyCharm Community Edition 2024.3.3\jbr\bin\java.exe'}
if(!(Test-Path $java)){throw '请安装JDK17或更新版本，并设置java命令。'}
$node=(Get-Command node -ErrorAction SilentlyContinue).Source
if(!$node){$node=Join-Path $bundled 'node\bin\node.exe'}
if(!(Test-Path $node)){throw '请安装Node18以上版本。'}
if(!(Test-Path release/backend.jar)){throw '缺少构建产物，请先运行make.ps1 build并复制backend/target中的jar至release/backend.jar。'}
foreach($port in @(8001,8080,8088)){
 if(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue){throw "端口 $port 已被使用。若系统已运行，直接打开 http://127.0.0.1:8088"}
}
$algo=Start-Process -FilePath $python -ArgumentList '-m uvicorn main:app --host 127.0.0.1 --port 8001' -WorkingDirectory (Join-Path $PSScriptRoot 'algo') -RedirectStandardOutput (Join-Path $PSScriptRoot 'runtime/algo.log') -RedirectStandardError (Join-Path $PSScriptRoot 'runtime/algo.err.log') -WindowStyle Hidden -PassThru
$env:SEED_DIR=Join-Path $PSScriptRoot 'data/seed'
$backend=Start-Process -FilePath $java -ArgumentList '-Xmx768m -jar ../release/backend.jar' -WorkingDirectory (Join-Path $PSScriptRoot 'backend') -RedirectStandardOutput (Join-Path $PSScriptRoot 'runtime/backend.log') -RedirectStandardError (Join-Path $PSScriptRoot 'runtime/backend.err.log') -WindowStyle Hidden -PassThru
$web=Start-Process -FilePath $node -ArgumentList 'scripts/serve-web.cjs' -WorkingDirectory $PSScriptRoot -RedirectStandardOutput (Join-Path $PSScriptRoot 'runtime/web.log') -RedirectStandardError (Join-Path $PSScriptRoot 'runtime/web.err.log') -WindowStyle Hidden -PassThru
@($algo.Id,$backend.Id,$web.Id)|ConvertTo-Json|Set-Content runtime/pids.json
Write-Host '服务已启动。首次导入数据需要等候；打开 http://127.0.0.1:8088。日志在runtime目录。'
