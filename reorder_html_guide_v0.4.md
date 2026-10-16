# reorder_html_v0.4.py — User Guide

Reorder the motif rows of a HOMER `knownResults.html` table by a chosen ranking method,
an explicit row order, or by **motif group**, optionally filter by q-value, and optionally
export a **table-only PDF figure** with **vector Arial Bold motif logos**, custom column
names, an optional **Rank** column, a **motif similarity heatmap** (PNG), and a
**gene / ENSEMBL-id table** (tab-separated text).

## Requirements

- Python 3 (standard library only) for the HTML output and the gene table.
- PDF export (`--pdf`) additionally needs **PyMuPDF** (`pip install pymupdf`) and an Arial
  font, auto-detected from the usual system locations.
- The heatmap (`--heatmap`) additionally needs **numpy** and **matplotlib**
  (`pip install numpy matplotlib`).

## Usage

```bash
python reorder_html_v0.4.py --filename <input.html> [--reorder {pctarget|difference|ratio|<positions>}] \
    [--reordergroups {pctarget|difference|ratio}] [--q <threshold>] \
    [--pdf [--showrank] [--shortname] [--fontsize <pt>] [--rowheight <pt>] [--width <in>] \
     [--height <in>] [--colwidth <w1,...,w6>] [--colnames <n1,...,n6>] [--pdfout <file>]] \
    [--heatmap <file> --knownresults_txt <file>] [--heatmapscale <min,max>] \
    [--genes --genes_id_map <file> [--genesoutfile <file>]]
```

## Arguments

| Argument | Required | Description |
| --- | --- | --- |
| `--filename` | Yes | Path to the input `.html` file (the HOMER known-results table). |
| `--reorder` | No | Ranking method — `pctarget`, `difference` or `ratio` — **or** a comma-separated list of 1-based row positions (e.g. `5,4,3,2,1`) for an explicit order. See below. When omitted (and no `--reordergroups`), rows keep their input order. |
| `--reordergroups` | No | Reorder rows by **motif group** derived from the shortname; groups are sorted by the descending maximum of this method. See below. |
| `--q` | No | Numeric threshold for the _q-value (Benjamini)_ column. Any row whose q-value is **greater than or equal to** this value is removed. When used, `_q<value>` is appended to the output filename. **Cannot be combined with a custom position list.** |
| `--pdf` | No | Also create a **table-only PDF figure** of the reordered (and optionally filtered) rows. |
| `--showrank` | No | PDF only. Prepend a narrow **Rank** column (see below). |
| `--shortname` | No | PDF only. Show the Name only up to the first `/` and **narrow the Name column** to fit the shortened labels, reducing the overall figure width. |
| `--nolines` | No | PDF only. Omit the table **grid lines**. |
| `--linescolor` | No | PDF only. Hex colour for the grid lines (default `#999999`, e.g. `#CCCCCC` pale grey). |
| `--colorgroups` | No | PDF only. Fill the motif **Name cells** with the group colour **under the text**. |
| `--colorgroup_palette` | No | PDF only. Comma-separated hex colours assigned to groups **sequentially by first appearance** and **recycled** if more groups than colours. Default: `#FFCC99,#99FFCC,#66CCFF,#FFFF99,#FF9933,#33FF99,#3399CC,#CCCC00,#FFCCFF,#99CC00,#CCCCCC,#9966CC`. Requires `--colorgroups`. |
| `--fontsize` | No | PDF only. Font size in pt (default `8`). |
| `--rowheight` | No | PDF only. Row height in pt (default `18`; derived from `--height` when given). |
| `--width` | No | PDF only. Page width in inches (default `8.5`; further reduced by `--shortname`). |
| `--height` | No | PDF only. Page height in inches (default: auto, sized to fit the rows). |
| `--colwidth` | No | PDF only. Six comma-separated integers (relative weights) for columns 1–6; `0` keeps that column's default (see below). Not counting the optional Rank column. |
| `--colnames` | No | PDF only. Six comma-separated custom column names (default `Motif,Name,p,FDR,% targets,% bkg`). The optional Rank header is always `Rank`. |
| `--pdfout` | No | PDF only. Output PDF path; without a directory it is placed next to the input file. |
| `--heatmap` | No | Output **PNG heatmap** filename: pairwise consensus-sequence similarity of the table motifs, rows/columns ordered by k-means clustering. The `.png` extension is enforced; without a directory it is placed next to the input file. See below. |
| `--knownresults_txt` | No | Path to `knownResults.txt` (tab-separated; **consensus in column 2**). Required with `--heatmap`; a bare name is resolved next to the input HTML. |
| `--heatmapscale` | No | Heatmap **colour-scale range**: two comma-separated integers (percent, default `0,100`). Similarities below the minimum or above the maximum clip to the scale ends. Requires `--heatmap`. |
| `--genes` | No | Write a **three-column tab-separated table** mapping each motif of the output table to the gene name(s) embedded in its name and their **human ENSEMBL gene ids**. See below. |
| `--genesoutfile` | No | Output path for `--genes` (default `genes.txt`); a bare name is resolved next to the input HTML. Requires `--genes`. |
| `--genes_id_map` | No | Two-column tab-separated **gene → ENSEMBL-id map** (col 1 gene name, col 2 human `ENSG…` id; one line per id). Required with `--genes`; a bare name is resolved next to the input HTML. |

