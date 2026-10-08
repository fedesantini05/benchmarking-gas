"""End-to-end deterministic Conecta PDF-to-CIER workbook pipeline."""
import argparse
import json
import re
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from conecta_source import extract_report
from cier_auto import write_workbook, sheet_paths, sha256

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS = {"m": MAIN}
SCALE = 1_000_000


def source_formula(values, *, expense=False):
    terms = [str(abs(int(v))) if expense else str(int(v)) for v in values]
    expression = " + ".join(terms) if terms else "0"
    return f"=-({expression})/{SCALE}" if expense else f"=({expression})/{SCALE}"


def f(record, key):
    return int(record["facts"][key]["value"])


def f0(record, key):
    """Zero only for concepts absent from a complete published table."""
    return int(record["facts"][key]["value"]) if key in record["facts"] else 0


def reconciliation(record):
    reversal = abs(f0(record, "reversal_total"))
    revenue_other = (f(record, "goods_sales") + f(record, "services_sales") + f(record, "tariff_penalties")
                     + f(record, "other_income") + reversal)
    gross_revenue = f(record, "gas_sales") + revenue_other
    pmso = -sum(f(record, f"{name}_{area}") for name in ("personnel", "fees", "services", "rent", "transport", "other")
                for area in ("operations", "commercial", "admin"))
    other_expenses = -(f0(record, "other_cost_total") + f(record, "taxes_total") + f(record, "bad_debt_total")
                       + f(record, "canon_miem") + f(record, "canon_ursea"))
    gross_profit = gross_revenue + f(record, "sales_deductions") - f(record, "gas_purchase_total")
    ebitda = gross_profit + pmso + other_expenses
    ebit = ebitda - f(record, "da_total")
    financial = f(record, "financial_income") + f(record, "financial_expense")
    net = ebit + financial + f(record, "income_tax")
    return {"gross_revenue_UYU": gross_revenue, "gross_profit_UYU": gross_profit,
            "pmso_UYU": pmso, "other_expenses_UYU": other_expenses, "ebitda_UYU": ebitda,
            "ebit_UYU": ebit, "financial_result_UYU": financial, "net_income_UYU": net,
            "ebit_difference_UYU": ebit - f(record, "ebit"),
            "net_income_difference_UYU": net - f(record, "net_income"),
            "assets_difference_UYU": f(record, "assets") - f(record, "liabilities") - f(record, "equity")}


