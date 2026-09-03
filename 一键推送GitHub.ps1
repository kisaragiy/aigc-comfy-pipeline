# 在 GitHub 网页先创建空仓库 aigc-comfy-pipeline 后运行本脚本
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path .git)) { git init }
git add -A
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "feat: AIGC ComfyUI pipeline portfolio with samples and GALLERY"
}
git branch -M main
git remote remove origin 2>$null
git remote add origin https://github.com/kisaragiy/aigc-comfy-pipeline.git
git push -u origin main
Write-Host ""
Write-Host "OK 作品集: https://github.com/kisaragiy/aigc-comfy-pipeline/blob/main/docs/GALLERY.html"
