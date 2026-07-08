---
name: import
description: Use when cold-starting a Stratagraph knowledge graph from an existing backlog — meeting transcripts, chat logs, wikis, specs, design docs, ADRs — and activating it. Triggers include "initial load", "backlog import", "cold start a Stratagraph project", "activate the imported graph", "write the baseline", or pointing at a corpus and asking for Stratagraph-ready documents.
compatibility: Requires a connected Stratagraph project MCP server (strata_import_document / strata_post_document / strata_get_graph_schema).
---

# Import — corpus → dormant graph → activated by baseline documents

Cold-starting a project is **two acts, one session**:

- **Act 1 — the dormant past.** Sweep the corpus and distill each source into atoms; publish an import **bundle**. Atoms land baked but **dormant** (`imported`, disconnected). This is *evidence for a human-reviewed graph, not a summary* — a wrong claim here is trusted graph truth until someone stumbles on it.
- **Act 2 — the present.** The user loads a few **Strata baseline documents** — current-state write-ups, structured the way *they* need — through the normal **gated** path. Their atoms drain against the dormant history and light it up.

## Rules that don't bend

- **Fetch the contract, don't remember it.** The per-atom payload shape, the six tier-1 node types, and the grain rule live in the `strata_import_document` tool description; `strata_get_graph_schema` has the live taxonomy. Read them while you build; if they disagree with this skill, they win. Never hard-code the type list from memory.
- **Iron Rule — derivatives steer, never source.** Never distill atoms from LLM artifacts (assertion logs, AI summaries, agent notes); use them only as a coverage map / recall checklist. Signs of a derivative: `extracted_at`/`assertion_count`/confidence frontmatter, per-claim lens taxonomies, "summary" in the path, a generator script beside it. Exception: a doc the **user vouches** as human-authored. This holds in Act 2 too — a baseline is LLM-authored but safe only because it's **gated** *and* every claim is **grounded in a retrieved atom**.
- **One claim per atom.** A statement fusing four decisions and an action is five atoms. Compound atoms are unadjudicatable and unbindable.
- **Spans are copied verbatim.** Each atom carries 1–5 quote fragments lifted character-for-character; the server re-snaps and stores verbatim-or-null, so a paraphrased span is a silently lost receipt.
- **Never guess a date or a speaker.** Resolve or flag (ladder below); omit an unattributed speaker.
- **Never merge across documents.** Restatements land dormant and the drain's `supports` is the dedup — not you.

## Provenance classes

| Class | What qualifies | Use |
|---|---|---|
| **Witnessed** | Transcripts / chat logs — humans speaking in time. Verbatim ASR ranks above AI-notes (record the notch-down) | Primary source — the spine. |
| **Unverified-authorship** | Every other doc (wikis, specs, PRDs, "ADRs"), however human it looks | Primary source; record the class so the reviewer can upgrade known-human docs. |
| **Machine-derivative** | Assertion logs, AI summaries, agent notes | Steer only; never distilled (vouched exception). |

Don't attempt authorship detection — classify conservatively and let the manifest pass resolve it.

## Inputs + levers (collect once, up front — strong defaults, not a form)

