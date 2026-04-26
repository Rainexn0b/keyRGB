# Bug Reports Documentation Guide

This directory contains issue-specific investigation notes, implementation summaries,
and follow-up session records for active or recent bug reports.

## When to use a single issue document

Use a single file for issues that are relatively self-contained or have a stable
summary state.

Example:

- `docs/bug-reports/issue-5.md`

A single issue document should include:

- a title and GitHub issue link
- current status or summary date
- the reporter environment and key symptoms
- what landed or what the repo now provides
- verification notes or regression coverage
- any remaining test/validation gaps

Keep the document concise and avoid long-running session histories when the
issue is already settled or the remaining work is only one focused task.

## When to use a multi-session issue folder

Use a folder when an issue is actively evolving across multiple rounds of
reporter feedback and maintainer follow-up.

Example:

- `docs/bug-reports/issue-4/`

This style is best when:

- the issue spans many retests or releases
- one report generates several distinct workstreams
- the history itself is useful for later review

### Folder structure

For an ongoing multi-session issue, prefer:

- `docs/bug-reports/issue-<n>/issue-<n>.md`
  - a short folder index explaining the contained docs
- `docs/bug-reports/issue-<n>/01-<phase>.md`
- `docs/bug-reports/issue-<n>/02-<phase>.md`
- `docs/bug-reports/issue-<n>/03-<phase>.md`
- etc.

The top-level issue index should not be a long monolithic note. It should
instead point readers to the individual session documents.

## Recommended session document format

Each session doc should be roughly one reply or one testing batch in length.
Use a dated session heading and keep the content scoped to that stage.

Suggested sections:

- Title and issue link
- Date or date range
- Reporter findings or test results
- Maintainer response and next planned action
- What landed or what changed in this round
- Current open items or remaining validation problems

Example headings:

- `## Session 01 — <date> — Initial report`
- `## Session 02 — <date> — Retest on <version>`
- `## Session 05 — <date> — Latest follow-up`

## Style guidelines

- Use plain Markdown with clear headings and bullet lists.
- Prefer short, factual sentences.
- Keep the chronology explicit: label each round with a date or version.
- Distinguish between:
  - reporter-observed behavior
  - maintainer actions
  - implementation outcomes
  - remaining open issues
- Avoid embedding large raw logs or full diagnostics dumps. Summarize the
  evidence and point to attachments when needed.

## Naming conventions

- `issue-<n>.md` for a single-shot issue note.
- `issue-<n>/` for a multi-session issue folder.
- `01-<descriptor>.md`, `02-<descriptor>.md`, etc.
- Keep filenames short, lower-case, and descriptive.

## Why this matters

A session-based issue format helps keep long-running investigations readable.
It also makes it easier to track which changes were made for which retest, and
what remains unresolved.

When the issue is resolved, a final summary document can be kept, but the
intermediate session docs should still be preserved for auditability.
