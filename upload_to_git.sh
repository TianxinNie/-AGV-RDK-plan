#!/bin/bash
echo "=== 开始上传代码到 Git ==="

git init
git remote add origin https://github.com/你的用户名/你的仓库名.git
git add .
git commit -m "提交更新"
git branch -M main
git push -u origin main

echo "=== 上传完成 ==="

