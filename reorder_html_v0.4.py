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
RANK_COL_IN = 0.4  # fixed narrow width of the --showrank column
COL_WEIGHTS = (22, 40, 9, 9, 10, 10)
HEADERS = ("Motif", "Name", "p", "FDR", "% targets", "% bkg")
NAMED_METHODS = ("pctarget", "difference", "ratio")
ORDER_RE = re.compile(r"\d+(?:\s*,\s*\d+)*")
PAREN_RE = re.compile(r"\(([^)]*)\)")
COLORGROUP_PALETTE = ("#FFCC99", "#99FFCC", "#66CCFF", "#FFFF99", "#FF9933",
                      "#33FF99", "#3399CC", "#CCCC00", "#FFCCFF", "#99CC00",
                      "#CCCCCC", "#9966CC")
IUPAC_SETS = {
    "A": frozenset("A"), "C": frozenset("C"), "G": frozenset("G"), "T": frozenset("T"),
    "R": frozenset("AG"), "Y": frozenset("CT"), "S": frozenset("CG"), "W": frozenset("AT"),
    "K": frozenset("GT"), "M": frozenset("AC"), "B": frozenset("CGT"), "D": frozenset("AGT"),
    "H": frozenset("ACT"), "V": frozenset("ACG"), "N": frozenset("ACGT"),
}

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


def method_key(tds, method):
    """Sort key for a row's <TD> list under a named method."""
    pct_target = parse_pct(tds[7])
    pct_bkg = parse_pct(tds[9])
    if method == "pctarget":
        return pct_target
    if method == "difference":
        return pct_target - pct_bkg
    # ratio
    if pct_bkg == 0.0:
        return float("inf") if pct_target > 0 else 0.0
    return pct_target / pct_bkg


def group_of(name):
    """Group membership from a motif name (shortname, first parenthetical)."""
    short = name.split("/", 1)[0]
    m = PAREN_RE.search(short)
    return m.group(1) if m else ""


def genes_from_motif(name):
    """Gene tokens from a motif name ('GeneName(Family)/Experiment/DB')."""
    seg = name.split("/", 1)[0]
    seg = re.sub(r"\([^)]*\)", "", seg)
    seen = set()
    tokens = []
    for tok in re.split(r"[,:]", seg):
        tok = tok.strip()
        if tok and tok not in seen:
            seen.add(tok)
            tokens.append(tok)
    return tokens


def load_genes_id_map(path):
    """gene name (upper-cased) -> [ENSEMBL ids] from a two-column TSV.

    Lines whose second column is not a human ENSEMBL id (ENSG...) are skipped
    (this also drops a BioMart header line).
    """
    mapping = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            name = parts[0].strip()
            ensg = parts[1].strip()
            if not name or not re.fullmatch(r"ENSG\d+", ensg):
                continue
            ids = mapping.setdefault(name.upper(), [])
            if ensg not in ids:
                ids.append(ensg)
    return mapping


def compute_ranks(records, source):
    """Map each record's input index to its 1-based rank.

    records: list of (input_index, row, tds) in input order.
    source:  ("method", name) | ("fdr",) | ("order", positions).
    """
    rank_of = {}
    if source[0] == "order":
        for pos, rec_pos in enumerate(source[1], start=1):
            rank_of[records[rec_pos - 1][0]] = pos
    elif source[0] == "fdr":
        for pos, rec in enumerate(sorted(records, key=lambda r: parse_pct(r[2][5])), start=1):
            rank_of[rec[0]] = pos
    else:
        method = source[1]
        for pos, rec in enumerate(
            sorted(records, key=lambda r: method_key(r[2], method), reverse=True), start=1
        ):
            rank_of[rec[0]] = pos
    return rank_of


