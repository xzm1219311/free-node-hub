@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ============================================
echo   节点项目 - 一键上传到 GitHub
echo ============================================
echo.
echo 前提：你已经在 GitHub 网页上建好了一个空仓库
echo      （建的时候不要勾 Add a README file）
echo.

where git >nul 2>nul
if errorlevel 1 (
  echo [X] 没装 Git。先去 https://git-scm.com/download/win 下载安装，
  echo     安装时一路点 Next 就行，装完关掉这个窗口重新双击我。
  echo.
  pause
  exit /b 1
)

set "GHUSER="
set "GHREPO="
set /p GHUSER=请输入 GitHub 用户名（英文）:
set /p GHREPO=请输入仓库名（英文，例如 free-node-hub）:

if "%GHUSER%"=="" goto :bad
if "%GHREPO%"=="" goto :bad

echo.
echo 正在准备提交...

if not exist ".git" (
  git init -q
  git branch -M main
)

git config user.name "%GHUSER%" >nul 2>nul
git config user.email "%GHUSER%@users.noreply.github.com" >nul 2>nul

git add -A
git commit -q -m "初始化：节点订阅项目" 2>nul

git remote remove origin >nul 2>nul
git remote add origin "https://github.com/%GHUSER%/%GHREPO%.git"

echo.
echo 正在推送到 GitHub，可能会弹出登录窗口 —— 按提示授权就行...
echo.
git push -u origin main
if errorlevel 1 (
  echo.
  echo [X] 推送失败，最常见的三个原因：
  echo     1. 仓库还没在网页上创建
  echo     2. 仓库名或用户名打错了
  echo     3. 登录没通过（重跑一次，按弹窗授权）
  echo.
  echo 把上面红色的报错整段复制给我，我帮你看。
  pause
  exit /b 1
)

echo.
echo ============================================
echo   上传成功！
echo ============================================
echo.
echo 接下来还有 3 步（在 GitHub 网页上点）：
echo.
echo   1. Settings -^> Actions -^> General
echo      最下面 Workflow permissions 选 Read and write，点 Save
echo.
echo   2. Settings -^> Pages
echo      Source 选 GitHub Actions
echo.
echo   3. 顶部 Actions 标签 -^> 左边「更新节点订阅」-^> 右边 Run workflow
echo.
echo 跑完大约 5 分钟，然后打开：
echo   https://%GHUSER%.github.io/%GHREPO%/
echo.
echo 那个页面上会直接给你订阅地址。
echo.
pause
exit /b 0

:bad
echo.
echo [X] 用户名和仓库名都不能空着。
pause
exit /b 1
