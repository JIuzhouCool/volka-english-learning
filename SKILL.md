---
name: video-english-learning
description: Turn YouTube or Bilibili English teaching videos into structured Chinese-assisted study documents with vocabulary, IPA, examples, and exercises.
---

# Video English Learning

## Purpose
Create Chinese-assisted English study documents from video lessons. Supports YouTube (via Supadata) and Bilibili (via official API).

## Workflow
1. Extract transcript using `scripts/extract_video_transcript.py`
2. Select vocabulary per `references/vocabulary_selection.md`
3. Generate study document per `references/learning_doc_template.md`
4. Publish to Feishu if configured, else save as Markdown

## Platform Support
- **YouTube**: Requires `SUPADATA_API_KEY`. Mode: `auto` (captions → AI transcript)
- **Bilibili**: No config needed. Uses public API for CC subtitles
- **Douyin**: Not supported (no public subtitle API)

## Feishu Publishing Note
Documents are created in the tenant space (enterprise app), not directly in personal "My Space". After publishing, manually save the document to your folder in Feishu.

## Output Rules
- Deliver one final document only
- Use safe filename: `video-title-study-notes.md`
- Link the actual Feishu doc or Markdown file in response
