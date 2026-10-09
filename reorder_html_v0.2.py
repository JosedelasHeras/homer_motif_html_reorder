#!/usr/bin/env python3
import argparse
import os
import re
import sys

ROW_RE = re.compile(r"<TR>.*?</TR>", re.DOTALL)
TD_RE = re.compile(r"<TD>(.*?)</TD>", re.DOTALL)
RANK_RE = re.compile(r"^<TR><TD>.*?</TD>")
SVG_RE = re.compile(r"<svg\b.*?</svg>", re.DOTALL)

# logo SVG parsing (HOMER sequence logos: <g font-size=..> <text fill transform>L</text>)
SVG_TAG_RE = re.compile(r"<svg\b([^>]*)>")
G_TAG_RE = re.compile(r"<g\b([^>]*)>")
TEXT_RE = re.compile(r"<text\b([^>]*)>(.*?)</text>", re.DOTALL)
ATTR_RE = re.compile(r'([\w-]+)\s*=\s*"([^"]*)"')
INNER_TAG_RE = re.compile(r"<[^>]*>")
MATRIX_RE = re.compile(
    r"matrix\(\s*([-0-9.eE]+)\s*,\s*([-0-9.eE]+)\s*,\s*([-0-9.eE]+)\s*,"
    r"\s*([-0-9.eE]+)\s*,\s*([-0-9.eE]+)\s*,\s*([-0-9.eE]+)\s*\)"
)

# PDF table defaults / layout
DEF_FONTSIZE = 8.0
DEF_ROWHEIGHT = 18.0
DEF_WIDTH = 8.5
MARGIN_IN = 0.25
RASTER_DPI = 300  # only used for non-text SVG logos (fallback)
COL_WEIGHTS = (22, 40, 9, 9, 10, 10)
HEADERS = ("Motif", "Name", "p", "FDR", "% targets", "% bkg")

