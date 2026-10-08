#!/usr/bin/env bash
#
# reorder_html.sh - Reorder the motif rows of a HOMER knownResults.html table.
#
# Usage:
#   ./reorder_html.sh --filename <input.html> --reorder {pctarget|difference} \
#                     [--q <threshold>] [--pdf]
#
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: reorder_html.sh --filename <input.html> --reorder {pctarget|difference} [--q <threshold>] [--pdf]

  --filename  Input .html file (HOMER known-results table).
  --reorder   Ranking method:
                pctarget   -> sort by "% of Targets Sequences with Motif"
                difference -> sort by (target % - background %)
  --q         Delete rows whose "q-value (Benjamini)" is >= this threshold.
              When used, "_q<value>" is appended to the output filename.
  --pdf       Also create a PDF version of the resulting HTML.

Writes <name>_<method>[_q<value>].html next to the input and prints its path.
EOF
}

filename=""
reorder=""
q_threshold=""
want_pdf=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --filename)
      [[ $# -ge 2 ]] || { echo "Missing value for --filename" >&2; exit 2; }
      filename=$2; shift 2 ;;
    --reorder)
      [[ $# -ge 2 ]] || { echo "Missing value for --reorder" >&2; exit 2; }
      reorder=$2; shift 2 ;;
    --q)
      [[ $# -ge 2 ]] || { echo "Missing value for --q" >&2; exit 2; }
      q_threshold=$2; shift 2 ;;
    --pdf)
      want_pdf=1; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n $filename ]] || { echo "Error: --filename is required" >&2; usage >&2; exit 2; }
case "$reorder" in
  pctarget|difference) ;;
  "") echo "Error: --reorder is required" >&2; usage >&2; exit 2 ;;
  *)  echo "Error: --reorder must be 'pctarget' or 'difference'" >&2; exit 2 ;;
esac
if [[ -n $q_threshold ]] && \
   ! [[ $q_threshold =~ ^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?$ ]]; then
  echo "Error: --q must be a number, got: $q_threshold" >&2; exit 2
fi
[[ -f $filename ]] || { echo "Error: file not found: $filename" >&2; exit 1; }

# Read entire file verbatim, including trailing newlines.
IFS= read -r -d '' content < "$filename" || true

