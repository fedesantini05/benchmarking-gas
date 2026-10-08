"""Independent Southwest Gas Corporation 2020-2025 PDF-to-CIER pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from cier_auto import sha256, sheet_paths, write_workbook
from sgc_source import extract_report

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS = {"m": MAIN}
SCALE = 1_000


def f(record, key):
    return int(record["facts"][key]["value"])


def trace(values, *, expense=False):
    values = [int(v) for v in values]
    parts = []
    for index, value in enumerate(values):
        sign = "-" if value < 0 else ("+" if index else "")
        parts.append(f"{sign}{abs(value)}")
    expression = "".join(parts) or "0"
    return f"=-({expression})/{SCALE}" if expense else f"=({expression})/{SCALE}"


def income_patches(record, col):
    other = f(record, "other_income_deductions")
    revenue_components = [
        f(record, "residential"), f(record, "small_commercial"), f(record, "large_commercial"),
        f(record, "industrial_other"), f(record, "transportation"),
        f(record, "alternative_revenue"), f(record, "other_revenue"),
    ]
    residual = f(record, "gas_operating_revenue") - sum(revenue_components)
    return {
        f"{col}2": f"={col}3+{col}13",
        f"{col}3": f"=SUM({col}4:{col}12)",
        f"{col}4": trace([f(record, "residential")]),
        f"{col}5": trace([f(record, "small_commercial"), f(record, "large_commercial")]),
        f"{col}6": trace([f(record, "industrial_other")]),
        f"{col}12": trace([f(record, "transportation"), f(record, "alternative_revenue"), f(record, "other_revenue"), residual]),
        f"{col}13": trace([other]) if other > 0 else trace([0]),
        f"{col}14": trace([0]),
        f"{col}15": f"={col}2+{col}14",
        f"{col}16": trace([f(record, "gas_cost")], expense=True),
        f"{col}17": f"={col}15+{col}16",
        # No monetary PMSO-by-nature breakdown exists; use the published O&M total.
        f"{col}18": trace([f(record, "operations_maintenance")], expense=True),
        f"{col}35": f"=SUM({col}36:{col}42)",
        f"{col}37": trace([f(record, "taxes_other_income")], expense=True),
        f"{col}43": f"={col}17+{col}18+{col}35",
        f"{col}44": trace([f(record, "da")], expense=True),
        f"{col}45": f"={col}43+{col}44",
        f"{col}46": f"={col}47+{col}48",
        f"{col}47": trace([0]),
        f"{col}48": trace([f(record, "interest_deductions"), abs(other) if other < 0 else 0], expense=True),
        f"{col}49": f"={col}45+{col}46",
        f"{col}50": f"={col}51+{col}52",
        f"{col}51": trace([0]),
        f"{col}52": trace([f(record, "income_tax")], expense=True),
        f"{col}53": f"={col}49+{col}50",
    }


def balance_patches(record, col):
    current_other = [f(record, key) for key in (
        "accrued_utility_revenue", "income_tax_receivable", "deferred_gas_cost_asset",
        "receivable_parent", "inventory", "prepaid_other_current", "held_for_sale")]
    liability_other = [f(record, key) for key in (
        "customer_deposits", "accrued_taxes", "accrued_interest", "deferred_gas_cost_liability",
        "payable_parent", "dividends_declared", "other_current_liabilities")]
    return {
        f"{col}2": f"={col}3+{col}7", f"{col}3": f"={col}4+{col}5+{col}6",
        f"{col}4": trace([f(record, "cash")]), f"{col}5": trace([f(record, "receivables")]),
        f"{col}6": trace(current_other), f"{col}7": f"={col}8+{col}9",
        f"{col}8": trace([f(record, "net_utility_plant"), f(record, "other_property_investments")]),
        f"{col}9": trace([f(record, "goodwill"), f(record, "deferred_other_assets")]),
        f"{col}10": f"={col}11+{col}15", f"{col}11": f"={col}12+{col}13+{col}14",
        f"{col}12": trace([f(record, "suppliers")]),
        f"{col}13": trace([f(record, "current_debt_maturities"), f(record, "short_debt")]),
        f"{col}14": trace(liability_other), f"{col}15": f"={col}16+{col}17",
        f"{col}16": trace([f(record, "long_debt")]),
        f"{col}17": trace([f(record, "deferred_tax_credits"), f(record, "removal_costs"), f(record, "other_long_liabilities")]),
        f"{col}18": f"={col}19+{col}20+{col}21", f"{col}19": trace([f(record, "equity")]),
        f"{col}20": trace([0]), f"{col}21": trace([0]),
        f"{col}23": f"={col}18*1000000/{col}25",
        f"{col}24": f"='Estado de Resultados'!{col}53*1000000/{col}25",
        f"{col}25": f"={f(record, 'shares_thousand')}",
        f"{col}26": f"={col}27-{col}28", f"{col}27": f"={col}3-{col}4",
        f"{col}28": f"={col}11-{col}13", f"{col}29": f"={col}30-{col}31",
        f"{col}30": trace([f(record, "gas_plant_gross"), f(record, "construction_work_progress")]),
        f"{col}31": trace([f(record, "net_utility_plant")]),
    }


def notes(records):
    years = [r["year"] for r in records]
    year_text = ", ".join(str(y) for y in years)
    revenue_sources = "; ".join(f"{r['year']}: nota de ingresos p. {f(r, 'residential') and r['facts']['residential']['page']}" for r in records)
    statement_sources = "; ".join(f"{r['year']}: estado de resultados p. {r['facts']['gas_operating_revenue']['page']}" for r in records)
    balance_sources = "; ".join(f"{r['year']}: balance pp. {r['facts']['cash']['page']}-{r['facts']['cash']['page'] + 1}" for r in records)
    e = {
        "N2": f"{year_text}: valores publicados en miles de USD y convertidos a millones mediante /1.000.",
        "N3": f"{year_text}: ventas de gas calculadas como suma de las categorías de clientes publicadas.",
        "N4": f"{year_text}: clientes residenciales.", "N5": f"{year_text}: clientes comerciales pequeños y grandes.",
        "N6": f"{year_text}: clientes industriales y otros.",
        "N12": f"{year_text}: transporte, programas alternativos y otros ingresos. En 2025 incluye ajuste trazable de 2,1 para conciliar la nota con el estado principal.",
        "N13": "2020-2022: sin otros ingresos positivos; 2023-2025: other income se presenta positivo y se ubica como otros ingresos no operacionales.",
        "N14": f"{year_text}: ingresos regulados presentados netos; sin deducciones sobre ventas separadas.",
        "N16": f"{year_text}: net cost of gas sold, con signo negativo.",
        "N18": f"{year_text}: operations and maintenance se publica como total sin apertura monetaria PMSO por naturaleza; se reemplaza la fórmula del total.",
        "N37": f"{year_text}: taxes other than income taxes, separados del PMSO.",
        "N44": f"{year_text}: depreciation and amortization, con signo negativo.",
        "N48": "2020-2022: interés neto más other deductions; 2023-2025: únicamente interés neto porque other income positivo se presenta en fila 13.",
        "N52": f"{year_text}: income tax expense, con signo negativo.",
    }
    for row in (2, 3, 4, 5, 6, 12): e[f"O{row}"] = revenue_sources if row != 2 else statement_sources
    for row in (13, 14, 16, 18, 37, 44, 48, 52): e[f"O{row}"] = statement_sources
    b = {
        "N2": e["N2"], "N4": f"{year_text}: cash and cash equivalents.",
        "N5": f"{year_text}: accounts receivable, net.",
        "N6": f"{year_text}: restantes activos corrientes publicados.",
        "N8": f"{year_text}: net regulated operations plant más other property and investments.",
        "N9": f"{year_text}: goodwill más deferred charges and other assets.",
        "N12": f"{year_text}: accounts payable.", "N13": f"{year_text}: deuda corriente y vencimientos de largo plazo.",
        "N14": f"{year_text}: restantes pasivos corrientes publicados.",
        "N16": f"{year_text}: long-term debt.", "N17": f"{year_text}: deferred taxes, removal costs y otros pasivos no corrientes.",
        "N19": f"{year_text}: total equity; sin reserva de valor llave informada.",
        "N23": f"{year_text}: patrimonio por mil acciones, calculado.", "N24": f"{year_text}: resultado neto por mil acciones, calculado.",
        "N25": f"{year_text}: 47.482 miles de acciones ordinarias.",
        "N26": f"{year_text}: fila 27 menos fila 28.", "N27": f"{year_text}: activo corriente menos disponibilidades.",
        "N28": f"{year_text}: pasivo corriente menos préstamos de corto plazo.",
        "N29": f"{year_text}: fila 30 menos fila 31.",
        "N30": f"{year_text}: gas plant bruto más construction work in progress.",
        "N31": f"{year_text}: net regulated operations plant.",
    }
    for row in (2,4,5,6,8,9,12,13,14,16,17,19,23,24,25,26,27,28,29,30,31): b[f"O{row}"] = balance_sources
    return e, b


def reconciliation(record):
    other = f(record, "other_income_deductions")
    revenue_sum = sum(f(record, key) for key in ("residential", "small_commercial", "large_commercial", "industrial_other", "transportation", "alternative_revenue", "other_revenue"))
    ebit = f(record, "gas_operating_revenue") + max(other, 0) - f(record, "gas_cost") - f(record, "operations_maintenance") - f(record, "taxes_other_income") - f(record, "da")
    net = ebit - f(record, "interest_deductions") + min(other, 0) - f(record, "income_tax")
    current_assets = f(record, "cash") + f(record, "receivables") + sum(f(record, k) for k in ("accrued_utility_revenue", "income_tax_receivable", "deferred_gas_cost_asset", "receivable_parent", "inventory", "prepaid_other_current", "held_for_sale"))
    current_liabilities = f(record, "suppliers") + f(record, "current_debt_maturities") + f(record, "short_debt") + sum(f(record, k) for k in ("customer_deposits", "accrued_taxes", "accrued_interest", "deferred_gas_cost_liability", "payable_parent", "dividends_declared", "other_current_liabilities"))
    assets = current_assets + f(record, "net_utility_plant") + f(record, "other_property_investments") + f(record, "goodwill") + f(record, "deferred_other_assets")
    liabilities = current_liabilities + f(record, "long_debt") + f(record, "deferred_tax_credits") + f(record, "removal_costs") + f(record, "other_long_liabilities")
    return {
        "year": record["year"], "revenue_note_to_statement": revenue_sum - f(record, "gas_operating_revenue"),
        "net_income_difference": net - f(record, "net_income"), "current_assets_difference": current_assets - f(record, "current_assets"),
        "current_liabilities_difference": current_liabilities - f(record, "current_liabilities"),
        "balance_difference": assets - liabilities - f(record, "equity"),
        "fixed_asset_difference": f(record, "gas_plant_gross") + f(record, "construction_work_progress") - f(record, "net_utility_plant") - f(record, "accumulated_depreciation"),
    }


def validate_package(template, output, expected):
    with ZipFile(template) as before, ZipFile(output) as after:
        if after.testzip() is not None: raise ValueError("Paquete XLSX corrupto")
        before_paths, after_paths = sheet_paths(before), sheet_paths(after)
        allowed = {before_paths["Estado de Resultados"], before_paths["Balance Patrimonial"], "xl/workbook.xml"}
        changed = [name for name in before.namelist() if before.read(name) != after.read(name)]
        if set(changed) - allowed or before_paths != after_paths: raise ValueError(f"Cambios fuera de alcance: {set(changed) - allowed}")
        checks = 0
        for sheet_name, formulas in expected.items():
            root = etree.fromstring(after.read(after_paths[sheet_name]))
            found = {cell.get("r"): "=" + cell.findtext("m:f", namespaces=NS) for cell in root.xpath("//m:c[m:f]", namespaces=NS)}
            for ref, formula_text in formulas.items():
                if isinstance(formula_text, str) and formula_text.startswith("="):
                    checks += 1
                    if found.get(ref) != formula_text: raise ValueError(f"Fórmula no preservada {sheet_name}!{ref}")
        return {"zip_ok": True, "changed_parts": changed, "formula_checks": checks}


def run(config_path):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    template = Path(config["template"])
    records = [extract_report(Path(config["reports"][str(year)]), year) for year in config["years"]]
    reconciliations = [reconciliation(r) for r in records]
    for rec in reconciliations:
        allowed_revenue = -2100 if rec["year"] == 2025 else 0
        if rec["revenue_note_to_statement"] != allowed_revenue or any(rec[k] != 0 for k in rec if k.endswith("difference")):
            raise ValueError(f"Conciliación Southwest Gas fallida: {rec}")
    e_patches, b_patches = {}, {}
    for record in records:
        col = config["period_columns"][str(record["year"])]
        e_patches.update(income_patches(record, col)); b_patches.update(balance_patches(record, col))
    e_notes, b_notes = notes(records); e_patches.update(e_notes); b_patches.update(b_notes)
    output_dir = (config_path.parent.parent.parent / config["output_dir"]).resolve(); output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / config["output_filename"]
    write_workbook(template, output, e_patches, b_patches)
    package = validate_package(template, output, {"Estado de Resultados": e_patches, "Balance Patrimonial": b_patches})
    extraction_path = output_dir / "sgc_2020_2025.extraction.json"; audit_path = output_dir / "sgc_2020_2025.audit.json"
    extraction_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    audit = {"status": "PASS", "mode": "independent_hash_pinned_python", "scope": "Southwest Gas Corporation 2020-2025",
        "template": {"path": str(template), "sha256": sha256(template)},
        "sources": [{"year": r["year"], "path": r["path"], "sha256": r["sha256"]} for r in records],
        "output": {"path": str(output), "sha256": sha256(output)}, "reconciliation": reconciliations, "package": package,
        "warnings": ["2025 nota de ingresos difiere en USD 2,1 millones del estado principal; la fila Otras categorías incluye el ajuste explícito.",
                     "2025 revisa comparativos 2023-2024; la planilla conserva para cada año el valor de su informe original."]}
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "PASS", "workbook": str(output), "audit": str(audit_path), "extraction": str(extraction_path)}
