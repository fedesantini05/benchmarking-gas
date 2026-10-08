"""Read-only discovery for Southwest Gas Corporation annual reports."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader


TERMS = {
    "balance": r"BALANCE SHEETS?|CONSOLIDATED BALANCE SHEETS?",
    "income": r"STATEMENTS? OF INCOME|CONSOLIDATED STATEMENTS? OF INCOME",
    "revenue": r"OPERATING REVENUES?|GAS OPERATING REVENUE",
    "expenses": r"OPERATING EXPENSES?|OPERATING COSTS",
    "financial": r"INTEREST EXPENSE|OTHER INCOME",
    "shares": r"COMMON STOCK|SHARES OUTSTANDING",
    "segments": r"NATURAL GAS DISTRIBUTION|SEGMENT INFORMATION",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()
    pdf = args.pdf.resolve()
    out = Path(__file__).resolve().parents[1] / "tmp" / "sgc"
    out.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(str(pdf))
    pages, hits = [], {name: [] for name in TERMS}
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(f"\n===== PDF PAGE {index} =====\n{text}")
        upper = text.upper()
        for name, pattern in TERMS.items():
            if re.search(pattern, upper):
                hits[name].append(index)
    text_path = out / f"sgc_{args.year}.txt"
    text_path.write_text("".join(pages), encoding="utf-8")
    print(json.dumps({
        "pdf": str(pdf), "sha256": sha256(pdf), "pages": len(reader.pages),
        "text_chars": sum(len(page) for page in pages), "hits": hits,
        "text_output": str(text_path),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
