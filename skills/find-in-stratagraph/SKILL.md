---
name: find-in-stratagraph
description: >-
  Find and verify specific information in a connected Stratagraph project.
  Use when the user asks to find, look up, check, verify, or answer a focused
  question from Stratagraph. Common requests include "what do we know about
  X?", "what is current?", "who owns X?", "what did this person say?", "find
  this node key", or questions about a fact, requirement, status, source,
  decision, or conflict. Search to locate candidates, then read full nodes and
  relevant relationships. This skill is read-only. Do not use it for broad
  histories, topic evolution, exhaustive tracing, importing sources, daily
  gathering, or writing documents to Stratagraph.
---

# Find information in Stratagraph

Answer a focused question from the connected Stratagraph project. Verify the answer with full node content and relationships. Cite every node key as a link. Do not require briefs.

## Select the project safely

- Find attached Stratagraph tools by names ending in values such as `strata_search_nodes`. Full tool names may start with an MCP-generated identifier. Never assume a connector UUID, server URL, project key, or full tool name.
- If 1 Stratagraph connector is attached, use it. If several are attached, use the connector named by `strata_project`. If no connector is selected, ask which project to use before querying.
- If no Stratagraph connector is available, tell the user to connect the project's MCP server. Stop until the tools are available.
- Treat the live tool descriptions and input schemas as authoritative because tool parameters may change.
- Use only read tools. Never call `strata_post_document` or another write tool while following this skill.
- Read the project key from the MCP server instructions or tool descriptions. Do not infer it when the server provides it.
- Read the application origin from the attached MCP connector URL when it is visible. Keep only the scheme and host. If the connector URL is not visible, use `https://stratagraph.io`.

## Frame the lookup

Read the request and identify:

1. The fact or question to answer.
2. Any named document, date range, speaker, or source.
3. Whether the user asks what is current, what changed, or what conflicts.
4. Whether the request is a focused lookup or a broad history. Use this skill only for the focused lookup.

Ask a question only when 2 or more reasonable scopes would produce different answers. Otherwise, use the narrowest reasonable scope and state it when helpful.

## Delegate the lookup to a subagent when possible

If the environment can spawn subagents and a subagent can reach this project's Stratagraph tools, run the lookup in 1 subagent instead of the main conversation. The full nodes, documents, and traversals this skill reads are its context-heavy part, and the skill is read-only, so delegation keeps that payload out of the main context at no risk.

- Give the subagent the framed question and this skill to follow.
- The subagent's report must contain the exact returned node keys and the full node content behind every statement, including `occurred_at`, speaker, review status, and relevant edges. Never accept a paraphrase without keys: the report is the calling agent's only verification evidence, and every node key cited in the final answer comes from it.
- If subagents are unavailable, or they cannot reach the project's tools, follow the rest of this skill directly.

## Choose the first tool

| Question shape | Start with | What to do |
|---|---|---|
| Exact node key | `strata_get_node` | Fetch the known node directly. Do not search for it. |
| Focused topic, fact, status, requirement, or owner | `strata_search_nodes` | Write 1 concise semantic query. Add a type filter only when the request supports it. |
| Named document, source, date, or speaker | `strata_list_documents` | Find the relevant documents. Then use `strata_get_document` or search with `document_ids` or `speaker`. |
| Relationship between known nodes | `strata_list_edges` | Read the relevant incoming or outgoing edges without expanding unrelated claims. |
| Connected context around a known node | `strata_traverse` | Start with `max_depth: 1`. Set `edge_types` when only specific relationships matter. |
| Named brief or explicit request for maintained synthesis | `strata_list_briefs`, then `strata_get_brief` | Use briefs only when they are available and clearly relevant. Continue without them when none exist. |
| Unfamiliar node types or relationship meanings | `strata_get_graph_schema` | Read the live taxonomy instead of guessing. |

For a question limited to a named source, use `strata_get_document` to inspect every returned extracted claim before declaring a gap. The document response contains claim snippets, not full claim bodies. Fetch each node used in the answer with `strata_get_node` or `strata_get_nodes`. If the document response returns `truncated: true`, state that the claim list is incomplete and do not claim that the document lacks a matching claim. For a question limited to a person, set `speaker` instead of only adding the person's name to the query.

