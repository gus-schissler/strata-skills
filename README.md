# strata-skills

Project-agnostic Claude Code skills for feeding a [Strata](https://strata-one-phi.vercel.app) knowledge graph, built to run as unattended **cloud routines**.

A routine clones this repo, loads the skill from `.claude/skills/`, reads its config from the routine prompt, and posts to whichever Strata project connector you attach. Nothing here is tied to a specific project, team, or connector, so any team can point their own routine at this repo with their own connections.

## Skills

### `daily-strata-gather`

Gathers the previous calendar day of Slack messages, Gmail, and calendar events for a configured set of sources, assembles one dated markdown document, and posts it to the connected Strata project via `strata_post_document`. Idempotent per day (`external_id = slack-email-<date>`), so re-runs never duplicate. Writes nothing to disk.

## Install as a plugin (interactive sessions)

To use the skill in your own Claude Code sessions (not just cloud routines), this repo doubles as a plugin marketplace:

```
/plugin marketplace add gus-schissler/strata-skills
/plugin install daily-strata@strata-skills
/reload-plugins
```

On install you are prompted for your **Strata MCP server URL** (e.g. `https://strata-one-phi.vercel.app/api/mcp/YOURPROJECT`) — the plugin wires that server up for you. If the server flags as needing authentication, run `/mcp` and complete the OAuth sign-in once. If you already have the same Strata project connected as a claude.ai connector in this environment, skip the plugin's server or expect duplicate Strata tools.

The skill is then available as `/daily-strata:daily-strata-gather`, or Claude invokes it automatically when you ask for a daily Strata gather. Supply the same config keys (channels, timezone, etc.) in your request. No `version` is pinned, so every commit here ships as an update.

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

## Notes

- Routines are per claude.ai account and use that account's connectors. "Many users" means each person creates their own routine; they can share this repo.
- If a connector's auth goes stale, a nightly run fails quietly in the routine transcript rather than nudging you. Glance at it periodically.
- Adding more skills: drop them under `.claude/skills/<name>/SKILL.md` and reference them from a routine prompt.
