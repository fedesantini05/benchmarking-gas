"""Read-only readiness probe for the future Compagas PDF adapter."""
import argparse
import hashlib
import json
from pathlib import Path
from pypdf import PdfReader


def probe(path, year):
    path = Path(path)
    reader = PdfReader(path)
    page_resources = []
    for page_number, page in enumerate(reader.pages, 1):
        resources = page.get("/Resources") or {}
        fonts = resources.get("/Font") or {}
        objects = resources.get("/XObject") or {}
        page_resources.append({"page": page_number, "fonts": len(fonts), "xobjects": len(objects)})
    image_only = all(item["fonts"] == 0 and item["xobjects"] > 0 for item in page_resources)
    return {"year": year, "path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "pages": len(reader.pages), "page_resources": page_resources,
            "status": "OCR_REQUIRED" if image_only else "EMBEDDED_TEXT_AVAILABLE",
            "next_step": "Instalar/configurar OCR local y validar tablas" if image_only else "Desarrollar parser y conciliaciones"}


def run(config_path):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    reports = [probe(config["reports"][str(year)], year) for year in config["years"]]
    output_dir = (config_path.parent.parent.parent / "outputs/compagas_probe").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "compagas.readiness.json"
    status = "OCR_REQUIRED" if any(r["status"] == "OCR_REQUIRED" for r in reports) else "READY_FOR_PARSER"
    output.write_text(json.dumps({"company": config["company"], "status": status, "reports": reports,
                                  "workbook_created": False,
                                  "note": "Esta prueba no usa ni copia el caso dorado."}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": status, "readiness": str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/companies/compagas_regression.json")
    args = parser.parse_args()
    print(json.dumps(run(args.config), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