def year_patches(record, col):
    reversal = abs(f0(record, "reversal_total"))
    e = {
        f"{col}2": f"={col}3+{col}13", f"{col}3": source_formula([f(record, "gas_sales")]),
        f"{col}13": source_formula([f(record, "goods_sales"), f(record, "services_sales"),
                                     f(record, "tariff_penalties"), f(record, "other_income"), reversal]),
        f"{col}14": source_formula([f(record, "sales_deductions")]), f"{col}15": f"={col}2+{col}14",
        f"{col}16": source_formula([f(record, "gas_purchase_total")], expense=True), f"{col}17": f"={col}15+{col}16",
        f"{col}18": f"={col}19+{col}23+{col}27+{col}31", f"{col}19": f"={col}20+{col}21+{col}22",
        f"{col}20": source_formula([f(record, "personnel_admin"), f(record, "fees_admin")], expense=True),
        f"{col}21": source_formula([f(record, "personnel_commercial"), f(record, "fees_commercial")], expense=True),
        f"{col}22": source_formula([f(record, "personnel_operations"), f(record, "fees_operations")], expense=True),
        f"{col}23": f"={col}24+{col}25+{col}26",
        f"{col}24": source_formula([f(record, "transport_admin")], expense=True),
        f"{col}25": source_formula([f(record, "transport_commercial")], expense=True),
        f"{col}26": source_formula([f(record, "transport_operations")], expense=True),
        f"{col}27": f"={col}28+{col}29+{col}30",
        f"{col}28": source_formula([f(record, "services_admin"), f(record, "rent_admin")], expense=True),
        f"{col}29": source_formula([f(record, "services_commercial"), f(record, "rent_commercial")], expense=True),
        f"{col}30": source_formula([f(record, "services_operations"), f(record, "rent_operations")], expense=True),
        f"{col}31": f"={col}32+{col}33+{col}34",
        f"{col}32": source_formula([f(record, "other_admin")], expense=True),
        f"{col}33": source_formula([f(record, "other_commercial")], expense=True),
        f"{col}34": source_formula([f(record, "other_operations")], expense=True),
        f"{col}35": f"=SUM({col}36:{col}42)",
        f"{col}36": source_formula([f0(record, "other_cost_total")], expense=True),
        f"{col}37": source_formula([f(record, "taxes_total")], expense=True),
        f"{col}38": source_formula([f(record, "canon_ursea")], expense=True),
        f"{col}39": source_formula([f(record, "canon_miem")], expense=True),
        f"{col}40": source_formula([0], expense=True),
        f"{col}41": source_formula([f(record, "bad_debt_total")], expense=True),
        f"{col}42": source_formula([0], expense=True),
        f"{col}43": f"={col}17+{col}18+{col}35",
        f"{col}44": source_formula([f(record, "da_total")], expense=True), f"{col}45": f"={col}43+{col}44",
        f"{col}46": f"={col}47+{col}48",
        f"{col}47": source_formula([f(record, "interest_income"), f(record, "fx_gain") if "fx_gain" in record["facts"] else 0]),
        f"{col}48": source_formula([f(record, "fx_loss"), f(record, "other_financial_cost")]),
        f"{col}49": f"={col}45+{col}46", f"{col}50": f"={col}51+{col}52",
        f"{col}51": source_formula([0]), f"{col}52": source_formula([f(record, "income_tax")]),
        f"{col}53": f"={col}49+{col}50",
    }
    suppliers = [f(record, "suppliers_foreign"), f(record, "suppliers_local"), f(record, "related_payable")]
    other_current_liabilities = [f(record, key) for key in ("payroll_payable", "tax_payable", "social_payable", "other_payable")
                                 if key in record["facts"]]
    b = {
        f"{col}2": f"={col}3+{col}7", f"{col}3": f"={col}4+{col}5+{col}6",
        f"{col}4": source_formula([f(record, "cash")]), f"{col}5": source_formula([f(record, "receivables_total")]),
        f"{col}6": source_formula([f(record, "inventory")]), f"{col}7": f"={col}8+{col}9",
        f"{col}8": source_formula([f(record, "ppe_net"), f(record, "intangibles_net")]),
        f"{col}9": source_formula([f(record, "deposits")]), f"{col}10": f"={col}11+{col}15",
        f"{col}11": f"={col}12+{col}13+{col}14", f"{col}12": source_formula(suppliers),
        f"{col}13": source_formula([0]), f"{col}14": source_formula(other_current_liabilities),
        f"{col}15": f"={col}16+{col}17", f"{col}16": source_formula([0]),
        f"{col}17": source_formula([f(record, "liabilities_noncurrent")]),
        f"{col}18": f"={col}19+{col}20+{col}21", f"{col}19": source_formula([f(record, "equity")]),
        f"{col}20": source_formula([0]), f"{col}21": source_formula([0]),
        f"{col}26": f"={col}27-{col}28",
        f"{col}27": f"={col}3-{col}4", f"{col}28": f"={col}11-{col}13",
        f"{col}29": f"={col}30-{col}31",
        f"{col}30": source_formula([f(record, "ppe_gross"), f(record, "intangibles_gross")]),
        f"{col}31": source_formula([f(record, "ppe_net"), f(record, "intangibles_net")]),
    }
    return e, b


