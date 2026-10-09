# reorder_html_v0.2.py — User Guide

Reorder the motif rows of a HOMER `knownResults.html` table by a chosen ranking method,
optionally filter by q-value, and optionally export a **table-only PDF figure** with
**vector Arial Bold motif logos**.

## Requirements

- Python 3 (standard library only) for the HTML output.
- PDF export (`--pdf`) additionally needs **PyMuPDF** (`pip install pymupdf`) and an Arial
  font, auto-detected from the usual system locations.

## Usage

```bash
python reorder_html_v0.2.py --filename <input.html> --reorder {pctarget|difference} [--q <threshold>] \
    [--pdf [--shortname] [--fontsize <pt>] [--rowheight <pt>] [--width <in>] [--height <in>] \
     [--colwidth <w1,...,w6>] [--pdfout <file>]]
```

## Arguments

| Argument | Required | Description |
| --- | --- | --- |
| `--filename` | Yes | Path to the input `.html` file (the HOMER known-results table). |
| `--reorder` | Yes | Ranking method. One of `pctarget` or `difference` (see below). |
| `--q` | No | Numeric threshold for the _q-value (Benjamini)_ column. Any row whose q-value is **greater than or equal to** this value is removed. When used, `_q<value>` is appended to the output filename. |
| `--pdf` | No | Also create a **table-only PDF figure** of the reordered (and optionally filtered) rows. |
| `--shortname` | No | PDF only. Show the Name only up to the first `/` and **narrow the Name column** to fit the shortened labels, reducing the overall figure width. |
| `--fontsize` | No | PDF only. Font size in pt (default `8`). |
| `--rowheight` | No | PDF only. Row height in pt (default `18`; derived from `--height` when given). |
| `--width` | No | PDF only. Page width in inches (default `8.5`; further reduced by `--shortname`). |
| `--height` | No | PDF only. Page height in inches (default: auto, sized to fit the rows). |
| `--colwidth` | No | PDF only. Six comma-separated integers (relative weights) for columns 1–6; `0` keeps that column's default (see below). |
| `--pdfout` | No | PDF only. Output PDF path; without a directory it is placed next to the input file. |

## Ranking methods

| Value | Sort key (descending) | Resulting file |
| --- | --- | --- |
| `pctarget` | _% of Targets Sequences with Motif_ | `<name>_pctarget.html` |
| `difference` | _% of Targets Sequences with Motif_ − _% of Background Sequences with Motif_ | `<name>_difference.html` |

## Column widths (`--colwidth`)

The six integers are **relative weights** for columns **1–6** (Motif, Name, p, FDR,
% targets, % bkg). The available table width is split in proportion to the weights; a value
of `0` means "use this column's default".

| Column | Default weight |
| --- | --- |
| 1 — Motif | 22 |
| 2 — Name | 40 |
| 3 — p | 9 |
| 4 — FDR | 9 |
| 5 — % targets | 10 |
| 6 — % bkg | 10 |

Examples (values are weights, not percentages):

- `--colwidth 0,0,0,0,0,0` — the defaults above.
- `--colwidth 30,30,10,10,10,10` — wider Motif and Name columns.
- `--colwidth 0,50,0,0,0,0` — only the Name column changes (weight 50).

When `--shortname` is used and the Name column is left at its default (weight `0`), the
Name column is instead sized to fit the shortened labels; the other five columns keep their
absolute widths and the page becomes narrower. Setting an explicit Name weight (a non-zero
second value) disables that automatic shrink.

## The PDF figure

- Columns: **Motif** (logo), **Name**, **p**, **FDR**, **% targets**, **% bkg**.
- Arial regular/bold, a bold header row, and a light grid.
- **Vector Arial Bold logos:** each motif logo is drawn as resolution-independent Arial Bold
  glyphs, so it stays crisp at any zoom and does not depend on a bitmap resolution.
- The `%` sign is stripped from the two percentage columns.
- Long names are truncated with an ellipsis (`…`) to fit the column; use `--shortname` for
  compact labels.
- Page width is `--width`; height is automatic unless `--height` is given. If a fixed height
  is too small, the script stops with a clear message.

## Output filenames

The HTML suffix is inserted before the extension: `<name>_<method>[_q<value>].html`. The PDF,
when `--pdfout` is omitted, uses the same base and suffix with a `.pdf` extension.

| Command options | Output |
| --- | --- |
| `--reorder pctarget` | `knownResults_pctarget.html` |
| `--reorder pctarget --q 0.05` | `knownResults_pctarget_q0.05.html` |
| `--reorder pctarget --pdf` | `knownResults_pctarget.html` and `knownResults_pctarget.pdf` |
| `--reorder difference --q 0.05 --pdf --shortname` | `knownResults_difference_q0.05.html` and `knownResults_difference_q0.05.pdf` |

## What it does

- Reads the table and reorders the motif rows in **descending** order by the selected key.
- The **Rank** column is **renumbered 1..N** to match the new display order.
- Everything else (header, footer, links, SVG logos, other columns) is preserved byte-for-byte in the HTML.
- Ties keep their original relative order (stable sort).
- With `--q`, rows with q-value `>=` the threshold are dropped before sorting, so Rank
  continues to run `1..N` over the kept rows.
- The output is written next to the input file. The input file is not modified.

## Examples

```bash
# Rank by % of target sequences
python reorder_html_v0.2.py --filename knownResults.html --reorder pctarget
# -> writes knownResults_pctarget.html

# Drop rows with q-value >= 0.05, then rank by (target % - background %)
python reorder_html_v0.2.py --filename knownResults.html --reorder difference --q 0.05
# -> writes knownResults_difference_q0.05.html

# Compact short-label figure with a wider Motif/Name area
python reorder_html_v0.2.py --filename knownResults.html --reorder pctarget --pdf --shortname --colwidth 30,30,10,10,10,10

# Fully custom figure (large fonts, fixed height)
python reorder_html_v0.2.py --filename knownResults.html --reorder pctarget --pdf \
    --fontsize 10 --rowheight 22 --width 11 --height 13 --pdfout figure.pdf
```

## Notes

- The suffix is inserted before the extension, so `knownResults.html` becomes `knownResults_pctarget.html`.
- The exact `--q` text you type is used in the filename (e.g. `--q 0.050` gives `_q0.050`),
  while filtering uses its numeric value.
- `--shortname`, `--fontsize`, `--rowheight`, `--width`, `--height`, `--colwidth` and
  `--pdfout` require `--pdf`; otherwise the script exits with an error.
- `--colwidth` must contain exactly six non-negative integers separated by commas.
- If PyMuPDF or an Arial font is unavailable, the HTML output is still written and the
  script reports an error for the PDF step.

See `history_v0.2.html` for the version history.
