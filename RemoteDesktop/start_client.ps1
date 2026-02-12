# 启动客户端
# 在控制端运行此脚本

param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 9999
)

cd $PSScriptRoot
Write-Host "==================================" -ForegroundColor Green
Write-Host "  远程桌面 - 控制端客户端" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Green
Write-Host ""
Write-Host "连接到: $Host:$Port" -ForegroundColor Yellow
Write-Host ""

python client.py $Host $Port