Basics: corpus root(s) + exclusions · output folder (default `<root>/_import/` — use one **absolute** path for every `import.py` command; always excluded from the sweep) · engagement name + date span · the corpus-relative path convention (each doc's `externalId`, the idempotency key) · any user-vouched docs.

Levers:
- **Scope** — which sources, how far back. *Default: everything.*
- **Extraction strategy** — `doc-by-doc` (faithful, most atoms) or `temporal-economy` (bucket by time, coarser, fewer atoms). *Default: doc-by-doc.*
- **Materiality floor** — distill what still binds (decisions, constraints, risks, open questions), not every utterance. *Default: still-binds.* Volume is reported, never capped.

Run on the best model available (**Opus-tier recommended, Sonnet-class floor**) for distill and synthesis alike — subtly-wrong baked claims are the worst failure. Record the model + contract version (**v0.5**) in the sweep report.

---

# Act 1 — build the dormant past

Steps run in order. Nothing is uploaded until dates are resolved and the sweep report is approved.

1. **Inventory → STOP.** Run `python3 import.py inventory <root> --output-dir <out>` — it walks the tree (skipping `.git`/`node_modules`/caches by default) and writes the manifest to `<out>/inventory.json` (paths, sizes, `chars/4` tokens, head peeks, date + derivative *signals*); a compact summary prints to stdout. Read the manifest and **classify** each file (provenance + read/skip — signals, not verdicts). Present the plan and **wait for go-ahead before reading content.**

2. **Temporal bucketing + cost table** *(temporal-economy only; else skip).* Re-run with `--bucket quarter|month|year` for the per-bucket rollup (`byBucket`; undated → a catch-all, don't guess). Show `bucket · #docs · est. tokens`; the user picks **full / coarse / skip** per bucket. Coarse still **reads every doc** — it distills the *period* into fewer atoms (the expensive output side); reading a summary to save input would break the Iron Rule.

3. **Distill each source** — `full` → worker-per-doc; `coarse` → worker-per-bucket. Read → distill → verify **in one session, source in context** (distilling from memory is the confabulation vector). Per atom: one claim · a fetched tier-1 type · 1–5 verbatim spans · optional speaker/sectionLabel. **Resolve the doc's `occurredAt`** — filename → content → user-supplied span; unresolvable → flag it, **never guess** (load-bearing for import order *and* the drain's chronology). **Verify** with `python3 import.py validate <atoms.json> --text <doc> --types <fetched>` (non-zero exit = bad type or non-verbatim span), then **append** the `{document, atoms}` entry with `python3 import.py bundle --output-dir <out> <entry.json>` (idempotent by `externalId`; `worklist.json` is the resume journal). Files >~50KB: chunk sequentially.

   ```
   { "version": 1, "documents": [ {
     "document": { "externalId", "name", "occurredAt", "source", "text", "participants"? },
     "atoms": [ { "type", "content", "speaker"?, "spans"?, "sectionLabel"? } ]
   } ] }
   ```
   Each entry is exactly the `strata_import_document` payload (minus `projectId`/`userId`).

4. **Recall-check.** *After* all primary sources are distilled, open derivatives as a **miss-list** only: any gap → distill from the *primary* source; no primary → "unconfirmed" appendix, never an atom.

5. **Sweep report → review gate.** Write `sweep-report.md` (files read/skipped · per-doc & per-bucket counts + total · span coverage · people roster · provenance manifest · undated flags · unconfirmed appendix · extraction mode · bundle path + totals · model + v0.5) and **have the user review it before upload.**

6. **Upload.** After approval, the user drops `import-bundle.json` on Strata's **Import** page — the browser route publishes each doc oldest-first by `occurredAt`, so the large text never rides through a model. Atoms land **dormant**; the importer writes no edges.

7. **Wait to embed.** Act 2 searches the imported atoms, so they must embed first: ~**1 min per 300 atoms**. Fill the wait with step 8 (the user picks a structure + fills in info); a `strata_search_nodes` on a known topic confirms readiness.

---

# Act 2 — assert the present (baseline documents)

The dormant graph has no edges, so no clusters to structure from — **the user supplies the structure and substance; you ground it.**

8. **Structure.** Offer: **single · by product/feature · by workstream/domain · custom** (keep it few — never sprint-by-sprint). The user picks and **fills in the required info** (e.g. by-product → their product list + key current facts each).

9. **Ground** each baseline with `strata_search_nodes` / `strata_get_node(s)` / `strata_list_*` — **not `strata_traverse`** (no edges to walk). Pull the atoms behind the user's points, catch gaps, judge recency by `occurred_at`, surface genuine conflicts rather than guessing.

10. **Draft** each baseline **normally** — clear current-state prose (no present-tense gymnastics): what's in force, what changed, open questions. Every substantive claim cites the retrieved node key. Keep it tight (a re-list of history just floods self-`supports`).

11. **Review → post.** Show each baseline concisely; the user reacts and corrects (not a wall of text). Post each with `strata_post_document` — it lands as a normal doc, extracts, and **stops at the gate** for review before bake; on bake it drains against the dormant history and activates it. Idempotent by `externalId` (`_import/baseline-<slug>.md`).
    - **No MCP connected?** Offer setup instructions, or write `baseline-<slug>.md` and have the user upload it the normal way — same gate + activation.

---

## Helpers + how distill is dispatched

[`import.py`](import.py) is stdlib-only Python (no installs, no network, no LLM) — deterministic mechanics you shell out to, available on **every** rung:
- `inventory <root> [--output-dir D] [--bucket quarter|month|year]` — walk → manifest (+ per-bucket cost rollup); skips `.git`/`node_modules`/caches by default (`--include-noise` to keep them).
- `validate <atoms.json> --text <doc> --types <t,…>` — type + verbatim-span check; non-zero exit on a violation.
- `bundle --output-dir D <entry.json> …` — append entries into `import-bundle.json` (idempotent) + `worklist.json`.

The **distill** (the LLM judgment) is the agent's, not the script's — dispatch it at the highest rung available:

1. **Workflow tool** → fan out per-doc (or per-bucket) distill workers in parallel; validate each with `import.py validate`; the orchestrator assembles via `import.py bundle`.
2. **Subagent dispatch** → per-worker distill subagents; the **orchestrator alone** owns the worklist, recall-check, and all of Act 2. Workers inherit the run's model — never a cheaper one.
3. **Neither** → a sequential read → distill → validate → bundle loop; the `worklist.json` is the resume journal.

Act 2 is orchestrator-driven in every case (search → draft → review → post — no fan-out).

## Stop signals

- Distilling from a derivative (`extracted_at`/confidence frontmatter, unvouched claim-shaped doc), or coarse mode about to read a summary instead of the source docs.
- An atom carrying a speaker/detail its source can't support, fusing two claims, or merged across documents.
- A span that isn't a character-exact copy of the `text`.
- A baseline claim you can't point to a retrieved atom for, structure you inferred from the graph instead of asking, or a `strata_traverse` call (no edges yet).
- A guessed date.

## What's new in v0.5

Act 2 (baseline documents → gated activation, ADR-0077) · the `temporal-economy` extraction lever (per-bucket cost table; coarse trades output atoms, not reads) · Act 2 is user-led (no clustering pre-activation) via search/get/list. The Act-1 distill contract is unchanged from v0.4.