# Split into chunks on the row terminator "</TR>".
#   chunks[0]  = everything before the header's </TR> (prefix + header body)
#   chunks[1]  = first motif row body (with a leading newline separator)
#   ...
#   last_chunk = everything after the last </TR> (table/body/html close)
chunks=()
tmp=$content
while [[ $tmp == *'</TR>'* ]]; do
  chunks+=("${tmp%%'</TR>'*}")
  tmp=${tmp#*'</TR>'}
done
last_chunk=$tmp

# Extract column values from one row body.
# Columns (0-based): 0 = rank, 5 = q-value, 7 = % targets, 9 = % background.
RANK=""; Q=""; TGT=""; BG=""
get_fields() {
  local s=$1 i=0 td before
  RANK=""; Q=""; TGT=""; BG=""
  while [[ $s == *'</TD>'* ]]; do
    before=${s%%'</TD>'*}
    s=${s#*'</TD>'}
    td=${before##*'<TD>'}
    case $i in
      0) RANK=$td ;;
      5) Q=${td//[[:space:]]/} ;;
      7) TGT=${td//[%]/}; TGT=${TGT//[[:space:]]/} ;;
      9) BG=${td//[%]/};  BG=${BG//[[:space:]]/} ;;
    esac
    i=$((i + 1))
  done
}

# Build "index<TAB>qvalue<TAB>target<TAB>background" records.
keys=$(mktemp)
sortable=$(mktemp)
trap 'rm -f "$keys" "$sortable"' EXIT
for ((i = 1; i < ${#chunks[@]}; i++)); do
  get_fields "${chunks[$i]}"
  printf '%d\t%s\t%s\t%s\n' "$i" "$Q" "$TGT" "$BG" >> "$keys"
done

# Determine the new order: descending by key, ties keep original order.
# Keys are emitted with full precision; the original index is the tie-breaker.
# With --q, rows whose q-value >= threshold are dropped first.
if [[ -n $q_threshold ]]; then
  if [[ $reorder == "pctarget" ]]; then
    awk -F'\t' -v OFS='\t' -v OFMT='%.17g' -v q="$q_threshold" \
      '$2 < q {print $3 + 0, $1}' "$keys" > "$sortable"
  else
    awk -F'\t' -v OFS='\t' -v OFMT='%.17g' -v q="$q_threshold" \
      '$2 < q {print $3 - $4, $1}' "$keys" > "$sortable"
  fi
else
  if [[ $reorder == "pctarget" ]]; then
    awk -F'\t' -v OFS='\t' -v OFMT='%.17g' '{print $3 + 0, $1}' "$keys" > "$sortable"
  else
    awk -F'\t' -v OFS='\t' -v OFMT='%.17g' '{print $3 - $4, $1}' "$keys" > "$sortable"
  fi
fi
mapfile -t order < <(sort -k1,1gr -k2,2n "$sortable" | cut -f2)

# Reassemble with the Rank column renumbered 1..N.
out="${chunks[0]}</TR>"
rank=0
for r in "${order[@]}"; do
  rank=$((rank + 1))
  chunk=${chunks[$r]}
  old=${chunk%%'</TD>'*}
  old=${old##*'<TD>'}
  nl=${chunk%%'<TR>'*}
  chunk="${nl}<TR><TD>${rank}</TD>${chunk#*<TR><TD>${old}</TD>}"
  out+="${chunk}</TR>"
done
out+="$last_chunk"

base=${filename%.*}
ext=${filename##*.}
out_suffix="_${reorder}"
[[ -n $q_threshold ]] && out_suffix+="_q${q_threshold}"
outfile="${base}${out_suffix}.${ext}"
printf '%s' "$out" > "$outfile"
echo "$outfile"

# ---------------------------------------------------------------------------
# Optional PDF export using a headless Chromium-based browser.
# ---------------------------------------------------------------------------

to_win_path() {
  if command -v wslpath >/dev/null 2>&1; then wslpath -w "$1"
  elif command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"
  else printf '%s\n' "$1"
  fi
}

find_browser() {
  local b p
  for b in google-chrome chromium chromium-browser microsoft-edge msedge; do
    if command -v "$b" >/dev/null 2>&1; then command -v "$b"; return 0; fi
  done
  for p in \
    "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" \
    "/mnt/c/Program Files/Microsoft/Edge/Application/msedge.exe" \
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe" \
    "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe" \
    "/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" \
    "/c/Program Files/Microsoft/Edge/Application/msedge.exe" \
    "/c/Program Files/Google/Chrome/Application/chrome.exe" \
    "/c/Program Files (x86)/Google/Chrome/Application/chrome.exe" \
    "/usr/bin/google-chrome" "/usr/bin/chromium" "/usr/bin/chromium-browser" \
    "/usr/bin/microsoft-edge" "/snap/bin/chromium"; do
    if [[ -x $p ]]; then printf '%s\n' "$p"; return 0; fi
  done
  return 1
}

create_pdf() {
  local html=$1 pdf=$2 browser uri pdf_arg prof prof_arg hl hf
  browser=$(find_browser) || {
    echo "Error: no Chromium-based browser (Edge/Chrome/Chromium) found for PDF export" >&2
    return 1
  }

  html=$(readlink -f "$html" 2>/dev/null || printf '%s' "$html")
  prof="$(dirname "$pdf")/.html2pdf.$$"
  mkdir -p "$prof"

  if [[ $browser == *.exe || $browser == /mnt/* || $browser == /c/* ]]; then
    uri="file:///$(to_win_path "$html")"
    uri=${uri//\\//}
    pdf_arg=$(to_win_path "$pdf")
    prof_arg=$(to_win_path "$prof")
  else
    uri="file://$html"
    pdf_arg=$pdf
    prof_arg=$prof
  fi

  for hl in --headless=new --headless; do
    for hf in --no-pdf-header-footer --print-to-pdf-no-header; do
      rm -f "$pdf"
      "$browser" "$hl" --disable-gpu --no-sandbox \
        "--user-data-dir=$prof_arg" \
        "--print-to-pdf=$pdf_arg" \
        "$hf" "$uri" >/dev/null 2>&1 || true
      if [[ -s $pdf ]]; then
        rm -rf "$prof"
        return 0
      fi
    done
  done
  rm -rf "$prof"
  echo "Error: browser did not produce a PDF" >&2
  return 1
}

if (( want_pdf )); then
  pdf_out="${base}${out_suffix}.pdf"
  create_pdf "$outfile" "$pdf_out" || exit 1
  echo "$pdf_out"
fi