## Ranking methods

| Value | Sort key (descending) | Resulting file |
| --- | --- | --- |
| `pctarget` | _% of Targets Sequences with Motif_ | `<name>_pctarget.html` |
| `difference` | _% of Targets Sequences with Motif_ − _% of Background Sequences with Motif_ | `<name>_difference.html` |
| `ratio` | _% of Targets Sequences with Motif_ ÷ _% of Background Sequences with Motif_ | `<name>_ratio.html` |

For `ratio`, a row with `% background = 0` and `% targets > 0` is treated as **infinity** and
ranked first; a row with both values `0` is treated as `0`.

## Custom row order (positions)

Instead of a named method, `--reorder` accepts a comma-separated list of **1-based row
positions** in the input table (the original Rank order). The rows are emitted in that
order and the Rank column is renumbered `1..N`.

- Example: `--reorder 5,4,3,2,1` reverses a 5-row table.
- A **subset** is allowed: `--reorder 3,1` emits only rows 3 and 1 (Rank `1`, `2`).
- Positions must be unique and within `1..N`; duplicates or out-of-range values are errors.
- The output filename uses the suffix `_order`.
- `--q` cannot be combined with a custom list, and a custom list cannot be combined with
  `--reordergroups`.

## Grouped ordering (`--reordergroups`)

`--reordergroups` takes `pctarget`, `difference` or `ratio` and reorders the rows so that all
members of a group are contiguous.

- **Group membership:** the motif's **shortname** (the part of the name before the first `/`)
  is scanned for a parenthetical; the text inside the first `(...)` is the group. A name with
  no parentheses belongs to the empty group `""`. This uses the shortname even when the full
  name is displayed.
- **Group order:** non-empty groups are ordered by the **descending maximum** of the chosen
  method among their members; equal maxima are ordered **alphabetically** by group name.
- **Rows without a group (`""`)** are placed **last**, sorted by the chosen method.
- **Within each group** rows are sorted by the chosen method (descending).
- **`--reorder` + `--reordergroups`:** both may be given. `--reordergroups` sets the row
  order; a named `--reorder` then only supplies the `--showrank` numbers (see below). A
  position-list `--reorder` cannot be combined with `--reordergroups`.
- The output filename uses the suffix `_group_<method>` (e.g. `knownResults_group_ratio.html`).

## Rank column (`--showrank`)

`--showrank` (PDF only) prepends a fixed narrow **Rank** column. The number shown for each
motif is the row's rank under the first applicable source:

1. `--reorder` (named method) — rank by that method across all displayed rows.
2. a position-list `--reorder` — the position in the list.
3. `--reordergroups` — rank by that method across all displayed rows (the grouping is not
   reflected in the numbers, so the column is generally not monotonic).
