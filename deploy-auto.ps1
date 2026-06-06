# JLAO 部署脚本 - 使用密码
$ErrorActionPreference = "Stop"

$Server = "root@47.120.41.143"
$ServerIP = "47.120.41.143"
$Password = "LEONkang@@"
$Package = "D:\JLAO\jlao-release.tar.gz"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  JLAO 服务器部署" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查发布包
if (-not (Test-Path $Package)) {
    Write-Host "错误: 发布包不存在 $Package" -ForegroundColor Red
    exit 1
}

# 使用 plink (PuTTY) 或 ssh + expect 方式
# 这里使用 echo + ssh 的方式

Write-Host "[JLAO] 上传发布包到服务器..." -ForegroundColor Yellow

# 创建临时脚本
$scpScript = @"
yes
""@

$scpScript | sshpass -p "$Password" scp -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null "$Package" "$Server`: /tmp/jlao-release.tar.gz"

if ($LASTEXITCODE -ne 0) {
    Write-Host "错误: 上传失败" -ForegroundColor Red
    exit 1
}

Write-Host "[JLAO] 在服务器上执行安装..." -ForegroundColor Yellow

# 执行远程安装
$installScript = @"
rm -rf /tmp/jlao-release && mkdir -p /tmp/jlao-release
 tar -xzf /tmp/jlao-release.tar.gz -C /tmp/jlao-release
 bash /tmp/jlao-release/deploy/server-install.sh
""@

$installScript | sshpass -p "$Password" ssh -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null $Server

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  部署完成!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "访问地址: http://$ServerIP" -ForegroundColor Cyan
