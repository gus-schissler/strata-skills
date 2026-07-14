# Evidence rules

Read this file before classifying inventory entries or extracting claims.

## Classify each source

| Source class | What it includes | What it can support |
|---|---|---|
| **Witnessed conversation** | Eligible human turns in transcripts and chat logs | Human decisions, rationale, questions, risks, and observations at that time. Record when automated transcription reduces confidence. |
| **Authorship not verified** | Wikis, specifications, product documents, and architecture decisions whose author is unknown | Claims stated by the document. Record the class so the user can confirm authorship later. |
| **Implementation record** | Source code, tests, database migrations, schemas, and configuration | Behavior or structure at a specific revision. Do not infer rationale or assume the record describes the current system. |
| **Version-control discussion** | Human-written pull request descriptions, review comments, and commit messages | Human rationale and intent. Treat bot comments and generated summaries as machine-written material. Treat diffs as implementation records. |
| **Machine-written narrative** | Assertion logs, summaries, agent turns and notes, continuation recaps, generated prompts, and generated handoffs | Topics to check against primary evidence. Do not use as claim evidence unless the user confirms human authorship. |

Do not classify authorship from writing style. Use the more conservative class until the user confirms it.

## Handle generated implementation files

A generated file may still be an authoritative implementation record. For example, a checked-in database migration may define what production runs.

Use a generated implementation file only when:

- it is a canonical input to deployment or runtime behavior
- a more direct source does not replace it
- its generated status is recorded

Skip compiled output, generated mirrors, lock files, and build artifacts by default. Use them only when they are the sole authoritative record and the user approves them.

## Use machine-written material only to find gaps

Do not extract claims from machine-written narrative. Open it only after primary sources have been processed.

Common signals include:

- `extracted_at`, `assertion_count`, or confidence fields in the document header
- a claim-by-claim taxonomy
- `summary` in the path
- a generator script beside the document
- a synthetic recap at the start of a resumed conversation

In a mixed transcript, use eligible human turns as evidence. Exclude agent turns and pasted structured data of uncertain authorship.

When machine-written material reveals a gap:

- return to the primary source and extract the missing claim
- add the topic to an unconfirmed appendix when no primary source exists

The user may confirm that a document was written by a person. Record that confirmation.

## Keep each claim verifiable

- Put one claim in each node.
- Copy 1 to 5 supporting spans exactly from the source.
- Include a speaker only when the source identifies them.
- Keep claims from different documents separate.
- Use implementation records for behavior, not unstated intent.
- Resolve the source date. Do not guess.

Stratagraph can connect repeated support after import. Do not merge it during extraction.

A generated current-state document is allowed only because the user reviews it and every factual claim points to retrieved evidence.
