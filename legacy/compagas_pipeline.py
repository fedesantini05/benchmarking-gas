"""Independent Compagas PDF-to-CIER workbook pipeline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from cier_auto import sha256, sheet_paths, write_workbook
from compagas_source import extract_report

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS = {"m": MAIN}
SCALE = 1_000  # Source reports are in thousands of BRL; template is millions.


def f(record, key):
    return int(record["facts"][key]["value"])


def formula(values, *, expense=False):
    values = [int(value) for value in values]
    if expense:
        expression = " + ".join(str(abs(value)) for value in values) or "0"
        return f"=-({expression})/{SCALE}"
    expression = " + ".join(str(value) for value in values) or "0"
    return f"=({expression})/{SCALE}"


def historical_split_2025(record):
    """Allocate the undisclosed 2025 admin/commercial bucket using 2023-24 shares."""
    pool = f(record, "admin_commercial")
    material_basis = 788 + 965
    service_basis = (16_909 + 117) + 19_242
    other_basis = 6_086 + 23_212
    total_basis = material_basis + service_basis + other_basis
    return {
        "materials": f"=-({pool}*{material_basis}/{total_basis})/{SCALE}",
        "services": f"=-({pool}*{service_basis}/{total_basis})/{SCALE}",
        "other": f"=-({pool})/{SCALE}-{{col}}23-{{col}}27",
        "basis": {"materials": material_basis, "services": service_basis, "other": other_basis, "total": total_basis},
    }


def income_patches(record, col):
    year = record["year"]
    positive_other = max(f(record, "other_operating_net"), 0)
    other_income = [f(record, "gross_services"), f(record, "construction_revenue"), positive_other]
    if year == 2025:
        sales_deductions = formula([f(record, "sales_deductions")])
    else:
        sales_deductions = formula([
            f(record, "regulatory_revenue_adjustment"), f(record, "icms"),
            f(record, "pis_cofins"), f(record, "iss"),
        ])
    e = {
        f"{col}2": f"={col}3+{col}13",
        f"{col}3": formula([f(record, "gross_gas")]),
        f"{col}13": formula(other_income),
        f"{col}14": sales_deductions,
        f"{col}15": f"={col}2+{col}14",
        f"{col}16": formula([f(record, "gas_cost"), f(record, "construction_cost")], expense=True),
        f"{col}17": f"={col}15+{col}16",
        f"{col}18": f"={col}19+{col}23+{col}27+{col}31",
        f"{col}19": formula([f(record, "personnel")], expense=True),
        f"{col}23": formula([f(record, "materials")], expense=True) if year < 2025 else None,
        f"{col}27": formula([f(record, "third_party_services"), f(record, "rent")], expense=True) if year < 2025 else None,
        f"{col}31": formula([f(record, "general_expenses")], expense=True) if year < 2025 else None,
        f"{col}35": f"=SUM({col}36:{col}42)",
        f"{col}43": f"={col}17+{col}18+{col}35",
        f"{col}44": formula([f(record, "da")], expense=True),
        f"{col}45": f"={col}43+{col}44",
        f"{col}46": f"={col}47+{col}48",
        f"{col}49": f"={col}45+{col}46",
        f"{col}50": f"={col}51+{col}52",
        f"{col}51": formula([0]),
        f"{col}52": formula([f(record, "tax_current"), f(record, "tax_deferred")]),
        f"{col}53": f"={col}49+{col}50",
    }
    if year == 2023:
        e[f"{col}36"] = formula([f(record, "distribution_other"), abs(f(record, "other_operating_net"))], expense=True)
        e[f"{col}37"] = formula([f(record, "taxes_fees")], expense=True)
        e[f"{col}47"] = formula([f(record, "financial_interest_clients"), f(record, "financial_investments")])
        e[f"{col}48"] = formula([f(record, "financial_fx"), f(record, "financial_loans"), f(record, "financial_other")])
    elif year == 2024:
        e[f"{col}36"] = formula([f(record, "distribution_other")], expense=True)
        e[f"{col}37"] = formula([f(record, "taxes_fees")], expense=True)
        e[f"{col}47"] = formula([f(record, "financial_interest_clients"), f(record, "financial_investments")])
        e[f"{col}48"] = formula([f(record, "financial_fx"), f(record, "financial_loans"), f(record, "financial_other")])
    else:
        split = historical_split_2025(record)
        e[f"{col}23"] = split["materials"]
        e[f"{col}27"] = split["services"]
        e[f"{col}31"] = split["other"].format(col=col)
        e[f"{col}47"] = formula([f(record, "financial_income")])
        e[f"{col}48"] = formula([f(record, "financial_expense")])
    return {key: value for key, value in e.items() if value is not None}


def balance_patches(record, col):
    net_distribution_assets = [f(record, "intangibles_net"), f(record, "contract_assets_net"), f(record, "financial_asset")]
    gross_distribution_assets = [f(record, "intangibles_gross"), f(record, "contract_assets_gross"), f(record, "financial_asset")]
    return {
        f"{col}2": f"={col}3+{col}7",
        f"{col}3": f"={col}4+{col}5+{col}6",
        f"{col}4": formula([f(record, "cash")]),
        f"{col}5": formula([f(record, "receivables")]),
        f"{col}6": formula([f(record, "inventory"), f(record, "current_other")]),
        f"{col}7": f"={col}8+{col}9",
        f"{col}8": formula(net_distribution_assets + [f(record, "right_of_use")]),
        f"{col}9": formula([f(record, "noncurrent_other")]),
        f"{col}10": f"={col}11+{col}15",
        f"{col}11": f"={col}12+{col}13+{col}14",
        f"{col}12": formula([f(record, "suppliers")]),
        f"{col}13": formula([f(record, "short_debt")]),
        f"{col}14": formula([f(record, "current_liabilities_other")]),
        f"{col}15": f"={col}16+{col}17",
        f"{col}16": formula([f(record, "long_debt")]),
        f"{col}17": formula([f(record, "noncurrent_liabilities_other")]),
        f"{col}18": f"={col}19+{col}20+{col}21",
        f"{col}19": formula([f(record, "equity")]),
        f"{col}20": formula([0]),
        f"{col}21": formula([0]),
        f"{col}23": f"={col}18*1000000/{col}25",
        f"{col}24": f"='Estado de Resultados'!{col}53*1000000/{col}25",
        f"{col}25": formula([f(record, "shares_thousand")]),
        f"{col}26": f"={col}27-{col}28",
        f"{col}27": f"={col}3-{col}4",
        f"{col}28": f"={col}11-{col}13",
        f"{col}29": f"={col}30-{col}31",
        f"{col}30": formula(gross_distribution_assets),
        f"{col}31": formula(net_distribution_assets),
    }


def reconciliation(record):
    year = record["year"]
    positive_other = max(f(record, "other_operating_net"), 0)
    negative_other = abs(min(f(record, "other_operating_net"), 0))
    gross = f(record, "gross_gas") + f(record, "gross_services") + f(record, "construction_revenue") + positive_other
    if year == 2025:
        deductions = f(record, "sales_deductions")
        materials_services_other = f(record, "admin_commercial")
        taxes_other = 0
    else:
        deductions = sum(f(record, key) for key in ("regulatory_revenue_adjustment", "icms", "pis_cofins", "iss"))
        materials_services_other = f(record, "materials") + f(record, "third_party_services") + f(record, "rent") + f(record, "general_expenses")
        taxes_other = f(record, "taxes_fees") + f(record, "distribution_other") + negative_other
    ebit = (gross + deductions - f(record, "gas_cost") - f(record, "construction_cost")
            - f(record, "personnel") - materials_services_other - taxes_other - f(record, "da"))
    if year == 2025:
        financial = f(record, "financial_income") + f(record, "financial_expense")
    else:
        financial = sum(f(record, key) for key in ("financial_interest_clients", "financial_investments", "financial_fx", "financial_loans", "financial_other"))
    net = ebit + financial + f(record, "tax_current") + f(record, "tax_deferred")
    return {
        "year": year,
        "ebit_thousands_BRL": ebit,
        "ebit_difference": ebit - f(record, "ebit"),
        "pretax_difference": ebit + financial - f(record, "pretax"),
        "net_income_thousands_BRL": net,
        "net_income_difference": net - f(record, "net_income"),
        "assets_difference": f(record, "assets") - f(record, "liabilities") - f(record, "equity"),
        "asset_formula_difference": (
            f(record, "cash") + f(record, "receivables") + f(record, "inventory") + f(record, "current_other")
            + f(record, "intangibles_net") + f(record, "contract_assets_net") + f(record, "right_of_use")
            + f(record, "financial_asset") + f(record, "noncurrent_other") - f(record, "assets")
        ),
    }


def notes(records):
    years = "; ".join(str(record["year"]) for record in records)
    e = {
        "N2": f"{years}: valores fuente en miles de R$ convertidos a millones (valor / 1.000).",
        "N3": f"{years}: venta bruta de gas; no se publica apertura monetaria por tipo de cliente.",
        "N13": "2023: servicios y construcción; 2024-2025: servicios, construcción y otros ingresos operacionales positivos.",
        "N14": "2023-2024: deducciones publicadas. 2025: residual contra la receita operacional líquida por diferencia interna de R$2 mil en Nota 24.",
        "N16": f"{years}: costo de gas y transporte más costo de construcción.",
        "N19": f"{years}: personal total; no se publica apertura funcional compatible.",
        "N23": "2023-2024: materiales publicados. 2025: estimación por participación histórica 2023-2024.",
        "N27": "2023-2024: servicios de terceros más locaciones. 2025: estimación por participación histórica 2023-2024.",
        "N31": "2023: gastos generales; 2024: residual contra el total por diferencia de R$2 mil; 2025: estimación histórica residual.",
        "N36": "2023: otros de distribución más otros resultados operacionales negativos; 2024: distribución de gas y otros.",
        "N37": "2023-2024: tributos y tasas separados del PMSO.",
        "N44": f"{years}: depreciación y amortización informadas por naturaleza.",
        "N47": "2023-2024: intereses de clientes más rendimientos de aplicaciones; 2025: total del estado principal.",
        "N48": "2023-2024: desglose de gastos financieros; 2025: total del estado principal.",
        "N52": f"{years}: impuesto corriente más diferido, respetando signos.",
    }
    e.update({
        "O2": "Informes contables originales 2023 p.1, 2024 p.1 y 2025 p.1.",
        "O3": "Notas de ingresos: 2023 p.4; 2024 p.3; 2025 p.4.",
        "O13": "Estados de resultados y notas de ingresos/otros resultados: 2023 p.1 y p.4; 2024 p.1 y p.3; 2025 p.1 y p.4.",
        "O14": "Notas de ingresos: 2023 p.4; 2024 p.3; 2025 p.4.",
        "O16": "Estados de resultados y costos por naturaleza: 2023 p.1/p.4; 2024 p.1/p.3; 2025 p.1/p.4.",
        "O19": "Costos y gastos por naturaleza: 2023 p.4; 2024 p.3; 2025 p.4.",
        "O23": "2023 p.4; 2024 p.3; 2025 estimación histórica documentada.",
        "O27": "2023 p.4; 2024 p.3; 2025 estimación histórica documentada.",
        "O31": "2023 p.4; 2024 p.3; 2025 estimación histórica documentada.",
        "O36": "Otros resultados y costos por naturaleza: 2023 p.1/p.4; 2024 p.3.",
        "O37": "Costos por naturaleza: 2023 p.4; 2024 p.3.",
        "O44": "Costos por naturaleza: 2023 p.4; 2024 p.3; 2025 p.4.",
        "O47": "Resultado financiero: 2023 p.4; 2024 p.3; 2025 p.1/p.4.",
        "O48": "Resultado financiero: 2023 p.4; 2024 p.3; 2025 p.1/p.4.",
        "O52": "Estados de resultados: 2023 p.1; 2024 p.1; 2025 p.1.",
    })
    b = {
        "N2": e["N2"], "N4": f"{years}: caja y equivalentes.", "N5": f"{years}: cuentas a cobrar de clientes.",
        "N6": f"{years}: inventarios más los restantes activos corrientes.",
        "N8": f"{years}: intangibles, activos de contrato, derecho de uso y activo financiero de concesión.",
        "N9": f"{years}: depósitos y otros recibibles no corrientes. En 2025 incluye residual de R$2 mil para conciliar el total del activo publicado.", "N12": f"{years}: proveedores.",
        "N13": f"{years}: préstamos y debêntures de corto plazo.", "N14": f"{years}: restantes pasivos corrientes.",
        "N16": f"{years}: préstamos y debêntures de largo plazo.", "N17": f"{years}: restantes pasivos no corrientes.",
        "N19": f"{years}: patrimonio total; no se identifica reserva de valor llave.",
        "N23": f"{years}: patrimonio por mil acciones.", "N24": f"{years}: resultado neto por mil acciones.",
        "N25": f"{years}: 33.600 miles de acciones.", "N26": f"{years}: fila 27 menos fila 28.",
        "N27": f"{years}: activo corriente menos disponibilidades.", "N28": f"{years}: pasivo corriente menos deuda de corto plazo.",
        "N29": f"{years}: fila 30 menos fila 31.", "N30": f"{years}: costo bruto de intangibles, contratos y activo financiero de concesión.",
        "N31": f"{years}: valor neto de intangibles, contratos y activo financiero de concesión.",
    }
    b.update({
        "O2": "Balances originales: 2023 p.1; 2024 p.1; 2025 p.1.", "O4": "Balances originales: 2023-2025 p.1.",
        "O5": "Balances originales: 2023-2025 p.1.", "O6": "Balances originales: 2023-2025 p.1.",
        "O8": "Balances originales y notas de concesión/arrendamientos: 2023 p.1/p.3; 2024 p.1/p.3; 2025 p.1/p.3.",
        "O9": "Balances originales: 2023-2025 p.1.", "O12": "Balances originales: 2023-2025 p.1.",
        "O13": "Balances originales: 2023-2025 p.1.", "O14": "Balances originales: 2023-2025 p.1.",
        "O16": "Balances originales: 2023-2025 p.1.", "O17": "Balances originales: 2023-2025 p.1.",
        "O19": "Balances originales: 2023-2025 p.1.", "O23": "Fórmula sobre patrimonio y acciones.",
        "O24": "Fórmula sobre resultado y acciones.", "O25": "Notas de patrimonio: 2023 p.4; 2024 p.3; 2025 p.4.",
        "O26": "Fórmula CIER solicitada.", "O27": "Fórmula CIER solicitada.", "O28": "Fórmula CIER solicitada.",
        "O29": "Fórmula CIER solicitada.", "O30": "Notas de activos de concesión: 2023 p.3; 2024 p.3; 2025 p.3.",
        "O31": "Balances y notas de activos de concesión: 2023 p.1/p.3; 2024 p.1/p.3; 2025 p.1/p.3.",
    })
    return e, b


def validate_package(template, output, expected_formulas):
    with ZipFile(template) as before, ZipFile(output) as after:
        if after.testzip() is not None:
            raise ValueError("Paquete XLSX corrupto")
        before_paths, after_paths = sheet_paths(before), sheet_paths(after)
        allowed = {before_paths["Estado de Resultados"], before_paths["Balance Patrimonial"], "xl/workbook.xml"}
        changed = [name for name in before.namelist() if before.read(name) != after.read(name)]
        if set(changed) - allowed or before_paths != after_paths:
            raise ValueError(f"Cambios fuera de alcance: {set(changed) - allowed}")
        checks = 0
        for sheet_name, formulas in expected_formulas.items():
            root = etree.fromstring(after.read(after_paths[sheet_name]))
            found = {cell.get("r"): "=" + cell.findtext("m:f", namespaces=NS)
                     for cell in root.xpath("//m:c[m:f]", namespaces=NS)}
            for ref, formula_text in formulas.items():
                if isinstance(formula_text, str) and formula_text.startswith("="):
                    checks += 1
                    if found.get(ref) != formula_text:
                        raise ValueError(f"Fórmula no preservada {sheet_name}!{ref}")
        return {"zip_ok": True, "changed_parts": changed, "formula_checks": checks}


def run(config_path):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    template = Path(config["template"])
    records = [extract_report(Path(config["reports"][str(year)]), year) for year in config["years"]]
    e_patches, b_patches, reconciliations = {}, {}, []
    for record in records:
        rec = reconciliation(record)
        rec["status"] = "PASS" if all(rec[key] == 0 for key in ("ebit_difference", "pretax_difference", "net_income_difference", "assets_difference")) else "FAIL"
        if rec["status"] != "PASS":
            raise ValueError(f"Conciliación Compagas fallida: {rec}")
        reconciliations.append(rec)
        col = config["period_columns"][str(record["year"])]
        e_patches.update(income_patches(record, col))
        b_patches.update(balance_patches(record, col))
    e_notes, b_notes = notes(records)
    e_patches.update(e_notes)
    b_patches.update(b_notes)
    output_dir = (config_path.parent.parent.parent / config["output_dir"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / config["output_filename"]
    write_workbook(template, output, e_patches, b_patches)
    package = validate_package(template, output, {"Estado de Resultados": e_patches, "Balance Patrimonial": b_patches})
    extraction = output_dir / "compagas.extraction.json"
    audit_path = output_dir / "compagas.audit.json"
    extraction.write_text(json.dumps({"company": config["company"], "records": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    audit = {
        "status": "PASS", "mode": "independent_hash_pinned_source_tables_python",
        "template": {"path": str(template), "sha256": sha256(template)},
        "sources": [{"year": r["year"], "path": r["path"], "sha256": r["sha256"]} for r in records],
        "output": {"path": str(output), "sha256": sha256(output)}, "policies": config["policies"],
        "reconciliations": reconciliations, "source_checks": {str(r["year"]): r["checks"] for r in records},
        "source_warnings": {str(r["year"]): r["warnings"] for r in records}, "package": package,
        "limitations": ["El adaptador está validado para estos hashes y formatos; un PDF nuevo o modificado se detiene para revisión.",
                        "El desglose PMSO 2025 usa participación histórica combinada 2023-2024 y queda identificado como estimado."],
    }
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "PASS", "workbook": str(output), "extraction": str(extraction), "audit": str(audit_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/companies/compagas.json")
    args = parser.parse_args()
    print(json.dumps(run(args.config), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