4. otherwise — rank by **increasing q-value (FDR)**.

Ranks are unique `1..N`; ties are broken by the original input order. The Rank column has a
fixed width and is **not** controlled by `--colwidth` or `--colnames`.

## Custom column names (`--colnames`)

`--colnames` replaces the six data-column headers **in the PDF figure only**; the HTML table
header is left unchanged. Provide exactly six comma-separated names.

```bash
--colnames "Motif,Name,p-value,FDR,% WT,% bkg"
```

Names are used for the header row and (with `--shortname`) when sizing the Name column.

## Column widths (`--colwidth`)

The six integers are **relative weights** for the six data columns (Motif, Name, p, FDR,
% targets, % bkg). The available width is split in proportion to the weights; a value of `0`
means "use this column's default". The optional Rank column is separate.

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
Name column is instead sized to fit the shortened labels; the other columns keep their
absolute widths and the page becomes narrower. Setting an explicit Name weight (a non-zero
second value) disables that automatic shrink.

## The PDF figure

- Columns: **Motif** (logo), **Name**, **p**, **FDR**, **% targets**, **% bkg** (renamable with `--colnames`), plus an optional leading **Rank** column.
- Arial regular/bold, a bold header row, and a light grid. Grid lines default to
  `#999999`; use `--linescolor` (e.g. `#CCCCCC`) to change the colour or `--nolines` to
  drop the grid entirely.
- Group colours (`--colorgroups`) fill each motif **Name cell** behind the text. Colours
  come from `--colorgroup_palette`, assigned to groups in order of **first appearance** in
  the table (with `--reordergroups` that is the grouped order: best group first) and
  recycled once the palette is exhausted. Rows whose name has no parenthetical group are
  left uncoloured.
- **Vector Arial Bold logos:** each motif logo is drawn as resolution-independent Arial Bold
  glyphs, so it stays crisp at any zoom and does not depend on a bitmap resolution.
- The `%` sign is stripped from the two percentage columns.
- Long names are truncated with an ellipsis (`…`) to fit the column; use `--shortname` for
  compact labels.
- Page width is `--width`; height is automatic unless `--height` is given. If a fixed height
  is too small, the script stops with a clear message.

## Motif similarity heatmap (`--heatmap`)

`--heatmap <file>` (independent of `--pdf`) computes a **pairwise sequence-similarity
matrix** for the motifs in the current output table (so `--q` filtering is respected) and
saves it as a cluster-ordered **PNG heatmap**.

- **Consensus sequences** come from `--knownresults_txt` (typically `knownResults.txt`,
  no default): a tab-separated file whose **column 2** holds each motif's IUPAC consensus.
  Motifs are matched by their **full motif name** (column 1 of the txt, the Name column of
  the table); a table motif missing from the txt is an error.
- **Similarity metric:** Needleman-Wunsch **global alignment** (consensuses differ in
  length). A match scores the overlap of the IUPAC nucleotide sets (`R` ~ `A,G`; `N` ~
  any base), a mismatch scores by set disjointness, gaps are penalised; the raw alignment
  score is normalised to **0–100 %** (identical sequences = 100 %).