def build_table_pdf(rows, pdf_path, fontsize, rowheight, width, height, weights,
                    shrink_name, headers, show_rank, draw_lines, line_color,
                    color_groups=False):
    """Build a single-page PDF containing only the motif table (figure)."""
    import fitz  # PyMuPDF, only required when --pdf is used

    n = len(rows)
    margin = MARGIN_IN * 72.0
    page_w = width * 72.0
    usable_w = page_w - 2 * margin

    header_list = (["Rank"] + list(headers)) if show_rank else list(headers)
    name_idx = 2 if show_rank else 1

    sum_w = float(sum(weights)) or 1.0
    if show_rank:
        rank_w = RANK_COL_IN * 72.0
        data_usable = usable_w - rank_w
        col_w = [rank_w] + [data_usable * w / sum_w for w in weights]
    else:
        col_w = [usable_w * w / sum_w for w in weights]

    reg_path = first_existing(ARIAL_CANDIDATES)
    bold_path = first_existing(ARIAL_BOLD_CANDIDATES)
    reg_font = fitz.Font(fontfile=reg_path) if reg_path else fitz.Font("helv")
    bold_font = fitz.Font(fontfile=bold_path) if bold_path else fitz.Font("hebo")

    # --shortname: shrink the Name column to its content and narrow the figure.
    if shrink_name:
        pad = 3.0
        widest = reg_font.text_length(headers[1], fontsize=fontsize)
        for r in rows:
            widest = max(widest, reg_font.text_length(r["name"], fontsize=fontsize))
        fit_w = widest + 2 * pad + 0.6
        if fit_w < col_w[name_idx]:
            col_w[name_idx] = fit_w
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

    grid_bottom = margin + header_h + n * rowheight

    shape = None
    if draw_lines:
        shape = page.new_shape()
        for xx in col_x:
            shape.draw_line(fitz.Point(xx, margin), fitz.Point(xx, grid_bottom))
        shape.draw_line(fitz.Point(margin, margin), fitz.Point(margin + usable_w, margin))

    y0 = margin
    y1 = y0 + header_h
    for c, htxt in enumerate(header_list):
        put(fitz.Rect(col_x[c], y0, col_x[c + 1], y1), htxt, bold_font, bold_name, "center")
    if draw_lines:
        shape.draw_line(fitz.Point(margin, y1), fitz.Point(margin + usable_w, y1))

    y = y1
    fills = []
    for r in rows:
        y0, y1 = y, y + rowheight
        ci = 0
        if show_rank:
            put(fitz.Rect(col_x[0], y0, col_x[1], y1), r["rank"], reg_font, reg_name, "center")
            ci = 1
        if r["logo"]:
            put_logo(fitz.Rect(col_x[ci], y0, col_x[ci + 1], y1), r["logo"])
        ci += 1
        put(fitz.Rect(col_x[ci], y0, col_x[ci + 1], y1), r["name"], reg_font, reg_name, "left")
        if color_groups and r.get("fill") is not None:
            fills.append((col_x[name_idx], y0, col_x[name_idx + 1], y1, r["fill"]))
        ci += 1
        put(fitz.Rect(col_x[ci], y0, col_x[ci + 1], y1), r["p"], reg_font, reg_name, "center")
        ci += 1
        put(fitz.Rect(col_x[ci], y0, col_x[ci + 1], y1), r["fdr"], reg_font, reg_name, "center")
        ci += 1
        put(fitz.Rect(col_x[ci], y0, col_x[ci + 1], y1), r["pct_targets"], reg_font, reg_name, "center")
        ci += 1
        put(fitz.Rect(col_x[ci], y0, col_x[ci + 1], y1), r["pct_bkg"], reg_font, reg_name, "center")
        if draw_lines:
            shape.draw_line(fitz.Point(margin, y1), fitz.Point(margin + usable_w, y1))
        y = y1

    if draw_lines:
        shape.finish(color=line_color, width=0.4)
        shape.commit(overlay=False)

    if color_groups and fills:
        by_color = {}
        for fx0, fy0, fx1, fy1, fill_rgb in fills:
            by_color.setdefault(fill_rgb, []).append((fx0, fy0, fx1, fy1))
        for fill_rgb, rects in by_color.items():
            fill_shape = page.new_shape()
            for fx0, fy0, fx1, fy1 in rects:
                fill_shape.draw_rect(fitz.Rect(fx0, fy0, fx1, fy1))
            fill_shape.finish(color=fill_rgb, fill=fill_rgb)
            fill_shape.commit(overlay=False)

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


def parse_colnames(text):
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 6:
        raise ValueError("--colnames must have exactly 6 comma-separated names")
    if any(p == "" for p in parts):
        raise ValueError("--colnames names must be non-empty")
    return tuple(parts)


