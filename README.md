# stratagraph-skills

Project-agnostic agent skills for using a [Stratagraph](https://stratagraph.io) knowledge graph. The skills find verified answers, post new source material, cold-start a project from an existing corpus, and keep it fed as an unattended cloud routine.

Nothing here is tied to a specific project, team, or connector, so any team can point its agent or routine at this repository with its own connections.

## Skills

### `find-in-stratagraph`

Answers focused questions from a connected Stratagraph project. It chooses the right read tool for a node key, topic, document, speaker, or relationship. Search results identify candidates. The skill reads full nodes and checks relationships before claiming that something is current, replaced, disputed, or resolved. Briefs are optional. The skill never writes to the project, and each material claim cites an exact node key linked to its Stratagraph page. Invoke it with `/stratagraph:find-in-stratagraph`, or ask a focused factual, requirement, status, ownership, or source question whose answer should come from Stratagraph. Use a separate trace workflow for broad topic histories.

### `post`

Turns material the agent can read into an extraction-ready Markdown document and posts it with `strata_post_document`. It accepts pasted text, files, webpages, emails, message threads, transcripts, notes, structured data, and agent-written drafts. The skill preserves full source content, speaker labels, timestamps, and provenance. It posts Markdown and simple lossless conversions directly. When the agent must process, consolidate, interpret, or materially adjust the source, it shows the converted document for approval before posting. Invoke it with `/stratagraph:post`, or ask to post, save, add, send, put, capture, or upload something to Stratagraph.

### `post-extracted`

Posts a document to a connected Stratagraph project together with claims and relationships already classified from it, using `strata_post_extracted_document`. Use it when a source's claims are already typed, with or without edges between them, and should attach to an active project in one call instead of waiting on automatic extraction. The skill never invents a node key: it only cites keys returned by a search, get, or list tool this session, or given by the user, and it omits an edge rather than guess an endpoint. It reads accepted node types from the live schema rather than a memorized list, and requires every quote span to be an exact substring of the posted document. `counters` and `replaces` edges always land as pending conflicts for a human to adjudicate. Everything posted, the document, its nodes, and its edges, stays in the human review gate; nothing is added to the graph automatically. Invoke it with `/stratagraph:post-extracted`, or ask to post a document together with its already-extracted claims or relationships.

### `import`

Cold-starts a new or empty Stratagraph graph from existing sources. The agent first explains the process and agrees the scope with you. It then inventories the approved sources, extracts small claims with exact source text, and prepares an import review report and `import-bundle.json` file. After you import and review that history, the agent helps write a current-state document that connects what still matters. `scripts/import.py` handles inventory, strict source validation, reviewed-entry replacement, import file assembly, and deterministic combination of separately reviewed import files. Invoke the skill with `/stratagraph:import`, or point it at a source collection and ask to cold-start a Stratagraph project. Do not use it for routine ingestion or posting one document.

### `gather`

Gathers the previous calendar day of Slack messages, Gmail, and calendar events for a configured set of sources, assembles one dated markdown document, and posts it to the connected Stratagraph project via `strata_post_document`. Idempotent per day (`external_id = slack-email-<date>`), so re-runs never duplicate. Writes nothing to disk. Built to run as an unattended cloud routine. The repository exposes the canonical skill to Claude through `.claude/skills/gather` without keeping another copy.

## Install

The skills follow the open [Agent Skills](https://agentskills.io) standard. Each skill has one canonical folder under `skills/`.

### Skills CLI

Choose and install skills for Codex, Claude Code, Cursor, Copilot, Gemini CLI, Goose, or another supported agent:

```bash
npx skills add Stratagraph/stratagraph-skills
```

Install one skill:

```bash
npx skills add Stratagraph/stratagraph-skills --skill find-in-stratagraph
npx skills add Stratagraph/stratagraph-skills --skill post
npx skills add Stratagraph/stratagraph-skills --skill post-extracted
npx skills add Stratagraph/stratagraph-skills --skill import
npx skills add Stratagraph/stratagraph-skills --skill gather
```

The skills CLI installs the selected canonical folders into the paths used by your agent. It uses project scope by default. Choose its global option when you want the skills available across projects.

### Claude Code plugin marketplace

```text
/plugin marketplace add Stratagraph/stratagraph-skills
/plugin install stratagraph@stratagraph-skills
/reload-plugins
```

Then `/stratagraph:find-in-stratagraph`, `/stratagraph:post`, `/stratagraph:post-extracted`, `/stratagraph:import`, and `/stratagraph:gather` are available. Claude can also invoke them automatically when a request matches. The marketplace manifest points at the same canonical `skills/` folders used by the skills CLI.

### MCP connection (all agents)

Every skill uses Stratagraph over MCP, so connect your project's MCP server wherever you run your agent:

- **Desktop / claude.ai:** Settings → Connectors → Add custom connector, name `strata`, URL `https://stratagraph.io/api/mcp/YOURPROJECT`
- **CLI:** `claude mcp add --transport http strata https://stratagraph.io/api/mcp/YOURPROJECT` (or the equivalent for your agent)

If the server flags as needing authentication, complete the OAuth sign-in once (`/mcp` in Claude Code).

## Multiple projects

Stratagraph projects are strictly isolated: one connector per project (`/api/mcp/PROJECTA`, `/api/mcp/PROJECTB`), named distinctly (e.g. `strata-projecta`). Then:

- **Routines:** one routine per project. Each attaches only that project's Stratagraph connector and carries that project's config (its channels differ anyway). No ambiguity.
- **Interactive:** if several Stratagraph connectors are attached to one session, add `strata_project: <connector name>` to the prompt or configuration so the skill knows which project to use. With exactly one attached, omit it.

## Setting up a routine

1. **Connect your accounts** at [claude.ai/customize/connectors](https://claude.ai/customize/connectors): Slack, Gmail, Google Calendar, and your Stratagraph project connector. Gmail and Calendar must be connected here (they do not support local OAuth).
2. **Create a routine** (claude.ai/code/routines → New → Remote, or `/schedule` in the CLI, or Desktop app → Routines).
3. Point it at this repository, set a **nightly schedule** at about `00:10` in your time zone (it gathers the full prior day), and attach the four connectors above (remove any others).
4. In the routine **prompt**, run the gather and supply your config:

```text
Run the gather skill for yesterday.
channels: #your-channel, #another-channel
dm_users: Person A, Person B
gmail_query: label:your-project
timezone: America/New_York
title_prefix: Slack & email log
```

5. **Test** with one manual run and check the transcript: the skill loaded, all connectors were reached, and exactly one Stratagraph document was posted with the right date. Then leave it nightly.

### Config reference

| Key | Required | Meaning |
|---|---|---|
| `channels` | yes | Slack channels to read (names or IDs) |
| `dm_users` | no | People whose DMs to include |
| `gmail_query` | no | Gmail search string; omit to skip email |
| `timezone` | yes | IANA time zone for the day window |
| `title_prefix` | no | Document title label |
| `strata_project` | no | Connector name to post to when several Stratagraph connectors are attached |

## Notes

- Routines are per claude.ai account and use that account's connectors. "Many users" means each person creates their own routine; they can share this repository.
- If a connector's auth goes stale, a nightly run fails quietly in the routine transcript rather than nudging you. Glance at it periodically.
- Add a new canonical skill under `skills/<name>/SKILL.md`. Add it to `.claude-plugin/marketplace.json` when the Claude plugin should include it.
- Add a `.claude/skills/<name>` symlink only when a cloned repository must expose that skill directly to a cloud routine.
