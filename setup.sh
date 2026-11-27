#!/usr/bin/env bash
# 一键上传到 GitHub（Mac / Linux）
# 用法：bash setup.sh
set -e
cd "$(dirname "$0")"

echo
echo "============================================"
echo "  节点项目 - 一键上传到 GitHub"
echo "============================================"
echo
echo "前提：你已经在 GitHub 网页上建好了一个空仓库"
echo "      （建的时候不要勾 Add a README file）"
echo

if ! command -v git >/dev/null 2>&1; then
  echo "[X] 没装 Git。Mac 执行 xcode-select --install；"
  echo "    Ubuntu/Debian 执行 sudo apt install git"
  exit 1
fi

read -r -p "GitHub 用户名: " GHUSER
read -r -p "仓库名（英文，例如 free-node-hub）: " GHREPO

if [ -z "$GHUSER" ] || [ -z "$GHREPO" ]; then
  echo "[X] 用户名和仓库名都不能空着。"
  exit 1
fi

if [ ! -d .git ]; then
  git init -q
  git branch -M main
fi

git config user.name  "$GHUSER"
git config user.email "$GHUSER@users.noreply.github.com"

git add -A
git commit -q -m "初始化：节点订阅项目" || true

git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/${GHUSER}/${GHREPO}.git"

echo
echo "正在推送，按提示输入 GitHub 账号密码 / token..."
echo
git push -u origin main

cat <<EOF

============================================
  上传成功！
============================================

接下来 3 步（在 GitHub 网页上点）：

  1. Settings -> Actions -> General
     最下面 Workflow permissions 选 Read and write，点 Save

  2. Settings -> Pages
     Source 选 GitHub Actions

  3. 顶部 Actions -> 左边「更新节点订阅」-> 右边 Run workflow

跑完约 5 分钟，打开：
  https://${GHUSER}.github.io/${GHREPO}/

页面上会直接给出订阅地址。
EOF
