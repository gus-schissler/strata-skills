---
name: gather
description: >-
  Gather the previous day's Slack messages, Gmail, and calendar events for a
  configured set of sources and post them as one dated markdown document to
  the connected Stratagraph project over MCP. Built to run as an unattended
  nightly cloud routine. Project-agnostic: posts to whichever Stratagraph
  connector is attached and reads its source config from the routine prompt.
  Trigger when a routine asks to gather yesterday's Slack / email / calendar
  activity into Stratagraph, or to run the daily Stratagraph gather.
compatibility: Requires a connected Stratagraph project MCP server (strata_post_document) plus Slack / Gmail / Calendar connectors.
---

# daily-strata-gather

Assemble one calendar day of team activity (Slack + Gmail + Calendar) into a single markdown document and post it to Strata over MCP. Built for an unattended nightly cloud routine. Writes nothing to disk.

## Project-agnostic by design

- **Destination.** Post to whichever Strata connector is attached to this routine. Use the tool whose name ends in `strata_post_document`. Never assume a specific project, server URL, or connector UUID. If more than one Strata connector is attached, use the one named by `strata_project`; if that isn't set, stop and report the ambiguity rather than guessing.
- **Tools by suffix.** Refer to every connector tool by its suffix, not its UUID prefix: `slack_read_channel`, `slack_read_thread`, `slack_read_user_profile`, `slack_search_*`, Gmail `search_threads` / `get_thread`, Calendar `list_events`. Use whatever Slack / Gmail / Calendar connector the routine has attached.
- **Sources from config.** Read the config below from the routine prompt. Nothing about any specific team, channel, or person is baked into this skill.

## Config (supplied by the routine prompt)

- `channels` (required): Slack channels to read, by name or ID.
- `dm_users` (optional): people whose DMs with you to include.
- `gmail_query` (optional): Gmail search string identifying relevant mail (a label, sender set, or terms). Omit to skip email.
- `timezone` (required): IANA tz for the day window, e.g. `America/New_York`.
- `title_prefix` (optional): document title label. Default `Slack & email log`.
- `strata_project` (optional): which Strata connector to post to, by connector name, when more than one is attached. Unnecessary when exactly one is attached.

## Steps

1. **Window.** Using the current date in `timezone`, set the target to the full previous calendar day, 00:00 to 23:59:59 local. Call it `DATE` (YYYY-MM-DD).
2. **Slack.** For each channel in `channels`, read messages inside the window. Expand any thread that has replies. If `dm_users` is set, include those DMs for the same window.
3. **Attribution.** Resolve author display names with `slack_read_user_profile` per user id. For Slack Connect or external messages with no resolvable sender, look them up best-effort; if still unknown, label `Unknown (external)`. Never fabricate a name.
4. **Gmail.** If `gmail_query` is set, search it restricted to the window and include each matching thread's relevant messages (sender, time, subject, gist). Skip firmwide or automated noise.
5. **Calendar.** List events in the window. Include title, time, attendees, and any recording or recap that surfaced. Skip clearly unrelated personal events.
6. **Assemble** one markdown document: a short header (date, sources covered), a section per source, then a brief "Loose threads worth surfacing" list of anything decision-, risk-, or action-like. Stay faithful to the source; do not invent.
7. **Post** by calling the attached `strata_post_document` with:
   - `title`: `{title_prefix}, {weekday} {DATE}`
   - `kind`: `document`
   - `source`: `routine`
   - `occurred_at`: `DATE`
   - `external_id`: `slack-email-{DATE}` (idempotent: re-runs return the existing doc, never a duplicate)
   - `content`: the assembled markdown
8. **Empty day.** If nothing substantive was found, do not post. Report `no activity for {DATE}` and stop.
9. **No disk.** Never write files. The routine transcript is the only local record.

## Output

End with a one-line summary for the routine transcript: `DATE`, per-source counts, and the returned Strata `document_id` (or `skipped: empty`).
