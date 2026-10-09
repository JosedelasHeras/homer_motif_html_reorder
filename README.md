# reorder_html — User Guide

Reorder the motif rows of a HOMER `knownResults.html` table by a chosen ranking method,
optionally filter rows by q-value, and optionally export a PDF.

Four implementations are provided:

- `reorder_html.py` — Python 3 (standard library only)
- `reorder_html.sh` — Bash (coreutils; uses a headless browser only for `--pdf`)
- `reorder_html_v0.1.py` — Python 3; adds a self-contained, table-only **PDF figure**
  (PyMuPDF, no browser) plus `--shortname` and PDF layout options.
- `reorder_html_v0.2.py` — Python 3; v0.1 plus **vector Arial Bold logos**,
  `--colwidth`, and a `--shortname` layout that narrows the figure. Drops `--res`.

All four produce **byte-identical** HTML output.

## Requirements

- **Python scripts:** Python 3 (standard library only) for the HTML output. Run from
  any directory.
- **Bash script:** `bash`, plus `sort`, `awk`, `cut`, `mktemp`.
- **PDF export (`--pdf`):**
  - `reorder_html.py` / `reorder_html.sh` render the whole HTML page with a
    Chromium-based browser — Microsoft Edge, Google Chrome, or Chromium. For the Bash
    script running under WSL/Git Bash, a Windows-hosted browser is auto-detected and
    paths are converted with `wslpath`/`cygpath`.
  - `reorder_html_v0.1.py` / `reorder_html_v0.2.py` build a table-only figure directly
    with **PyMuPDF** (`pip install pymupdf`) and an auto-detected **Arial** font; no
    browser is needed.

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

## The v0.1 PDF figure (`reorder_html_v0.1.py`)

Unlike the original `--pdf` (which prints the whole HTML page via a headless browser),
`reorder_html_v0.1.py --pdf` writes a clean, single-page **table figure** — columns
Motif (logo), Name, p, FDR, % targets, % bkg — in Arial, with a bold header and a light
grid. The `%` sign is stripped from the two percentage columns, long names are truncated
with an ellipsis (`…`), and motif logos are rasterized from the table's inline SVG.

| Argument | Required | Description |
| --- | --- | --- |
| `--shortname` | No | PDF only. Show the Name only up to the first `/` (e.g. `Bcl11a(Zf)/HSPC-…/Homer` → `Bcl11a(Zf)`). |
| `--fontsize` | No | PDF only. Font size in pt (default `8`). |
| `--rowheight` | No | PDF only. Row height in pt (default `18`; derived from `--height` when given). |
| `--width` | No | PDF only. Page width in inches (default `8.5`). |
| `--height` | No | PDF only. Page height in inches (default: auto, sized to fit the rows). |
| `--res` | No | PDF only. Logo rasterization resolution in dpi (default `300`). |
| `--pdfout` | No | PDF only. Output PDF path; without a directory it is placed next to the input file. |

These PDF-only options require `--pdf`; otherwise the script exits with an error. When
`--pdfout` is omitted the PDF uses the same base and suffix as the HTML with a `.pdf`
extension (e.g. `--reorder pctarget --pdf` → `knownResults_pctarget.pdf`).

## The v0.2 PDF figure (`reorder_html_v0.2.py`)

Like v0.1, `--pdf` writes a single-page table figure (Motif, Name, p, FDR, % targets,
% bkg). v0.2 changes:

- **Vector Arial Bold logos.** Each motif logo is drawn as resolution-independent
  Arial Bold glyphs (MuPDF's SVG renderer ignores the logo's specified font, so the
  glyphs are drawn directly instead) — no bitmap resolution needed. `--res` is removed.
- **`--colwidth`.** Six comma-separated integers (relative weights) for columns 1–6;
  `0` keeps that column's default. Defaults: `22,40,9,9,10,10` (Motif, Name, p, FDR,
  % targets, % bkg). The available width is split in proportion to the weights.
- **`--shortname` narrows the figure.** Besides shortening the labels (up to the first
  `/`), the Name column is sized to its content and the page is narrowed accordingly;
  the other five columns keep their absolute widths. Set an explicit Name weight (a
  non-zero second `--colwidth` value) to disable the automatic shrink.

| Argument | Required | Description |
| --- | --- | --- |
| `--shortname` | No | PDF only. Show the Name up to the first `/` and narrow the Name column/figure. |
| `--fontsize` | No | PDF only. Font size in pt (default `8`). |
| `--rowheight` | No | PDF only. Row height in pt (default `18`; derived from `--height` when given). |
| `--width` | No | PDF only. Page width in inches (default `8.5`). |
| `--height` | No | PDF only. Page height in inches (default: auto, sized to fit the rows). |
| `--colwidth` | No | PDF only. Six comma-separated integers (relative weights) for columns 1–6; `0` = default. |
| `--pdfout` | No | PDF only. Output PDF path; without a directory it is placed next to the input file. |

The PDF-only options require `--pdf`. `--colwidth` must contain exactly six non-negative
integers.

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

# v0.1: export a short-label table figure with a wide page
python reorder_html_v0.1.py --filename knownResults.html --reorder pctarget --pdf --shortname --width 11

# v0.1: fully custom figure (large fonts, fixed height, high-res logos)
python reorder_html_v0.1.py --filename knownResults.html --reorder pctarget --pdf \
    --fontsize 10 --rowheight 22 --width 11 --height 13 --res 600 --pdfout figure.pdf

# v0.2: compact short-label figure with a wider Motif/Name area
python reorder_html_v0.2.py --filename knownResults.html --reorder pctarget --pdf --shortname --colwidth 30,30,10,10,10,10

# v0.2: fully custom figure (vector Arial Bold logos, large fonts, fixed height)
python reorder_html_v0.2.py --filename knownResults.html --reorder pctarget --pdf \
    --fontsize 10 --rowheight 22 --width 11 --height 13 --pdfout figure.pdf
```

## Notes

- The suffix is inserted before the extension, so `knownResults.html` becomes
  `knownResults_pctarget.html`.
- The exact `--q` text you type is used in the filename (e.g. `--q 0.050` gives `_q0.050`),
  while filtering uses its numeric value.
- PDF export requires Edge/Chrome/Chromium; if none is found the HTML is still written and
  the script reports an error.
- `reorder_html_v0.1.py` / `reorder_html_v0.2.py --pdf` require PyMuPDF and an Arial
  font; if either is missing the HTML is still written and the script reports an error
  for the PDF step.
- `reorder_html_v0.2.py` removed `--res` (logos are vector); passing it is an error.
