#!/usr/bin/env python3
"""
import.py -- deterministic helpers for the import skill.

This file holds ONLY mechanics. The discipline (provenance, node grain, the
Iron Rule, what to distill) lives in SKILL.md and is the agent's job; the agent
does the reading and the LLM reasoning. These subcommands do the boring,
error-prone, token-heavy parts that a script does reliably and an agent does
badly:

  inventory  walk a corpus -> a manifest JSON (paths, sizes, chars/4 token
             estimates, head peeks, derivative/date signals, optional time
             buckets + a per-bucket cost rollup for the temporal-economy lever).
             Skips VCS/dependency/cache noise (.git, node_modules, ...) by
             default so a real project dir doesn't drown the manifest.
  validate   check one document's distilled nodes JSON: types against the
             fetched schema, 1-5 spans per node, and every span a
             CHARACTER-EXACT substring of the document text.
  bundle     assemble/append document+node entries into import-bundle.json,
             idempotent by externalId, with optional explicit replacement and
             a resumable worklist journal.
  combine    validate and combine reviewed bundles in chronological order,
             rejecting duplicate externalIds and writing a hash manifest.

Design constraints:
  * Python 3 standard library only -- no pip installs, runs on whatever the
    user's agent ships. No version-gated syntax (no match, walrus, `X | Y`).
  * Never crashes on whatever the user throws at it: unreadable/binary files,
    odd encodings, symlink loops, huge trees, malformed JSON, wrong-shape
    nodes/entries. Problems are RECORDED in the output, never raised.
  * No LLM calls, no network, no API key. Pure local computation.

Usage:
  python3 scripts/import.py inventory <root> [--exclude DIR ...] [--output-dir DIR]
                                      [--head-lines N] [--bucket quarter|month|year]
                                      [--include-noise]
  python3 scripts/import.py validate <nodes.json> --text <document> --types t1,t2,...
  python3 scripts/import.py bundle [--replace] --output-dir DIR <entry.json> ...
  python3 scripts/import.py combine --output-dir DIR --types t1,t2,... <bundle.json> ...
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

HEAD_BYTES = 8192  # how much of each file to sniff for signals / head peek
IMPORT_CONTRACT_VERSION = 2

# Directory names skipped by default at ANY depth: VCS, dependency trees, build
# and tool caches. A source corpus is never these, and a raw project dir is
# ~90% node_modules/.git by file count. Override with --include-noise.
DEFAULT_EXCLUDE_DIRS = frozenset([
    ".git", ".svn", ".hg", ".bzr",
    # NB: bare "env" is deliberately NOT here -- it's too often a real content
    # folder (a project's env-config dir), not a virtualenv. .venv/venv are safe.
    "node_modules", ".venv", "venv", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".cache",
    ".next", ".nuxt", ".turbo", ".svelte-kit", ".parcel-cache",
    ".idea", ".vscode", ".terraform",
])
DEFAULT_EXCLUDE_FILES = frozenset([".DS_Store", "Thumbs.db"])

# Date shapes seen in filenames/content: 2025-09-10, 2025_09_10, 2025.09.10.
# Non-authoritative signal only: this matches impossible dates (2025-02-30) and
# mixed separators. The agent resolves the real date; this just flags candidates.
_DATE_RE = re.compile(r"(20\d{2})[-_./](0[1-9]|1[0-2])[-_./](0[1-9]|[12]\d|3[01])")
# Frontmatter/keys that mark a machine-derived (LLM-generated) artifact.
_DERIVATIVE_KEYS = ("extracted_at", "assertion_count", "confidence:", "generated_by")


def est_tokens(num_bytes):
    """Approximate token count. chars/4 is the standard English heuristic; we use
    byte size as the char proxy so huge files aren't read in full. Slightly
    over-estimates on multi-byte text -- the safe direction for a ceiling. Not a
    billing figure."""
    return (num_bytes + 3) // 4


def read_head(path):
    """Return (head_text, is_binary). Never raises; degrades to ('', False)."""
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(HEAD_BYTES)
    except (OSError, IOError):
        return "", False
    if b"\x00" in chunk:
        return "", True  # null byte -> treat as binary, no head peek
    return chunk.decode("utf-8", errors="replace"), False


def iso_mtime(path):
    try:
        ts = os.path.getmtime(path)
    except (OSError, IOError):
        return None
    return datetime.datetime.fromtimestamp(
        ts, datetime.timezone.utc
    ).strftime("%Y-%m-%d")


def find_date(text):
    """First YYYY-MM-DD-ish date in `text`, normalized to YYYY-MM-DD, or None."""
    m = _DATE_RE.search(text or "")
    if not m:
        return None
    return "%s-%s-%s" % (m.group(1), m.group(2), m.group(3))


def bucket_label(date_str, grain):
    """date_str 'YYYY-MM-DD' -> a bucket label for the chosen grain, or None."""
    if not date_str:
        return None
    year, month = date_str[:4], int(date_str[5:7])
    if grain == "year":
        return year
    if grain == "month":
        return date_str[:7]
    return "%s-Q%d" % (year, (month - 1) // 3 + 1)  # quarter (default)


def detect_signals(rel_path, head):
    """Non-authoritative hints the agent uses to classify. Signals, not verdicts."""
    signals = []
    low_head = head.lower()
    for key in _DERIVATIVE_KEYS:
        if key in low_head:
            signals.append("frontmatter:" + key.rstrip(":"))
    if "summary" in rel_path.lower():
        signals.append("path-contains:summary")
    return signals


def short(value):
    if isinstance(value, str) and len(value) > 60:
        return value[:60] + "..."
    return value


# ---------------------------------------------------------------------------
# inventory
# ---------------------------------------------------------------------------

def cmd_inventory(args):
    root = os.path.abspath(args.root)
    # Explicit --exclude paths resolve against root (like the default output dir).
    excludes = set(os.path.abspath(os.path.join(root, e)) for e in (args.exclude or []))
    out_dir_abs = None
    if args.output_dir:
        # Resolve from CWD (like `bundle` does) so one --output-dir value points
        # at the same folder for every subcommand; still excluded from the walk
        # whenever it lands under root (the normal <root>/_import case).
        out_dir_abs = os.path.abspath(args.output_dir)
        excludes.add(out_dir_abs)
    skip_noise = not args.include_noise
    head_lines = args.head_lines

    files = []
    by_ext = {}
    by_bucket = {}
    total_bytes = 0
    total_tokens = 0

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Prune excluded + noise directories in-place (don't descend).
        dirnames[:] = [
            d for d in dirnames
            if os.path.abspath(os.path.join(dirpath, d)) not in excludes
            and not (skip_noise and d in DEFAULT_EXCLUDE_DIRS)
        ]
        for name in sorted(filenames):
            if skip_noise and name in DEFAULT_EXCLUDE_FILES:
                continue
            abs_path = os.path.join(dirpath, name)
            if os.path.abspath(abs_path) in excludes:
                continue
            if os.path.islink(abs_path):
                continue  # don't chase symlinks
            try:
                size = os.path.getsize(abs_path)
            except (OSError, IOError):
                size = 0
            rel = os.path.relpath(abs_path, root)
            head, is_binary = read_head(abs_path)
            tokens = est_tokens(size)
            fn_date = find_date(name)
            content_date = None if is_binary else find_date(head)
            resolved_date = fn_date or content_date
            bucket = bucket_label(resolved_date, args.bucket) if args.bucket else None

            files.append({
                "externalId": rel,
                "sizeBytes": size,
                "ext": os.path.splitext(name)[1].lower(),
                "mtime": iso_mtime(abs_path),
                "estTokens": tokens,
                "binary": is_binary,
                "headPeek": "" if is_binary else "\n".join(head.splitlines()[:head_lines]),
                "signals": [] if is_binary else detect_signals(rel, head),
                "filenameDate": fn_date,
                "contentDate": content_date,
                "candidateBucket": bucket,
            })

            ext = os.path.splitext(name)[1].lower() or "(none)"
            slot = by_ext.setdefault(ext, {"files": 0, "estTokens": 0})
            slot["files"] += 1
            slot["estTokens"] += tokens
            total_bytes += size
            total_tokens += tokens
            if args.bucket:
                key = bucket or "(undated)"
                bslot = by_bucket.setdefault(key, {"files": 0, "estTokens": 0})
                bslot["files"] += 1
                bslot["estTokens"] += tokens

    manifest = {
        "root": root,
        "generatedBy": "import.py inventory",
        "tokenEstimateNote": "chars/4 from byte size; approximate, not billing",
        "autoExcludedDirs": [] if args.include_noise else sorted(DEFAULT_EXCLUDE_DIRS),
        "totals": {"files": len(files), "bytes": total_bytes, "estTokens": total_tokens},
        "byExtension": by_ext,
        "files": files,
    }
    if args.bucket:
        manifest["bucketGrain"] = args.bucket
        manifest["byBucket"] = by_bucket

    # Full manifest can be hundreds of KB (head peeks). When we persist it to a
    # file, print only a compact summary to stdout so we don't flood the agent's
    # context; the agent reads the file for the per-file detail.
    summary = {
        "root": root,
        "totals": manifest["totals"],
        "autoExcludedDirs": manifest["autoExcludedDirs"],
        "byExtension": by_ext,
    }
    if args.bucket:
        summary["byBucket"] = by_bucket
    _emit(manifest, out_dir_abs, "inventory.json", summary=summary)
    return 0


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

def validate_nodes(nodes, text, allowed):
    """Return a deterministic validation report for one document's nodes."""
    results = []
    ok = True
    for i, node in enumerate(nodes):
        errors = []
        warnings = []
        if not isinstance(node, dict):
            errors.append("node is not an object")
            results.append({"index": i, "type": None, "errors": errors, "warnings": warnings})
            ok = False
            continue

        node_type = node.get("type")
        if node_type not in allowed:
            errors.append("type %r not in fetched schema" % (node_type,))
        content = node.get("content")
        if not isinstance(content, str) or not content.strip():
            errors.append("empty or non-string content")

        spans = node.get("spans")
        if not isinstance(spans, list):
            spans = []
        if not spans:
            errors.append("expected 1-5 spans; found 0")
        if len(spans) > 5:
            errors.append("expected 1-5 spans; found %d" % len(spans))
        for span in spans:
            # The load-bearing check: a span that isn't a verbatim, non-empty
            # substring degrades to null server-side.
            if not isinstance(span, str) or span == "" or span not in text:
                errors.append("span not verbatim in text: %r" % (short(span),))

        if errors:
            ok = False
        results.append({"index": i, "type": node_type, "errors": errors, "warnings": warnings})

    return {"nodeCount": len(nodes), "ok": ok, "nodes": results}


