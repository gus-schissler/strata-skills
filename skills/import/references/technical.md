# Technical workflow

Read this file before running `scripts/import.py`, assembling bundles, or assigning workers.

## Resolve the helper path

Set `<skill-dir>` to the directory that contains `SKILL.md`. The helper is at `<skill-dir>/scripts/import.py`. The corpus is usually the working directory, so do not assume the helper is there.

Use one absolute `<out>` path for every command that accepts `--output-dir`.

Use a separate subdirectory for each source-group review bundle, such as `<out>/durable-docs` and `<out>/transcripts`. Write the derived upload bundle to `<out>/combined`.

## Commands

Review and upload bundles use import contract version 1. Every document entry
requires a `nodes` array.

### Inventory

```bash
python3 <skill-dir>/scripts/import.py inventory <approved-root> --output-dir <out>
```

Optional flags:

- `--exclude <path>` can be repeated.
- `--bucket quarter|month|year` adds time-period estimates.
- `--include-noise` includes the version-control, dependency, cache, and build folders skipped by default. It does not include or select every generated file automatically.

## Choose the extraction method

Use `doc-by-doc` by default. It processes each source independently at the agreed level of detail and usually produces the most claims.

Use `temporal-economy` only when the corpus is chronological and repetitive, and the user prefers fewer claims. It does not reduce source-reading cost.

For `temporal-economy`:

1. Run inventory with `--bucket month`, `--bucket quarter`, or `--bucket year`.
2. Show the user each period's document count and estimated tokens.
3. Ask the user to mark each period as full, coarse, or skip.

Apply the choices as follows:

- **Full:** Use normal `doc-by-doc` extraction for every document in the period.
- **Coarse:** Read every document, but apply a stricter relevance threshold so the period produces fewer claims. Keep a separate entry for each source document. Do not merge claims or supporting spans across documents.
- **Skip:** Do not read or extract the period.

### Validate one entry

```bash
python3 <skill-dir>/scripts/import.py validate <nodes.json> \
  --text <document> \
  --types <comma-separated-live-types>
```

`--types` is required. Validation fails when a type is not allowed, content is empty, a claim has fewer than 1 or more than 5 spans, or a span is not an exact source substring.

### Add or replace reviewed entries

```bash
python3 <skill-dir>/scripts/import.py bundle --output-dir <out> <entry.json> ...
```

The command skips an `externalId` that is already present. Use explicit replacement after a reviewed entry changes:

```bash
python3 <skill-dir>/scripts/import.py bundle --replace --output-dir <out> <entry.json> ...
```

Validate every changed entry again before replacement.

### Combine reviewed bundles

Use a new output directory. Do not overwrite a parent review bundle.

```bash
python3 <skill-dir>/scripts/import.py combine \
  --output-dir <out>/combined \
  --types <comma-separated-live-types> \
  <reviewed-bundle-1.json> <reviewed-bundle-2.json> ...
```

The command:

- validates document fields, types, and exact spans
- requires a resolved ISO `occurredAt`
- rejects duplicate `externalId` values
- sorts documents by `occurredAt`, then `externalId`
- writes `import-bundle.json`
- writes `combined-manifest.json` with parent and output SHA-256 hashes

Both the combined bundle and its hash manifest declare `"version": 1`.

Keep every parent review bundle.

## Entry shape

```json
{
  "document": {
    "externalId": "...",
    "name": "...",
    "occurredAt": "...",
    "source": "...",
    "text": "...",
    "participants": []
  },
  "nodes": [
    {
      "type": "...",
      "content": "...",
      "speaker": "...",
      "spans": ["..."],
      "sectionLabel": "..."
    }
  ]
}
```

Optional fields may be omitted. Each entry matches one document in the `strata_import_document` payload without `projectId` and `userId`.

## Assign workers safely

Use parallel workers only after the user approves them.

The orchestrating agent owns:

- source classification
- date policy
- the worklist
- corpus-wide gap checks
- final quality review
- bundle assembly
- all current-state documents

Give workers separate inputs and output files. Use the same evidence and model-capability standards for every worker. Do not use a weaker model for worker extraction.

Validate every worker result before adding it to a bundle. Use `worklist.json` as the resume journal.
