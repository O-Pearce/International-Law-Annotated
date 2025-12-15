#!/usr/bin/env python3
"""
qc.py
Quality checks for extracted CSV (ICJ style para-### ids).
Reports:
- missing paragraph numbers
- duplicates
- suspiciously short/long paragraphs
"""
import argparse, csv, re, statistics

ID_RE=re.compile(r'^para-(\d{3})$')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--min_len", type=int, default=40)
    ap.add_argument("--max_len", type=int, default=2500)
    args=ap.parse_args()

    with open(args.csv_path,"r",encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))

    nums=[]
    seen=set()
    dups=[]
    lengths=[]
    short=[]
    long=[]
    for r in rows:
        rid=(r.get("id") or "").strip()
        m=ID_RE.match(rid)
        if m:
            n=int(m.group(1))
            nums.append(n)
            if rid in seen:
                dups.append(rid)
            seen.add(rid)
            txt=(r.get("text_md") or "")
            L=len(txt.strip())
            lengths.append(L)
            if L and L < args.min_len:
                short.append((rid,L,txt[:120]))
            if L > args.max_len:
                long.append((rid,L,txt[:120]))

    nums_sorted=sorted(nums)
    missing=[]
    if nums_sorted:
        for n in range(nums_sorted[0], nums_sorted[-1]+1):
            if n not in set(nums_sorted):
                missing.append(n)

    print("QC REPORT")
    print(f"Paragraphs detected: {len(nums_sorted)}")
    if nums_sorted:
        print(f"Range: {nums_sorted[0]}–{nums_sorted[-1]}")
    if dups:
        print(f"Duplicates: {dups[:20]}{' ...' if len(dups)>20 else ''}")
    if missing:
        print(f"Missing numbers ({len(missing)}): {missing[:50]}{' ...' if len(missing)>50 else ''}")
    if lengths:
        print(f"Median length: {statistics.median(lengths):.0f} chars")
    if short:
        print(f"Short (<{args.min_len}) examples:")
        for rid,L,preview in short[:10]:
            print(f" - {rid} ({L}): {preview!r}")
    if long:
        print(f"Long (>{args.max_len}) examples:")
        for rid,L,preview in long[:5]:
            print(f" - {rid} ({L}): {preview!r}")

if __name__=="__main__":
    main()
