#!/bin/bash

# 远程仓库地址
REMOTE_REPO="https://github.com/TianxinNie/-AGV-RDK-plan.git"

echo "开始初始化 Git 仓库..."

# 初始化本地仓库
git init

# 添加所有文件
git add .

# 提交代码，提交信息你可以改
git commit -m "首次提交"

# 关联远程仓库（如果之前设置过，可以先删除再添加）
git remote remove origin 2>/dev/null

git remote add origin $REMOTE_REPO

# 设置默认分支为 main
git branch -M main

# 推送代码到远程仓库
git push -u origin main

echo "代码已成功推送到远程仓库：$REMOTE_REPO"

