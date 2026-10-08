"""Mechanical migration of local configurations to publishable examples."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sgc-source", type=Path, required=True)
    args = parser.parse_args()
    for company in ("conecta", "compagas", "potigas", "contugas", "sgc"):
        original = ROOT / "config" / "local" / f"{company}.json"
        config = json.loads(original.read_text(encoding="utf-8-sig"))
        if company == "sgc":
            config["template"] = str((args.sgc_source / "plantillas/SGC_original.xlsx").resolve())
            config["reference"] = str((args.sgc_source / "referencia/SGC_aprobada_2020_2025.xlsx").resolve())
            config["output_dir"] = "outputs/sgc"
            config["output_filename"] = "SGC_2020_2025_python.xlsx"
            original.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        example = dict(config)
        example["template"] = f"data/{company}/plantilla.xlsx"
        example["reports"] = {year: f"data/{company}/{Path(path).name}" for year, path in config["reports"].items()}
        example["output_dir"] = f"outputs/{company}"
        example.pop("reference", None)
        (ROOT / "config/examples" / f"{company}.json").write_text(
            json.dumps(example, ensure_ascii=False, indent=2), encoding="utf-8")
    for fixture in (ROOT / "tests/fixtures/sgc").glob("extraccion_*.json"):
        record = json.loads(fixture.read_text(encoding="utf-8"))
        record["path"] = f"data/sgc/Southwest Gas Corporation - informe contable - {record['year']}.pdf"
        fixture.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