## Read the evidence

Use `strata_search_nodes` to locate candidates. Treat `semantic_similarity` when supplied as relative proximity, not truth, confidence, relevance, or currentness. Never answer a substantive question from search snippets alone.

After a useful search:

- Fetch 1 clearly relevant candidate with `strata_get_node`.
- Fetch several relevant, disconnected candidates in 1 `strata_get_nodes` call.
- Traverse from a finding at depth 1 when its support, replacement, conflict, or resolution affects the answer.
- Fetch the document when the answer depends on all claims extracted from that document. Then fetch every relevant node in full before citing it.

Read full results before running another search. Do not repeat a successful query with synonyms. Search again only to fill a specific gap, such as a named source, person, date, or term found in full node content.

Stop when the evidence answers the question and you have checked whether relevant claims are replaced, disputed, or resolved. If traversal returns `truncated: true`, continue only from the relevant relationship or node key.

## Check the answer

A node's existence in the graph does not establish that it is relevant, true, or current. Describe conclusions as graph grounding — what the project records and currently treats as canonical — rather than externally verified truth unless separate evidence verifies them.

- Base each factual statement on full node or document content, not on similarity rank.
- For current-state questions, inspect `occurred_at`, `occurred_at_basis` when supplied, `review`, incoming `replaces` and `resolves` relationships, and `counters` relationships in both directions. An inbound `replaces` edge retires a claim; counters and age alone do not.
- Keep the source or event date from `occurred_at` when present. `document_date` is source context, not a promise of precise event time; `record_created` is the fallback for a documentless node. Do not silently replace either with another timestamp.
- Attribute a statement to a person only when the node or source names that speaker.
- Read edge direction as `source verb target`. A source with `replaces` supersedes its target. A `counters` edge means both claims still stand but disagree. A source with `resolves` closes its target question, action item, or risk. Report meaningful conflicts instead of choosing a side by similarity or date alone.
- If the answer presents a replacing node as the current successor, follow its inbound `replaces` relationships: fetch the source of the inbound edge, then repeat until the endpoint has no further inbound `replaces`. Cite the terminal successor and any chain needed to explain the change.
- If a claim's `review` value is `imported`, say so when review status affects trust. Do not describe it as confirmed current state.
- If an edge meaning is unclear, use `strata_get_graph_schema` instead of relying on memory.
- Remember that semantic search returns only the highest-ranked candidates. It does not inspect every node, so a missing result does not prove that the project lacks the information.

A recently posted node may still be waiting for search indexing. Say so when that could explain an empty result. If the document is known, use `strata_get_document`. Otherwise, run at most 1 more search with a different document, speaker, date, or specific term. Then name what you searched and the remaining limitation.

If verified reading turns up a relationship between two already-baked nodes that the graph does not represent, mention that the attached tool ending in `strata_suggest_edges` can propose it with a reason. Do not call that write tool as part of this read-only skill. A later request to propose the relationship is separate explicit write intent; before acting on it, leave this workflow, read the tool's live description and schema, and report its returned status accurately. Do not promise that every proposal waits for human review: an eligible `supports` suggestion may be promoted directly into the graph.

## Answer with linked node keys

Lead with the answer. Link every displayed node key to `{origin}/projects/{project_key}/nodes/{node_key}`. This rule applies to inline citations, supporting evidence, replacements, conflicts, and source lists.

Use Markdown links with the exact returned key as the label. For example: `The launch target moved to September [PROJ-142](https://stratagraph.io/projects/PROJ/nodes/PROJ-142).`

Include only what helps the user judge the answer:

- the document, speaker, or date scope
- any later replacement or unresolved conflict
- any relevant review note
- any evidence gap

Never display a bare node key in the user-facing answer. Never invent or reconstruct a node key. Do not describe the tool calls unless the user asks. After semantic search, say, “I didn't find this in the returned matches.” Claim only that a specific document lacks an extracted claim after retrieving the document and confirming that `truncated` is `false`.
