# stratagraph-skills

Project-agnostic agent skills for using a [Stratagraph](https://stratagraph.io) knowledge graph. The skills find verified answers, cold-start a project from an existing corpus, and keep it fed as an unattended cloud routine.

Nothing here is tied to a specific project, team, or connector, so any team can point their own agent or routine at this repo with their own connections.

## Skills

### `find-in-stratagraph`

Answers focused questions from a connected Stratagraph project. It chooses the right read tool for a node key, topic, document, speaker, or relationship. Search results identify candidates. The skill reads full nodes and checks relationships before claiming that something is current, replaced, disputed, or resolved. Briefs are optional. The skill never writes to the project, and each material claim cites an exact node key linked to its Stratagraph page. Invoke it with `/stratagraph:find-in-stratagraph`, or ask a focused factual, requirement, status, ownership, or source question whose answer should come from Stratagraph. Use a separate trace workflow for broad topic histories.

### `import`

Cold-starts a new or empty Stratagraph graph from existing sources. The agent first explains the process and agrees the scope with you. It then inventories the approved sources, extracts small claims with exact source text, and prepares an import review report and `import-bundle.json` file. After you import and review that history, the agent helps write a current-state document that connects what still matters. `import.py` handles inventory, strict source validation, reviewed-entry replacement, bundle assembly, and deterministic combination of separately reviewed bundles. Invoke the skill with `/stratagraph:import`, or point it at a source collection and ask to cold-start a Stratagraph project. Do not use it for routine ingestion or posting one document.

### `gather`

Gathers the previous calendar day of Slack messages, Gmail, and calendar events for a configured set of sources, assembles one dated markdown document, and posts it to the connected Stratagraph project via `strata_post_document`. Idempotent per day (`external_id = slack-email-<date>`), so re-runs never duplicate. Writes nothing to disk. Built to run as an unattended **cloud routine** (a routine clones this repo and loads the skill from `.claude/skills/`).

## Install

The skills follow the open [Agent Skills](https://agentskills.io) standard (a `SKILL.md` folder), so one copy works across every skills-compatible agent. This repo hosts them two ways.

### Claude Code (plugin marketplace)

```
/plugin marketplace add Stratagraph/stratagraph-skills
/plugin install stratagraph@stratagraph-skills
/reload-plugins
```

Then `/stratagraph:find-in-stratagraph` (focused lookup), `/stratagraph:import` (cold-start), and `/stratagraph:gather` (daily ingestion) are available, and Claude invokes them automatically when a request matches. No `version` is pinned, so every commit ships as an update.

### Codex, Cursor, Copilot, Gemini CLI, Goose, and other agents

These agents auto-discover skills from an `.agents/skills/` directory. Point yours at this repository's copies: clone it and symlink or copy the skills you want into your `~/.agents/skills/` (or a repository-local `.agents/skills/`), or use your agent's skill installer if it supports GitHub sources (e.g. Codex's `$skill-installer`). Each skill activates automatically when a matching request is made.

### MCP connection (all agents)

Every skill uses Strata over MCP, so connect your project's MCP server wherever you run your agent:

- **Desktop / claude.ai:** Settings → Connectors → Add custom connector, name `strata`, URL `https://stratagraph.io/api/mcp/YOURPROJECT`
- **CLI:** `claude mcp add --transport http strata https://stratagraph.io/api/mcp/YOURPROJECT` (or the equivalent for your agent)

If the server flags as needing authentication, complete the OAuth sign-in once (`/mcp` in Claude Code).

## Multiple projects

Strata projects are strictly isolated: one connector per project (`/api/mcp/PROJECTA`, `/api/mcp/PROJECTB`), named distinctly (e.g. `strata-projecta`). Then:

- **Routines:** one routine per project. Each attaches only that project's Strata connector and carries that project's config (its channels differ anyway). No ambiguity.
- **Interactive:** if several Strata connectors are attached to one session, add `strata_project: <connector name>` to the prompt or configuration so the skill knows which project to use. With exactly one attached, omit it.

## Setting up a routine

1. **Connect your accounts** at [claude.ai/customize/connectors](https://claude.ai/customize/connectors): Slack, Gmail, Google Calendar, and your Strata project connector. Gmail and Calendar must be connected here (they do not support local OAuth).
2. **Create a routine** (claude.ai/code/routines → New → Remote, or `/schedule` in the CLI, or Desktop app → Routines).
3. Point it at this repo, set a **nightly schedule** at ~00:10 in your timezone (it gathers the full prior day), and attach the four connectors above (remove any others).
4. In the routine **prompt**, run the gather and supply your config:

```
Run the gather skill for yesterday.
channels: #your-channel, #another-channel
dm_users: Person A, Person B
gmail_query: label:your-project
timezone: America/New_York
title_prefix: Slack & email log
```

5. **Test** with one manual run and check the transcript: the skill loaded, all connectors were reached, and exactly one Strata document was posted with the right date. Then leave it nightly.

### Config reference

| Key | Required | Meaning |
|---|---|---|
| `channels` | yes | Slack channels to read (names or IDs) |
| `dm_users` | no | People whose DMs to include |
| `gmail_query` | no | Gmail search string; omit to skip email |
| `timezone` | yes | IANA tz for the day window |
| `title_prefix` | no | Document title label |
| `strata_project` | no | Connector name to post to when several Strata connectors are attached |

## Notes

- Routines are per claude.ai account and use that account's connectors. "Many users" means each person creates their own routine; they can share this repo.
- If a connector's auth goes stale, a nightly run fails quietly in the routine transcript rather than nudging you. Glance at it periodically.
- Adding more skills: drop them under `.claude/skills/<name>/SKILL.md` and reference them from a routine prompt.
