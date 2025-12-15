# International Law Annotated — Prep Folder

This folder is meant to be **duplicated per new instrument**.

## What you do each time (no tinkering)
1. Put your PDF in the same folder (or reference it by path).
2. Extract to CSV:
   - ICJ judgments/advisory opinions (numbered paragraphs like `112.`):
     ```bash
     python extract_icj.py input.pdf --out instrument.csv
     python qc.py instrument.csv
     ```
3. Add contributor comments in the CSV (Excel/Sheets):
   - Fill `comment_author`, `comment_text`, optional `comment_title`, `comment_source`
   - **Do NOT** change the `id` column.
4. Build the site:
   ```bash
   python build_site.py instrument.csv --title "Instrument Title" --slug instrument --outdir site
   ```
5. Open `site/instrument.html` in a browser (or publish the `site/` directory).

## Files
- `extract_icj.py` — PDF → CSV for ICJ-style documents
- `qc.py` — sanity checks (missing paras, duplicates, weird lengths)
- `build_site.py` — CSV → HTML + notes JS
- `template.html` — your page template; content is injected at `<!-- ILA_CONTENT_PLACEHOLDER -->`

## Notes on formatting
- `text_md` supports a tiny subset:
  - `*italic*` → `<em>`
  - `**bold**` → `<strong>`
- Comments are compiled into `window.NOTES` and `notes:ready` is dispatched.

## Dependencies
- Python 3.10+
- PyMuPDF (`pip install pymupdf`)
