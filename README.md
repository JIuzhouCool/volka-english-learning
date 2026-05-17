# YouTube English Learning Skill

把 YouTube 英语教学视频或已粘贴的英文字幕，整理成适合中文学习者使用的学习文档。默认优先发布到飞书文档；如果没有配置飞书，或飞书发布失败，则生成本地 Markdown 文件。

## 快速开始

1. 安装 skill。
2. 可选配置 Supadata 和飞书环境变量。
3. 在 Codex 中使用 `$youtube-english-learning` 分析 YouTube 英语教学视频。
4. 查看最终交付：飞书文档链接，或 Markdown 兜底文件链接。

示例：

```text
Use $youtube-english-learning to analyze this YouTube English lesson:
https://www.youtube.com/watch?v=VIDEO_ID
```

也可以直接粘贴 transcript：

```text
Use $youtube-english-learning to turn this transcript into a Chinese-assisted study note:

[paste transcript here]
```

## 安装 Skill

推荐使用内置 `skill-installer` 从 GitHub 安装：

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" --repo JIuzhouCool/youtube-english-learning --path . --name youtube-english-learning
```

macOS/Linux：

```bash
python "$HOME/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py" --repo JIuzhouCool/youtube-english-learning --path . --name youtube-english-learning
```

如果你的 Codex 环境支持直接调用系统 skill，也可以让 Codex 帮你执行：

```text
Use $skill-installer to install https://github.com/JIuzhouCool/youtube-english-learning
```

手动安装方式：

```powershell
git clone https://github.com/JIuzhouCool/youtube-english-learning.git "$env:USERPROFILE\.codex\skills\youtube-english-learning"
```

macOS/Linux：

```bash
git clone https://github.com/JIuzhouCool/youtube-english-learning.git ~/.codex/skills/youtube-english-learning
```

安装后重启 Codex，让新 skill 被重新发现。

默认安装位置：

- Windows：`%USERPROFILE%\.codex\skills\youtube-english-learning`
- macOS/Linux：`~/.codex/skills/youtube-english-learning`

## 能做什么

- 从 YouTube URL 提取英文字幕，或直接使用用户粘贴的 transcript。
- 识别 UP 主真正想教的词汇、短语、句型、搭配和发音点。
- 生成中文辅助学习笔记，包括摘要、重点表达、IPA、语境解释、例句、易混点、复习卡片和小测。
- 飞书配置可用时，优先创建飞书文档。
- 飞书未配置或发布失败时，输出 Markdown 文件作为兜底。

## API 申请入口

### Supadata

Supadata 用于增强 YouTube transcript 提取能力。

- 控制台/API key 申请：<https://dash.supadata.ai>
- 官方文档：<https://docs.supadata.ai/>

申请后把 key 设置到 `SUPADATA_API_KEY`。如果不配置 Supadata，脚本仍会尝试使用本地回退方案 `youtube-transcript-api`。

### 飞书开放平台

飞书用于把学习笔记发布成飞书文档。

- 飞书开放平台应用管理：<https://open.feishu.cn/app>
- 创建「企业自建应用」后，在「凭证与基础信息」中获取 `App ID` 和 `App Secret`。
- 如果希望文档创建到指定文件夹，还需要准备 `FEISHU_FOLDER_TOKEN`。

飞书应用需要具备创建和编辑文档所需权限。当前脚本使用自建应用的 tenant token，不使用用户 OAuth。

### youtube-transcript-api

`youtube-transcript-api` 是本地回退方案，不需要 API key，只需要安装 Python 包。

```powershell
python -m pip install youtube-transcript-api
```

## 环境变量设置

### Windows PowerShell 当前会话

```powershell
$env:SUPADATA_API_KEY="your_supadata_key"
$env:FEISHU_APP_ID="cli_xxx"
$env:FEISHU_APP_SECRET="your_feishu_secret"
$env:FEISHU_FOLDER_TOKEN="optional_folder_token"
$env:YOUTUBE_ENGLISH_OUTPUT_DIR="D:\notes\english"
```

当前会话设置只对当前终端窗口有效。

### Windows 持久化

```powershell
setx SUPADATA_API_KEY "your_supadata_key"
setx FEISHU_APP_ID "cli_xxx"
setx FEISHU_APP_SECRET "your_feishu_secret"
setx FEISHU_FOLDER_TOKEN "optional_folder_token"
setx YOUTUBE_ENGLISH_OUTPUT_DIR "D:\notes\english"
```

执行 `setx` 后需要重新打开终端或重启 Codex，新的环境变量才会生效。

### macOS/Linux 当前会话

```bash
export SUPADATA_API_KEY="your_supadata_key"
export FEISHU_APP_ID="cli_xxx"
export FEISHU_APP_SECRET="your_feishu_secret"
export FEISHU_FOLDER_TOKEN="optional_folder_token"
export YOUTUBE_ENGLISH_OUTPUT_DIR="$HOME/notes/english"
```

### macOS/Linux 持久化

写入 `~/.zshrc` 或 `~/.bashrc`：

```bash
export SUPADATA_API_KEY="your_supadata_key"
export FEISHU_APP_ID="cli_xxx"
export FEISHU_APP_SECRET="your_feishu_secret"
export FEISHU_FOLDER_TOKEN="optional_folder_token"
export YOUTUBE_ENGLISH_OUTPUT_DIR="$HOME/notes/english"
```

写入后运行 `source ~/.zshrc` 或重新打开终端。

不要把真实 API key、App Secret 或 token 提交到 GitHub。

## 目录结构

```text
youtube-english-learning/
├── SKILL.md
├── README.md
├── agents/
│   └── openai.yaml
├── references/
│   ├── learning_doc_template.md
│   └── vocabulary_selection.md
└── scripts/
    ├── extract_youtube_transcript.py
    └── publish_feishu_doc.py
