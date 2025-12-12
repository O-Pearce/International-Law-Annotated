import argparse
import html
import re

import docx

# You can change this if you ever want para-IDs to start from a
# different number (e.g. 50 -> para-50, para-51, ...).
START_ID_DEFAULT = 1


def make_para_html(para_id: str, label: str, text: str) -> str:
    """
    Turn one paragraph into the HTML block used on your site.
    """
    label_esc = html.escape(label)
    text_esc = html.escape(text)
    return (
        '<div id="{pid}">\n'
        '  <div class="grid grid-cols-[6ch_1fr] items-start gap-3">\n'
        '    <button\n'
        '      @click.prevent="copyLink(\'{pid}\')"\n'
        '      class="para-id text-center shrink-0 w-full mt-1 px-2 py-0.5 rounded-md border text-xs text-neutral-700 bg-white hover:bg-neutral-50"\n'
        '      data-para="{pid}"\n'
        '      title="Copy link; hover/click for notes">{label}</button>\n'
        '    <p>{text}</p>\n'
        '  </div>\n'
        '</div>'
    ).format(pid=para_id, label=label_esc, text=text_esc)


def make_heading_html(text: str, level: int = 2) -> str:
    """
    Make an <h2> or <h3> heading, matching your existing pages.
    """
    text_esc = html.escape(text)
    if level == 2:
        # Big article heading
        return '<h2 class="mt-10 font-semibold"><strong>{}</strong></h2>'.format(text_esc)
    else:
        # Smaller sub-heading (e.g. DEFINITIONS *)
        return '<h3 class="mt-4"><strong>{}</strong></h3>'.format(text_esc)


def extract_label_and_text(text: str):
    """
    Detects leading numbering like:
      (1) text
      (a) text
      1. text
      A. text
    Returns (label, rest_of_text) or (None, original_text).

    The visible label is normalised to (1), (2), (a), (b), etc.
    """
    patterns = [
        r"^\((\d+)\)\s+(.*)$",      # (1) text
        r"^\(([a-z])\)\s+(.*)$",    # (a) text
        r"^(\d+)\.\s+(.*)$",        # 1. text
        r"^([A-Z])\.\s+(.*)$",      # A. text
    ]

    for pat in patterns:
        m = re.match(pat, text)
        if m:
            label = m.group(1)
            body = m.group(2)

            # Normalise label appearance
            if label.isdigit() or (len(label) == 1 and label.isalpha()):
                label_str = f"({label})"
            else:
                label_str = label

            return label_str, body

    return None, text


def generate_body(docx_path: str, start_id: int = START_ID_DEFAULT) -> str:
    """
    Read the UNFCCC DOCX and generate the BODY HTML (no <html> / <head>).

    - Preamble paragraphs (The Parties ... Have agreed as follows:) get
      a pilcrow label (¶).
    - Article headings (ARTICLE 1, ARTICLE 2 OBJECTIVE, etc.) become <h2>.
    - DEFINITIONS * becomes an <h3> under Article 1.
    - Other short ALL-CAPS lines (PRINCIPLES, COMMITMENTS, etc.) become <h3>.
    - Normal paragraphs become <div id="para-N"> blocks, with the label:
        * parsed numbering (1), (a), etc. where present; or
        * ¶ as a fallback.
    """
    doc = docx.Document(docx_path)

    para_id_counter = start_id
    output_lines = []

    in_preamble = False
    finished_preamble = False
    last_was_article1 = False

    for p in doc.paragraphs:
        raw = p.text
        text = raw.strip()

        # Skip completely empty lines
        if not text:
            continue

        # Once we’ve finished the preamble, ignore the title repetition
        if finished_preamble and text.startswith("UNITED NATIONS FRAMEWORK CONVENTION ON CLIMATE CHANGE"):
            continue

        # -------------------------
        # 1. Detect start of preamble
        # -------------------------
        if not in_preamble and not finished_preamble:
            # Be slightly fuzzy here in case of minor spacing differences
            if "The Parties to this Convention" in text:
                in_preamble = True
            else:
                # Skip cover page stuff before the preamble
                continue

        # -------------------------
        # 2. Inside the preamble
        # -------------------------
        if in_preamble:
            para_id = f"para-{para_id_counter}"
            para_id_counter += 1
            # All preamble paras use the pilcrow label
            output_lines.append(make_para_html(para_id, "¶", text))

            # Last preamble line
            if text.endswith("Have agreed as follows:"):
                in_preamble = False
                finished_preamble = True
            continue

        # -------------------------
        # 3. After the preamble: articles + body
        # -------------------------

        # ARTICLE 1 (special case: separate DEFINITIONS * line)
        if text == "ARTICLE 1":
            output_lines.append(make_heading_html(text, level=2))
            last_was_article1 = True
            continue

        # DEFINITIONS * line directly under ARTICLE 1
        if last_was_article1 and text == "DEFINITIONS *":
            output_lines.append(make_heading_html(text, level=3))
            last_was_article1 = False
            continue

        # Other article headings (e.g. "ARTICLE 2 OBJECTIVE")
        if text.startswith("ARTICLE ") and text != "ARTICLE 1":
            output_lines.append(make_heading_html(text, level=2))
            last_was_article1 = False
            continue

        # Short ALL-CAPS lines (e.g. "PRINCIPLES", "COMMITMENTS")
        if text.isupper() and len(text.split()) <= 4 and not text.startswith("UNITED NATIONS"):
            output_lines.append(make_heading_html(text, level=3))
            continue

        # Everything else is a normal paragraph of the Convention
        para_id = f"para-{para_id_counter}"
        para_id_counter += 1

        # Try to pull out a visible numbering prefix, else use ¶
        label, clean_text = extract_label_and_text(text)
        if label is None:
            label = "¶"

        output_lines.append(make_para_html(para_id, label, clean_text))

    return "\n".join(output_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate UNFCCC body HTML from DOCX."
    )
    parser.add_argument("docx_path", help="Path to the UNFCCC .docx file")
    parser.add_argument(
        "--start-id",
        type=int,
        default=START_ID_DEFAULT,
        help="Number to start para-IDs from (default 1 gives para-1, para-2, ...)",
    )
    args = parser.parse_args()

    html_body = generate_body(args.docx_path, start_id=args.start_id)
    print(html_body)


if __name__ == "__main__":
    main()
