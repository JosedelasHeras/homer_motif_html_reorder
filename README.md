# reorder_html — User Guide

Reorder the motif rows of a HOMER `knownResults.html` table by a chosen ranking method,
optionally filter rows by q-value, and optionally export a PDF.

Two equivalent implementations are provided:

- `reorder_html.py` — Python 3 (standard library only)
- `reorder_html.sh` — Bash (coreutils; uses a headless browser only for `--pdf`)

Both produce **byte-identical** HTML output.

## Requirements

- **Python script:** Python 3 (standard library only). Run from any directory.
- **Bash script:** `bash`, plus `sort`, `awk`, `cut`, `mktemp`.
- **PDF export (`--pdf`, both scripts):** a Chromium-based browser — Microsoft Edge,
  Google Chrome, or Chromium. For the Bash script running under WSL/Git Bash, a
  Windows-hosted browser is auto-detected and paths are converted with
  `wslpath`/`cygpath`.

## Usage

Python:

```bash
python reorder_html.py --filename <input.html> --reorder {pctarget|difference} [--q <threshold>] [--pdf]
```

Bash:

```bash
./reorder_html.sh --filename <input.html> --reorder {pctarget|difference} [--q <threshold>] [--pdf]
```

## Arguments

| Argument | Required | Description |
| --- | --- | --- |
| `--filename` | Yes | Path to the input `.html` file (the HOMER known-results table). |
| `--reorder` | Yes | Ranking method. One of `pctarget` or `difference` (see below). |
| `--q` | No | Numeric threshold for the _q-value (Benjamini)_ column. Any row whose q-value is **greater than or equal to** this value is removed. When used, `_q<value>` is appended to the output filename. |
| `--pdf` | No | Also create a PDF version of the resulting HTML (same base name, `.pdf` extension). |

## Ranking methods

| Value | Sort key (descending) | Resulting file |
| --- | --- | --- |
| `pctarget` | Column _% of Targets Sequences with Motif_ | `<name>_pctarget.html` |
| `difference` | _% of Targets Sequences with Motif_ − _% of Background Sequences with Motif_ | `<name>_difference.html` |

## Output filenames

The suffix is inserted before the extension: `<name>_<method>[_q<value>].html`.

| Command options | Output |
| --- | --- |
| `--reorder pctarget` | `knownResults_pctarget.html` |
| `--reorder pctarget --q 0.05` | `knownResults_pctarget_q0.05.html` |
| `--reorder difference --q 0.05 --pdf` | `knownResults_difference_q0.05.html` and `knownResults_difference_q0.05.pdf` |

## What it does

- Reads the table and reorders the motif rows in **descending** order by the selected key.
- The **Rank** column is **renumbered 1..N** to match the new display order.
- Everything else (header, footer, links, SVG logos, other columns) is preserved byte-for-byte.
- Ties keep their original relative order (stable sort).
- With `--q`, rows with q-value `>=` the threshold are dropped before sorting, so Rank
  continues to run `1..N` over the kept rows.
- With `--pdf`, the resulting HTML is rendered to PDF using a headless Chromium-based browser.
- The output is written next to the input file. The input file is not modified.

## Examples

```bash
# Rank by % of target sequences
python reorder_html.py --filename knownResults.html --reorder pctarget
# -> writes knownResults_pctarget.html

# Rank by (target % - background %)
python reorder_html.py --filename knownResults.html --reorder difference
# -> writes knownResults_difference.html

# Drop rows with q-value >= 0.05, then rank by target %
python reorder_html.py --filename knownResults.html --reorder pctarget --q 0.05
# -> writes knownResults_pctarget_q0.05.html

# Also export a PDF of the filtered, reordered table
python reorder_html.py --filename knownResults.html --reorder difference --q 0.05 --pdf
# -> writes knownResults_difference_q0.05.html and knownResults_difference_q0.05.pdf
```

## Notes

- The suffix is inserted before the extension, so `knownResults.html` becomes
  `knownResults_pctarget.html`.
- The exact `--q` text you type is used in the filename (e.g. `--q 0.050` gives `_q0.050`),
  while filtering uses its numeric value.
- PDF export requires Edge/Chrome/Chromium; if none is found the HTML is still written and
  the script reports an error.