def notes(records):
    def pages(*keys):
        return "; ".join(f"{r['year']} p. {sorted({r['facts'][k]['page'] for k in keys if k in r['facts']})}" for r in records)
    years = "; ".join(str(r["year"]) for r in records)
    e_obs = {
        "N2": f"{years}: importes en pesos uruguayos convertidos a millones (valor fuente / 1.000.000).",
        "N3": f"{years}: venta de gas total; no se publica apertura monetaria compatible por tipo de cliente.",
        "N13": f"{years}: venta de bienes, servicios, multas tarifarias y reversiones de deterioro cuando corresponden.",
        "N16": f"{years}: compras de gas. Se excluyen canon, depreciaciones, personal y otros costos.",
        "N20": f"{years}: personal y honorarios profesionales, Administración.",
        "N21": f"{years}: personal y honorarios profesionales, Comercial.",
        "N22": f"{years}: personal y honorarios profesionales, Operación y Mantenimiento.",
        "N24": f"{years}: locomoción y transporte, Administración; criterio de continuidad de Conecta.",
        "N25": f"{years}: locomoción y transporte, Comercial; criterio de continuidad de Conecta.",
        "N28": f"{years}: servicios contratados y arrendamientos, Administración.",
        "N29": f"{years}: servicios contratados y arrendamientos, Comercial.",
        "N32": f"{years}: otros gastos, Administración.", "N33": f"{years}: otros gastos, Comercial.",
        "N36": f"{years}: otros costos informados por naturaleza.", "N37": f"{years}: impuestos separados del PMSO.",
        "N38": f"{years}: componente URSEA del canon, separado como tasa regulatoria.",
        "N39": f"{years}: componente MIEM del canon.",
        "N41": f"{years}: deudores incobrables separados del PMSO.",
        "N44": f"{years}: amortizaciones y depreciaciones totales.",
        "N47": f"{years}: intereses y diferencia de cambio ganada cuando corresponde.",
        "N48": f"{years}: diferencia de cambio perdida y otros gastos financieros.",
        "N52": f"{years}: impuesto a la renta con el signo del estado de resultados.",
    }
    e_src = {
        "O2": "Estados financieros originales 2023, 2024 y 2025.",
        "O3": "Nota 11: " + pages("gas_sales"), "O13": "Notas 11, 12 y 14: " + pages("goods_sales", "reversal_total", "other_income"),
        "O16": "Nota 12: " + pages("gas_purchase_total"), "O20": "Nota 12: " + pages("personnel_admin", "fees_admin"),
        "O21": "Nota 12: " + pages("personnel_commercial", "fees_commercial"), "O22": "Nota 12: " + pages("personnel_operations"),
        "O24": "Nota 12: " + pages("transport_admin"), "O25": "Nota 12: " + pages("transport_commercial"),
        "O28": "Nota 12: " + pages("services_admin", "rent_admin"), "O29": "Nota 12: " + pages("services_commercial", "rent_commercial"),
        "O32": "Nota 12: " + pages("other_admin"), "O33": "Nota 12: " + pages("other_commercial"),
        "O36": "Nota 12: " + pages("other_cost_total"), "O37": "Nota 12: " + pages("taxes_total"),
        "O38": "Nota 17: " + pages("canon_ursea"), "O39": "Nota 17: " + pages("canon_miem"),
        "O41": "Nota 12: " + pages("bad_debt_total"), "O44": "Nota 12: " + pages("da_total"),
        "O47": "Nota 15: " + pages("interest_income", "fx_gain"), "O48": "Nota 15: " + pages("fx_loss", "other_financial_cost"),
        "O52": "Estado de resultados: " + pages("income_tax"),
    }
    b_obs = {
        "N2": e_obs["N2"], "N4": f"{years}: efectivo y equivalentes.", "N5": f"{years}: deudores corrientes netos.",
        "N6": f"{years}: inventarios.", "N8": f"{years}: PPE e intangibles netos.", "N9": f"{years}: depósitos en garantía no corrientes.",
        "N12": f"{years}: proveedores del exterior, plaza y partes relacionadas.",
        "N13": f"{years}: no se publican préstamos de corto plazo.",
        "N14": f"{years}: personal, fiscales, cargas sociales y otras deudas corrientes.",
        "N16": f"{years}: no se publican préstamos de largo plazo.", "N17": f"{years}: otras deudas no corrientes.",
        "N19": f"{years}: patrimonio total; no se identifica reserva de valor llave del negocio.",
        "N20": f"{years}: sin reserva de valor llave identificada.", "N21": f"{years}: sin saldo separado después de cargar el patrimonio total en fila 19.",
        "N26": f"{years}: capital de trabajo = fila 27 menos fila 28.",
        "N27": f"{years}: activo corriente menos disponibilidades.", "N28": f"{years}: pasivo corriente menos préstamos de corto plazo.",
        "N29": f"{years}: activo inmovilizado = fila 30 menos fila 31.",
        "N30": f"{years}: costo bruto de PPE más intangibles.", "N31": f"{years}: PPE más intangibles netos.",
    }
    b_src = {
        "O2": "Estados de situación financiera originales 2023, 2024 y 2025.",
        "O4": "Estado de situación financiera: " + pages("cash"), "O5": "Estado de situación financiera: " + pages("receivables_total"),
        "O6": "Estado de situación financiera: " + pages("inventory"), "O8": "Estado de situación y notas 8-9: " + pages("ppe_net", "intangibles_net"),
        "O9": "Estado de situación financiera: " + pages("deposits"), "O12": "Nota 10: " + pages("suppliers_foreign", "suppliers_local", "related_payable"),
        "O13": "Estados de situación financiera: sin préstamos separados.", "O14": "Nota 10: " + pages("payroll_payable", "social_payable", "other_payable"),
        "O16": "Estados de situación financiera: sin préstamos separados.", "O17": "Estado de situación financiera: " + pages("liabilities_noncurrent"),
        "O19": "Estado de situación financiera: " + pages("equity"), "O20": "Estado de situación financiera y nota 18.",
        "O21": "Estado de situación financiera y nota 18.", "O26": "Fórmula CIER solicitada.",
        "O27": "Fórmula CIER solicitada.", "O28": "Fórmula CIER solicitada.", "O29": "Fórmula CIER solicitada.",
        "O30": "Notas 8 y 9: " + pages("ppe_gross", "intangibles_gross"), "O31": "Estado de situación financiera: " + pages("ppe_net", "intangibles_net"),
    }
    return e_obs | e_src, b_obs | b_src


