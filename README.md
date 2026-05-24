# Volka English Learning Skill

把 Volka English / YouTube / Bilibili 英语教学视频整理成中文辅助学习文档：先获取或生成英文 transcript，再生成学习笔记。默认优先发布到飞书；没有配置飞书或发布失败时，生成本地 Markdown。

## 1. 直接让 Codex 安装

在 Codex 里直接说：

```text
请使用 $skill-installer 安装这个 skill：https://github.com/JIuzhouCool/volka-english-learning
```

安装后重启 Codex，让 skill 被重新发现。

也可以手动运行安装脚本：

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" --repo JIuzhouCool/volka-english-learning --path . --name volka-english-learning
```

## 2. Transcript 提取依赖

YouTube 继续通过 Supadata API 获取 transcript。

- API key 申请：<https://dash.supadata.ai>
- Free 用户额度：每月 100 credits，限速 1 req/s。
- 已有 transcript 通常消耗 1 credit。
- 没有现成字幕时，默认允许 AI generated transcript，按 2 credits/min 消耗。

配置 `SUPADATA_API_KEY` 后才能用 YouTube URL 自动提取字幕。

Bilibili 没有稳定公开免费的字幕 API，本 skill 使用本地方案：

- 先尝试公开视频已有字幕。
- 拿不到字幕时，下载临时音频并用本地 ASR 转写。

本地 ASR 需要：

- `yt-dlp`：下载公开视频音频或字幕。
- `faster-whisper`：本地语音识别。
- `ffmpeg`：通常不必单独配置；如果 `yt-dlp` 在某些视频上提示需要它，再安装。

```bash
pip install faster-whisper yt-dlp
```

下载的临时音频会在转写成功或失败后自动删除。

## 3. 飞书，可选

配置飞书后，最终学习笔记会优先创建为飞书文档。当前实现只读取环境变量里的 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`。

- 应用管理：<https://open.feishu.cn/app>
- 创建「企业自建应用」。
- 在「凭证与基础信息」里获取 `App ID` 和 `App Secret`。
- 给应用开通创建、编辑云文档所需权限。

目前未配置发布到个人指定文件夹。飞书发布成功后，可以在飞书里手动保存一份到自己的目标文件夹。

## 4. 设置环境变量

Windows PowerShell，当前会话：

```powershell
$env:SUPADATA_API_KEY="your_supadata_key"
$env:FEISHU_APP_ID="cli_xxx"
$env:FEISHU_APP_SECRET="your_feishu_secret"
$env:YOUTUBE_ENGLISH_OUTPUT_DIR="D:\notes\english"
```

Windows PowerShell，持久化：

```powershell
setx SUPADATA_API_KEY "your_supadata_key"
setx FEISHU_APP_ID "cli_xxx"
setx FEISHU_APP_SECRET "your_feishu_secret"
setx YOUTUBE_ENGLISH_OUTPUT_DIR "D:\notes\english"
```

`setx` 后需要重新打开终端或重启 Codex。

## 5. 在 Codex 中使用

分析 YouTube 视频：

```text
Use $youtube-english-learning to analyze this YouTube English lesson:
https://www.youtube.com/watch?v=VIDEO_ID
```

分析 Bilibili 视频：

```text
Use $youtube-english-learning to analyze this Bilibili English lesson:
https://www.bilibili.com/video/BV...
```

交付规则：

- 飞书发布成功：只返回飞书文档链接。
- 飞书未配置：生成 Markdown 文件。
- 飞书发布失败：生成 Markdown 兜底，并说明失败原因。
- Bilibili 下载失败：请稍后重试，或直接粘贴 transcript。

## 6. Markdown 输出

没有飞书或飞书发布失败时，最终学习笔记会写成 Markdown。

- 默认目录：`outputs/`
- 自定义目录：`YOUTUBE_ENGLISH_OUTPUT_DIR`
- 支持绝对路径和相对路径
- 相对路径按 skill 根目录解析

## 7. 学习文档内容

学习文档会包含：

- 视频信息和中文摘要
- `UP` 主讲课重点
- 重点词汇、短语、IPA、中文含义、语境解释、原文例句和学习例句
- 易混点、用法提醒、发音提示
- 复习卡片、小测和今日练习

选词规则见 `references/vocabulary_selection.md`，文档模板见 `references/learning_doc_template.md`。
