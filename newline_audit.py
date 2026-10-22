#!/usr/bin/env python3
"""Audit UTF-8 file line endings without changing any files."""

import argparse
import codecs
import json
from pathlib import Path
import sys


def inspect_stream(stream, chunk_size=65536):
    """Count byte-level newline sequences, including pairs split across chunks."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    counts = {"lf": 0, "crlf": 0, "cr": 0}
    pending = b""
    prefix = b""
    size = 0
    last = b""
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        decoder.decode(chunk)
        if b"\x00" in chunk:
            raise ValueError("NUL bytes found; binary or UTF-16/32 input is unsupported")
        size += len(chunk)
        prefix = (prefix + chunk)[:3]
        last = chunk[-1:]
        data = pending + chunk
        pending = b"\r" if data.endswith(b"\r") else b""
        if pending:
            data = data[:-1]
        pairs = data.count(b"\r\n")
        counts["crlf"] += pairs
        counts["lf"] += data.count(b"\n") - pairs
        counts["cr"] += data.count(b"\r") - pairs
    decoder.decode(b"", final=True)
    counts["cr"] += bool(pending)
    bom = prefix == codecs.BOM_UTF8
    content_size = size - (3 if bom else 0)
    styles = [style for style, count in counts.items() if count]
    return {
        "bytes": size,
        "utf8_bom": bom,
        **counts,
        "style": "mixed" if len(styles) > 1 else styles[0] if styles else "none",
        "final_newline": last in (b"\n", b"\r") if content_size else None,
    }


def violations(result, expected=None, require_final=False):
    problems = []
    if result["style"] == "mixed":
        problems.append("mixed line endings")
    if expected and any(result[style] for style in ("lf", "crlf", "cr") if style != expected):
        problems.append(f"expected {expected.upper()} line endings")
    if require_final and result["final_newline"] is False:
        problems.append("missing final newline")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path, help="Explicit file paths (no recursive directory scanning)")
    parser.add_argument("--expect", choices=("lf", "crlf", "cr"), help="Require this newline style when newlines exist")
    parser.add_argument("--require-final-newline", action="store_true", help="Require a final newline in nonempty text")
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable JSON array")
    args = parser.parse_args(argv)
    rows = []
    exit_code = 0
    try:
        for path in args.files:
            row = {"path": str(path)}
            try:
                with path.open("rb") as stream:
                    row.update(inspect_stream(stream))
                row["issues"] = violations(row, args.expect, args.require_final_newline)
                row["status"] = "fail" if row["issues"] else "ok"
                exit_code = max(exit_code, bool(row["issues"]))
            except (OSError, ValueError) as exc:
                # Never include decoded contents or UnicodeDecodeError excerpts.
                row.update(status="error", error="Input is not valid UTF-8" if isinstance(exc, UnicodeError)
                           else (exc.strerror or type(exc).__name__) if isinstance(exc, OSError) else str(exc))
                exit_code = 2
            rows.append(row)
        if args.json:
            print(json.dumps(rows, indent=2, ensure_ascii=True))
        else:
            for row in rows:
                if row["status"] == "error":
                    print(f"ERROR {row['path']!r}: {row['error']!r}")
                    continue
                ending = {True: "yes", False: "no", None: "n/a"}[row["final_newline"]]
                print(f"{row['status'].upper():4} {row['path']!r}: {row['style'].upper()} | "
                      f"LF={row['lf']} CRLF={row['crlf']} CR={row['cr']} | "
                      f"BOM={'yes' if row['utf8_bom'] else 'no'} | final={ending}")
                for issue in row["issues"]:
                    print(f"     {issue}")
        return int(exit_code)
    except KeyboardInterrupt:
        print("Audit cancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