def cmd_validate(args):
    try:
        with open(args.nodes, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, IOError, ValueError) as exc:
        _fail("could not read nodes JSON %s: %s" % (args.nodes, exc))
        return 2
    try:
        with open(args.text, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except (OSError, IOError) as exc:
        _fail("could not read document text %s: %s" % (args.text, exc))
        return 2

    nodes = data.get("nodes", data) if isinstance(data, dict) else data
    if not isinstance(nodes, list):
        _fail("nodes JSON is not a list (or {nodes: [...]})")
        return 2
    allowed = set(t.strip() for t in args.types.split(",") if t.strip())
    if not allowed:
        _fail("--types must contain at least one fetched type")
        return 2

    report = validate_nodes(nodes, text, allowed)
    report["document"] = args.text
    _print_json(report)
    return 0 if report["ok"] else 1


# ---------------------------------------------------------------------------
# bundle
# ---------------------------------------------------------------------------

def cmd_bundle(args):
    out_dir = os.path.abspath(args.output_dir)
    try:
        os.makedirs(out_dir, exist_ok=True)
    except (OSError, IOError) as exc:
        _fail("could not create output dir %s: %s" % (out_dir, exc))
        return 2
    bundle_path = os.path.join(out_dir, "import-bundle.json")
    journal_path = os.path.join(out_dir, "worklist.json")

    # Refuse to clobber an existing bundle we can't parse or that's the wrong
    # shape -- otherwise a corrupt file would silently drop every prior entry.
    if os.path.exists(bundle_path):
        try:
            with open(bundle_path, "r", encoding="utf-8") as fh:
                bundle = json.load(fh)
        except (OSError, IOError, ValueError) as exc:
            _fail("existing import-bundle.json is unreadable; refusing to overwrite: %s" % exc)
            return 2
        contract_error = _bundle_contract_error(bundle)
        if contract_error:
            _fail(
                "existing import-bundle.json uses a stale or invalid import contract; "
                "regenerate it with contract version %d and nodes[] before resuming: %s"
                % (IMPORT_CONTRACT_VERSION, contract_error)
            )
            return 2
    else:
        bundle = {"version": IMPORT_CONTRACT_VERSION, "documents": []}

    journal = _load_json(journal_path, {"entries": {}})
    if not isinstance(journal, dict) or not isinstance(journal.get("entries"), dict):
        journal = {"entries": {}}
    seen = {}
    for index, existing in enumerate(bundle["documents"]):
        if isinstance(existing, dict) and isinstance(existing.get("document"), dict):
            ext_id = existing["document"].get("externalId")
            if ext_id:
                seen[ext_id] = index

    added, replaced, skipped, invalid = 0, 0, 0, 0
    for entry_path in args.entries:
        entry = _load_json(entry_path, None)
        if not isinstance(entry, dict) or not isinstance(entry.get("document"), dict):
            _warn("skipping entry with missing/invalid document: %s" % entry_path)
            invalid += 1
            continue
        ext_id = entry["document"].get("externalId")
        if not ext_id:
            _warn("skipping entry with no externalId: %s" % entry_path)
            invalid += 1
            continue
        if not isinstance(entry.get("nodes"), list):
            _warn("skipping entry with missing/invalid nodes: %s" % entry_path)
            invalid += 1
            continue
        payload = {"document": entry["document"], "nodes": entry["nodes"]}
        if ext_id in seen:
            if args.replace:
                bundle["documents"][seen[ext_id]] = payload
                journal["entries"][ext_id] = {"status": "replaced", "nodes": len(entry["nodes"])}
                replaced += 1
            else:
                skipped += 1
                journal["entries"][ext_id] = {"status": "already-in-bundle"}
            continue
        bundle["documents"].append(payload)
        seen[ext_id] = len(bundle["documents"]) - 1
        journal["entries"][ext_id] = {"status": "bundled", "nodes": len(entry["nodes"])}
        added += 1

    _write_json(bundle_path, bundle)
    _write_json(journal_path, journal)
    total_nodes = sum(
        len(d["nodes"]) for d in bundle["documents"]
        if isinstance(d, dict) and isinstance(d.get("nodes"), list)
    )
    _print_json({
        "bundle": bundle_path,
        "documents": len(bundle["documents"]),
        "nodes": total_nodes,
        "addedThisRun": added,
        "replacedThisRun": replaced,
        "skippedAlreadyPresent": skipped,
        "skippedInvalid": invalid,
    })
    return 1 if invalid else 0


# ---------------------------------------------------------------------------
# combine
# ---------------------------------------------------------------------------

def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bundle_contract_error(bundle):
    if not isinstance(bundle, dict):
        return "bundle is not an object"
    if bundle.get("version") != IMPORT_CONTRACT_VERSION:
        return "expected version %d; found %r" % (
            IMPORT_CONTRACT_VERSION,
            bundle.get("version"),
        )
    documents = bundle.get("documents")
    if not isinstance(documents, list):
        return "bundle has no documents[] array"
    for index, entry in enumerate(documents):
        if not isinstance(entry, dict):
            return "document %d is not an object" % index
        if not isinstance(entry.get("nodes"), list):
            return "document %d has no nodes[] array" % index
        if "atoms" in entry:
            return "document %d contains the legacy atoms key" % index
    return None


def _occurred_sort_key(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("occurredAt is missing")
    raw = value.strip()
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        if "T" in normalized:
            parsed = datetime.datetime.fromisoformat(normalized)
        else:
            parsed = datetime.datetime.strptime(normalized, "%Y-%m-%d")
    except ValueError:
        raise ValueError("occurredAt is not an ISO date or datetime: %r" % raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    else:
        parsed = parsed.astimezone(datetime.timezone.utc)
    return parsed, raw


def cmd_combine(args):
    allowed = set(t.strip() for t in args.types.split(",") if t.strip())
    if not allowed:
        _fail("--types must contain at least one fetched type")
        return 2

    out_dir = os.path.abspath(args.output_dir)
    output_bundle = os.path.join(out_dir, "import-bundle.json")
    input_paths = [os.path.abspath(path) for path in args.bundles]
    if output_bundle in input_paths:
        _fail("combined output must use a different directory from every input bundle")
        return 2

    combined = []
    parents = []
    seen = {}
    errors = []

    for path in input_paths:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                bundle = json.load(fh)
            parent_hash = _sha256(path)
        except (OSError, IOError, ValueError) as exc:
            errors.append({"bundle": path, "error": "could not read bundle: %s" % exc})
            continue
        contract_error = _bundle_contract_error(bundle)
        if contract_error:
            errors.append({
                "bundle": path,
                "error": (
                    "stale or invalid import contract; regenerate with version %d "
                    "and nodes[]: %s"
                ) % (IMPORT_CONTRACT_VERSION, contract_error),
            })
            continue
        documents = bundle.get("documents") if isinstance(bundle, dict) else None

        parent_nodes = 0
        for index, entry in enumerate(documents):
            label = "%s document %d" % (path, index)
            if not isinstance(entry, dict) or not isinstance(entry.get("document"), dict):
                errors.append({"bundle": path, "index": index, "error": "invalid document entry"})
                continue
            document = entry["document"]
            nodes = entry.get("nodes")
            ext_id = document.get("externalId")
            if not isinstance(ext_id, str) or not ext_id:
                errors.append({"bundle": path, "index": index, "error": "missing externalId"})
                continue
            if ext_id in seen:
                errors.append({
                    "bundle": path,
                    "index": index,
                    "error": "duplicate externalId %r; first seen in %s" % (ext_id, seen[ext_id]),
                })
                continue
            missing = [
                field for field in ("name", "source", "text")
                if not isinstance(document.get(field), str) or not document.get(field)
            ]
            if missing:
                errors.append({"bundle": path, "index": index, "error": "missing document fields: %s" % ", ".join(missing)})
                continue
            try:
                sort_key = _occurred_sort_key(document.get("occurredAt"))
            except ValueError as exc:
                errors.append({"bundle": path, "index": index, "error": str(exc)})
                continue
            validation = validate_nodes(nodes, document["text"], allowed)
            if not validation["ok"]:
                errors.append({"bundle": path, "index": index, "externalId": ext_id, "validation": validation})
                continue
            seen[ext_id] = label
            parent_nodes += len(nodes)
            combined.append((sort_key, ext_id, entry))

        parents.append({
            "path": path,
            "sha256": parent_hash,
            "documents": len(documents),
            "nodes": parent_nodes,
        })

    if errors:
        _print_json({"ok": False, "errors": errors})
        return 1

    combined.sort(key=lambda item: (item[0], item[1]))
    output = {"version": IMPORT_CONTRACT_VERSION, "documents": [item[2] for item in combined]}
    try:
        os.makedirs(out_dir, exist_ok=True)
        _write_json(output_bundle, output)
        manifest_path = os.path.join(out_dir, "combined-manifest.json")
        total_nodes = sum(len(entry.get("nodes", [])) for entry in output["documents"])
        manifest = {
            "version": IMPORT_CONTRACT_VERSION,
            "generatedBy": "import.py combine",
            "parents": parents,
            "combined": {
                "path": output_bundle,
                "sha256": _sha256(output_bundle),
                "documents": len(output["documents"]),
                "nodes": total_nodes,
            },
        }
        _write_json(manifest_path, manifest)
    except (OSError, IOError) as exc:
        _fail("could not write combined bundle: %s" % exc)
        return 2

    _print_json({"ok": True, "bundle": output_bundle, "manifest": manifest_path, "documents": len(output["documents"]), "nodes": total_nodes})
    return 0


# ---------------------------------------------------------------------------
# small IO utilities
# ---------------------------------------------------------------------------

def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, IOError, ValueError):
        return default


def _write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _print_json(obj):
    json.dump(obj, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _emit(obj, output_dir, filename, summary=None):
    """Persist the full object to output_dir/filename when given, and print a
    compact `summary` to stdout (so a big manifest doesn't flood context). With
    no output_dir, print the full object to stdout."""
    if output_dir:
        try:
            os.makedirs(output_dir, exist_ok=True)
            dest = os.path.join(output_dir, filename)
            _write_json(dest, obj)
            out = dict(summary or {})
            out["manifest"] = dest
            _print_json(out)
            return
        except (OSError, IOError) as exc:
            _warn("could not write %s: %s (printing full output instead)" % (filename, exc))
    _print_json(obj)


def _warn(msg):
    sys.stderr.write("warning: " + msg + "\n")


def _fail(msg):
    sys.stderr.write("error: " + msg + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(description="Deterministic helpers for the import skill.")
    sub = p.add_subparsers(dest="command")

    inv = sub.add_parser("inventory", help="walk a corpus -> manifest JSON")
    inv.add_argument("root", help="corpus root directory")
    inv.add_argument("--exclude", action="append", default=[], help="path (relative to root) to skip; repeatable")
    inv.add_argument("--output-dir", help="folder for inventory.json (resolved from CWD, use an absolute path so it matches `bundle`); excluded from the walk")
    inv.add_argument("--head-lines", type=int, default=20, help="lines of head peek per file (default 20)")
    inv.add_argument("--bucket", choices=["quarter", "month", "year"], help="also roll up per time bucket (the temporal-economy cost table)")
    inv.add_argument("--include-noise", action="store_true", help="do NOT skip .git/node_modules/caches (off by default)")
    inv.set_defaults(func=cmd_inventory)

    val = sub.add_parser("validate", help="check one document's nodes JSON (types + verbatim spans)")
    val.add_argument("nodes", help="nodes JSON file: [ ... ] or { nodes: [ ... ] }")
    val.add_argument("--text", required=True, help="the document text the spans must match verbatim")
    val.add_argument("--types", required=True, help="comma-separated allowed node types (from the fetched schema)")
    val.set_defaults(func=cmd_validate)

    bun = sub.add_parser("bundle", help="assemble/append entries into import-bundle.json")
    bun.add_argument("--output-dir", required=True, help="folder holding import-bundle.json + worklist.json")
    bun.add_argument("--replace", action="store_true", help="replace an existing entry with the same externalId")
    bun.add_argument("entries", nargs="+", help="entry JSON files: { document: {...}, nodes: [...] }")
    bun.set_defaults(func=cmd_bundle)

    com = sub.add_parser("combine", help="validate and combine reviewed bundles")
    com.add_argument("--output-dir", required=True, help="new folder for import-bundle.json + combined-manifest.json")
    com.add_argument("--types", required=True, help="comma-separated allowed node types (from the fetched schema)")
    com.add_argument("bundles", nargs="+", help="reviewed import-bundle.json files")
    com.set_defaults(func=cmd_combine)
    return p


def main(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
