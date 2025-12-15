#!/usr/bin/env python3
"""
extract_icj.py

Extract numbered paragraphs + headings from ICJ PDFs into the standard CSV.

Key goals (ICJ-style PDFs):
- Capture numbered paragraphs that begin with: <number>. (e.g., "112.")
- Capture headings as standalone rows (Roman numerals, A./B., short Title Case captions)
- Automatically drop front matter (TOC / abbreviations / etc.) by detecting the first
  "real body" run starting at paragraph 1.
- Preserve the small ICJ “formula” block immediately before paragraph 1 (optional),
  e.g.: "The International Court of Justice, ... Makes/Gives/Delivers the following ..."

Outputs CSV columns:
id,row_type,label,text_md,comment_author,comment_title,comment_text,comment_source

Notes:
- This script intentionally does NOT try to perfectly preserve italics/bold from PDF.
- For best results on ICJ PDFs, the “strip front matter” heuristic is the big win.
"""
import argparse
import csv
import re
from typing import List, Dict, Optional

import fitz  # PyMuPDF

# ----------------------------
# Patterns
# ----------------------------
PARA_RE = re.compile(r'^\s*(\d{1,4})\.\s+(.*\S)\s*$')
ROMAN_RE = re.compile(r'^\s*([IVXLCDM]{1,8})\.\s+(.*\S)\s*$')
LETTER_RE = re.compile(r'^\s*([A-Z])\.\s+(.*\S)\s*$')

# Useful to identify TOC-ish lines
PAGE_RANGE_RE = re.compile(r"\b\d{1,4}\s*-\s*\d{1,4}\b\s*$")

# Lines we *might* want to keep as the “ICJ formula” block before para 1
LEADIN_PAT = re.compile(
    r'^(The International Court of Justice,|Composed as above,|After deliberation,|Having regard to|'
    r'Makes the following|Finds as follows|Gives the following|Delivers the following)',
    re.I
)

# Quick header/footer fuzz removal (best-effort; not perfect)
HEADER_FUZZ = re.compile(
    r'^(international court of justice|cour internationale de justice|advisory opinion|judgment|order)\b',
    re.I
)


# ----------------------------
# Helpers
# ----------------------------
def normalize_space(s: str) -> str:
    return " ".join((s or "").strip().split())


def looks_like_page_range(s: str) -> bool:
    return bool(PAGE_RANGE_RE.search((s or "").strip()))


def is_heading(line: str) -> bool:
    """
    Conservative heading detector:
    - Roman numeral headings: "I. ..." "II. ..."
    - Letter headings: "A. ..." "B. ..."
    - Short Title Case captions without trailing period
    """
    s = line.strip()
    if not s:
        return False
    if ROMAN_RE.match(s) or LETTER_RE.match(s):
        return True
    if len(s) <= 80 and s == s.title() and not s.endswith('.'):
        return True
    return False


def collect_leadin(lines: List[str], para1_line_index: int, max_backscan: int = 140) -> List[str]:
    """
    Capture a small “ICJ formula” block immediately preceding paragraph 1,
    while trying not to swallow TOC-like junk.
    """
    start = max(0, para1_line_index - max_backscan)
    block: List[str] = []

    for i in range(start, para1_line_index):
        s = normalize_space(lines[i])
        if not s:
            continue

        if LEADIN_PAT.match(s):
            block.append(s)
            continue

        # allow continuations of "Having regard to ..." etc.
        if block:
            prev = block[-1].lower()
            if prev.startswith(("having regard to", "after deliberation", "the international court of justice")):
                # avoid TOC-ish lines
                if len(s) <= 260 and not looks_like_page_range(s):
                    block.append(s)

    # de-duplicate consecutive repeats
    cleaned: List[str] = []
    for s in block:
        if not cleaned or cleaned[-1] != s:
            cleaned.append(s)
    return cleaned


def find_para1_line_index(lines: List[str]) -> Optional[int]:
    for i, ln in enumerate(lines):
        m = PARA_RE.match(ln.strip())
        if m and int(m.group(1)) == 1:
            return i
    return None