def validate_package(template, output, expected_formulas):
    with ZipFile(template) as before, ZipFile(output) as after:
        if after.testzip() is not None:
            raise ValueError("Paquete XLSX corrupto")
        bpaths, apaths = sheet_paths(before), sheet_paths(after)
        allowed = {bpaths["Estado de Resultados"], bpaths["Balance Patrimonial"], "xl/workbook.xml"}
        changed = [name for name in before.namelist() if before.read(name) != after.read(name)]
        if set(changed) - allowed or bpaths != apaths:
            raise ValueError(f"Cambios fuera de alcance: {set(changed) - allowed}")
        for sheet_name, formulas in expected_formulas.items():
            root = etree.fromstring(after.read(apaths[sheet_name]))
            found = {c.get("r"): "=" + c.findtext("m:f", namespaces=NS)
                     for c in root.xpath("//m:c[m:f]", namespaces=NS)}
            for ref, formula in formulas.items():
                if isinstance(formula, str) and formula.startswith("=") and found.get(ref) != formula:
                    raise ValueError(f"Formula no preservada {sheet_name}!{ref}: {found.get(ref)} != {formula}")
        return {"zip_ok": True, "changed_parts": changed, "formula_checks": sum(len(x) for x in expected_formulas.values())}


def run(config_path):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    template = Path(config["template"])
    records = []
    for year in config["years"]:
        records.append(extract_report(Path(config["reports"][str(year)]), year))
    e_patches, b_patches, recs = {}, {}, []
    for record in records:
        result = reconciliation(record)
        result["year"] = record["year"]
        result["status"] = "PASS" if all(result[k] == 0 for k in ("ebit_difference_UYU", "net_income_difference_UYU", "assets_difference_UYU")) else "FAIL"
        if result["status"] != "PASS":
            raise ValueError(f"Conciliacion CIER fallida: {result}")
        recs.append(result)
        e, b = year_patches(record, config["period_columns"][str(record["year"])])
        e_patches.update(e); b_patches.update(b)
    e_notes, b_notes = notes(records)
    e_patches.update(e_notes); b_patches.update(b_notes)
    output_dir = (config_path.parent.parent.parent / config["output_dir"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / config["output_filename"]
    extraction_path = output_dir / "conecta.extraction.json"
    audit_path = output_dir / "conecta.audit.json"
    write_workbook(template, output, e_patches, b_patches)
    verification = validate_package(template, output, {"Estado de Resultados": e_patches, "Balance Patrimonial": b_patches})
    compact_records = [{k: v for k, v in record.items() if k != "pages"} for record in records]
    extraction_path.write_text(json.dumps({"company": config["company"], "records": compact_records}, ensure_ascii=False, indent=2), encoding="utf-8")
    audit = {"status": "PASS", "mode": "independent_pdf_extraction_python", "template": {"path": str(template), "sha256": sha256(template)},
             "sources": [{"year": r["year"], "path": r["path"], "sha256": r["sha256"]} for r in records],
             "output": {"path": str(output), "sha256": sha256(output)}, "policies": config["policies"],
             "reconciliations": recs, "source_checks": {str(r["year"]): r["checks"] for r in records},
             "source_warnings": {str(r["year"]): r["warnings"] for r in records}, "package": verification,
             "limitations": ["Locomocion y transporte conserva la clasificacion historica de Conecta en Materiales y Suministros."]}
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "PASS", "workbook": str(output), "extraction": str(extraction_path), "audit": str(audit_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/companies/conecta.json")
    args = parser.parse_args()
    print(json.dumps(run(args.config), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
