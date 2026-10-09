# reorder_html — Version History

Concise record of what each version of the script added and removed.

| Version | Added | Removed |
| --- | --- | --- |
| **v0.2** (current) | Vector Arial Bold motif logos (resolution-independent).<br>`--colwidth w1..w6` — relative column weights (`0` = default).<br>`--shortname` now also narrows the Name column and the figure width. | `--res` (logos are vector now). |
| **v0.1** | Browser-free, table-only PDF figure via PyMuPDF (`--pdf`).<br>`--shortname` (labels cut at the first `/`).<br>PDF layout options: `--fontsize`, `--rowheight`, `--width`, `--height`, `--res`, `--pdfout`.<br>PDF-only options require `--pdf`. | — |
| **v0.0** (original) | Reorder `knownResults.html` rows by `pctarget` or `difference`.<br>`--q` threshold filter (rows with q-value `>=` the value are dropped).<br>`--pdf` exported the full reordered HTML page via a headless browser. | — |

## Unchanged throughout

- The **HTML** output is byte-identical across versions for the same inputs.
- **Rank** is renumbered `1..N`; ties keep their original order (stable sort).
- Output filenames follow `<name>_<method>[_q<value>].html`.

See `reorder_html_guide_v0.2.html` for the current user guide.
