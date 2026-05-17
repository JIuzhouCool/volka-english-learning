---
name: youtube-english-learning
description: Turn a YouTube English teaching video or pasted transcript into one polished Chinese-assisted study document. Use when the user wants to learn from a YouTube English lesson, extract the creator's intended vocabulary and phrases, and receive a final study note with IPA, Chinese meanings, examples, usage notes, review cards, and exercises. Prefer publishing to Feishu when configured; otherwise deliver Markdown.
---

# YouTube English Learning

## Goal

Create one final study document for Chinese-speaking English learners. Prefer a Feishu document when Feishu is configured; otherwise create a local Markdown document. Transcript extraction is only an internal step; do not deliver a separate transcript unless the user explicitly asks for it.

## Workflow

1. Get lesson text.
   - If the user provides a YouTube URL, run `scripts/extract_youtube_transcript.py`.
   - The script uses Supadata first when `SUPADATA_API_KEY` is set, then falls back to `youtube-transcript-api`.
   - If both providers fail, ask the user to paste the transcript.
   - If the user already provides transcript text, use it directly.
2. Read `references/vocabulary_selection.md` before selecting vocabulary.
3. Read `references/learning_doc_template.md` before writing the document.
4. Draft the final study note as Markdown using the template.
5. Try to publish the Markdown draft to Feishu with `scripts/publish_feishu_doc.py`.
   - If `FEISHU_APP_ID` and `FEISHU_APP_SECRET` are configured and publishing succeeds, deliver only the Feishu document link.
   - If Feishu is not configured, skip Feishu and create a Markdown file.
   - If Feishu is configured but publishing fails, create a Markdown file as a fallback and briefly mention the Feishu failure in the final response.
6. For Markdown fallback, write the file to the directory from `YOUTUBE_ENGLISH_OUTPUT_DIR`.
   - If `YOUTUBE_ENGLISH_OUTPUT_DIR` is unset, use `outputs/`.
   - Resolve relative paths from the skill directory.
   - Create the directory if it does not exist.
   - Use a concise, filesystem-safe filename such as `video-title-study-notes.md`.
   - If the video title is unknown, use a short topic-based filename or the video ID.
7. Generate only the final study document as the deliverable.
8. In the final user-facing response, link only the Feishu document or the Markdown fallback file. Do not mention transcript files, provider logs, or intermediate artifacts unless needed to explain a failure.

## Internal Transcript Helper

Run from the skill directory or pass the full path:

```powershell
python scripts/extract_youtube_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID" --output transcript.md
```

Options:

```powershell
python scripts/extract_youtube_transcript.py "URL" --provider supadata
python scripts/extract_youtube_transcript.py "URL" --provider local-api
python scripts/extract_youtube_transcript.py "URL" --supadata-mode auto
```

Configure Supadata with:

```powershell
$env:SUPADATA_API_KEY="your_key"
```

Default Supadata mode is `native`, which uses existing captions and avoids unnecessary generated transcription credits. Use `--supadata-mode auto` only when the user wants stronger transcript fallback.

The helper supports Supadata's immediate transcript responses and async `jobId` responses. For async jobs, it polls briefly and reports a clear retry message if the transcript is still not ready.

Do not use `yt-dlp`, download audio, or run local speech recognition in this workflow.

## Feishu Publishing Helper

Publish a completed Markdown study note to Feishu:

```powershell
python scripts/publish_feishu_doc.py --input outputs/video-title-study-notes.md --title "Video Title English Study Notes"
```

You can also pass the Markdown draft through stdin:

```powershell
Get-Content outputs/video-title-study-notes.md -Raw | python scripts/publish_feishu_doc.py --title "Video Title English Study Notes"
```

Configure Feishu with:

```powershell
$env:FEISHU_APP_ID="cli_xxx"
$env:FEISHU_APP_SECRET="your_secret"
$env:FEISHU_FOLDER_TOKEN="optional_folder_token"
```

The helper exit codes are:

- `0`: Feishu document created; stdout contains the document URL.
- `1`: Feishu was configured but publishing failed; create a Markdown fallback.
- `2`: Feishu was not configured; create a Markdown fallback.

## Markdown Fallback Output

Configure the Markdown fallback directory with:

```powershell
$env:YOUTUBE_ENGLISH_OUTPUT_DIR="D:\notes\english"
```

If unset, use `outputs/`. This setting only controls the final Markdown study note; it does not control transcript helper output.

## Study Document Requirements

The final Markdown document must include:

- Video information.
- A short Chinese summary.
- A section named `UP 主本课重点`.
- A vocabulary/phrase table with English item, IPA, Chinese meaning, context explanation, original sentence, learner example, and common collocations or patterns.
- Pronunciation or usage notes for tricky items.
- Review cards and a short quiz.

For IPA, provide the best-known pronunciation. If uncertain, mark it as approximate.

## Quality Bar

- Select 15-25 high-value items by default.
- Prefer phrases, chunks, collocations, discourse markers, and teaching targets over isolated rare words.
- Explain meanings in the video's context first, then give general meaning.
- Keep Chinese explanations concise and learner-friendly.
- Create original learner examples that are natural and reusable.
- Never dump the full transcript into the final learning document unless the user explicitly asks for it.
