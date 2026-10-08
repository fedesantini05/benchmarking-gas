"""Independent Potigas 2023-2025 PDF-to-CIER workbook pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from cier_auto import sha256, sheet_paths, write_workbook
from potigas_multiyear_source import extract_report

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS = {"m": MAIN}
SCALE = 1_000


def f(record, key):
    return int(record["facts"].get(key, {"value": 0})["value"])


def formula(values, *, expense=False):
    expression = "+".join(str(abs(int(value))) for value in values) or "0"
    return f"=-({expression})/{SCALE}" if expense else f"=({expression})/{SCALE}"


def income_patches(record, col="K"):
    sales = {
        4: "sales_residential", 5: "sales_commercial", 6: "sales_industrial",
        7: "sales_cogeneration", 10: "sales_automotive", 12: "sales_unbilled",
    }
    patches = {f"{col}{row}": formula([f(record, key)]) for row, key in sales.items()}
    patches.update({
        f"{col}2": f"={col}3+{col}13",
        f"{col}3": f"=SUM({col}4:{col}12)",
        f"{col}13": formula([f(record, key) for key in (
            "service_revenue", "construction_revenue", "other_income_pcld_reversal",
            "other_income_contingency_reversal", "other_income_gas_gain",
            "other_income_penalties", "other_income_other",
        )]),
        f"{col}14": formula([f(record, key) for key in (
            "deduction_returns", "deduction_icms_gnc", "deduction_pis_gnc",
            "deduction_cofins_gnc", "deduction_iss", "deduction_icms_gnv",
            "deduction_pis_gnv", "deduction_cofins_gnv",
        )], expense=True),
        f"{col}15": f"={col}2+{col}14",
        f"{col}16": formula([f(record, "gas_fuel_cost"), f(record, "gas_vehicle_cost"), f(record, "construction_cost")], expense=True),
        f"{col}17": f"={col}15+{col}16",
        f"{col}18": f"={col}19+{col}23+{col}27+{col}31",
        f"{col}19": formula([f(record, "personnel")], expense=True),
        f"{col}23": formula([f(record, "materials")], expense=True),
        f"{col}27": formula([f(record, "third_party_services"), f(record, "rent")], expense=True),
        f"{col}31": f"=-({f(record, 'travel')}+{f(record, 'general_expenses')}+({f(record, 'other_costs')}-{f(record, 'da')}))/{SCALE}",
        f"{col}35": f"=SUM({col}36:{col}42)",
        f"{col}36": formula([f(record, "contingency_expense"), f(record, "penalty_expense"), f(record, "other_operating_expense")], expense=True),
        f"{col}37": formula([f(record, "tax_expense")], expense=True),
        f"{col}41": formula([f(record, "pcld_expense")], expense=True),
        f"{col}43": f"={col}17+{col}18+{col}35",
        f"{col}44": formula([f(record, "da")], expense=True),
        f"{col}45": f"={col}43+{col}44",
        f"{col}46": f"={col}47+{col}48",
        f"{col}47": formula([f(record, "financial_income")]),
        f"{col}48": formula([f(record, "financial_expense")], expense=True),
        f"{col}49": f"={col}45+{col}46",
        f"{col}50": f"={col}51+{col}52",
        f"{col}51": formula([0]),
        f"{col}52": f"=(-{f(record, 'tax_current')}+({f(record, 'tax_deferred')})+{f(record, 'tax_incentive')})/{SCALE}",
        f"{col}53": f"={col}49+{col}50",
    })
    return patches


def balance_patches(record, col="K"):
    return {
        f"{col}2": f"={col}3+{col}7",
        f"{col}3": f"={col}4+{col}5+{col}6",
        f"{col}4": formula([f(record, "cash"), f(record, "financial_investments")]),
        f"{col}5": formula([f(record, "receivables")]),
        f"{col}6": formula([f(record, key) for key in (
            "current_tax_recoverable", "inventory", "commercial_credits", "prepaid", "current_other",
        )]),
        f"{col}7": f"={col}8+{col}9",
        f"{col}8": formula([f(record, "intangibles_net"), f(record, "ppe_net")]),
        f"{col}9": formula([f(record, key) for key in (
            "long_receivables", "deferred_tax_asset", "long_tax_recoverable",
            "judicial_deposits", "long_other", "held_for_sale",
        )]),
        f"{col}10": f"={col}11+{col}15",
        f"{col}11": f"={col}12+{col}13+{col}14",
        f"{col}12": formula([f(record, "suppliers")]),
        f"{col}13": formula([f(record, "short_debt")]),
        f"{col}14": formula([f(record, key) for key in (
            "labor_liabilities", "tax_payable", "dividends_payable", "related_payable",
            "commercial_debits", "current_liability_other",
        )]),
        f"{col}15": f"={col}16+{col}17",
        f"{col}16": formula([f(record, "long_debt")]),
        f"{col}17": formula([f(record, "contingency_provision"), f(record, "noncurrent_liability_other")]),
        f"{col}18": f"={col}19+{col}20+{col}21",
        f"{col}19": formula([f(record, "capital")]),
        f"{col}20": formula([f(record, "profit_reserves")]),
        f"{col}21": formula([f(record, "additional_dividends")]),
        f"{col}23": f"={col}18*1000000/{col}25",
        f"{col}24": f"='Estado de Resultados'!{col}53*1000000/{col}25",
        f"{col}25": f"={f(record, 'shares_thousand')}",
        f"{col}26": f"={col}27-{col}28",
        f"{col}27": f"={col}3-{col}4",
        f"{col}28": f"={col}11-{col}13",
        f"{col}29": f"={col}30-{col}31",
        f"{col}30": formula([f(record, "distribution_assets_gross")]),
        f"{col}31": formula([f(record, "distribution_assets_net")]),
    }


def notes():
    e = {
        "N2": "2023: valores fuente en miles de R$ convertidos a millones (valor / 1.000).",
        "N3": "2023: ventas de gas calculadas como suma de las categorías de clientes publicadas.",
        "N13": "2023: servicios, construcción y otras recetas operacionales positivas, incluidas reversiones.",
        "N14": "2023: devoluciones e impuestos sobre ventas con signo negativo.",
        "N16": "2023: compras de gas combustible y vehicular más costo de construcción; excluye amortización y PMSO.",
        "N19": "2023: personal publicado en gastos generales y administrativos.",
        "N23": "2023: materiales publicados en gastos generales y administrativos.",
        "N27": "2023: servicios de terceros más alquileres.",
        "N31": "2023: viajes, gastos generales y residual exacto de otros costos del CPV neto de amortización.",
        "N36": "2023: provisión de contingencias y penalidad contractual.",
        "N37": "2023: gastos tributarios separados del PMSO.",
        "N41": "2023: provisión de créditos de liquidación dudosa.",
        "N44": "2023: depreciación, amortización y agotamiento.",
        "N47": "2023: ingresos financieros totales.",
        "N48": "2023: gastos financieros totales.",
        "N52": "2023: impuesto corriente más diferido e incentivo fiscal, respetando signos.",
        "O2": "Informe contable Potigás 2023, estados principales pp. 18-19.",
        "O3": "Nota 14, p. 35.", "O13": "Notas 14 y 17, pp. 35 y 37.", "O14": "Nota 14, p. 35.",
        "O16": "Nota 15, p. 36.", "O19": "Nota 16, p. 36.", "O23": "Nota 16, p. 36.",
        "O27": "Nota 16, p. 36.", "O31": "Notas 15-16, p. 36; DVA p. 22.",
        "O36": "Nota 17, p. 37.", "O37": "Estado de resultados, p. 19.", "O41": "Nota 17, p. 37.",
        "O44": "DVA, p. 22; Nota 9, p. 28.", "O47": "Nota 18, p. 37.", "O48": "Nota 18, p. 37.",
        "O52": "Estado de resultados, p. 19; Nota 13, p. 34.",
    }
    b = {
        "N2": e["N2"], "N4": "2023: caja y equivalentes.", "N5": "2023: cuentas a cobrar de clientes.",
        "N6": "2023: restantes activos corrientes.", "N8": "2023: intangibles más activo por derecho de uso.",
        "N9": "2023: realizable a largo plazo más activo no corriente destinado a venta.",
        "N12": "2023: proveedores.", "N13": "2023: deuda de corto plazo.", "N14": "2023: restantes pasivos corrientes.",
        "N16": "2023: deuda de largo plazo.", "N17": "2023: provisiones y restantes pasivos no corrientes.",
        "N19": "2023: capital social.", "N20": "2023: reservas de lucros.", "N21": "2023: dividendos adicionales propuestos.",
        "N23": "2023: patrimonio por mil acciones.", "N24": "2023: resultado neto por mil acciones.",
        "N25": "2023: 4.245 miles de acciones.", "N26": "2023: fila 27 menos fila 28.",
        "N27": "2023: activo corriente menos disponibilidades.", "N28": "2023: pasivo corriente menos deuda de corto plazo.",
        "N29": "2023: fila 30 menos fila 31.", "N30": "2023: costo bruto del intangible de concesión.",
        "N31": "2023: valor neto del intangible de concesión.",
        "O2": "Balance Potigás 2023, p. 18.", "O4": "Balance, p. 18.", "O5": "Balance y Nota 6, pp. 18 y 26.",
        "O6": "Balance, p. 18.", "O8": "Balance y Nota 9, pp. 18 y 28.", "O9": "Balance, p. 18.",
        "O12": "Balance y Nota 10, pp. 18 y 29.", "O13": "Balance y Nota 9.3, pp. 18 y 29.", "O14": "Balance, p. 18.",
        "O16": "Balance y Nota 9.3, pp. 18 y 29.", "O17": "Balance, p. 18.", "O19": "Balance y Nota 12, pp. 18 y 31.",
        "O20": "Balance y Nota 12.3, pp. 18 y 32.", "O21": "Balance y Nota 12.2, pp. 18 y 31-32.",
        "O23": "Fórmula sobre patrimonio y acciones.", "O24": "Fórmula sobre resultado y acciones.", "O25": "Nota 12.4, p. 32.",
        "O26": "Fórmula CIER solicitada.", "O27": "Fórmula CIER solicitada.", "O28": "Fórmula CIER solicitada.",
        "O29": "Fórmula CIER solicitada.", "O30": "Nota 9.1, p. 28.", "O31": "Nota 9.1, p. 28.",
    }
    return e, b


def multiyear_notes():
    e, b = notes()
    e.update({
        "N2": "2023-2025: valores fuente en miles de R$ convertidos a millones (valor / 1.000).",
        "N3": "2023, 2024 y 2025: ventas de gas calculadas como suma de las categorías de clientes publicadas.",
        "N13": "2023-2025: servicios, construcción y otras recetas operacionales positivas, incluidas reversiones.",
        "N14": "2023-2025: devoluciones e impuestos sobre ventas con signo negativo.",
        "N16": "2023-2025: compras de gas combustible y vehicular más costo de construcción; excluye amortización y PMSO.",
        "N19": "2023-2025: personal publicado en gastos generales y administrativos.",
        "N23": "2023-2025: materiales publicados en gastos generales y administrativos.",
        "N27": "2023-2025: servicios de terceros más alquileres.",
        "N31": "2023-2025: viajes, gastos generales y residual exacto de otros costos del CPV neto de depreciación y amortización.",
        "N36": "2023-2025: contingencias, penalidades y otras despesas operacionales negativas.",
        "N37": "2023-2025: gastos tributarios separados del PMSO.",
        "N41": "2023-2025: provisión de créditos de liquidación dudosa.",
        "N44": "2023-2025: depreciación, amortización y agotamiento.",
        "N47": "2023-2025: ingresos financieros totales.",
        "N48": "2023-2025: gastos financieros totales.",
        "N52": "2023-2025: impuesto corriente, diferido e incentivo fiscal, respetando signos.",
        "O2": "2023: estados pp. 18-19. 2024: estados pp. 22-23. 2025: estados pp. 1-2.",
        "O3": "2023: Nota 14 p. 35. 2024: Nota 14 pp. 38-39. 2025: Nota 14 pp. 17-18.",
        "O13": "2023: Notas 14 y 17 pp. 35 y 37. 2024: Notas 14 y 17 pp. 38-40. 2025: Notas 14 y 17 pp. 17-19.",
        "O14": "2023: Nota 14 p. 35. 2024: Nota 14 p. 39. 2025: Nota 14 p. 18.",
        "O16": "2023: Nota 15 p. 36. 2024: Nota 15 p. 40. 2025: Nota 15 p. 18.",
        "O19": "2023: Nota 16 p. 36. 2024: Nota 16 p. 40. 2025: Nota 16 p. 19.",
        "O23": "2023: Nota 16 p. 36. 2024: Nota 16 p. 40. 2025: Nota 16 p. 19.",
        "O27": "2023: Nota 16 p. 36. 2024: Nota 16 p. 40. 2025: Nota 16 p. 19.",
        "O31": "2023: Notas 15-16 p. 36 y DVA p. 22. 2024: Notas 15-16 p. 40 y DVA p. 26. 2025: Notas 15-16 pp. 18-19 y DVA p. 5.",
        "O36": "2023: Nota 17 p. 37. 2024: Nota 17 p. 40. 2025: Nota 17 p. 19.",
        "O37": "2023: estado p. 19. 2024: estado p. 23. 2025: estado p. 2.",
        "O41": "2023: Nota 17 p. 37. 2024: Nota 17 p. 40. 2025: Nota 17 p. 19.",
        "O44": "2023: DVA p. 22. 2024: DVA p. 26. 2025: DVA p. 5.",
        "O47": "2023: Nota 18 p. 37. 2024: Nota 18 pp. 40-41. 2025: Nota 18 p. 19.",
        "O48": "2023: Nota 18 p. 37. 2024: Nota 18 pp. 40-41. 2025: Nota 18 p. 19.",
        "O52": "2023: estado p. 19. 2024: estado p. 23 y Nota 13 p. 38. 2025: estado p. 2 y Nota 13 p. 16.",
    })
    b.update({
        "N2": e["N2"],
        "N4": "2023-2025: caja y equivalentes; en 2025 incluye aplicaciones financieras como disponibilidades.",
        "N5": "2023-2025: cuentas a cobrar de clientes.",
        "N6": "2023-2025: restantes activos corrientes.",
        "N8": "2023-2025: intangibles más activo por derecho de uso.",
        "N9": "2023-2025: realizable a largo plazo más activo no corriente destinado a venta.",
        "N12": "2023-2025: proveedores.", "N13": "2023-2025: deuda de corto plazo.",
        "N14": "2023-2025: restantes pasivos corrientes.", "N16": "2023-2025: deuda de largo plazo.",
        "N17": "2023-2025: provisiones y restantes pasivos no corrientes.",
        "N19": "2023-2025: capital social.", "N20": "2023-2025: reservas de lucros.",
        "N21": "2023-2025: dividendos adicionales propuestos.",
        "N23": "2023-2025: patrimonio por mil acciones.", "N24": "2023-2025: resultado neto por mil acciones.",
        "N25": "2023-2025: 4.245 miles de acciones.", "N26": "2023-2025: fila 27 menos fila 28.",
        "N27": "2023-2025: activo corriente menos disponibilidades.",
        "N28": "2023-2025: pasivo corriente menos deuda de corto plazo.",
        "N29": "2023-2025: fila 30 menos fila 31.",
        "N30": "2023-2025: costo bruto del intangible de concesión.",
        "N31": "2023-2025: valor neto del intangible de concesión.",
        "O2": "2023: Balance p. 18. 2024: Balance p. 22. 2025: Balance p. 1.",
        "O4": "2023: Balance p. 18. 2024: Balance p. 22. 2025: Balance p. 1.",
        "O5": "2023: Balance p. 18. 2024: Balance p. 22. 2025: Balance p. 1.",
        "O6": "2023: Balance p. 18. 2024: Balance p. 22. 2025: Balance p. 1.",
        "O8": "2023: Balance p. 18. 2024: Balance p. 22. 2025: Balance p. 1.",
        "O9": "2023: Balance p. 18. 2024: Balance p. 22. 2025: Balance p. 1.",
        "O12": "2023: Balance p. 18. 2024: Balance p. 22. 2025: Balance p. 1.",
        "O13": "2023: Balance p. 18. 2024: Balance p. 22. 2025: Balance p. 1.",
        "O14": "2023: Balance p. 18. 2024: Balance p. 22. 2025: Balance p. 1.",
        "O16": "2023: Balance p. 18. 2024: Balance p. 22. 2025: Balance p. 1.",
        "O17": "2023: Balance p. 18. 2024: Balance p. 22. 2025: Balance p. 1.",
        "O19": "2023: Balance p. 18. 2024: Balance p. 22. 2025: Balance p. 1.",
        "O20": "2023: Nota 12 p. 32. 2024: Balance p. 22. 2025: Balance p. 1.",
        "O21": "2023: Nota 12 pp. 31-32. 2024: Balance p. 22. 2025: Balance p. 1.",
        "O23": "Fórmula sobre patrimonio y acciones para 2023-2025.",
        "O24": "Fórmula sobre resultado y acciones para 2023-2025.",
        "O25": "2023: Nota 12.4 p. 32. 2024: Nota 12.1 p. 34. 2025: Nota 12.4 p. 15.",
        "O26": "Fórmula CIER solicitada para 2023-2025.", "O27": "Fórmula CIER solicitada para 2023-2025.",
        "O28": "Fórmula CIER solicitada para 2023-2025.", "O29": "Fórmula CIER solicitada para 2023-2025.",
        "O30": "2023: Nota 9.1 p. 28. 2024: Nota 9.1 p. 32. 2025: Nota 9.1 p. 10.",
        "O31": "2023: Nota 9.1 p. 28. 2024: Nota 9.1 p. 32. 2025: Nota 9.1 p. 10.",
    })
    return e, b


def reconciliation(record):
    gross_sales = sum(f(record, key) for key in (
        "sales_residential", "sales_commercial", "sales_industrial",
        "sales_cogeneration", "sales_automotive", "sales_unbilled",
    ))
    other_income = sum(f(record, key) for key in (
        "service_revenue", "construction_revenue", "other_income_pcld_reversal",
        "other_income_contingency_reversal", "other_income_gas_gain",
        "other_income_penalties", "other_income_other",
    ))
    deductions = sum(f(record, key) for key in (
        "deduction_returns", "deduction_icms_gnc", "deduction_pis_gnc",
        "deduction_cofins_gnc", "deduction_iss", "deduction_icms_gnv",
        "deduction_pis_gnv", "deduction_cofins_gnv",
    ))
    direct_cost = f(record, "gas_fuel_cost") + f(record, "gas_vehicle_cost") + f(record, "construction_cost")
    pmso = (f(record, "personnel") + f(record, "materials") + f(record, "third_party_services") + f(record, "rent")
            + f(record, "travel") + f(record, "general_expenses") + f(record, "other_costs") - f(record, "da"))
    other_expenses = (f(record, "tax_expense") + f(record, "contingency_expense") + f(record, "penalty_expense")
                      + f(record, "pcld_expense") + f(record, "other_operating_expense"))
    ebit = gross_sales + other_income - deductions - direct_cost - pmso - other_expenses - f(record, "da")
    pretax = ebit + f(record, "financial_income") - f(record, "financial_expense")
    net = pretax - f(record, "tax_current") + f(record, "tax_deferred") + f(record, "tax_incentive")
    current_assets = sum(f(record, key) for key in (
        "cash", "financial_investments", "receivables", "current_tax_recoverable", "inventory", "commercial_credits", "prepaid", "current_other",
    ))
    noncurrent_assets = sum(f(record, key) for key in (
        "long_receivables", "deferred_tax_asset", "long_tax_recoverable", "judicial_deposits", "long_other",
        "held_for_sale", "ppe_net", "intangibles_net",
    ))
    return {
        "year": record["year"],
        "net_revenue_difference": gross_sales + f(record, "service_revenue") - deductions - f(record, "net_revenue"),
        "ebit_difference": ebit - f(record, "ebit"),
        "pretax_difference": pretax - f(record, "pretax"),
        "net_income_difference": net - f(record, "net_income"),
        "asset_formula_difference": current_assets + noncurrent_assets - f(record, "assets"),
        "balance_difference": f(record, "assets") - f(record, "liabilities") - f(record, "equity"),
    }


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
    records = [extract_report(Path(path), int(year)) for year, path in sorted(config["reports"].items())]
    reconciliations = []
    e_patches, b_patches = {}, {}
    for record in records:
        rec = reconciliation(record)
        rec["status"] = "PASS" if all(value == 0 for key, value in rec.items() if key.endswith("difference")) else "FAIL"
        if rec["status"] != "PASS":
            raise ValueError(f"Conciliación Potigas fallida: {rec}")
        reconciliations.append(rec)
        col = config["period_columns"][str(record["year"])]
        e_patches.update(income_patches(record, col))
        b_patches.update(balance_patches(record, col))
    e_notes, b_notes = multiyear_notes()
    e_patches.update(e_notes)
    b_patches.update(b_notes)
    output_dir = (config_path.parent.parent.parent / config["output_dir"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / config["output_filename"]
    write_workbook(template, output, e_patches, b_patches)
    package = validate_package(template, output, {"Estado de Resultados": e_patches, "Balance Patrimonial": b_patches})
    extraction_path = output_dir / "potigas.extraction.json"
    audit_path = output_dir / "potigas.audit.json"
    extraction_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    audit = {
        "status": "PASS", "mode": "independent_hash_pinned_python", "scope": "Potigas 2023-2025",
        "template": {"path": str(template), "sha256": sha256(template)},
        "sources": [{"year": r["year"], "path": r["path"], "sha256": r["sha256"]} for r in records],
        "output": {"path": str(output), "sha256": sha256(output)},
        "checks": {str(r["year"]): r["checks"] for r in records},
        "warnings": ["2025: aplicaciones financieras se incluyen en disponibilidades para el capital de trabajo."],
        "reconciliation": reconciliations,
        "package": package,
    }
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "PASS", "workbook": str(output), "audit": str(audit_path), "extraction": str(extraction_path)}
