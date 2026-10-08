"""Read-only discovery for Potigas financial statements."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader


OUT = Path(__file__).resolve().parents[1] / "tmp" / "potigas"
TERMS = {
    "balance": r"BALAN[ÇC]O PATRIMONIAL",
    "income": r"DEMONSTRA[ÇC][ÃA]O DO RESULTADO",
    "revenue": r"RECEITA(?: OPERACIONAL)? L[IÍ]QUIDA|RECEITA BRUTA",
    "nature": r"CUSTOS E DESPESAS|DESPESAS POR NATUREZA",
    "financial": r"RESULTADO FINANCEIRO|RECEITAS FINANCEIRAS",
    "shares": r"CAPITAL SOCIAL|N[ÚU]MERO DE A[ÇC][ÕO]ES",
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
    OUT.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(str(pdf))
    pages = []
    hits = {name: [] for name in TERMS}
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(f"\n===== PDF PAGE {index} =====\n{text}")
        normalized = text.upper()
        for name, pattern in TERMS.items():
            if re.search(pattern, normalized):
                hits[name].append(index)
    text_path = OUT / f"potigas_{args.year}.txt"
    text_path.write_text("".join(pages), encoding="utf-8")
    result = {
        "pdf": str(pdf),
        "sha256": sha256(pdf),
        "pages": len(reader.pages),
        "text_chars": sum(len(page) for page in pages),
        "hits": hits,
        "text_output": str(text_path),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
