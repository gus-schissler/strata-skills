---
name: gather
description: >-
  Gather Slack messages, Gmail messages, and calendar events from the previous
  calendar day for a configured set of sources. Post them as one dated Markdown
  document to the connected Stratagraph project over MCP. Runs as an unattended
  nightly cloud routine. Project-agnostic: posts to whichever Stratagraph
  connector is attached and reads its source configuration from the routine
  prompt. Trigger when a routine asks to gather yesterday's Slack, email, and
  calendar activity into Stratagraph, or to run the daily Stratagraph gather.
  Do not use for ad hoc searches or manual imports.
compatibility: >-
  Requires a connected Stratagraph project MCP server (`strata_post_document`)
  and Slack, Gmail, and Calendar connectors.
---

# Gather daily activity

Gather one calendar day of Slack messages, Gmail messages, and calendar events. Post them to Stratagraph as one Markdown document over MCP. This skill runs as an unattended nightly cloud routine and writes nothing to disk.

## Choose tools and sources at runtime

- **Choose the destination.** Post to the Stratagraph connector attached to the routine. Use the tool whose name ends in `strata_post_document`. Never assume a specific project, server URL, or connector UUID. If more than one Stratagraph connector is attached, use the connector named by `strata_project`. If `strata_project` is missing, stop and report that it is required.
- **Choose tools by suffix.** Refer to connector tools by their suffixes, not their UUID prefixes. Use `slack_read_channel`, `slack_read_thread`, `slack_read_user_profile`, and `slack_search_*` for Slack. Use `search_threads` and `get_thread` for Gmail. Use `list_events` for Calendar. Use the matching tools from the connectors attached to the routine.
- **Read sources from the configuration.** Read the configuration below from the routine prompt. Do not hard-code a team, channel, or person in this skill.

If a required connector or tool is unavailable, stop and name it in the routine transcript.

## Read the routine configuration

`channels` and `timezone` are required. If either is missing, stop and report which field the routine prompt must supply.

- `channels` (required): Slack channels to read, by name or ID.
- `timezone` (required): IANA time zone for the day window. For example, `America/New_York`.
- `dm_users` (optional): people whose direct messages with the connected Slack account to include.
- `gmail_query` (optional): Gmail search string that identifies relevant messages, such as a label, set of senders, or search terms. Omit it to skip email.
- `title_prefix` (optional): document title label. The default is `Slack & email log`.
- `strata_project` (optional): Stratagraph connector name. It is required when more than one Stratagraph connector is attached. Omit it when exactly one is attached.

## Gather and post the activity

1. **Set the window.** Use the current date in `timezone` to identify the previous calendar day. Set the window to `00:00` through `23:59:59` local time. Call the date `DATE` and format it as `YYYY-MM-DD`.
2. **Gather Slack messages.** Read messages inside the window for each channel in `channels`. Expand every thread that has replies. If `dm_users` is set, include those direct messages for the same window.
3. **Resolve author names.** Use `slack_read_user_profile` for each user ID. Make a reasonable attempt to identify unresolved senders from Slack Connect or other external messages. If a sender is still unknown, use `Unknown (external)`. Never fabricate a name.
4. **Gather Gmail messages.** If `gmail_query` is set, restrict the search to the window. Include the sender, time, subject, and a short source-faithful summary of relevant messages in each matching thread. Skip organization-wide or automated messages that do not add relevant information.
5. **Gather calendar events.** List events inside the window. Include the title, time, attendees, and any recording or recap in the event details. Skip clearly unrelated personal events.
6. **Assemble the document.** Write a short header with the date and sources covered. Add one section for each source. End with a brief `Decisions, risks, and actions` list. Stay faithful to the sources. Do not invent details.
7. **Post the document.** Call the attached `strata_post_document` with:
   - `title`: `{title_prefix}, {weekday} {DATE}`
   - `kind`: `document`
   - `source`: `routine`
   - `occurred_at`: `DATE`
   - `external_id`: `slack-email-{DATE}` (re-runs use the same identifier and do not create a duplicate)
   - `content`: the assembled Markdown
8. **Handle an empty day.** If no Slack messages, Gmail messages, or calendar events remain after the filters above, do not post. Report `no activity for {DATE}` and stop.
9. **Keep the run off disk.** Never write files. The routine transcript is the only local record.

## Report the result

End with one summary line for the routine transcript. Include `DATE`, the count for each source, and the `document_id` returned by Stratagraph. For an empty day, include `skipped: empty` instead of a document ID.