def parse_order(text, n_rows):
    parts = [p.strip() for p in text.split(",")]
    values = []
    for p in parts:
        if not re.fullmatch(r"\d+", p):
            raise ValueError(f"--reorder positions must be integers, got: {text}")
        values.append(int(p))
    if not values:
        raise ValueError("--reorder position list is empty")
    for v in values:
        if v < 1 or v > n_rows:
            raise ValueError(
                f"--reorder position {v} is out of range 1..{n_rows}"
            )
    if len(set(values)) != len(values):
        raise ValueError("--reorder positions must be unique")
    return values


def parse_colorgroup_palette(text):
    parts = [p.strip() for p in text.split(",")]
    if not parts or any(p == "" for p in parts):
        raise ValueError("--colorgroup_palette must be non-empty hex colours separated by commas")
    for p in parts:
        if not re.fullmatch(r"#?[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", p):
            raise ValueError(f"--colorgroup_palette contains an invalid hex colour: {p}")
    return [hex_to_rgb(p) for p in parts]


def parse_heatmapscale(text):
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 2 or not all(re.fullmatch(r"-?\d+", p) for p in parts):
        raise ValueError("--heatmapscale must be two integers separated by a comma, e.g. 0,100")
    lo, hi = int(parts[0]), int(parts[1])
    if lo >= hi:
        raise ValueError(f"--heatmapscale min must be less than max, got: {text}")
    return lo / 100.0, hi / 100.0


def nw_similarity(seq_a, seq_b, cache=None):
    """Needleman-Wunsch similarity of two IUPAC consensus sequences, in [0, 1]."""
    if cache is None:
        cache = {}
    a = (seq_a or "").upper()
    b = (seq_b or "").upper()
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    gap = -1.0
    prev = [gap * j for j in range(len(b) + 1)]
    for i in range(1, len(a) + 1):
        sa = IUPAC_SETS.get(a[i - 1], IUPAC_SETS["N"])
        cur = [gap * i]
        for j in range(1, len(b) + 1):
            sb = IUPAC_SETS.get(b[j - 1], IUPAC_SETS["N"])
            key = (a[i - 1], b[j - 1])
            jac = cache.get(key)
            if jac is None:
                union = sa | sb
                jac = len(sa & sb) / len(union) if union else 1.0
                cache[key] = jac
            best = prev[j - 1] + 2.0 * jac - 1.0
            v = prev[j] + gap
            if v > best:
                best = v
            v = cur[j - 1] + gap
            if v > best:
                best = v
            cur.append(best)
        prev = cur
    sim = max(0.0, prev[-1]) / min(len(a), len(b))
    return sim if sim < 1.0 else 1.0


def consensus_similarity_matrix(sequences):
    """Symmetric pairwise NW-similarity matrix with a diagonal of 1.0."""
    n = len(sequences)
    sims = [[1.0] * n for _ in range(n)]
    cache = {}
    for i in range(n):
        for j in range(i + 1, n):
            s = nw_similarity(sequences[i], sequences[j], cache)
            sims[i][j] = s
            sims[j][i] = s
    return sims


def auto_k(n):
    """Automatic k for the heatmap k-means: round(sqrt(n/2)), clamped to [2, n]."""
    if n <= 1:
        return 1
    return min(n, max(2, round((n / 2.0) ** 0.5)))