def find_body_start_row_index(rows: List[Dict], window: int = 25) -> int:
    """
    Identify where the real body begins by finding the best run starting at para 1
    with consecutive paragraph numbers and non-TOC-like text lengths.
    Returns index in `rows` list.
    """
    para_idxs = [i for i, r in enumerate(rows) if r.get("row_type") == "para"]
    if not para_idxs:
        return 0

    candidates = []
    for i in para_idxs:
        lab = (rows[i].get("label") or "").strip()
        if lab.startswith("1."):
            candidates.append(i)

    if not candidates:
        return 0

    best_i = candidates[0]
    best_score = (-1, -1.0, 10**9)  # (consec, avg_len, page_range_count)

    for start_i in candidates:
        chunk = []
        for j in range(start_i, len(rows)):
            if rows[j].get("row_type") == "para":
                chunk.append(rows[j])
                if len(chunk) >= window:
                    break

        consec = 0
        lens = []
        page_ranges = 0

        for k, r in enumerate(chunk, start=1):
            # expected labels 1..window
            try:
                n = int(re.sub(r"\D", "", r.get("label", "")))
            except Exception:
                n = None

            if n == k:
                consec += 1

            t = r.get("text_md") or ""
            lens.append(len(t))
            if looks_like_page_range(t):
                page_ranges += 1

        avg_len = sum(lens) / max(1, len(lens))
        score = (consec, avg_len, page_ranges)

        # Prefer: more consecutive, longer avg text, fewer page-range-like endings
        if score[0] > best_score[0] or (
            score[0] == best_score[0] and (
                score[1] > best_score[1] or (score[1] == best_score[1] and score[2] < best_score[2])
            )
        ):
            best_score = score
            best_i = start_i

    return best_i


def strip_front_matter_keep_leadin(rows: List[Dict], leadin_lines: List[str]) -> List[Dict]:
    start_i = find_body_start_row_index(rows, window=25)
    body = rows[start_i:] if start_i > 0 else rows[:]

    if leadin_lines:
        lead_text = " ".join(leadin_lines)
        lead_row = {
            "id": "pre-icj-formula",
            "row_type": "lead",
            "label": "",
            "text_md": lead_text,
            "comment_author": "",
            "comment_title": "",
            "comment_text": "",
            "comment_source": ""
        }
        return [lead_row] + body

    return body


# ----------------------------
# Extraction
# ----------------------------
def extract_lines(pdf_path: str) -> List[str]:
    """
    Simple line extraction with light cleanup.
    If you later want a stronger extractor, switch to block-based extraction.
    """
    doc = fitz.open(pdf_path)
    lines: List[str] = []

    for page in doc:
        text = page.get_text("text")

        # Fix hard hyphenation at line breaks: "inter-\nnational" -> "international"
        text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)

        for ln in text.splitlines():
            s = ln.strip()

            # keep blank lines (can help separation)
            if not s:
                lines.append("")
                continue

            # drop simple page numbers
            if re.fullmatch(r'\d{1,4}', s):
                continue

            # drop some common running headers
            if HEADER_FUZZ.match(s):
                continue

            lines.append(ln.rstrip())

    return lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf_path")
    ap.add_argument("--out", default=None)
    ap.add_argument("--start", type=int, default=None, help="start paragraph number (optional)")
    ap.add_argument("--end", type=int, default=None, help="end paragraph number (optional)")
    args = ap.parse_args()

    lines = extract_lines(args.pdf_path)

    # Only attempt lead-in + front-matter stripping when we're extracting from the start
    do_strip = (args.start is None) or (args.start <= 1)

    leadin_lines: List[str] = []
    if do_strip:
        para1_idx = find_para1_line_index(lines)
        if para1_idx is not None:
            leadin_lines = collect_leadin(lines, para1_idx)

    rows: List[Dict] = []
    current_num: Optional[int] = None
    buffer: List[str] = []

    def flush_para() -> None:
        nonlocal buffer, current_num, rows
        if current_num is None:
            buffer = []
            return
        text = " ".join([b.strip() for b in buffer if b.strip()])
        pid = f"para-{current_num:03d}"
        rows.append({
            "id": pid,
            "row_type": "para",
            "label": f"{current_num}.",
            "text_md": text,
            "comment_author": "",
            "comment_title": "",
            "comment_text": "",
            "comment_source": ""
        })
        buffer = []

    for ln in lines:
        s = ln.strip()
        if not s:
            continue

        m = PARA_RE.match(s)
        if m:
            num = int(m.group(1))

            if args.start is not None and num < args.start:
                current_num = None
                buffer = []
                continue
            if args.end is not None and num > args.end:
                break

            flush_para()
            current_num = num
            buffer = [m.group(2)]
            continue

        # headings: always standalone rows (do NOT glue into paragraphs)
        if is_heading(s):
            flush_para()
            rows.append({
                "id": "",
                "row_type": "heading",
                "label": "",
                "text_md": s,
                "comment_author": "",
                "comment_title": "",
                "comment_text": "",
                "comment_source": ""
            })
            continue

        # continuation line
        if current_num is not None:
            buffer.append(s)

    flush_para()

    if do_strip:
        rows = strip_front_matter_keep_leadin(rows, leadin_lines)

    out = args.out or (re.sub(r'\.pdf$', '', args.pdf_path, flags=re.I) + ".csv")
    fieldnames = [
        "id", "row_type", "label", "text_md",
        "comment_author", "comment_title", "comment_text", "comment_source"
    ]
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"Wrote {out} with {len(rows)} rows")


if __name__ == "__main__":
    main()