```

## 字幕提取

脚本会优先使用 Supadata，再回退到 `youtube-transcript-api`。

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

默认 Supadata mode 是 `native`，只使用已有字幕，避免不必要的生成式转写额度消耗。只有在确实需要更强兜底时，再使用 `--supadata-mode auto`。

## 飞书发布

手动发布 Markdown 到飞书：

```powershell
python scripts/publish_feishu_doc.py --input outputs/video-title-study-notes.md --title "Video Title English Study Notes"
```

也可以从 stdin 传入 Markdown：

```powershell
Get-Content outputs/video-title-study-notes.md -Raw | python scripts/publish_feishu_doc.py --title "Video Title English Study Notes"
```

退出码：

- `0`：飞书文档创建成功，stdout 输出文档 URL。
- `1`：飞书已配置但发布失败，应生成 Markdown 兜底。
- `2`：飞书未配置，应生成 Markdown 兜底。

## Markdown 兜底输出

默认输出到 `outputs/`。你可以用 `YOUTUBE_ENGLISH_OUTPUT_DIR` 修改输出目录：

```powershell
$env:YOUTUBE_ENGLISH_OUTPUT_DIR="D:\notes\english"
```

规则：

- 支持绝对路径和相对路径。
- 相对路径按 skill 根目录解析。
- 目录不存在时应先创建。
- 文件名建议使用 `video-title-study-notes.md` 这类安全文件名。
- 该变量只影响最终学习笔记，不影响 transcript helper 的 `--output`。

最终交付规则：

- 飞书发布成功：只返回飞书文档链接。
- 飞书未配置：生成 Markdown 文件并返回文件链接。
- 飞书已配置但发布失败：生成 Markdown 文件兜底，并简短说明飞书失败原因。

## 生成内容要求

最终学习文档应包含：

- 视频信息。
- 3-5 句话中文摘要。
- `UP 主本课重点`。
- 重点词汇与表达表格。
- 易混点与用法提醒。
- 发音提示。
- 复习卡片。
- 小测与今日练习。

选词原则见 `references/vocabulary_selection.md`，文档结构见 `references/learning_doc_template.md`。

## 注意事项

- 不使用 `yt-dlp`、不下载音频、不运行本地语音识别。
- transcript 只是中间步骤，默认不要把完整 transcript 作为最终交付。
- IPA 不确定时标记为 `approx.` 或 `近似`。
- 优先选择短语、搭配、句型、话语标记和 UP 主反复讲解的教学目标，而不是孤立生词。
