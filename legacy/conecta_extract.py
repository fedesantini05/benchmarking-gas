"""Independent, read-only PDF extraction pilot. Never reads a completed workbook."""
import argparse
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader

LABELS = (
    "Venta de gas", "Venta de bienes", "Servicios prestados",
    "Ingresos por multas de tarifas", "Descuentos, bonificaciones e impuestos",
)
AMOUNT = r"\(?\d{1,3}(?:\.\d{3})*\)?|-"


def parse_revenue_page(text, year):
    """Require explicit ordered annual headers and exactly two amount columns."""
    if not re.search(rf"Dic-{year % 100:02d}\s+Dic-{(year-1) % 100:02d}", text):
        raise ValueError("REVIEW: encabezados de periodo ausentes o invertidos")
    result = {}
    for label in LABELS:
        matches = re.findall(
            rf"^\s*{re.escape(label)}\s+({AMOUNT})\s+({AMOUNT})\s*$",
            text, re.MULTILINE,
        )
        if len(matches) != 1:
            raise ValueError(f"REVIEW: fila ausente o ambigua: {label}")
        raw, comparative = matches[0]
        if raw == "-":
            raise ValueError(f"REVIEW: guion sin politica de cero: {label}")
        value = int(raw.replace(".", "").replace("(", "-").replace(")", ""))
        result[label] = {"value_source_units": value, "raw": raw,
                         "comparative_raw_control_only": comparative}
    return result


def extract(path, year):
    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    combined = "\n".join(pages)
    if not re.search(r"Conecta\s+S\.?A\.?", combined, re.I):
        raise ValueError("REVIEW: identidad Conecta no encontrada")
    if not re.search(rf"Estados financieros al 31 de diciembre de {year}", combined, re.I):
        raise ValueError("REVIEW: fecha del informe no encontrada")
    candidates = [(i+1, text) for i, text in enumerate(pages)
                  if all(label in text for label in LABELS)]
    if len(candidates) != 1:
        raise ValueError("REVIEW: tabla de ingresos ausente o ambigua")
    page, text = candidates[0]
    values = parse_revenue_page(text, year)
    return {"year": year, "source": str(path.resolve()),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "page": page, "values": values,
            "status": "PARTIAL_EXTRACTION_NOT_WORKBOOK_VALIDATION",
            "pending": ["Validar unidades y alcance", "Extraer gastos y balance",
                        "Conciliar estados", "Mapear y escribir copia Excel"],
            "evidence_page_text": text}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, required=True)
    args = parser.parse_args()
    records = [extract(args.reports_dir / f"Conecta S.A. - informe contable - {year}.pdf", year)
               for year in (2023, 2024, 2025)]
    print(json.dumps(records, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