- **Clustering:** the rows of the similarity matrix (each motif's similarity profile) are
  clustered with **k-means** (deterministic, fixed seed). The number of clusters is chosen
  automatically as `round(sqrt(n/2))` clamped to `[2, n]` (e.g. **4** for 39 motifs) and
  is printed with the cluster sizes when the PNG is written.
- **Heatmap order:** clusters are drawn tightest-first (descending mean intra-cluster
  similarity); within a cluster motifs keep the table display order. Rows and columns use
  the **same order** (the matrix is symmetric), giving a block-diagonal structure with
  white separator lines between clusters.
- **Colour scale:** `--heatmapscale <min,max>` spreads the colours over that percentage
  range (default `0,100`); similarities below the minimum or above the maximum clip to
  the scale ends. Useful to zoom into a low-similarity range (e.g. `--heatmapscale 0,30`).
- **Labels** are the motif shortnames (up to the first `/`); duplicates are disambiguated
  with `#2`, `#3`, …
- The PNG filename extension is forced to `.png`; a bare filename is written next to the
  input HTML.

## Gene table (`--genes`)

`--genes` (independent of `--pdf` and `--heatmap`) exports a **tab-separated text table**
(three columns, no header) covering the rows of the current output table (so `--q` and the
reordering are respected):

`<original motif name>  <gene name>  <human ENSEMBL gene id>`

- **Gene names** are read from each motif name, whose first segment has the form
  `GeneName(Family)`. The family is stripped and the remaining text is split on `,` and
  `:` into gene tokens, so `Bcl11a(Zf)/…` → `Bcl11a`, `LXRE(NR),DR4/…` → `LXRE` + `DR4`,
  `FOXA1:AR(Forkhead,NR)/…` → `FOXA1` + `AR`, and `ZNF652` stays `ZNF652`.
- **ENSEMBL ids** come from `--genes_id_map <file>`, a two-column tab-separated map
  (col 1 gene name, col 2 human ENSEMBL id). An Ensembl **BioMart** export with the
  attributes „Gene name“ and „Gene stable ID“ works directly. The lookup is
  **case-insensitive**, so `Bcl11a` matches a map row `BCL11A`.
- A gene with **several ENSEMBL ids** produces **one row per id**;
  a gene token **without** any id still appears, with an **empty** third column
  (e.g. `LXRE`, `HRE` — motif-name tokens that are not human gene symbols).
- Map lines whose second column is not an `ENSG…` id are ignored (this also drops the
  BioMart header line). A missing file or a file with no valid rows is an error.
- The output is `--genesoutfile <file>` (default `genes.txt`); a bare filename is written
  next to the input HTML, and its absolute path is printed.

```bash
# Genes + ENSEMBL ids for every motif of the sorted table -> genes.txt
python reorder_html_v0.4.py --filename knownResults.html --reorder difference \
    --genes --genes_id_map human_gene_ids.tsv

# Custom output path
python reorder_html_v0.4.py --filename knownResults.html --reorder difference \
    --genes --genes_id_map human_gene_ids.tsv --genesoutfile motif_genes.tsv
```

## Output filenames

The HTML suffix is inserted before the extension: `<name>_<method>[_q<value>].html`. The PDF,
when `--pdfout` is omitted, uses the same base and suffix with a `.pdf` extension.

| Command options | Output |
| --- | --- |
| `--reorder pctarget` | `knownResults_pctarget.html` |
| `--reorder pctarget --q 0.05` | `knownResults_pctarget_q0.05.html` |
| `--reorder ratio` | `knownResults_ratio.html` |
| `--reorder 5,4,3,2,1` | `knownResults_order.html` |
| `--reordergroups ratio` | `knownResults_group_ratio.html` |
| _(no `--reorder`/`--reordergroups`)_ | `knownResults_fdr.html` |
| `--reorder difference --q 0.05 --pdf --shortname` | `knownResults_difference_q0.05.html` and `knownResults_difference_q0.05.pdf` |

## What it does

- Reads the table and reorders the motif rows in **descending** order by the selected key,
  in the explicit order given by a position list, or into contiguous groups.
- The **Rank** column is **renumbered 1..N** to match the new display order.
- Everything else (header, footer, links, SVG logos, other columns) is preserved byte-for-byte in the HTML.
- Ties keep their original relative order (stable sort).
- With `--q`, rows with q-value `>=` the threshold are dropped before ordering, so Rank
  continues to run `1..N` over the kept rows.
- The output is written next to the input file. The input file is not modified.

## Examples

```bash
# Rank by % of target sequences
python reorder_html_v0.4.py --filename knownResults.html --reorder pctarget

# Rank by the target/background percentage ratio
python reorder_html_v0.4.py --filename knownResults.html --reorder ratio

# Explicit order: first five rows reversed
python reorder_html_v0.4.py --filename knownResults.html --reorder 5,4,3,2,1

# Group rows by motif family (group order by best ratio)
python reorder_html_v0.4.py --filename knownResults.html --reordergroups ratio
# -> writes knownResults_group_ratio.html

# Group rows by difference, but show each motif's global ratio rank in the PDF
python reorder_html_v0.4.py --filename knownResults.html --reorder ratio --reordergroups difference \
    --pdf --showrank

# Drop rows with q-value >= 0.05, then rank by (target % - background %)
python reorder_html_v0.4.py --filename knownResults.html --reorder difference --q 0.05

# Compact figure with a Rank column and custom headers
python reorder_html_v0.4.py --filename knownResults.html --reorder ratio --pdf \
    --showrank --shortname --colnames "Motif,Name,p-value,FDR,% WT,% bkg" --colwidth 30,30,10,10,10,10

# Grid-free figure: drop the grid entirely
python reorder_html_v0.4.py --filename knownResults.html --reorder ratio --pdf --nolines

# Figure with pale-grey grid lines
python reorder_html_v0.4.py --filename knownResults.html --reorder ratio --pdf --linescolor "#CCCCCC"

# Grouped rows with colour-coded Name cells
python reorder_html_v0.4.py --filename knownResults.html --reordergroups difference --colorgroups --pdf

# Colour-coded cells with a custom palette (red/blue, recycled)
python reorder_html_v0.4.py --filename knownResults.html --reorder ratio --colorgroups \
    --colorgroup_palette "#FF0000,#0000FF" --pdf

# Similarity heatmap of the q <= 0.05 motifs
python reorder_html_v0.4.py --filename knownResults.html --reorder difference --q 0.05 \
    --heatmap heatmap --knownresults_txt knownResults.txt
# -> writes heatmap.png next to the input file

# Same heatmap with the colour scale zoomed to 0-30 %
python reorder_html_v0.4.py --filename knownResults.html --reorder difference --q 0.05 \
    --heatmap heatmap --knownresults_txt knownResults.txt --heatmapscale 0,30

# Grouped table, colour-coded PDF and heatmap in one run
python reorder_html_v0.4.py --filename knownResults.html --reordergroups ratio \
    --pdf --colorgroups --heatmap heatmap.png --knownresults_txt knownResults.txt

# Motif -> gene -> human ENSEMBL id table (genes.txt next to the input)
python reorder_html_v0.4.py --filename knownResults.html --reorder difference --q 0.05 \
    --genes --genes_id_map human_gene_ids.tsv
```

## Notes

- The suffix is inserted before the extension, so `knownResults.html` becomes `knownResults_pctarget.html`.
- The exact `--q` text you type is used in the filename (e.g. `--q 0.050` gives `_q0.050`),
  while filtering uses its numeric value.
- `--q` is rejected with a custom position list; use `--q` only with the named methods.
- `--showrank`, `--shortname`, `--nolines`, `--fontsize`, `--rowheight`, `--width`,
  `--height`, `--colwidth`, `--colnames`, `--linescolor`, `--colorgroups`,
  `--colorgroup_palette` and `--pdfout` require `--pdf`; otherwise the script exits with an error.
- `--colorgroup_palette` is only meaningful together with `--colorgroups`; giving it alone
  is an error.
- `--heatmap` and `--knownresults_txt` require each other; giving either one alone is an
  error. `--heatmapscale` requires `--heatmap`. `--heatmap` is independent of `--pdf`
  (no `--pdf` needed for the PNG) and needs numpy + matplotlib.
- `--genesoutfile` and `--genes_id_map` require `--genes`, and `--genes` requires
  `--genes_id_map`; giving `--genesoutfile` alone is an error. `--genes` is independent of
  `--pdf` and `--heatmap` (standard library only) and writes a three-column
  tab-separated file with no header.
- `--colwidth` must contain exactly six non-negative integers separated by commas.
- `--colnames` must contain exactly six non-empty names separated by commas.
- If PyMuPDF or an Arial font is unavailable, the HTML output is still written and the
  script reports an error for the PDF step.

See `history_v0.4.html` for the version history.
