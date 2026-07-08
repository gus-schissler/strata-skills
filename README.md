# strata-skills

Project-agnostic Claude Code skills for feeding a [Strata](https://stratagraph.io) knowledge graph — one for **cold-starting** a project from an existing backlog, one for **keeping it fed** as an unattended cloud routine.

Nothing here is tied to a specific project, team, or connector, so any team can point their own agent or routine at this repo with their own connections.

## Skills

### `strata-genesis`

Cold-starts a Strata project from a backlog. Runs **interactively** on your agent: sweep a corpus of transcripts, docs, and chat logs, distill each source into atom-grain claims, and publish a `genesis-import.json` bundle you drop into Strata's **Import** page — then write a *baseline document* that activates the imported history. Ships `genesis.py`, a stdlib-only helper for the deterministic parts (corpus inventory, verbatim-span validation, bundle assembly). See ADR-0077. Invoke it with `/stratagraph:strata-genesis`, or by pointing it at a corpus and asking to cold-start a Strata project.

### `daily-strata-gather`

Gathers the previous calendar day of Slack messages, Gmail, and calendar events for a configured set of sources, assembles one dated markdown document, and posts it to the connected Strata project via `strata_post_document`. Idempotent per day (`external_id = slack-email-<date>`), so re-runs never duplicate. Writes nothing to disk. Built to run as an unattended **cloud routine** (a routine clones this repo and loads the skill from `.claude/skills/`).

## Install as a plugin (interactive sessions)

To use the skill in your own Claude Code sessions (not just cloud routines), this repo doubles as a plugin marketplace:

```
/plugin marketplace add gus-schissler/strata-skills
/plugin install stratagraph@strata-skills
/reload-plugins
```

The plugin needs your Strata project's MCP server connected. Add it wherever you run Claude:

- **Desktop / claude.ai:** Settings → Connectors → Add custom connector, name `strata`, URL `https://stratagraph.io/api/mcp/YOURPROJECT`
- **CLI:** `claude mcp add --transport http strata https://stratagraph.io/api/mcp/YOURPROJECT`

If the server flags as needing authentication, run `/mcp` and complete the OAuth sign-in once.

The skill is then available as `/stratagraph:daily-strata-gather`, or Claude invokes it automatically when you ask for a daily Strata gather. Supply the same config keys (channels, timezone, etc.) in your request. No `version` is pinned, so every commit here ships as an update.

## Multiple projects

Strata projects are strictly isolated — one connector per project (`/api/mcp/PROJECTA`, `/api/mcp/PROJECTB`), named distinctly (e.g. `strata-projecta`). Then:

- **Routines:** one routine per project. Each attaches only that project's Strata connector and carries that project's config (its channels differ anyway). No ambiguity.
- **Interactive:** if several Strata connectors are attached to one session, add `strata_project: <connector name>` to the config so the skill knows where to post. With exactly one attached, omit it.

## Setting up a routine

1. **Connect your accounts** at [claude.ai/customize/connectors](https://claude.ai/customize/connectors): Slack, Gmail, Google Calendar, and your Strata project connector. Gmail and Calendar must be connected here (they do not support local OAuth).
2. **Create a routine** (claude.ai/code/routines → New → Remote, or `/schedule` in the CLI, or Desktop app → Routines).
3. Point it at this repo, set a **nightly schedule** at ~00:10 in your timezone (it gathers the full prior day), and attach the four connectors above (remove any others).
4. In the routine **prompt**, run the gather and supply your config:

```
Run the daily-strata-gather skill for yesterday.
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
