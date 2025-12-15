#!/usr/bin/env python3
"""
build_site.py
Convert a CSV (paragraph table + optional comments) into:
- <slug>.html (ILA page)
- <slug>-notes.js (window.NOTES)

CSV expected columns (UTF-8):
id,row_type,label,text_md,comment_author,comment_title,comment_text,comment_source

row_type: heading | para
text_md: markdown-like emphasis (*italic*, **bold**). Converted to <em>/<strong>.
"""
import argparse, csv, html, os, re, json
from collections import defaultdict

def md_to_html(s: str) -> str:
    """Very small Markdown subset: **bold**, *italic*. Escapes everything else."""
    if s is None:
        return ""
    # Escape first
    esc = html.escape(s, quote=False)
    # Bold then italic (non-greedy)
    esc = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', esc)
    esc = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', esc)
    # Preserve double newlines as <br><br> inside notes, but for treaty text keep as spaces
    return esc

def render_rows(rows):
    parts=[]
    for r in rows:
        rid=r['id'].strip()
        rt=(r.get('row_type') or 'para').strip().lower()
        label=(r.get('label') or '').strip()
        text_md=(r.get('text_md') or '').strip()
        if rt=='heading':
            if text_md:
                parts.append(f'<h2 class="mt-6 text-xl font-semibold">{md_to_html(text_md)}</h2>')
            continue
        # Paragraph
        btn = f'<button class="para-btn" data-para="{html.escape(rid)}">{html.escape(label or "¶")}</button>'
        p = f'<p class="para-text">{md_to_html(text_md)}</p>'
        parts.append(f'<div id="{html.escape(rid)}" class="para-row">{btn}{p}</div>')
    return "\n".join(parts)

def build_notes(rows, default_author="Contributor"):
    notes=defaultdict(list)
    for r in rows:
        rid=(r.get('id') or '').strip()
        if not rid:
            continue
        ct=(r.get('comment_text') or '').strip()
        if not ct:
            continue
        author=(r.get('comment_author') or '').strip() or default_author
        title=(r.get('comment_title') or '').strip()
        source=(r.get('comment_source') or '').strip()
        notes[rid].append({"author": author, "title": title, "text": ct, "source": source})
    return dict(notes)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--template", default="template.html")
    ap.add_argument("--title", default="International Law Annotated")
    ap.add_argument("--slug", default=None, help="output base name (without extension)")
    ap.add_argument("--outdir", default="site")
    args=ap.parse_args()

    slug=args.slug or os.path.splitext(os.path.basename(args.csv_path))[0]
    os.makedirs(args.outdir, exist_ok=True)

    # Read CSV (Excel-safe)
    with open(args.csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader=csv.DictReader(f)
        rows=list(reader)

    content_html=render_rows(rows)
    notes=build_notes(rows)

    # Write notes JS
    notes_js_path=os.path.join(args.outdir, f"{slug}-notes.js")
    with open(notes_js_path,"w",encoding="utf-8") as f:
        f.write("window.NOTES = ")
        json.dump(notes, f, ensure_ascii=False, indent=2)
        f.write(";\nwindow.dispatchEvent(new Event('notes:ready'));\n")

    # Fill template placeholders
    with open(args.template,"r",encoding="utf-8") as f:
        tpl=f.read()
    page=tpl.replace("{{TITLE}}", html.escape(args.title))
    page=page.replace("{{NOTES_JS}}", f"{slug}-notes.js")
    page=page.replace("<!-- ILA_CONTENT_PLACEHOLDER -->", content_html)

    html_path=os.path.join(args.outdir, f"{slug}.html")
    with open(html_path,"w",encoding="utf-8") as f:
        f.write(page)

    print(f"Wrote {html_path}")
    print(f"Wrote {notes_js_path}")

if __name__=="__main__":
    main()
