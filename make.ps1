param([ValidateSet('up','down','test','prepare','build','backup')][string]$Action='up',[string]$Raw='')
$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
switch($Action){
 'up' { docker compose up --build -d; if($LASTEXITCODE){throw 'Docker启动失败'}; Write-Host '浏览器打开 http://localhost:8080，首次导入请等候。' }
 'down' { docker compose down }
 'build' { Push-Location backend; mvn package; Pop-Location; Push-Location web; npm ci; npm run build; Pop-Location }
 'test' { python -m pytest tests -q }
 'prepare' { if(!$Raw){throw '请用 -Raw 指定 yf_amazon 目录'}; python scripts/build_dataset.py --raw $Raw; python scripts/check_dataset.py; python scripts/precompute.py }
 'backup' { New-Item -ItemType Directory -Force runtime/backups | Out-Null; $stamp=Get-Date -Format yyyyMMdd-HHmmss; docker compose exec -T mysql sh -c 'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction qr' | Set-Content -Encoding utf8 "runtime/backups/qr-$stamp.sql"; Get-ChildItem runtime/backups -Filter 'qr-*.sql' | Sort-Object LastWriteTime -Descending | Select-Object -Skip 7 | Remove-Item }
}
