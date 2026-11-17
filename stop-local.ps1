$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
if(Test-Path runtime/pids.json){
 foreach($processId in (Get-Content runtime/pids.json -Raw|ConvertFrom-Json)){
  # 只结束本项目启动记录且命令行含本项目标识的进程，避免PID复用误杀。
  $process=Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue
  if($process -and ($process.CommandLine -match 'uvicorn main:app|release/backend.jar|scripts/serve-web.cjs')){Stop-Process -Id $processId -ErrorAction SilentlyContinue}
 }
 Remove-Item -LiteralPath runtime/pids.json
}
Write-Host '已停止本项目记录的本地服务。数据库文件保留。'
