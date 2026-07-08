#!/usr/bin/env python3
"""
import.py -- deterministic helpers for the import skill.

This file holds ONLY mechanics. The discipline (provenance, atom grain, the
Iron Rule, what to distill) lives in SKILL.md and is the agent's job; the agent
does the reading and the LLM reasoning. These subcommands do the boring,
error-prone, token-heavy parts that a script does reliably and an agent does
badly:

  inventory  walk a corpus -> a manifest JSON (paths, sizes, chars/4 token
             estimates, head peeks, derivative/date signals, optional time
             buckets + a per-bucket cost rollup for the temporal-economy lever).
             Skips VCS/dependency/cache noise (.git, node_modules, ...) by
             default so a real project dir doesn't drown the manifest.
  validate   check one document's distilled atoms JSON: types against the
             fetched schema, and every span a CHARACTER-EXACT substring of the
             document text (the verbatim-span check that agents get wrong).
  bundle     assemble/append document+atom entries into import-bundle.json,
             idempotent by externalId, with a resumable worklist journal.

Design constraints:
  * Python 3 standard library only -- no pip installs, runs on whatever the
    user's agent ships. No version-gated syntax (no match, walrus, `X | Y`).
  * Never crashes on whatever the user throws at it: unreadable/binary files,
    odd encodings, symlink loops, huge trees, malformed JSON, wrong-shape
    atoms/entries. Problems are RECORDED in the output, never raised.
  * No LLM calls, no network, no API key. Pure local computation.

Usage:
  python3 import.py inventory <root> [--exclude DIR ...] [--output-dir DIR]
                                      [--head-lines N] [--bucket quarter|month|year]
                                      [--include-noise]
  python3 import.py validate <atoms.json> --text <document> --types t1,t2,...
  python3 import.py bundle --output-dir DIR <entry.json> [<entry.json> ...]
"""

import argparse
import datetime
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

HEAD_BYTES = 8192  # how much of each file to sniff for signals / head peek

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

def cmd_validate(args):
    try:
        with open(args.atoms, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, IOError, ValueError) as exc:
        _fail("could not read atoms JSON %s: %s" % (args.atoms, exc))
        return 2
    try:
        with open(args.text, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except (OSError, IOError) as exc:
        _fail("could not read document text %s: %s" % (args.text, exc))
        return 2

    atoms = data.get("atoms", data) if isinstance(data, dict) else data
    if not isinstance(atoms, list):
        _fail("atoms JSON is not a list (or {atoms: [...]})")
        return 2
    allowed = set(t.strip() for t in (args.types or "").split(",") if t.strip())

    results = []
    ok = True
    for i, atom in enumerate(atoms):
        errors = []
        warnings = []
        if not isinstance(atom, dict):
            errors.append("atom is not an object")
            results.append({"index": i, "type": None, "errors": errors, "warnings": warnings})
            ok = False
            continue

        atom_type = atom.get("type")
        if allowed and atom_type not in allowed:
            errors.append("type %r not in fetched schema" % (atom_type,))
        content = atom.get("content")
        if not isinstance(content, str) or not content.strip():
            errors.append("empty or non-string content")

        spans = atom.get("spans")
        if not isinstance(spans, list):
            spans = []
        if not spans:
            warnings.append("no spans (server stores no receipt)")
        if len(spans) > 5:
            warnings.append("more than 5 spans")
        for span in spans:
            # The load-bearing check: a span that isn't a verbatim, non-empty
            # substring degrades to null server-side -- a silently lost receipt.
            if not isinstance(span, str) or span == "" or span not in text:
                errors.append("span not verbatim in text: %r" % (short(span),))

        if errors:
            ok = False
        results.append({"index": i, "type": atom_type, "errors": errors, "warnings": warnings})

    report = {"document": args.text, "atomCount": len(atoms), "ok": ok, "atoms": results}
    _print_json(report)
    return 0 if ok else 1


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
        if not isinstance(bundle, dict) or not isinstance(bundle.get("documents"), list):
            _fail("existing import-bundle.json has no documents[] array; refusing to overwrite")
            return 2
    else:
        bundle = {"version": 1, "documents": []}

    journal = _load_json(journal_path, {"entries": {}})
    if not isinstance(journal, dict) or not isinstance(journal.get("entries"), dict):
        journal = {"entries": {}}
    seen = set(
        d.get("document", {}).get("externalId")
        for d in bundle["documents"]
        if isinstance(d, dict) and isinstance(d.get("document"), dict)
    )

    added, skipped = 0, 0
    for entry_path in args.entries:
        entry = _load_json(entry_path, None)
        if not isinstance(entry, dict) or not isinstance(entry.get("document"), dict):
            _warn("skipping entry with missing/invalid document: %s" % entry_path)
            continue
        ext_id = entry["document"].get("externalId")
        if not ext_id:
            _warn("skipping entry with no externalId: %s" % entry_path)
            continue
        if ext_id in seen:
            skipped += 1
            journal["entries"][ext_id] = {"status": "already-in-bundle"}
            continue
        atoms = entry.get("atoms") if isinstance(entry.get("atoms"), list) else []
        bundle["documents"].append({"document": entry["document"], "atoms": atoms})
        seen.add(ext_id)
        journal["entries"][ext_id] = {"status": "bundled", "atoms": len(atoms)}
        added += 1

    _write_json(bundle_path, bundle)
    _write_json(journal_path, journal)
    total_atoms = sum(
        len(d["atoms"]) for d in bundle["documents"]
        if isinstance(d, dict) and isinstance(d.get("atoms"), list)
    )
    _print_json({
        "bundle": bundle_path,
        "documents": len(bundle["documents"]),
        "atoms": total_atoms,
        "addedThisRun": added,
        "skippedAlreadyPresent": skipped,
    })
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
    inv.add_argument("--output-dir", help="folder for inventory.json (resolved from CWD — use an absolute path so it matches `bundle`); excluded from the walk")
    inv.add_argument("--head-lines", type=int, default=20, help="lines of head peek per file (default 20)")
    inv.add_argument("--bucket", choices=["quarter", "month", "year"], help="also roll up per time bucket (the temporal-economy cost table)")
    inv.add_argument("--include-noise", action="store_true", help="do NOT skip .git/node_modules/caches (off by default)")
    inv.set_defaults(func=cmd_inventory)

    val = sub.add_parser("validate", help="check one document's atoms JSON (types + verbatim spans)")
    val.add_argument("atoms", help="atoms JSON file: [ ... ] or { atoms: [ ... ] }")
    val.add_argument("--text", required=True, help="the document text the spans must match verbatim")
    val.add_argument("--types", help="comma-separated allowed node types (from the fetched schema)")
    val.set_defaults(func=cmd_validate)

    bun = sub.add_parser("bundle", help="assemble/append entries into import-bundle.json")
    bun.add_argument("--output-dir", required=True, help="folder holding import-bundle.json + worklist.json")
    bun.add_argument("entries", nargs="+", help="entry JSON files: { document: {...}, atoms: [...] }")
    bun.set_defaults(func=cmd_bundle)
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
