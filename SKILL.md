---
name: youtube-english-learning
description: Turn a YouTube English teaching video or pasted transcript into one polished Chinese-assisted study document. Use when the user wants to learn from a YouTube English lesson, extract the creator's intended vocabulary and phrases, and receive a final study note with IPA, Chinese meanings, examples, usage notes, review cards, and exercises. Requires Supadata for YouTube transcript extraction. Prefer publishing to Feishu when configured; otherwise deliver Markdown.
---

# YouTube English Learning

## Purpose

Create one final Chinese-assisted English study document from a YouTube English lesson or pasted transcript. The final deliverable should be a Feishu document when Feishu is configured; otherwise use Markdown.

## Workflow

1. Get the lesson text.
   - For a YouTube URL, run `scripts/extract_youtube_transcript.py`.
   - The transcript helper is Supadata-only and requires `SUPADATA_API_KEY`.
   - Its default Supadata mode is `auto`: existing captions first, AI-generated transcript when captions are unavailable.
   - If Supadata fails because of missing config, quota, rate limit, or API error, ask the user to fix Supadata, retry later, or paste the transcript.
   - If the user pasted transcript text, use it directly.
2. Read `references/vocabulary_selection.md` before selecting vocabulary.
3. Read `references/learning_doc_template.md` before writing the study document.
4. Draft the final study note as Markdown.
5. Publish the draft with `scripts/publish_feishu_doc.py`.
   - Success: final reply should only include the Feishu document link.
   - Feishu publishing requires saved user OAuth tokens. If missing, tell the user to run `python scripts/publish_feishu_doc.py --auth-url REDIRECT_URI`, open the URL, then run `python scripts/publish_feishu_doc.py --auth-code CODE`.
   - On Windows, the publisher also checks User environment variables when the current process does not include `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, or `FEISHU_FOLDER_TOKEN`; do not assume Feishu is unconfigured from process env alone.
   - The default OAuth scope is `docx:document offline_access`; `FEISHU_OAUTH_SCOPE` can override it.
   - Documents are created in the authorized user's Feishu cloud space. `FEISHU_FOLDER_TOKEN` is optional and only selects a target folder in that user space.
   - Feishu not configured: write a Markdown fallback.
   - Feishu configured but failed: write a Markdown fallback and briefly mention the Feishu failure.
6. For Markdown fallback, use `YOUTUBE_ENGLISH_OUTPUT_DIR` when set; otherwise write to `outputs/` under the skill directory. Create the directory first.

## Encoding Notes

- Treat all skill Markdown files as UTF-8. On Windows PowerShell, read them with `Get-Content -Raw -Encoding UTF8 ...` or Python `Path.read_text(encoding="utf-8")`; default PowerShell decoding may display valid Chinese text as mojibake.
- If Chinese appears garbled in terminal output, verify file bytes with an explicit UTF-8 read before editing the file.

## Feishu Location

- Feishu publishing uses `user_access_token`, not `tenant_access_token`, so documents go to the authorized user's cloud space.
- The publisher stores OAuth tokens in `%USERPROFILE%\.codex\youtube-english-learning\feishu_state.json` by default.
- To inspect the target, run `python scripts/publish_feishu_doc.py --print-location`.
- If `FEISHU_FOLDER_TOKEN` is unset, Feishu chooses the user's default document location. If set, it must be a folder accessible to the authorized user.

## Output Rules

- Deliver only one final study document.
- Do not deliver transcript files, provider logs, or intermediate artifacts unless the user asks.
- Use a safe Markdown filename like `video-title-study-notes.md`; if title is unknown, use a short topic name or video ID.
- Link the actual Feishu document or Markdown file in the final response.

## Study Document Requirements

- Video information and a short Chinese summary.
- A section for the creator's key lesson points.
- 15-25 high-value vocabulary or phrase items by default.
- For each item: English, IPA, Chinese meaning, context explanation, original sentence, learner example, and common collocations or patterns.
- Pronunciation or usage notes for tricky items.
- Review cards, a short quiz, and a small practice task.

Prefer phrases, chunks, collocations, discourse markers, and the creator's teaching targets over isolated rare words. Keep Chinese explanations concise and learner-friendly. Never dump the full transcript into the final document unless explicitly requested.
