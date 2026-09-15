<#
.SYNOPSIS
  双轨上游同步脚本：main = 上游镜像，huihui = 慧惠定制。

.DESCRIPTION
  1. 拉取上游 upstream/main。
  2. 若上游领先，将 main 重置为上游镜像（剥离 token 无法推送的 CI workflow）并强制推送。
  3. 将 main 合并到 huihui（--no-ff），冲突时暂停，等待人工按分诊规则裁决后再推送。

.NOTES
  - 前置：已配置上游远程
      git remote add upstream https://github.com/lsdefine/GenericAgent.git
  - 当前 token 无 workflow scope，main 镜像会剥离 .github/workflows/* 以便推送。
  - main 轨道使用 force push（vendor 标准）；huihui 轨道只 merge，不 force push。
#>

Write-Host "== 双轨上游同步 ==" -ForegroundColor Cyan

# 1) 拉取上游
git fetch upstream --prune
if ($LASTEXITCODE -ne 0) {
    Write-Host "fetch upstream 失败，请检查网络/代理。" -ForegroundColor Red
    exit 1
}

# 2) 计算领先 / 落后
$counts = (git rev-list --left-right --count main...upstream/main) -split "\s+"
$ahead  = [int]$counts[0]
$behind = [int]$counts[1]
Write-Host ("main 相对 upstream/main：ahead={0}  behind={1}" -f $ahead, $behind) -ForegroundColor Cyan

if ($behind -le 0) {
    Write-Host "已是最新，无需同步。" -ForegroundColor Green
    exit 0
}

Write-Host ("上游有 {0} 个提交待同步。开始同步 main 分支..." -f $behind) -ForegroundColor Yellow

# 3) main 重置为上游镜像
git switch main
if ($LASTEXITCODE -ne 0) { Write-Host "切换 main 失败。" -ForegroundColor Red; exit 1 }

git reset --hard upstream/main
if ($LASTEXITCODE -ne 0) { Write-Host "reset main 失败。" -ForegroundColor Red; exit 1 }

# 4) 剥离 token 无法推送的 CI workflow（无 workflow scope）
$wf = @(git ls-files ".github/workflows")
if ($wf.Count -gt 0) {
    git rm --quiet --ignore-unmatch ".github/workflows/*"
    $staged = @(git diff --cached --name-only)
    if ($staged.Count -gt 0) {
        git commit --quiet -m "chore: 剥离上游 CI workflow（token 无 workflow scope）"
        Write-Host "已剥离上游 CI workflow。" -ForegroundColor Yellow
    }
}

git push --force origin main
if ($LASTEXITCODE -ne 0) { Write-Host "force push main 失败。" -ForegroundColor Red; exit 1 }
Write-Host "main 分支已同步至 upstream/main。" -ForegroundColor Green

# 5) huihui 合并 main
git switch huihui
if ($LASTEXITCODE -ne 0) { Write-Host "切换 huihui 失败。" -ForegroundColor Red; exit 1 }

git merge main --no-ff -m "chore(sync): merge main (upstream sync)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "合并冲突，请按分诊规则裁决后执行：git add -A; git commit" -ForegroundColor Red
    exit 1
}

git push origin huihui
if ($LASTEXITCODE -ne 0) { Write-Host "push huihui 失败。" -ForegroundColor Red; exit 1 }
Write-Host "huihui 分支已更新。" -ForegroundColor Green

Write-Host "== 同步完成 ==" -ForegroundColor Green