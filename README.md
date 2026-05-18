# YouTube English Learning

把 YouTube 英语教学视频整理成中文辅助学习文档。流程是：用 Supadata 获取英文 transcript，生成中文辅助学习笔记；如果已配置飞书，就发布为飞书新版文档，否则输出本地 Markdown。

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

Supadata 是必需项，用来获取 YouTube transcript。

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

配置飞书后，学习笔记会发布到授权用户的飞书云空间。

### 3.1 创建飞书应用

1. 打开 <https://open.feishu.cn/app>。
2. 创建「企业自建应用」。
3. 在「凭证与基础信息」复制 `App ID` 和 `App Secret`。
4. 在应用里配置 OAuth 重定向 URL，例如 `https://example.com/callback`。
5. 给应用开通云文档权限，至少需要新版文档创建/编辑权限和 `offline_access`。

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

授权 token 会保存到：

```text
%USERPROFILE%\.codex\youtube-english-learning\feishu_state.json
```

### 3.4 指定飞书文件夹，可选

如果想把文档放到某个固定文件夹：

1. 打开飞书云文档里的目标文件夹。
2. 复制文件夹链接。
3. 取 `/folder/` 后面的 token。

示例：

```text
https://xxx.feishu.cn/drive/folder/fldcnxxxxxxxxxxxxxx
```

设置：

```powershell
setx FEISHU_FOLDER_TOKEN "fldcnxxxxxxxxxxxxxx"
```

不设置 `FEISHU_FOLDER_TOKEN` 时，飞书会使用授权用户的默认文档位置。

## 4. 使用

分析 YouTube 视频：

```text
Use $youtube-english-learning to analyze this YouTube English lesson:
https://www.youtube.com/watch?v=VIDEO_ID
```

也可以直接粘贴 transcript：

```text
Use $youtube-english-learning to turn this transcript into a Chinese-assisted study note:

[paste transcript here]
```

输出规则：

- 飞书配置完整：返回飞书文档链接。
- 飞书未配置或发布失败：生成本地 Markdown。
- Markdown 默认写入 `outputs/`，也可以用 `YOUTUBE_ENGLISH_OUTPUT_DIR` 指定目录。

## 5. 常用命令

手动提取 transcript：

```powershell
python scripts/extract_youtube_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID" --output transcript.md
```

只使用已有字幕，避免 AI 转写消耗更多额度：

```powershell
python scripts/extract_youtube_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID" --supadata-mode native --output transcript.md
```

发布 Markdown 到飞书：

```powershell
python scripts/publish_feishu_doc.py --input outputs/video-title-study-notes.md --title "Video Title English Study Notes"
```

查看当前飞书发布位置：

```powershell
python scripts/publish_feishu_doc.py --print-location
```

清除本地飞书授权：

```powershell
python scripts/publish_feishu_doc.py --clear-auth
```

## 6. 排错

- `FEISHU_NOT_CONFIGURED`：没有配置 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`，或还没有运行 `--auth-code` 保存用户授权。
- 飞书授权链接打不开：检查应用的 OAuth 重定向 URL 是否和 `--auth-url` 参数完全一致。
- 文档没有进指定文件夹：检查 `FEISHU_FOLDER_TOKEN` 是否来自授权用户可访问的文件夹。
- YouTube transcript 获取失败：检查 `SUPADATA_API_KEY`、Supadata 额度和视频是否有可用字幕。

不要把真实 API key、App Secret、OAuth code 或 token 提交到 GitHub。
