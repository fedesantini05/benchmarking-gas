"""Unified local entry point; never invokes AI or downloads documents."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
COMPANIES = ("conecta", "compagas", "potigas", "sgc", "contugas", "efigas", "ecogas_cuyo")


def validate_pilot_config(company, config):
    if set(config['reports']) != {'2023','2024','2025'}:
        raise ValueError(f'{company}: caso revisado exclusivamente para 2023-2025')
    if company=='efigas' and config.get('missing_policy')!='PUBLISHED_TOTALS_WHEN_NO_BREAKDOWN':
        raise ValueError('Efigas requiere la política vigente de totales publicados sin desglose')


def generate_pilot(company, config, output):
    validate_pilot_config(company,config)
    if company=='ecogas_cuyo':
        from spanish_cases.reviewed_southern import build
        return build(company,template=Path(config['template']),
                     reports={int(y):p for y,p in config['reports'].items()},output=output)
    if company=='efigas':
        from spanish_cases.efigas import build
        return build(Path(config['template']),{int(y):p for y,p in config['reports'].items()},output)
    raise ValueError('Verificación aprobada disponible sólo para Ecogas y Efigas')


def resolve_config(config, root=ROOT):
    result = dict(config)
    def absolute(value):
        path = Path(value)
        return str(path.resolve() if path.is_absolute() else (root / path).resolve())
    for key in ("template", "reference", "output_dir"):
        if result.get(key):
            result[key] = absolute(result[key])
    result["reports"] = {year: absolute(path) for year, path in config["reports"].items()}
    return result


def main():
    parser = argparse.ArgumentParser(description="Benchmarking contable local, sin IA")
    parser.add_argument("company", choices=COMPANIES)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--check", action="store_true", help="Revisar archivos sin generar Excel")
    parser.add_argument("--verify-approved", action="store_true", help="Regenerar y comparar con la versión aprobada sin sobrescribirla")
    parser.add_argument("--allow-inactive", action="store_true")
    args = parser.parse_args()
    if args.company == "contugas" and not args.allow_inactive:
        parser.error("Contugas está inactiva. Su reactivación requiere revisar fuentes y períodos.")
    path = args.config or ROOT / "config" / "local" / f"{args.company}.json"
    if not path.is_file():
        parser.error(f"Falta configuración: {path}. Copie el ejemplo de config/examples a config/local.")
    config = resolve_config(json.loads(path.read_text(encoding="utf-8-sig")))
    missing = [p for p in [config["template"], *config["reports"].values()] if not Path(p).is_file()]
    if config.get("reference") and not Path(config["reference"]).is_file():
        missing.append(config["reference"])
    if missing:
        parser.error("Faltan archivos:\n" + "\n".join(missing))
    if args.check:
        print(json.dumps({"status": "FILES_PRESENT", "company": args.company,
                          "reports": list(config["reports"]),
                          "note": "No valida el contenido contable ni genera planillas."}, ensure_ascii=False))
        return
    if args.verify_approved:
        from spanish_cases.regression import verify_approved
        report=verify_approved(args.company,config)
        print(json.dumps(report,ensure_ascii=False))
        raise SystemExit(0 if report['status']=='PASS' else 1)
    output = Path(config["output_dir"]) / config["output_filename"]
    if output.exists() or output.resolve() == Path(config["template"]).resolve():
        parser.error("La salida ya existe o coincide con la plantilla. Elija un nombre nuevo.")
    if args.company in ('efigas','ecogas_cuyo'):
        audit=generate_pilot(args.company,config,output)
        print(json.dumps({"output":audit["output"],"status":audit.get('status','GENERATED')},ensure_ascii=False))
        return
    scripts = {"conecta": "conecta_pipeline.py", "compagas": "compagas_pipeline.py",
               "potigas": "potigas_pipeline.py", "contugas": "cier_auto.py"}
    folder = ROOT / ("sgc" if args.company == "sgc" else "legacy")
    script = folder / ("generar_planilla.py" if args.company == "sgc" else scripts[args.company])
    # The normalized config is local and disposable; sources remain untouched.
    with tempfile.TemporaryDirectory(prefix="benchmarking-config-") as temporary:
        normalized = Path(temporary) / "company.json"
        normalized.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run([sys.executable, str(script), "--config", str(normalized)], cwd=ROOT)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
