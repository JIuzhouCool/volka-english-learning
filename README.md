# Video English Learning

将 YouTube 和 Bilibili 英语教学视频转化为中文辅助学习文档。

## 快速开始

### 1. 安装

```bash
# 在 Codex 中:
请使用 $skill-installer 安装这个 skill：
https://github.com/YOUR_USERNAME/video-english-learning
```

### 2. 配置

```bash
# YouTube (必需)
export SUPADATA_API_KEY="your_key"  # https://dash.supadata.ai

# Feishu (可选)
export FEISHU_APP_ID="cli_xxx"
export FEISHU_APP_SECRET="xxx"

# 输出目录 (可选)
export YOUTUBE_ENGLISH_OUTPUT_DIR="$HOME/notes/english"
```

### 3. 使用

```
Use $video-english-learning to analyze:
https://www.youtube.com/watch?v=VIDEO_ID
```

## 支持的平台

| 平台 | 状态 | 配置 | 说明 |
|------|------|------|------|
| YouTube | ✅ 支持 | SUPADATA_API_KEY | 自动提取字幕或AI生成 |
| Bilibili | ✅ 支持 | 无需配置 | 提取CC字幕 |
| 抖音 | ❌ 不支持 | - | 无公开API，建议手动粘贴字幕 |

## 命令行工具

```bash
# 提取字幕
python scripts/extract_video_transcript.py "URL"

# 发布到飞书
python scripts/publish_feishu_doc.py -i doc.md -t "标题"
```

## 常见问题

### 为什么不支持抖音？

抖音没有公开的字幕API。建议：
1. 在抖音APP中复制字幕文本，直接粘贴分析
2. 使用 [video-subtitle-extractor](https://github.com/YaoFANGUK/video-subtitle-extractor) 本地提取
3. 使用 `yt-dlp` + `whisper` 语音识别

### 飞书发布到哪里？

使用企业应用凭证创建的文档会保存在**企业空间**，不会自动出现在个人空间。发布后请手动另存到你的文件夹。

## 项目结构

```
video-english-learning/
├── SKILL.md                    # 技能配置
├── README.md                   # 本文件
├── scripts/
│   ├── extract_video_transcript.py    # 提取字幕
│   ├── publish_feishu_doc.py          # 发布到飞书
│   └── extractors/
│       ├── __init__.py
│       ├── youtube.py
│       └── bilibili.py
└── references/
    ├── vocabulary_selection.md
    └── learning_doc_template.md
```

## 许可证

MIT
