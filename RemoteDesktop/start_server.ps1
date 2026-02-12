# 启动服务器
# 在被控端运行此脚本

cd $PSScriptRoot
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  远程桌面 - 被控端服务器" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

python server.py
