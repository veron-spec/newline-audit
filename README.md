# Newline Audit

A small, read-only command-line tool for the invisible formatting bugs that travel between Windows and Linux. Find mixed line endings, enforce a newline convention, and check for missing final newlines.

Python 3.10+. Standard library only. Independently written implementation. MIT licensed.

## Run it

Download or clone this repository, then pass the files you want to inspect:

```sh
python newline_audit.py README.md newline_audit.py
python newline_audit.py app.py config.json --expect lf --require-final-newline
python newline_audit.py notes.txt --json
```

On macOS/Linux, use `python3` if necessary. Quote paths that contain spaces. Pass explicit files; directories and literal wildcard patterns are not expanded by the tool.

Example output for a file containing `first\r\nsecond\n`:

```text
FAIL 'notes.txt': MIXED | LF=1 CRLF=1 CR=0 | BOM=no | final=yes
     mixed line endings
```

The input files are never rewritten. The program prints paths, counts, and diagnostics; it does not print file contents or make network requests.

## Options

| Option | Behavior |
| --- | --- |
| `--expect lf` | Reject CRLF and lone CR. Also accepts `crlf` or `cr`. |
| `--require-final-newline` | Require a terminating newline in nonempty text. |
| `--json` | Print a JSON array with one result per supplied path. |

Without options, a file fails only when it mixes newline styles. A consistent CR-only file passes unless you request another style. Files without any newline satisfy `--expect`; use `--require-final-newline` to reject a nonempty single line without its terminator. Empty and UTF-8 BOM-only files pass both checks and report `final_newline: null`.

Exit codes: `0` all files pass, `1` policy violations, `2` unreadable or unsupported input / invalid command, `130` cancelled. An input error takes precedence over policy violations, regardless of file order. Unsupported input is never reported as a clean pass.

## What the labels mean

- **LF**: byte `0A`, commonly used on Linux and macOS.
- **CRLF**: byte pair `0D 0A`, commonly used on Windows.
- **CR**: lone byte `0D`, used by some older text formats.
- **BOM**: an optional UTF-8 byte-order marker at the beginning of a file.

A CRLF pair counts once, including when its bytes fall into separate read chunks. Unicode line separators such as U+2028 are not counted as LF/CRLF/CR.

## JSON output

Successful reads include `path`, `bytes`, `utf8_bom`, `lf`, `crlf`, `cr`, `style`, `final_newline`, `issues`, and `status`. The style is `lf`, `crlf`, `cr`, `mixed`, or `none`; the status is `ok` or `fail`. Unreadable or unsupported files return only `path`, `status: "error"`, and `error`.

## CI example

After checking out your repository and installing Python:

```yaml
- name: Check newline conventions
  run: python newline_audit.py app.py config.json --expect lf --require-final-newline
```

The audit checks bytes present in the working tree. Git's `core.autocrlf` and `.gitattributes` can convert newlines during checkout; set your repository's policy accordingly.

## Boundaries

Inputs must be valid UTF-8, optionally with a UTF-8 BOM. Invalid UTF-8 and NUL bytes produce errors; UTF-16/32 is unsupported. NUL-free binary data that happens to be valid UTF-8 cannot be reliably distinguished from text. Explicitly supplied symbolic links are followed. Supply trusted, regular files: device files and named pipes can block, and concurrently edited files are not a consistent snapshot.

Files are read in 64 KiB chunks with constant auxiliary memory per file. The JSON result list uses memory proportional to the number of supplied files. Output contains filenames and paths, which should be reviewed before sharing logs.

## Tests

```sh
python -m unittest -v
```

Tests enumerate short CR/LF combinations across chunk boundaries, cover multibyte UTF-8 and BOM splits, validate exit-code precedence, and check that input bytes are preserved. CI runs on Windows/Linux with Python 3.10 and 3.14.
