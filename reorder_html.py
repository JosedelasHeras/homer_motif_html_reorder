#!/usr/bin/env python3
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROW_RE = re.compile(r"<TR>.*?</TR>", re.DOTALL)
TD_RE = re.compile(r"<TD>(.*?)</TD>", re.DOTALL)
RANK_RE = re.compile(r"^<TR><TD>.*?</TD>")


def parse_pct(text):
    return float(text.strip().rstrip("%").strip())


def find_browser():
    """Return a path to a Chromium-based browser, or None."""
    for name in ("msedge", "microsoft-edge", "google-chrome", "chrome", "chromium", "chromium-browser"):
        exe = shutil.which(name)
        if exe:
            return exe
    if os.name == "nt":
        candidates = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
    else:
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/microsoft-edge",
            "/snap/bin/chromium",
        ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def create_pdf(html_path, pdf_path):
    """Render html_path to pdf_path using a headless Chromium-based browser."""
    browser = find_browser()
    if not browser:
        raise RuntimeError(
            "no Chromium-based browser (Edge/Chrome/Chromium) found for PDF export"
        )

    html_path = os.path.abspath(html_path)
    pdf_path = os.path.abspath(pdf_path)
    uri = Path(html_path).as_uri()
    profile = tempfile.mkdtemp(prefix="html2pdf_")
    try:
        for headless in ("--headless=new", "--headless"):
            for header in ("--no-pdf-header-footer", "--print-to-pdf-no-header"):
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
                subprocess.run(
                    [
                        browser, headless, "--disable-gpu", "--no-sandbox",
                        f"--user-data-dir={profile}",
                        f"--print-to-pdf={pdf_path}",
                        header, uri,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                    return
        raise RuntimeError("browser did not produce a PDF")
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="Reorder HOMER knownResults.html rows.")
    ap.add_argument("--filename", required=True, help="input .html file")
    ap.add_argument("--reorder", required=True, choices=["pctarget", "difference"])
    ap.add_argument("--q", default=None,
                    help="delete rows whose 'q-value (Benjamini)' is >= this threshold")
    ap.add_argument("--pdf", action="store_true",
                    help="also create a PDF version of the resulting HTML")
    args = ap.parse_args()

    q_threshold = None
    if args.q is not None:
        try:
            q_threshold = float(args.q)
        except ValueError:
            ap.error(f"--q must be a number, got: {args.q}")

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
        items.append((key, i, row))

    items.sort(key=lambda t: t[0], reverse=True)

    new_rows = [
        RANK_RE.sub(f"<TR><TD>{rank}</TD>", row, count=1)
        for rank, (_k, _i, row) in enumerate(items, start=1)
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
        pdf_path = f"{base}{out_suffix}.pdf"
        try:
            create_pdf(out_path, pdf_path)
        except RuntimeError as exc:
            sys.exit(f"Error creating PDF: {exc}")
        print(os.path.abspath(pdf_path))


if __name__ == "__main__":
    main()
