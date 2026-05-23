# 推送到 GitHub（若 Agent 未自动推送成功）

本地已 `git commit`，在 GitHub 网页新建空仓库 **`aigc-comfy-pipeline`**（不要勾选 README），然后：

```powershell
cd C:\面试\aigc-comfy-pipeline
git remote add origin https://github.com/kisaragiy/aigc-comfy-pipeline.git
git branch -M main
git push -u origin main
```

推送后验证：

- 仓库：https://github.com/kisaragiy/aigc-comfy-pipeline  
- 作品集页：https://github.com/kisaragiy/aigc-comfy-pipeline/blob/main/docs/GALLERY.html  
- 在仓库 Settings → 勾选 **Pages**（可选）：Source 选 `main` / `/docs`，可用 Pages 打开 GALLERY（需把 GALLERY 放到 docs 根或配置）

## Profile README

把 `C:\面试\github-profile-README.md` 内容复制到 GitHub 新建仓库 **`kisaragiy/kisaragiy`** 的 README.md。