ARIAL_CANDIDATES = (
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)
ARIAL_BOLD_CANDIDATES = (
    r"C:\Windows\Fonts\arialbd.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)


def parse_pct(text):
    return float(text.strip().rstrip("%").strip())


def first_existing(paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def hex_to_rgb(text):
    s = (text or "").strip()
    if s.startswith("#"):
        s = s[1:]
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) != 6:
        return (0.0, 0.0, 0.0)
    try:
        return tuple(int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return (0.0, 0.0, 0.0)


def parse_logo_svg(svg_text):
    """Return (view_w, view_h, glyphs) for a HOMER logo SVG.

    glyphs is a list of (letter, fill, (a, b, c, d, e, f), fontsize).
    """
    view_w = view_h = None
    m = SVG_TAG_RE.search(svg_text)
    if m:
        attrs = dict(ATTR_RE.findall(m.group(1)))
        view_w = to_float(attrs.get("width"))
        view_h = to_float(attrs.get("height"))

    group_size = None
    g = G_TAG_RE.search(svg_text)
    if g:
        group_size = to_float(dict(ATTR_RE.findall(g.group(1))).get("font-size"))

    glyphs = []
    for attr_text, inner in TEXT_RE.findall(svg_text):
        attrs = dict(ATTR_RE.findall(attr_text))
        letter = INNER_TAG_RE.sub("", inner).strip()
        if not letter:
            continue
        size = to_float(attrs.get("font-size")) or group_size or 66.5
        mm = MATRIX_RE.search(attrs.get("transform", ""))
        if mm:
            transform = tuple(float(x) for x in mm.groups())
        else:
            tx = to_float(attrs.get("x")) or 0.0
            ty = to_float(attrs.get("y")) or 0.0
            transform = (1.0, 0.0, 0.0, 1.0, tx, ty)
        glyphs.append((letter, attrs.get("fill", "#000000"), transform, size))
    return view_w, view_h, glyphs


def truncate(text, font, fontsize, max_w):
    if max_w <= 0 or font.text_length(text, fontsize=fontsize) <= max_w:
        return text
    ell = "\u2026"
    ell_w = font.text_length(ell, fontsize=fontsize)
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if font.text_length(text[:mid], fontsize=fontsize) + ell_w <= max_w:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + ell


def build_table_pdf(rows, pdf_path, fontsize, rowheight, width, height, weights, shrink_name):
    """Build a single-page PDF containing only the motif table (figure)."""
    import fitz  # PyMuPDF, only required when --pdf is used

    n = len(rows)
    margin = MARGIN_IN * 72.0
    page_w = width * 72.0
    usable_w = page_w - 2 * margin

    sum_w = float(sum(weights)) or 1.0
    col_w = [usable_w * w / sum_w for w in weights]

    reg_path = first_existing(ARIAL_CANDIDATES)
    bold_path = first_existing(ARIAL_BOLD_CANDIDATES)
    reg_font = fitz.Font(fontfile=reg_path) if reg_path else fitz.Font("helv")
    bold_font = fitz.Font(fontfile=bold_path) if bold_path else fitz.Font("hebo")

    # --shortname: shrink the Name column to its content and narrow the figure.
    if shrink_name:
        pad = 3.0
        widest = reg_font.text_length(HEADERS[1], fontsize=fontsize)
        for r in rows:
            widest = max(widest, reg_font.text_length(r["name"], fontsize=fontsize))
        fit_w = widest + 2 * pad + 0.6
        if fit_w < col_w[1]:
            col_w[1] = fit_w
            usable_w = sum(col_w)
            page_w = usable_w + 2 * margin

    col_x = [margin]
    for w in col_w:
        col_x.append(col_x[-1] + w)

    page_h_given = None if height is None else height * 72.0

    if rowheight is None:
        if page_h_given is None or n == 0:
            rowheight = DEF_ROWHEIGHT
        else:
            rowheight = (page_h_given - 2 * margin) / (n + 1)
            if rowheight <= 1:
                raise RuntimeError("--height too small for the number of rows")

    header_h = max(rowheight, fontsize * 1.6)
    content_h = header_h + n * rowheight
    need_h = content_h + 2 * margin
    if page_h_given is None:
        page_h = need_h
    else:
        page_h = page_h_given
        if need_h > page_h + 0.5:
            raise RuntimeError(
                f"table needs {need_h / 72:.2f} in but --height is {height} in; "
                "reduce --rowheight/--fontsize or increase --height"
            )

    doc = fitz.open()
    page = doc.new_page(width=page_w, height=page_h)

    reg_name = "Arial" if reg_path else "helv"
    bold_name = "Arial-Bold" if bold_path else "hebo"
    if reg_path:
        page.insert_font(fontname=reg_name, fontfile=reg_path)
    if bold_path:
        page.insert_font(fontname=bold_name, fontfile=bold_path)

    def put(cell, text, font, fontname, align):
        pad = 3.0
        text = truncate(text, font, fontsize, cell.width - 2 * pad)
        tw = font.text_length(text, fontsize=fontsize)
        if align == "center":
            x = cell.x0 + (cell.width - tw) / 2.0
        elif align == "right":
            x = cell.x1 - pad - tw
        else:
            x = cell.x0 + pad
        baseline = (cell.y0 + cell.y1) / 2.0 + fontsize * 0.36
        page.insert_text((x, baseline), text, fontsize=fontsize, fontname=fontname,
                         overlay=False)

    def put_logo(cell, svg_text):
        view_w, view_h, glyphs = parse_logo_svg(svg_text)
        simple = bool(glyphs) and all(
            tr[1] == 0.0 and tr[2] == 0.0 for (_l, _c, tr, _s) in glyphs
        )
        pad = 2.0
        if not simple:
            try:
                svg_doc = fitz.open(stream=svg_text.encode("utf-8"), filetype="svg")
            except Exception:
                return
            scale = RASTER_DPI / 72.0
            pix = svg_doc[0].get_pixmap(matrix=fitz.Matrix(scale, scale))
            png = pix.tobytes("png")
            iw, ih = pix.width, pix.height
            svg_doc.close()
            s = min((cell.width - 2 * pad) / iw, (cell.height - 2 * pad) / ih)
            w, h = iw * s, ih * s
            x = cell.x0 + (cell.width - w) / 2.0
            y = cell.y0 + (cell.height - h) / 2.0
            page.insert_image(fitz.Rect(x, y, x + w, y + h), stream=png, overlay=False)
            return

        W = view_w or 305.0
        H = view_h or 50.0
        s = min((cell.width - 2 * pad) / W, (cell.height - 2 * pad) / H)
        ox = cell.x0 + (cell.width - s * W) / 2.0
        oy = cell.y0 + (cell.height - s * H) / 2.0
        for letter, fill, (a, _b, _c, d, e, f), size in glyphs:
            bx = ox + s * e
            by = oy + s * f
            page.insert_text(
                (bx, by), letter,
                fontname=bold_name, fontsize=size, color=hex_to_rgb(fill), overlay=False,
                morph=(fitz.Point(bx, by), fitz.Matrix(s * a, 0, 0, s * d, 0, 0)),
            )

    line_color = (0.6, 0.6, 0.6)
    grid_bottom = margin + header_h + n * rowheight

    shape = page.new_shape()
    for xx in col_x:
        shape.draw_line(fitz.Point(xx, margin), fitz.Point(xx, grid_bottom))
    shape.draw_line(fitz.Point(margin, margin), fitz.Point(margin + usable_w, margin))

    y0 = margin
    y1 = y0 + header_h
    for c, htxt in enumerate(HEADERS):
        put(fitz.Rect(col_x[c], y0, col_x[c + 1], y1), htxt, bold_font, bold_name, "center")
    shape.draw_line(fitz.Point(margin, y1), fitz.Point(margin + usable_w, y1))

    y = y1
    for r in rows:
        y0, y1 = y, y + rowheight
        if r["logo"]:
            put_logo(fitz.Rect(col_x[0], y0, col_x[1], y1), r["logo"])
        put(fitz.Rect(col_x[1], y0, col_x[2], y1), r["name"], reg_font, reg_name, "left")
        put(fitz.Rect(col_x[2], y0, col_x[3], y1), r["p"], reg_font, reg_name, "center")
        put(fitz.Rect(col_x[3], y0, col_x[4], y1), r["fdr"], reg_font, reg_name, "center")
        put(fitz.Rect(col_x[4], y0, col_x[5], y1), r["pct_targets"], reg_font, reg_name, "center")
        put(fitz.Rect(col_x[5], y0, col_x[6], y1), r["pct_bkg"], reg_font, reg_name, "center")
        shape.draw_line(fitz.Point(margin, y1), fitz.Point(margin + usable_w, y1))
        y = y1

    shape.finish(color=line_color, width=0.4)
    shape.commit(overlay=False)

    doc.save(pdf_path, deflate=True, garbage=4)
    doc.close()


def parse_colwidth(text):
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 6:
        raise ValueError("--colwidth must have exactly 6 comma-separated integers")
    values = []
    for p in parts:
        if not re.fullmatch(r"\d+", p):
            raise ValueError(
                f"--colwidth values must be non-negative integers, got: {text}"
            )
        values.append(int(p))
    return values


def main():
    ap = argparse.ArgumentParser(description="Reorder HOMER knownResults.html rows.")
    ap.add_argument("--filename", required=True, help="input .html file")
    ap.add_argument("--reorder", required=True, choices=["pctarget", "difference"])
    ap.add_argument("--q", default=None,
                    help="delete rows whose 'q-value (Benjamini)' is >= this threshold")
    ap.add_argument("--pdf", action="store_true",
                    help="also create a PDF table figure")
    ap.add_argument("--shortname", action="store_true",
                    help="PDF only: show only the motif name up to the first '/' and narrow the Name column")
    ap.add_argument("--fontsize", type=float, default=None, help="PDF font size in pt (default 8)")
    ap.add_argument("--rowheight", type=float, default=None, help="PDF row height in pt (default 18)")
    ap.add_argument("--width", type=float, default=None, help="PDF width in inches (default 8.5)")
    ap.add_argument("--height", type=float, default=None, help="PDF height in inches (default auto)")
    ap.add_argument("--colwidth", default=None,
                    help="PDF only: 6 comma-separated integers (relative weights) for columns "
                         "1-6; 0 keeps that column's default (22,40,9,9,10,10)")
    ap.add_argument("--pdfout", default=None, help="output PDF filename (default <base><suffix>.pdf)")
    args = ap.parse_args()

    pdf_only_used = any(v is not None for v in (
        args.fontsize, args.rowheight, args.width, args.height, args.colwidth, args.pdfout,
    )) or args.shortname
    if pdf_only_used and not args.pdf:
        ap.error("--shortname, --fontsize, --rowheight, --width, --height, --colwidth and "
                 "--pdfout require --pdf")

    q_threshold = None
    if args.q is not None:
        try:
            q_threshold = float(args.q)
        except ValueError:
            ap.error(f"--q must be a number, got: {args.q}")

    colwidth_given = None
    if args.colwidth is not None:
        try:
            colwidth_given = parse_colwidth(args.colwidth)
        except ValueError as exc:
            ap.error(str(exc))

    weights = COL_WEIGHTS
    if colwidth_given is not None:
        weights = tuple(v if v > 0 else d for v, d in zip(colwidth_given, COL_WEIGHTS))
    shrink_name = args.shortname and (colwidth_given is None or colwidth_given[1] == 0)

    with open(args.filename, "r", encoding="utf-8", newline="") as fh:
        content = fh.read()

    matches = list(ROW_RE.finditer(content))
    if len(matches) < 2:
        sys.exit("No motif rows found.")

    prefix = content[:matches[0].end()]
    suffix = content[matches[-1].end():]
    sep = content[matches[0].end():matches[1].start()]

    items = []
    for i, m in enumerate(matches[1:]):
        row = m.group(0)
        tds = TD_RE.findall(row)
        if q_threshold is not None and parse_pct(tds[5]) >= q_threshold:
            continue
        pct_target = parse_pct(tds[7])
        key = pct_target if args.reorder == "pctarget" else pct_target - parse_pct(tds[9])
        items.append((key, i, row, tds))

    items.sort(key=lambda t: t[0], reverse=True)

    new_rows = [
        RANK_RE.sub(f"<TR><TD>{rank}</TD>", row, count=1)
        for rank, (_k, _i, row, _tds) in enumerate(items, start=1)
    ]

    base, ext = os.path.splitext(args.filename)
    out_suffix = f"_{args.reorder}"
    if args.q is not None:
        out_suffix += f"_q{args.q}"
    out_path = f"{base}{out_suffix}{ext}"
    body = sep + sep.join(new_rows) if new_rows else ""
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        fh.write(prefix + body + suffix)

    print(out_path)

    if args.pdf:
        rows_pdf = []
        for _k, _i, _row, tds in items:
            name = tds[2].strip()
            if args.shortname:
                name = name.split("/", 1)[0]
            svg = SVG_RE.search(tds[1])
            rows_pdf.append({
                "logo": svg.group(0) if svg else None,
                "name": name,
                "p": tds[3].strip(),
                "fdr": tds[5].strip(),
                "pct_targets": tds[7].strip().rstrip("%").strip(),
                "pct_bkg": tds[9].strip().rstrip("%").strip(),
            })

        if args.pdfout:
            if os.path.dirname(args.pdfout):
                pdf_path = args.pdfout
            else:
                pdf_path = os.path.join(os.path.dirname(args.filename), args.pdfout)
        else:
            pdf_path = f"{base}{out_suffix}.pdf"

        fontsize = args.fontsize if args.fontsize is not None else DEF_FONTSIZE
        width = args.width if args.width is not None else DEF_WIDTH
        try:
            build_table_pdf(rows_pdf, pdf_path, fontsize, args.rowheight, width,
                            args.height, weights, shrink_name)
        except RuntimeError as exc:
            sys.exit(f"Error creating PDF: {exc}")
        print(os.path.abspath(pdf_path))


if __name__ == "__main__":
    main()
