#!/usr/bin/env python3
"""
extract_icj.py
Extract numbered paragraphs + headings from ICJ PDFs into the standard CSV.

Heuristics:
- main paragraphs begin with: <number>. (e.g., "112.")
- headings are lines that look like: "I.", "II.", "A.", "B.", "(a)", etc,
  or are in Title Case and short.

Outputs rows with: id,row_type,label,text_md,comment_author,comment_title,comment_text,comment_source
"""
import argparse, csv, re
from dataclasses import dataclass
from typing import List
import fitz  # PyMuPDF

PARA_RE = re.compile(r'^\s*(\d{1,4})\.\s+(.*\S)\s*$')
ROMAN_RE = re.compile(r'^\s*([IVXLCDM]{1,8})\.\s+(.*\S)\s*$')
LETTER_RE = re.compile(r'^\s*([A-Z])\.\s+(.*\S)\s*$')
SUB_RE = re.compile(r'^\s*\(([a-z0-9ivx]+)\)\s+(.*\S)\s*$')

def is_heading(line: str) -> bool:
    line=line.strip()
    if not line:
        return False
    if ROMAN_RE.match(line) or LETTER_RE.match(line):
        return True
    # Short, looks like a section caption
    if len(line) <= 80 and line == line.title() and not line.endswith('.'):
        return True
    return False

def extract_lines(pdf_path: str) -> List[str]:
    doc = fitz.open(pdf_path)
    lines=[]
    for page in doc:
        text = page.get_text("text")
        # Normalize hard hyphenation at line breaks: "inter-\nnational" -> "international"
        text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
        # Keep line breaks for detection
        for ln in text.splitlines():
            # drop page headers/footers (simple)
            if re.match(r'^\s*\d+\s*$', ln.strip()):
                continue
            lines.append(ln.rstrip())
    return lines

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("pdf_path")
    ap.add_argument("--out", default=None)
    ap.add_argument("--start", type=int, default=None, help="start paragraph number (optional)")
    ap.add_argument("--end", type=int, default=None, help="end paragraph number (optional)")
    args=ap.parse_args()

    lines=extract_lines(args.pdf_path)

    rows=[]
    current_para=None
    current_num=None
    buffer=[]

    def flush_para():
        nonlocal buffer, current_num
        if current_num is None:
            buffer=[]
            return
        text=" ".join([b.strip() for b in buffer if b.strip()])
        pid=f"para-{current_num:03d}"
        rows.append({
            "id": pid,
            "row_type":"para",
            "label": f"{current_num}.",
            "text_md": text,
            "comment_author":"",
            "comment_title":"",
            "comment_text":"",
            "comment_source":""
        })
        buffer=[]

    for ln in lines:
        s=ln.strip()
        m=PARA_RE.match(s)
        if m:
            num=int(m.group(1))
            if args.start is not None and num < args.start:
                current_num=None
                buffer=[]
                continue
            if args.end is not None and num > args.end:
                break
            # new para
            flush_para()
            current_num=num
            buffer=[m.group(2)]
            continue

        # headings between paragraphs
        if is_heading(s) and (args.start is None or (current_num is not None)):
            # flush any ongoing para before heading? usually headings precede paras
            if current_num is None:
                # standalone heading
                rows.append({
                    "id":"",
                    "row_type":"heading",
                    "label":"",
                    "text_md": s,
                    "comment_author":"",
                    "comment_title":"",
                    "comment_text":"",
                    "comment_source":""
                })
            else:
                # treat as part of paragraph if we're inside one
                buffer.append(s)
            continue

        # continuation line
        if current_num is not None:
            if s:
                buffer.append(s)

    flush_para()

    out=args.out or (re.sub(r'\.pdf$', '', args.pdf_path, flags=re.I) + ".csv")
    with open(out, "w", encoding="utf-8", newline="") as f:
        fieldnames=["id","row_type","label","text_md","comment_author","comment_title","comment_text","comment_source"]
        w=csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"Wrote {out} with {len(rows)} rows")

if __name__=="__main__":
    main()
