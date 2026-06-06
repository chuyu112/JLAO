# JLAO 前端部署流程

> **注意**：如果 agent 无法直接执行命令，请将此文档发给用户，由用户手动执行。

---

## 前置条件

- 本地已安装 Node.js 和 npm
- 已配置 SSH 免密登录（或知道服务器密码）
- 服务器地址：`47.120.41.143`
- 前端目录：`/var/www/jlao`

---

## 部署步骤

### 1. 构建前端

在本地 PowerShell 执行：

```powershell
cd D:\JLAO\frontend
npm run build
```

**预期输出**：
```
vite v5.x.x building for production...
✓ 100 modules transformed.
dist/                     0.83 kB │ gzip: 0.42 kB
dist/assets/index-xxx.js   136.96 kB │ gzip: 45.23 kB
dist/assets/index-xxx.css   39.90 kB │ gzip: 12.34 kB
✓ built in 4.08s
```

---

### 2. 上传到服务器

在本地 PowerShell 执行：

```powershell
scp -r D:\JLAO\frontend\dist\* root@47.120.41.143:/var/www/jlao/
```

**输入密码后预期输出**：
```
index.html              100%  834    74.0KB/s   00:00
assets/index-xxx.js     100%  134KB  1.9MB/s   00:00
assets/index-xxx.css    100%   39KB  1.2MB/s   00:00
...
```

---

### 3. 重启 nginx

在本地 PowerShell 执行：

```powershell
ssh root@47.120.41.143 "nginx -t && systemctl restart nginx"
```

**预期输出**：
```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

---

## 验证部署

浏览器访问：
```
https://jlao.szkakayiduo.com/live?api=http://127.0.0.1:8000
```

检查：
- [ ] 页面正常加载
- [ ] 顶部导航栏有"设置"按钮
- [ ] "其它分析"页面有"客户线索"栏目
- [ ] 没有 scrcpy 驱动面板

---

## 常见问题

### 问题 1：scp 上传失败

**错误**：
```
ssh: Could not resolve hostname d: Name or service not known
```

**原因**：在服务器上执行了 Windows 路径

**解决**：在本机 PowerShell 执行，不要在服务器上执行

---

### 问题 2：npm run build 失败

**错误**：
```
vite: not found
```

**解决**：
```powershell
cd D:\JLAO\frontend
npm install
npm run build
```

---

### 问题 3：nginx 重启失败

**错误**：
```
nginx: [emerg] bind() to 0.0.0.0:80 failed (98: Address already in use)
```

**解决**：
```bash
# 在服务器上执行
nginx -s reload
```

---

## 一键部署脚本

创建 `deploy-frontend.bat`：

```batch
@echo off
chcp 65001 >nul
echo ========================================
echo   JLAO 前端部署
echo ========================================
echo.

echo [1/3] 构建前端...
cd /d D:\JLAO\frontend
call npm run build
if errorlevel 1 (
    echo 错误: 前端构建失败
    pause
    exit /b 1
)

echo.
echo [2/3] 上传到服务器...
scp -r D:\JLAO\frontend\dist\* root@47.120.41.143:/var/www/jlao/
if errorlevel 1 (
    echo 错误: 上传失败
    pause
    exit /b 1
)

echo.
echo [3/3] 重启 nginx...
ssh root@47.120.41.143 "nginx -t && systemctl restart nginx"
if errorlevel 1 (
    echo 错误: nginx 重启失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo   部署完成!
echo ========================================
echo.
echo 访问地址: https://jlao.szkakayiduo.com
echo.
pause
```

使用方法：双击运行 `deploy-frontend.bat`

---

## 服务器信息

| 项目 | 值 |
|---|---|
| 服务器地址 | `47.120.41.143` |
| 前端目录 | `/var/www/jlao` |
| nginx 配置 | `/etc/nginx/conf.d/jlao.conf` |
| 后端端口 | `8001` |
| 域名 | `jlao.szkakayiduo.com` |

---

## 最近修改记录

| 日期 | 修改内容 |
|---|---|
| 2026-06-06 | 删除主页 scrcpy 驱动面板，添加到设置 |
| 2026-06-06 | 添加"客户线索"栏目，显示用户名字 |
| 2026-06-06 | 固定直播间名称为"浅玩翡翠-2号店" |
| 2026-06-06 | 优化 ADB 截图分辨率，与 scrcpy 一致 |

---

**最后更新**：2026-06-06
