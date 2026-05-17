# YouTube English Learning Skill

把 YouTube 英语教学视频或英文字幕整理成中文辅助学习文档。默认优先发布到飞书；没有配置飞书或发布失败时，生成本地 Markdown。

## 1. 安装

推荐用内置 `skill-installer` 安装：

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" --repo JIuzhouCool/youtube-english-learning --path . --name youtube-english-learning
```

macOS/Linux：

```bash
python "$HOME/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py" --repo JIuzhouCool/youtube-english-learning --path . --name youtube-english-learning
```

也可以手动安装：

```powershell
git clone https://github.com/JIuzhouCool/youtube-english-learning.git "$env:USERPROFILE\.codex\skills\youtube-english-learning"
```

macOS/Linux：

```bash
git clone https://github.com/JIuzhouCool/youtube-english-learning.git ~/.codex/skills/youtube-english-learning
```

安装后重启 Codex。

## 2. 申请 API

### Supadata，可选

用于增强 YouTube 字幕提取能力。

- API key 申请：<https://dash.supadata.ai>
- 文档：<https://docs.supadata.ai/>

不配置 Supadata 时，脚本会尝试使用 `youtube-transcript-api` 回退。

### 飞书，可选

用于把学习笔记创建成飞书文档。

- 应用管理：<https://open.feishu.cn/app>
- 创建「企业自建应用」后，在「凭证与基础信息」获取 `App ID` 和 `App Secret`。
- 应用需要有创建、编辑云文档的权限。

获取 `FEISHU_FOLDER_TOKEN`：

1. 打开飞书云文档里的目标文件夹。
2. 复制浏览器地址栏链接或文件夹分享链接。
3. 找到 `/folder/` 后面的字符串，例如：

```text
https://xxx.feishu.cn/drive/folder/fldcnxxxxxxxxxxxxxx
```

这里的 `fldcnxxxxxxxxxxxxxx` 就是 `FEISHU_FOLDER_TOKEN`。这个变量是可选的，不设置时会尝试创建到默认位置。

## 3. 设置环境变量

### Windows PowerShell，当前会话

```powershell
$env:SUPADATA_API_KEY="your_supadata_key"
$env:FEISHU_APP_ID="cli_xxx"
$env:FEISHU_APP_SECRET="your_feishu_secret"
$env:FEISHU_FOLDER_TOKEN="fldcnxxxxxxxxxxxxxx"
$env:YOUTUBE_ENGLISH_OUTPUT_DIR="D:\notes\english"
```

### Windows PowerShell，持久化

```powershell
setx SUPADATA_API_KEY "your_supadata_key"
setx FEISHU_APP_ID "cli_xxx"
setx FEISHU_APP_SECRET "your_feishu_secret"
setx FEISHU_FOLDER_TOKEN "fldcnxxxxxxxxxxxxxx"
setx YOUTUBE_ENGLISH_OUTPUT_DIR "D:\notes\english"
```

`setx` 后需要重新打开终端或重启 Codex。

### macOS/Linux，当前会话

```bash
export SUPADATA_API_KEY="your_supadata_key"
export FEISHU_APP_ID="cli_xxx"
export FEISHU_APP_SECRET="your_feishu_secret"
export FEISHU_FOLDER_TOKEN="fldcnxxxxxxxxxxxxxx"
export YOUTUBE_ENGLISH_OUTPUT_DIR="$HOME/notes/english"
```

### macOS/Linux，持久化

把上面的 `export ...` 写入 `~/.zshrc` 或 `~/.bashrc`，然后运行：

```bash
source ~/.zshrc
```

不要把真实 API key、App Secret 或 token 提交到 GitHub。

## 4. 使用

在 Codex 中调用：

```text
Use $youtube-english-learning to analyze this YouTube English lesson:
https://www.youtube.com/watch?v=VIDEO_ID
```

也可以直接粘贴字幕：

```text
Use $youtube-english-learning to turn this transcript into a Chinese-assisted study note:

[paste transcript here]
```

交付规则：

- 飞书发布成功：返回飞书文档链接。
- 飞书未配置：生成 Markdown 文件。
- 飞书发布失败：生成 Markdown 兜底，并说明失败原因。

## 5. 手动脚本

安装字幕回退依赖：

```powershell
python -m pip install youtube-transcript-api
```

提取字幕：

```powershell
python scripts/extract_youtube_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID" --output transcript.md
```

常用参数：

```powershell
python scripts/extract_youtube_transcript.py "URL" --provider supadata
python scripts/extract_youtube_transcript.py "URL" --provider local-api
python scripts/extract_youtube_transcript.py "URL" --format text
python scripts/extract_youtube_transcript.py "URL" --supadata-mode auto
```

发布 Markdown 到飞书：

```powershell
python scripts/publish_feishu_doc.py --input outputs/video-title-study-notes.md --title "Video Title English Study Notes"
```

飞书发布脚本退出码：

- `0`：成功，stdout 输出飞书文档 URL。
- `1`：飞书已配置但发布失败。
- `2`：飞书未配置。

## 6. Markdown 输出

没有飞书或飞书发布失败时，最终学习笔记会写成 Markdown。

- 默认目录：`outputs/`
- 自定义目录：`YOUTUBE_ENGLISH_OUTPUT_DIR`
- 支持绝对路径和相对路径
- 相对路径按 skill 根目录解析

## 7. 生成内容

学习文档会包含：

- 视频信息和中文摘要
- `UP 主本课重点`
- 重点词汇、短语、IPA、中文含义、语境解释、原文例句和学习例句
- 易混点、用法提醒、发音提示
- 复习卡片、小测和今日练习

选词规则见 `references/vocabulary_selection.md`，文档模板见 `references/learning_doc_template.md`。

## 注意事项

- 不使用 `yt-dlp`，不下载音频，不运行本地语音识别。
- transcript 只是中间步骤，默认不要作为最终交付。
- IPA 不确定时标记为 `approx.` 或 `近似`。
