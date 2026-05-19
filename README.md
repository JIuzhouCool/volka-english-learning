# YouTube English Learning

把 YouTube 英语教学视频整理成中文辅助学习文档。这个 skill 只支持 YouTube URL 输入，字幕只通过 Supadata 远程 API 获取。

## 1. 安装

在 Codex 里运行：

```text
请使用 $skill-installer 安装这个 skill：
https://github.com/JIuzhouCool/youtube-english-learning
```

安装完成后重启 Codex。

也可以手动安装：

```powershell
git clone https://github.com/JIuzhouCool/youtube-english-learning.git "$env:USERPROFILE\.codex\skills\youtube-english-learning"
```

macOS/Linux：

```bash
git clone https://github.com/JIuzhouCool/youtube-english-learning.git ~/.codex/skills/youtube-english-learning
```

## 2. 配置 Supadata

Supadata 是必需项，用来通过远程 API 获取 YouTube 英文字幕。

1. 打开 <https://dash.supadata.ai> 申请 API key。
2. 设置环境变量。

Windows PowerShell：

```powershell
setx SUPADATA_API_KEY "your_supadata_key"
```

macOS/Linux：

```bash
echo 'export SUPADATA_API_KEY="your_supadata_key"' >> ~/.zshrc
source ~/.zshrc
```

`setx` 后需要重新打开终端或重启 Codex。

## 3. 配置飞书，可选

如果你想把最终学习笔记发布到飞书，而不是只输出本地 Markdown，需要完成下面的配置。

### 3.1 创建飞书应用

1. 打开 <https://open.feishu.cn/app>。
2. 创建「企业自建应用」。
3. 在「凭证与基础信息」复制 `App ID` 和 `App Secret`。
4. 配置 OAuth 重定向 URL，例如 `https://example.com/callback`。
5. 给应用开通创建和编辑新版文档所需权限，并确保包含 `offline_access`。

### 3.2 设置飞书环境变量

Windows PowerShell：

```powershell
setx FEISHU_APP_ID "cli_xxx"
setx FEISHU_APP_SECRET "your_feishu_secret"
```

macOS/Linux：

```bash
cat >> ~/.zshrc <<'EOF'
export FEISHU_APP_ID="cli_xxx"
export FEISHU_APP_SECRET="your_feishu_secret"
EOF
source ~/.zshrc
```

### 3.3 完成用户授权

生成授权链接：

```powershell
python scripts/publish_feishu_doc.py --auth-url "https://example.com/callback"
```

打开输出的链接并完成授权。页面跳转后，从地址栏复制 `code` 参数，然后运行：

```powershell
python scripts/publish_feishu_doc.py --auth-code "paste_code_here"
```

成功后会输出：

```text
FEISHU_AUTH_SAVED
```

授权 token 默认保存到：

```text
%USERPROFILE%\.codex\youtube-english-learning\feishu_state.json
```

### 3.4 指定飞书文件夹，可选

如果想把文档放到一个固定文件夹里，可以设置 `FEISHU_FOLDER_TOKEN`。

1. 打开飞书云文档里的目标文件夹。
2. 复制文件夹链接。
3. 取 `/folder/` 后面的 token。

示例：

```text
https://xxx.feishu.cn/drive/folder/fldcnxxxxxxxxxxxxxx
```

Windows PowerShell：

```powershell
setx FEISHU_FOLDER_TOKEN "fldcnxxxxxxxxxxxxxx"
```

不设置 `FEISHU_FOLDER_TOKEN` 时，飞书会使用授权用户的默认文档位置。

## 4. 使用

在 Codex 里使用 YouTube URL 调用：

```text
Use $youtube-english-learning to analyze this YouTube English lesson:
https://www.youtube.com/watch?v=VIDEO_ID
```

处理流程固定为：

1. 用 Supadata 远程 API 获取字幕。
2. 提取视频里的重点词汇和表达。
3. 生成中文辅助学习文档。
4. 飞书已配置时发布到飞书，否则输出 Markdown。

## 5. 输出与排错

输出规则：

- 飞书配置完整：返回飞书文档链接。
- 飞书未配置或发布失败：生成本地 Markdown。
- Markdown 默认写入 `outputs/`，也可以用 `YOUTUBE_ENGLISH_OUTPUT_DIR` 指定目录。

常见问题：

- `SUPADATA_API_KEY` 未配置：先设置环境变量，再重启终端或 Codex。
- Supadata 返回额度或限流错误：检查账户 credits，或稍后重试。
- 视频没有可用英文字幕且远程转写失败：稍后重试，或换一个视频。
- 飞书未配置：这不会阻止生成学习笔记，只会回退到 Markdown。

不要把真实 API key、App Secret、OAuth code 或 token 提交到 GitHub。
