"""Simple local entrypoint. Usage: python run_company.py conecta|compagas"""
import argparse
import json
from pathlib import Path

from conecta_pipeline import run as run_conecta
from compagas_pipeline import run as run_compagas
from potigas_pipeline import run as run_potigas
from sgc_pipeline import run as run_sgc

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="Procesar una empresa CIER con Python local")
    parser.add_argument("company", choices=["conecta", "compagas", "potigas", "sgc"])
    args = parser.parse_args()
    if args.company == "conecta":
        result = run_conecta(ROOT / "config/companies/conecta.json")
    elif args.company == "compagas":
        result = run_compagas(ROOT / "config/companies/compagas.json")
    elif args.company == "potigas":
        result = run_potigas(ROOT / "config/companies/potigas.json")
    else:
        result = run_sgc(ROOT / "config/companies/sgc.json")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
