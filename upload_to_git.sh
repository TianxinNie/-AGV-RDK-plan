#!/bin/bash

# 配置区（请按需修改）
REMOTE_REPO_SSH="git@github.com:TianxinNie/-AGV-RDK-plan.git"
GIT_USER_NAME="Tianxin Nie"
GIT_USER_EMAIL="nietianxin7@gmail.com"

echo "=== 开始智能上传脚本 ==="

# 检查是否为 Git 仓库
if [ ! -d ".git" ]; then
  echo "[INFO] 当前目录未检测到 Git 仓库，正在初始化..."
  git init
else
  echo "[INFO] 已检测到 Git 仓库，跳过初始化"
fi

# 检查 Git 用户配置
USER_NAME=$(git config user.name)
USER_EMAIL=$(git config user.email)
if [ -z "$USER_NAME" ]; then
  echo "[INFO] 未检测到 Git 用户名，设置为: $GIT_USER_NAME"
  git config user.name "$GIT_USER_NAME"
else
  echo "[INFO] 当前 Git 用户名: $USER_NAME"
fi

if [ -z "$USER_EMAIL" ]; then
  echo "[INFO] 未检测到 Git 用户邮箱，设置为: $GIT_USER_EMAIL"
  git config user.email "$GIT_USER_EMAIL"
else
  echo "[INFO] 当前 Git 用户邮箱: $USER_EMAIL"
fi

# 添加所有改动文件
echo "[INFO] 添加所有文件到暂存区..."
git add .

# 检查是否有改动
if git diff --cached --quiet; then
  echo "[INFO] 没有检测到文件改动，无需提交"
else
  echo "[INFO] 检测到文件改动，正在提交..."
  git commit -m "自动提交：$(date '+%Y-%m-%d %H:%M:%S')"
fi

# 配置远程仓库（使用 SSH）
if git remote | grep origin > /dev/null; then
  echo "[INFO] 远程仓库已存在，更新远程仓库地址为：$REMOTE_REPO_SSH"
  git remote set-url origin $REMOTE_REPO_SSH
else
  echo "[INFO] 添加远程仓库地址：$REMOTE_REPO_SSH"
  git remote add origin $REMOTE_REPO_SSH
fi

# 确认主分支为 main
CURRENT_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "")
if [ "$CURRENT_BRANCH" != "main" ]; then
  echo "[INFO] 当前分支为 $CURRENT_BRANCH，切换到 main"
  git branch -M main
else
  echo "[INFO] 当前分支为 main"
fi

# 推送到远程仓库
echo "[INFO] 正在推送代码到远程仓库 main 分支..."
git push -u origin main

if [ $? -eq 0 ]; then
  echo "[SUCCESS] 代码已成功推送到远程仓库！"
else
  echo "[ERROR] 推送失败，请检查网络和认证状态。"
fi

echo "=== 脚本执行完毕 ==="

