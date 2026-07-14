---
name: import
description: Cold-start a new or empty Stratagraph graph from existing sources and activate it with reviewed current-state documents. Use for initial loads, bulk imports, or baseline creation from transcripts, chats, wikis, specifications, design documents, architecture decisions, implementation records, and similar collections. Do not use for routine ingestion, posting one document, or updating an active graph.
---

# Cold-start a Stratagraph project

An import has 2 parts:

1. Extract small, source-backed claims from the project's history. Stratagraph stores them without graph connections.
2. Create a reviewed current-state document. Stratagraph uses it to connect the history that still matters.

The work may span several sessions. Use the reports, entry files, bundle, and worklist to resume safely.

## Explain the process before using tools

On the first turn, explain the process before you inspect files or call tools. This may be the user's first experience of Stratagraph.

The first response must:

- preview all 5 stages below
- separate decisions needed before extraction from decisions that can wait
- say that a location does not approve everything inside it
- end with one source or exclusion question adapted to what the user already said

Do not select source categories, announce an inventory plan, or promise to use the whole location before the user answers. Do not use *bundle*, *baseline*, *dormant*, *bake*, or *drain* in the first response.

Cover these stages in plain language:

1. **Choose sources.** Agree what to include and leave out.
2. **Check the size.** Inventory the approved locations and estimate the work.
3. **Extract and verify.** Keep each claim small and link it to exact source text.
4. **Review and import.** Give the user an import review report and import file. Nothing reaches Stratagraph before approval.
5. **Connect current knowledge.** Help the user write a short current-state document after import.

Explain which decisions are needed now and which can wait:

- Decide sources, exclusions, detail, date handling, and use of parallel workers before extraction.
- Decide the structure and content of the current-state document after import.

Use familiar words in conversation. Say *import file* instead of *bundle* and *import review report* instead of `sweep-report.md`. If you use *node*, explain that it means one small claim. If you use *baseline*, explain that it means a reviewed current-state document.

Adapt your first question to the request:

- When scope is unclear, ask: **Which files, folders, or exports should I include? Is there anything I should leave out?**
- When the user already gave a precise scope, restate it and ask only for confirmation or exclusions.

A repository, folder, or export identifies a location. It does not give permission to use everything inside it.

## Confirm the target and agree the plan

Complete this preflight after the user understands the process.

### Confirm the target project

Identify the connected Stratagraph project. Confirm with the user that it is the intended target.

Use authoritative project metadata or an exhaustive node count or list to confirm that the graph is new or empty. One search with no results is not proof. If tools cannot confirm the state, ask the user to confirm it. Stop if the graph is active; this skill is not an update workflow.

### Check the required tools

For extraction, require:

- the description and input schema for `strata_import_document`
- `strata_get_graph_schema`

Inspect the `strata_import_document` tool description. Do not invoke the tool to read its contract.

For the current-state document, require:

- `strata_search_nodes`
- node retrieval tools such as `strata_get_node` or `strata_get_nodes`
- relevant `strata_list_*` tools
- `strata_post_document`

If a required tool is missing, explain what is missing and offer setup help before that phase.

### Agree the import plan

Collect the plan through conversation. Make recommendations and ask one or 2 questions at a time.

Agree:

- what to include and leave out
- which source groups to process now or later
- the date range
- how to resolve missing dates
- the level of detail
- the output folder and `externalId` path convention
- sequential work or user-approved parallel workers

Use `<root>/_import/` as the default output folder and exclude it from inventory.

Recommend these defaults:

- Start with a small pass for a mixed collection.
- Process source groups separately when they need different evidence rules.
- Use `doc-by-doc` extraction for the most faithful result.
- Keep decisions, constraints, risks, open questions, and facts that still matter. Call this the `still-binds` level in technical notes only.
- Use parallel workers only with the user's approval.

Use the strongest configured model that can handle long sources, exact citations, and careful synthesis. If the available model is not suitable, tell the user before extraction. Use the same capability level for workers.

Summarize the plan with user-facing labels:

- What I will include
- What I will leave out
- How I will handle missing dates
- How detailed the result will be
- Where I will write the import files
- How I will run the work

Ask for approval to inventory. Explain that inventory reads filenames, metadata, and a small sample from each file. It does not read full files or change the source collection.

## Follow the evidence rules

Before classifying inventory entries or extracting claims, read [references/evidence.md](references/evidence.md).

Always:

- inspect the live tool schema and taxonomy instead of using a remembered type list
- put one claim in each node
- copy 1 to 5 exact supporting spans from the same source
- include a speaker only when the source identifies them
- keep claims from different documents separate
- use machine-written narrative only to find gaps in primary evidence

Use `occurredAt` for the date represented by the source. Resolve it in this order:

1. A date in the source text that clearly represents the document or event
2. A trustworthy date in the filename
3. A user-approved metadata source, such as the first git commit
4. A date supplied by the user

Inventory date signals are only candidates. Do not use a file modification time as the source date unless the user approves it.

Do not upload a document with an unresolved date. Ask the user to resolve it or leave the document out and record it in the report.

Record the model and contract version in the report. Record `unknown` when the live contract does not state a version.

## Part 1: prepare and review the import

Read [references/technical.md](references/technical.md) before running `scripts/import.py`, assigning workers, or assembling bundles.

### 1. Inventory the approved sources

Run inventory only after preflight approval. Use the manifest to classify each file as read or skip. Treat date and machine-content signals as clues, not decisions.

Show the user:

- proposed sources and exclusions
- date-resolution plan
- estimated input size
- execution plan

Stop and ask for approval before reading full source files. Revise the plan if inventory reveals a different collection than expected.

For `temporal-economy`, follow the selection and output rules in the technical reference. Show document and token estimates by month, quarter, or year. Ask the user to mark each period as full, coarse, or skip. Coarse extraction must still read every primary document and keep claims separated by source.

### 2. Extract and validate each source

Read, extract, and verify each source while it remains in context. Process files over about 50 KB in order, one section at a time.

Write a separate entry file for each document. Validate it with the live comma-separated type list. Add a reviewed entry to its source-group bundle.

Validation must fail for an invalid type, empty content, fewer than 1 or more than 5 spans, or a span that is not an exact source substring.

### 3. Check gaps and review quality

After primary sources are processed, use machine-written material only as a gap checklist. Return to primary evidence for any missing claim. Put unsupported topics in an unconfirmed appendix.

Review a sample from every source group and the documents with the most claims. Split, narrow, retype, or remove claims that are compound, weak, outdated, or limited to one-time implementation detail.

When review changes an entry that is already bundled:

1. Validate the changed entry again.
2. Replace it with `bundle --replace`.
3. Confirm that `worklist.json` records the replacement.

### 4. Prepare the report and import files

Write `sweep-report.md` with source coverage, skipped files, claim and span counts, date decisions, source classes, unconfirmed topics, quality findings, important gaps, model details, contract version, and bundle paths.

Include a direct assessment of source support, one-claim quality, relevance, chronology, and coverage. Recommend a manageable human spot-check.

Keep separate review bundles for source groups with different origins or evidence rules. Use `scripts/import.py combine` to create one upload bundle in a new directory after the user approves every parent bundle. Keep the parent bundles and generated hash manifest.

### 5. Review, import, and wait for search

Ask the user to review the import review report. Do not upload before approval.

After approval, the user can drop `import-bundle.json` on the Stratagraph Import page. The page publishes documents from oldest to newest. Imported claims still have no graph edges.

Embedding time varies. About 1 minute for every 300 claims is only a rough estimate. A successful `strata_search_nodes` query for a known topic is the readiness check.

## Part 2: create the current-state document

Imported claims have no graph edges. The user must choose the structure and provide the current facts.

### 1. Choose a structure

Offer a small set of choices:

- one overview
- one document for each product or feature
- one document for each workstream or domain
- a custom structure

Avoid one document for every sprint. Ask for the names and current facts needed for the chosen structure.

### 2. Find supporting evidence

Use search, get, and list tools. Do not use `strata_traverse` before the graph has edges.

Find evidence for the user's facts. Compare dates, identify gaps, and show genuine conflicts instead of resolving them by guesswork.

### 3. Draft, review, and post

Write focused prose that covers what is in force, what changed, and what remains open. Cite the retrieved node key for every factual claim.

Show each draft to the user and ask for corrections. After approval, post it with `strata_post_document`. Use `_import/baseline-<slug>.md` as its `externalId`.

The document must pass the normal Stratagraph review gate. After approval there, Stratagraph connects it to relevant imported history.

If search or retrieval tools are unavailable, stop and offer setup help. Do not describe an ungrounded draft as evidence-backed. If the user chooses a manual path, use only facts they explicitly provide and ask them to verify every claim before upload.

## Stop and correct these problems

- The target project is not confirmed as new or empty.
- A mutating import tool is being invoked to inspect its schema.
- Machine-written narrative is being used as evidence.
- Coarse extraction is using summaries instead of primary documents.
- A claim contains more than one idea.
- A speaker, detail, or span is not supported exactly by the source.
- Claims from different documents have been merged.
- A source date is unresolved or guessed.
- A reviewed change was not validated and replaced in the bundle.
- A current-state claim has no retrieved evidence.
- The current-state structure was inferred instead of agreed with the user.
- `strata_traverse` is being used before the graph has edges.