def kmeans_cluster(sims, k, seed=0):
    """Deterministic k-means on the similarity profiles; returns a label per motif."""
    import numpy as np

    X = np.asarray(sims, dtype=float)
    n = X.shape[0]
    if k <= 1:
        return [0] * n
    if k >= n:
        return list(range(n))
    rng = np.random.default_rng(seed)
    centers = [X[int(rng.integers(n))]]
    for _ in range(1, k):
        d2 = np.min(np.array([((X - c) ** 2).sum(axis=1) for c in centers]), axis=0)
        total = float(d2.sum())
        if total <= 0.0:
            idx = int(rng.integers(n))
        else:
            idx = int(rng.choice(n, p=d2 / total))
        centers.append(X[idx])
    centers = np.array(centers, dtype=float)
    labels = None
    for _ in range(100):
        d2 = ((X[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        new_labels = d2.argmin(axis=1)
        if labels is not None and bool((new_labels == labels).all()):
            break
        labels = new_labels
        for c in range(k):
            pts = X[labels == c]
            if len(pts):
                centers[c] = pts.mean(axis=0)
            else:
                centers[c] = X[int(d2.min(axis=1).argmax())]
    return [int(v) for v in labels]


def sorted_clusters(sims, labels):
    """Clusters as index lists (display order kept inside), tightest cluster first."""
    clusters = {}
    for idx, lab in enumerate(labels):
        clusters.setdefault(lab, []).append(idx)

    def intra(idxs):
        if len(idxs) < 2:
            return 1.0
        total = 0.0
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                total += sims[idxs[a]][idxs[b]]
        return total / (len(idxs) * (len(idxs) - 1) / 2.0)

    return sorted(clusters.values(), key=lambda idxs: (-intra(idxs), idxs[0]))


def heat_labels(names):
    """Short motif names (up to the first '/'), duplicates disambiguated."""
    shorts = [n.split("/", 1)[0] for n in names]
    counts = {}
    for s in shorts:
        counts[s] = counts.get(s, 0) + 1
    seen = {}
    out = []
    for s in shorts:
        if counts[s] > 1:
            seen[s] = seen.get(s, 0) + 1
            out.append(f"{s} #{seen[s]}")
        else:
            out.append(s)
    return out


def render_heatmap_png(sims, names, groups, out_path, vmin=0.0, vmax=1.0):
    """Render the cluster-ordered similarity matrix as a PNG heatmap."""
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    order = [i for g in groups for i in g]
    M = np.asarray(sims, dtype=float)[np.ix_(order, order)]
    labs = heat_labels([names[i] for i in order])
    n = len(order)
    fs = max(4.0, min(7.0, 300.0 / n)) if n else 6.0
    cell = 0.28
    fig, ax = plt.subplots(figsize=(4.6 + cell * n, 2.6 + cell * n))
    im = ax.imshow(M, cmap="viridis", vmin=vmin, vmax=vmax, aspect="equal")
    ax.set_xticks(range(n))
    ax.set_xticklabels(labs, rotation=90, fontsize=fs)
    ax.set_yticks(range(n))
    ax.set_yticklabels(labs, fontsize=fs)
    pos = 0
    for g in groups[:-1]:
        pos += len(g)
        ax.axhline(pos - 0.5, color="white", linewidth=2.0)
        ax.axvline(pos - 0.5, color="white", linewidth=2.0)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ticks = np.linspace(vmin, vmax, 5)
    cbar.set_ticks(ticks)
    cbar.set_ticklabels([f"{int(round(float(t) * 100))}%" for t in ticks])
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description="Reorder HOMER knownResults.html rows.")
    ap.add_argument("--filename", required=True, help="input .html file")
    ap.add_argument("--reorder", default=None,
                    help="ranking method: pctarget, difference or ratio, or a "
                         "comma-separated list of 1-based row positions (e.g. 5,4,3,2,1)")
    ap.add_argument("--reordergroups", default=None, choices=NAMED_METHODS,
                    help="reorder rows by motif group (shortname parenthetical), groups "
                         "sorted by descending max of this method; ungroupped rows last")
    ap.add_argument("--q", default=None,
                    help="delete rows whose 'q-value (Benjamini)' is >= this threshold "
                         "(cannot be combined with a custom position list)")
    ap.add_argument("--pdf", action="store_true",
                    help="also create a PDF table figure")
    ap.add_argument("--showrank", action="store_true",
                    help="PDF only: prepend a narrow Rank column")
    ap.add_argument("--shortname", action="store_true",
                    help="PDF only: show only the motif name up to the first '/' and narrow the Name column")
    ap.add_argument("--nolines", action="store_true",
                    help="PDF only: omit the table grid lines")
    ap.add_argument("--linescolor", default=None,
                    help="PDF only: hex colour for the grid lines (default '#999999', e.g. '#CCCCCC' pale grey)")
    ap.add_argument("--colorgroups", action="store_true",
                    help="PDF only: fill the motif Name cells with the group colour under the text")
    ap.add_argument("--colorgroup_palette", default=None,
                    help="PDF only: comma-separated hex colours assigned sequentially to groups "
                         "by first appearance, recycled if more groups than colours "
                         "(default '#FFCC99,#99FFCC,#66CCFF,#FFFF99,#FF9933,#33FF99,"
                         "#3399CC,#CCCC00,#FFCCFF,#99CC00,#CCCCCC,#9966CC')")
    ap.add_argument("--fontsize", type=float, default=None, help="PDF font size in pt (default 8)")
    ap.add_argument("--rowheight", type=float, default=None, help="PDF row height in pt (default 18)")
    ap.add_argument("--width", type=float, default=None, help="PDF width in inches (default 8.5)")
    ap.add_argument("--height", type=float, default=None, help="PDF height in inches (default auto)")
    ap.add_argument("--colwidth", default=None,
                    help="PDF only: 6 comma-separated integers (relative weights) for columns "
                         "1-6; 0 keeps that column's default (22,40,9,9,10,10)")
    ap.add_argument("--colnames", default=None,
                    help="PDF only: 6 comma-separated custom column names "
                         "(default 'Motif,Name,p,FDR,%% targets,%% bkg')")
    ap.add_argument("--pdfout", default=None, help="output PDF filename (default <base><suffix>.pdf)")
    ap.add_argument("--heatmap", default=None, metavar="HEATMAPFILE",
                    help="output PNG heatmap filename: pairwise consensus-sequence similarity "
                         "of the table motifs, rows/columns ordered by k-means clustering "
                         "(k chosen automatically); the .png extension is enforced")
    ap.add_argument("--knownresults_txt", default=None, metavar="FILE",
                    help="path to knownResults.txt (tab-separated; consensus in column 2), "
                         "required with --heatmap; a bare name is resolved next to the input HTML")
    ap.add_argument("--heatmapscale", default=None, metavar="MIN,MAX",
                    help="heatmap colour-scale range as two comma-separated integers (percent), "
                         "e.g. 20,80 (default 0,100); values outside the range clip to the "
                         "scale ends; requires --heatmap")
    ap.add_argument("--genes", action="store_true",
                    help="also write a tab-separated text file mapping each motif name of the "
                         "output table to its gene name(s) and their human ENSEMBL gene ids "
                         "(three columns: motif name, gene name, ENSG id; one row per id)")
    ap.add_argument("--genesoutfile", default=None, metavar="FILE",
                    help="output filename for --genes (default 'genes.txt'); a bare name is "
                         "resolved next to the input HTML; requires --genes")
    ap.add_argument("--genes_id_map", default=None, metavar="FILE",
                    help="two-column tab-separated gene->ENSEMBL-id map (col1 gene name, "
                         "col2 human ENSEMBL id; one row per id; e.g. an Ensembl BioMart "
                         "'Gene name / Gene stable ID' export); lookup is case-insensitive; "
                         "required with --genes")
    args = ap.parse_args()

    is_order = args.reorder is not None and ORDER_RE.fullmatch(args.reorder) is not None
    if args.reorder is not None and not is_order and args.reorder not in NAMED_METHODS:
        ap.error("--reorder must be one of pctarget, difference, ratio, or a "
                 "comma-separated list of row positions (e.g. 5,4,3,2,1)")
    if is_order and args.reordergroups is not None:
        ap.error("a position-list --reorder cannot be combined with --reordergroups")
    if is_order and args.q is not None:
        ap.error("--q cannot be combined with a custom --reorder position list")

    pdf_only_used = any(v is not None for v in (
        args.fontsize, args.rowheight, args.width, args.height, args.colwidth,
        args.colnames, args.linescolor, args.colorgroup_palette, args.pdfout,
    )) or args.shortname or args.showrank or args.nolines or args.colorgroups
    if pdf_only_used and not args.pdf:
        ap.error("--showrank, --shortname, --nolines, --fontsize, --rowheight, --width, "
                 "--height, --colwidth, --colnames, --linescolor, --colorgroups, "
                 "--colorgroup_palette and --pdfout require --pdf")
    if args.colorgroup_palette is not None and not args.colorgroups:
        ap.error("--colorgroup_palette requires --colorgroups")
    if args.heatmap is not None and args.knownresults_txt is None:
        ap.error("--heatmap requires --knownresults_txt")
    if args.knownresults_txt is not None and args.heatmap is None:
        ap.error("--knownresults_txt is only meaningful with --heatmap")
    if args.heatmapscale is not None and args.heatmap is None:
        ap.error("--heatmapscale requires --heatmap")
    if args.genesoutfile is not None and not args.genes:
        ap.error("--genesoutfile requires --genes")
    if args.genes_id_map is not None and not args.genes:
        ap.error("--genes_id_map requires --genes")
    if args.genes and args.genes_id_map is None:
        ap.error("--genes requires --genes_id_map")

    txt_path = None
    if args.knownresults_txt is not None:
        if os.path.dirname(args.knownresults_txt):
            txt_path = args.knownresults_txt
        else:
            txt_path = os.path.join(os.path.dirname(args.filename), args.knownresults_txt)
        if not os.path.isfile(txt_path):
            ap.error(f"--knownresults_txt file not found: {txt_path}")

    heatmap_path = None
    if args.heatmap is not None:
        hm_base = os.path.splitext(args.heatmap)[0]
        if os.path.dirname(args.heatmap):
            heatmap_path = hm_base + ".png"
        else:
            heatmap_path = os.path.join(os.path.dirname(args.filename), hm_base + ".png")

    heatmap_scale = (0.0, 1.0)
    if args.heatmapscale is not None:
        try:
            heatmap_scale = parse_heatmapscale(args.heatmapscale)
        except ValueError as exc:
            ap.error(str(exc))

    genes_out_path = None
    if args.genes:
        if args.genesoutfile:
            if os.path.dirname(args.genesoutfile):
                genes_out_path = args.genesoutfile
            else:
                genes_out_path = os.path.join(os.path.dirname(args.filename), args.genesoutfile)
        else:
            genes_out_path = os.path.join(os.path.dirname(args.filename), "genes.txt")

    gene_map = None
    if args.genes:
        if os.path.dirname(args.genes_id_map):
            map_path = args.genes_id_map
        else:
            map_path = os.path.join(os.path.dirname(args.filename), args.genes_id_map)
        if not os.path.isfile(map_path):
            ap.error(f"--genes_id_map file not found: {map_path}")
        gene_map = load_genes_id_map(map_path)
        if not gene_map:
            ap.error("--genes_id_map has no valid rows (expected: gene name<TAB>ENSG id)")

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

    headers = HEADERS
    if args.colnames is not None:
        try:
            headers = parse_colnames(args.colnames)
        except ValueError as exc:
            ap.error(str(exc))

    weights = COL_WEIGHTS
    if colwidth_given is not None:
        weights = tuple(v if v > 0 else d for v, d in zip(colwidth_given, COL_WEIGHTS))
    shrink_name = args.shortname and (colwidth_given is None or colwidth_given[1] == 0)

    draw_lines = not args.nolines
    line_color = (0.6, 0.6, 0.6)
    if args.linescolor is not None:
        if not re.fullmatch(r"#?[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", args.linescolor.strip()):
            ap.error(f"--linescolor must be a hex colour like '#999999' or '#CCC', got: {args.linescolor}")
        line_color = hex_to_rgb(args.linescolor)

    color_group_palette = None
    if args.colorgroups:
        try:
            color_group_palette = parse_colorgroup_palette(
                args.colorgroup_palette) if args.colorgroup_palette is not None \
                else [hex_to_rgb(c) for c in COLORGROUP_PALETTE]
        except ValueError as exc:
            ap.error(str(exc))

    with open(args.filename, "r", encoding="utf-8", newline="") as fh:
        content = fh.read()

    matches = list(ROW_RE.finditer(content))
    if len(matches) < 2:
        sys.exit("No motif rows found.")

    n_rows = len(matches) - 1

    custom_order = None
    if is_order:
        try:
            custom_order = parse_order(args.reorder, n_rows)
        except ValueError as exc:
            ap.error(str(exc))

    prefix = content[:matches[0].end()]
    suffix = content[matches[-1].end():]
    sep = content[matches[0].end():matches[1].start()]

    records = []
    for i, m in enumerate(matches[1:]):
        row = m.group(0)
        tds = TD_RE.findall(row)
        if q_threshold is not None and parse_pct(tds[5]) >= q_threshold:
            continue
        records.append((i, row, tds))

    # Row order: groups win, then a position list, then a named method, else identity.
    if args.reordergroups is not None:
        groups = {}
        for rec in records:
            groups.setdefault(group_of(rec[2][2].strip()), []).append(rec)

        def gmax(g):
            return max(method_key(r[2], args.reordergroups) for r in groups[g])

        ordered = []
        for g in sorted((g for g in groups if g != ""), key=lambda g: (-gmax(g), g)):
            ordered.extend(sorted(groups[g], key=lambda r: method_key(r[2], args.reordergroups),
                                  reverse=True))
        if "" in groups:
            ordered.extend(sorted(groups[""], key=lambda r: method_key(r[2], args.reordergroups),
                                  reverse=True))
        items = [(i, row, tds) for (i, row, tds) in ordered]
    elif custom_order is not None:
        items = [records[pos - 1] for pos in custom_order]
    elif args.reorder is not None:
        keyed = sorted(records, key=lambda r: method_key(r[2], args.reorder), reverse=True)
        items = [(i, row, tds) for (i, row, tds) in keyed]
    else:
        items = list(records)

    rank_of = {}
    if args.showrank:
        if args.reorder is not None and args.reorder in NAMED_METHODS:
            rank_of = compute_ranks(records, ("method", args.reorder))
        elif custom_order is not None:
            rank_of = compute_ranks(records, ("order", custom_order))
        elif args.reordergroups is not None:
            rank_of = compute_ranks(records, ("method", args.reordergroups))
        else:
            rank_of = compute_ranks(records, ("fdr",))

    heat_seqs = None
    heat_names = None
    if args.heatmap:
        if not items:
            ap.error("the table has no motif rows for --heatmap (check --q)")
        consensus = {}
        with open(txt_path, "r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh):
                line = line.rstrip("\r\n")
                if line_no == 0 or not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                consensus.setdefault(parts[0].strip(), parts[1].strip())
        heat_seqs = []
        heat_names = []
        for _i, _row, tds in items:
            full = tds[2].strip()
            if full not in consensus:
                ap.error(f"motif not found in --knownresults_txt: {full}")
            heat_seqs.append(consensus[full])
            heat_names.append(full)

    new_rows = [
        RANK_RE.sub(f"<TR><TD>{rank}</TD>", row, count=1)
        for rank, (_i, row, _tds) in enumerate(items, start=1)
    ]

    base, ext = os.path.splitext(args.filename)
    if args.reordergroups is not None:
        out_suffix = f"_group_{args.reordergroups}"
    elif custom_order is not None:
        out_suffix = "_order"
    elif args.reorder is not None:
        out_suffix = f"_{args.reorder}"
    else:
        out_suffix = "_fdr"
    if args.q is not None:
        out_suffix += f"_q{args.q}"
    out_path = f"{base}{out_suffix}{ext}"
    body = sep + sep.join(new_rows) if new_rows else ""
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        fh.write(prefix + body + suffix)

    print(out_path)

    if args.heatmap:
        sims = consensus_similarity_matrix(heat_seqs)
        k = auto_k(len(heat_seqs))
        groups = sorted_clusters(sims, kmeans_cluster(sims, k))
        render_heatmap_png(sims, heat_names, groups, heatmap_path,
                           heatmap_scale[0], heatmap_scale[1])
        sizes = ",".join(str(len(g)) for g in groups)
        print(f"{os.path.abspath(heatmap_path)} (k={k}, cluster sizes: {sizes})")

    if args.genes:
        lines = []
        for _i, _row, tds in items:
            full = tds[2].strip()
            for gene in genes_from_motif(full):
                ids = gene_map.get(gene.upper())
                if ids:
                    for ensg in ids:
                        lines.append(f"{full}\t{gene}\t{ensg}")
                else:
                    lines.append(f"{full}\t{gene}\t")
        with open(genes_out_path, "w", encoding="utf-8", newline="") as fh:
            fh.write("\n".join(lines))
            if lines:
                fh.write("\n")
        print(os.path.abspath(genes_out_path))

    if args.pdf:
        rows_pdf = []
        group_fill = {}
        for i, _row, tds in items:
            name = tds[2].strip()
            if args.shortname:
                name = name.split("/", 1)[0]
            svg = SVG_RE.search(tds[1])
            fill = None
            if args.colorgroups:
                g = group_of(tds[2].strip())
                if g != "":
                    if g not in group_fill:
                        group_fill[g] = color_group_palette[len(group_fill) % len(color_group_palette)]
                    fill = group_fill[g]
            rows_pdf.append({
                "logo": svg.group(0) if svg else None,
                "name": name,
                "p": tds[3].strip(),
                "fdr": tds[5].strip(),
                "pct_targets": tds[7].strip().rstrip("%").strip(),
                "pct_bkg": tds[9].strip().rstrip("%").strip(),
                "rank": str(rank_of.get(i, "")),
                "fill": fill,
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
                            args.height, weights, shrink_name, headers, args.showrank,
                            draw_lines, line_color, args.colorgroups)
        except RuntimeError as exc:
            sys.exit(f"Error creating PDF: {exc}")
        print(os.path.abspath(pdf_path))


if __name__ == "__main__":
    main()
