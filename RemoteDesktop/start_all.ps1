# 一键启动远程桌面系统
# 启动服务器、客户端和Web服务器

param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 9999
)

cd $PSScriptRoot

Write-Host "==================================" -ForegroundColor Green
Write-Host "  远程桌面 - 一键启动所有组件" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Green
Write-Host ""

# 启动服务器 (被控端)
Write-Host "启动服务器..." -ForegroundColor Cyan
Start-Process -FilePath "python" -ArgumentList "server.py" -NoNewWindow

# 等待一下确保服务器启动
Start-Sleep -Seconds 2

# 启动客户端 (控制端)
Write-Host "启动客户端..." -ForegroundColor Yellow
Start-Process -FilePath "python" -ArgumentList "client.py $Host $Port" -NoNewWindow

# 启动Web服务器
Write-Host "启动Web服务器..." -ForegroundColor Magenta
Start-Process -FilePath "python" -ArgumentList "web_server.py" -NoNewWindow

Write-Host ""
Write-Host "所有组件已启动！" -ForegroundColor Green
Write-Host "服务器运行在被控端" -ForegroundColor Cyan
Write-Host "客户端连接到 $Host:$Port" -ForegroundColor Yellow
Write-Host "Web服务器启动，可通过浏览器访问" -ForegroundColor Magenta