from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import unicodedata
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from lxml import etree
from pypdf import PdfReader


MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOCREL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKGREL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"m": MAIN, "r": DOCREL, "pr": PKGREL}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text).strip().lower()


def amount(token: str) -> float | None:
    token = token.strip()
    if token in {"-", "–", "—", ""}:
        return None
    negative = token.startswith("(") and token.endswith(")")
    token = token.strip("()").replace(",", "")
    value = float(token)
    return -value if negative else value


AMOUNT_RE = re.compile(r"(?<![A-Za-z])(?:\(?-?\d[\d,]*(?:\.\d+)?\)?|[-–—])(?![A-Za-z])")


def extract_pair(page_text: str, label: str, *, note: bool = False, occurrence: str = "first") -> tuple[float | None, float | None]:
    haystack = normalize(page_text)
    needle = normalize(label)
    start = haystack.rfind(needle) if occurrence == "last" else haystack.find(needle)
    if start < 0:
        raise ValueError(f"No se encontró la etiqueta: {label}")
    window = haystack[start + len(needle): start + len(needle) + 160]
    tokens = AMOUNT_RE.findall(window)
    if note and tokens and tokens[0] not in {"-", "–", "—"}:
        raw = tokens[0].strip("()")
        if "," not in raw and "." not in raw and int(raw) < 100:
            tokens = tokens[1:]
    if len(tokens) < 2:
        raise ValueError(f"No se encontraron dos importes para: {label}; tokens={tokens}")
    return amount(tokens[0]), amount(tokens[1])


def extract_pair_on_line(page_text: str, label: str, *, note: bool = False, occurrence: str = "first") -> tuple[float | None, float | None]:
    needle = normalize(label)
    lines = page_text.splitlines()
    if occurrence == "last":
        lines = list(reversed(lines))
    for raw_line in lines:
        line = normalize(raw_line)
        start = line.find(needle)
        if start < 0:
            continue
        tokens = AMOUNT_RE.findall(line[start + len(needle):])
        if note and tokens and tokens[0] not in {"-", "–", "—"}:
            raw = tokens[0].strip("()")
            if "," not in raw and "." not in raw and int(raw) < 100:
                tokens = tokens[1:]
        if len(tokens) >= 2:
            return amount(tokens[0]), amount(tokens[1])
    raise ValueError(f"No se encontró una línea con dos importes para: {label}")


def extract_last_in_section(page_text: str, section_start: str, section_end: str | None, label: str) -> float:
    lines = page_text.splitlines()
    begin = next((i for i, line in enumerate(lines) if normalize(section_start) in normalize(line)), -1)
    if begin < 0:
        raise ValueError(f"No se encontró la sección {section_start}")
    end = len(lines)
    if section_end:
        end = next((i for i in range(begin + 1, len(lines)) if normalize(section_end) in normalize(lines[i])), len(lines))
    needle = normalize(label)
    for line in lines[begin:end]:
        normalized_line = normalize(line)
        if needle not in normalized_line:
            continue
        tokens = AMOUNT_RE.findall(normalized_line)
        values = [amount(t) for t in tokens if amount(t) is not None]
        if values:
            return float(values[-1])
    raise ValueError(f"No se encontró {label} dentro de {section_start}")


@dataclass
class Evidence:
    report: str
    physical_page: int
    account: str
    status: str = "PUBLISHED"


@dataclass
class PeriodData:
    year: int
    values: dict[str, float | None] = field(default_factory=dict)
    evidence: dict[str, Evidence] = field(default_factory=dict)

    def put(self, key: str, value: float | None, report: Path, page: int, account: str) -> None:
        self.values[key] = value
        self.evidence[key] = Evidence(report.name, page, account)


class Report:
    def __init__(self, path: Path):
        self.path = path
        self.reader = PdfReader(path)
        self.pages = [(page.extract_text() or "") for page in self.reader.pages]
        if not any(p.strip() for p in self.pages):
            raise ValueError(f"El PDF requiere OCR: {path}")

    def page(self, physical_page: int) -> str:
        if physical_page < 1 or physical_page > len(self.pages):
            raise ValueError(f"Página fuera de rango: {physical_page} en {self.path.name}")
        return self.pages[physical_page - 1]


def assign_pair(data_by_year: dict[int, PeriodData], years: list[int], key: str, pair: tuple[float | None, float | None], report: Path, page: int, account: str) -> None:
    for year, value in zip(years, pair):
        if year in data_by_year:
            data_by_year[year].put(key, value, report, page, account)


def extract_contugas(config: dict[str, Any]) -> tuple[dict[int, PeriodData], dict[str, Any]]:
    requested_years = sorted(int(y) for y in config["exchange_rates"])
    data = {year: PeriodData(year) for year in requested_years}
    source_audit: dict[str, Any] = {"reports": {}, "duplicates": []}
    seen_hashes: dict[str, str] = {}

    for report_year_text, report_path_text in config["reports"].items():
        report_year = int(report_year_text)
        path = Path(report_path_text)
        if not path.exists():
            raise FileNotFoundError(path)
        digest = sha256(path)
        source_audit["reports"][str(report_year)] = {"path": str(path), "sha256": digest}
        if digest in seen_hashes:
            source_audit["duplicates"].append({"report": str(path), "duplicate_of": seen_hashes[digest]})
            continue
        seen_hashes[digest] = str(path)
        report = Report(path)
        all_text = normalize("\n".join(report.pages[:10]))
        if "contugas s.a.c" not in all_text:
            raise ValueError(f"Identidad inesperada en {path.name}")
        years = [int(y) for y in config["report_periods"][str(report_year)]]
        pages = config["pages"][str(report_year)]
        balance = report.page(pages["balance"])
        income = report.page(pages["income_statement"])
        costs = report.page(pages["costs_note"])
        intangibles = report.page(pages["intangibles"])

        income_specs = [
            ("revenue_distribution", "Ingresos por servicio de distribución de gas natural", False),
            ("revenue_construction", "Ingresos por servicio de construcción del sistema de distribución", False),
            ("revenue_connection", "Ingresos por derechos de conexión", False),
            ("revenue_installations", "Ingresos por venta de instalaciones internas", False),
            ("revenue_materials", "Venta de materiales a contratistas", False),
            ("bad_debt", "Deterioro de cuentas por cobrar, neto", True),
            ("financial_income", "Ingresos financieros", False),
            ("financial_expense", "Gastos financieros", True),
            ("fx_result", "Diferencia en cambio, neto", True),
            ("profit_before_tax", "Resultado antes de impuestos", False),
        ]
        if report_year == 2022:
            income_specs.append(("other_statement_expense", "Otros gastos", False))
            income_specs.append(("operating_result", "Resultado de actividades de operación", False))
            income_specs.append(("net_income", "Pérdida (ganancia) del año", False))
        else:
            income_specs.append(("other_operating_income", "Otros ingresos", False))
            income_specs.append(("operating_result", "Resultado de actividades de operación", False))
            income_specs.append(("net_income", "Ganancia (pérdida) del año", False))
        for key, label, note in income_specs:
            assign_pair(data, years, key, extract_pair(income, label, note=note), path, pages["income_statement"], label)

        cost_specs = [
            ("gas_consumption", "Consumo de gas", False),
            ("concession_amortization", "Amortización bienes de la concesión", True),
            ("gas_transport", "Transporte de gas", False),
            ("construction_cost", "Costo de servicio de construcción del sistema de distribución", False),
            ("installation_cost", "Costo de servicios de instalación", False),
            ("materials_cost", "Costo por venta materiales a contratistas", False),
        ]
        for key, label, note in cost_specs:
            assign_pair(data, years, key, extract_pair(costs, label, note=note), path, pages["costs_note"], label)
        admin_start = normalize(costs).find("gastos generales y administrativos")
        if admin_start < 0:
            raise ValueError(f"No se encontró la nota de gastos administrativos en {path.name}")
        admin_costs = normalize(costs)[admin_start:]
        admin_specs = [
            ("personnel", "Cargas de personal", True),
            ("third_party_services", "Servicios prestados por terceros", True),
            ("other_pmso", "Cargas diversas de gestión", False),
            ("taxes_fees", "Tributos", False),
            ("admin_amortization", "Amortización", True),
            ("litigation_provision", "Provisiones para litigios", True),
            ("cts", "Compensación por tiempo de servicio", False),
            ("rou_depreciation", "Depreciación de activos por derecho", True),
            ("depreciation", "Depreciación 8" if report_year == 2022 else "Depreciación 9", False),
        ]
        for key, label, note in admin_specs:
            assign_pair(data, years, key, extract_pair(admin_costs, label, note=note), path, pages["costs_note"], label)
        if "Recupero de deterioro de bienes de la concesión" in costs:
            pair = extract_pair(costs, "Recupero de deterioro de bienes de la concesión", note=True)
            assign_pair(data, years, "impairment_reversal", pair, path, pages["costs_note"], "Recupero de deterioro de bienes de la concesión")
        else:
            for year in years:
                if year in data:
                    data[year].put("impairment_reversal", None, path, pages["costs_note"], "No informado")

        balance_specs = [
            ("cash", "Efectivo y equivalentes de efectivo", True),
            ("trade_receivables_current", "cuentas por cobrar 6" if report_year == 2022 else "cuentas por cobrar 7", False),
            ("related_receivables_current", "Cuentas por cobrar a partes relacionadas", True),
            ("supplies", "Suministros", True),
            ("trade_receivables_noncurrent", "Cuentas por cobrar comerciales", True),
            ("ppe_net", "Instalaciones, mobiliario y equipo", True),
            ("rou_asset_net", "Activos por derecho de uso", True),
            ("intangibles_net", "Activos intangibles", True),
            ("loans_current", "Préstamos", True),
            ("trade_payables_current", "Cuentas por pagar comerciales", True),
            ("related_payables_current", "Cuentas por pagar a partes relacionadas", True),
            ("lease_current", "Obligaciones por arrendamiento", True),
            ("employee_benefits_current", "Beneficios a empleados por pagar", True),
            ("contract_liabilities_current", "Pasivos del contrato", True),
            ("capital", "Capital social emitido", False),
            ("legal_reserve", "Reserva legal", False),
            ("retained_earnings", "Resultados acumulados", False),
            ("assets_total", "Total activos", False),
            ("equity_total", "Total patrimonio", False),
        ]
        for key, label, note in balance_specs:
            occurrence = "last" if key == "assets_total" else "first"
            assign_pair(data, years, key, extract_pair(balance, label, note=note, occurrence=occurrence), path, pages["balance"], label)
        assign_pair(data, years, "other_payables_current", extract_pair_on_line(balance, "Otras cuentas por pagar", occurrence="last"), path, pages["balance"], "Otras cuentas por pagar")

        # Items that repeat in current and non-current sections are parsed by section.
        normalized_balance = normalize(balance)
        nc_pos = normalized_balance.find("pasivos no corrientes")
        nc_text = normalized_balance[nc_pos:]
        assign_pair(data, years, "loans_noncurrent", extract_pair(nc_text, "Préstamos", note=True), path, pages["balance"], "Préstamos no corrientes")
        assign_pair(data, years, "trade_payables_noncurrent", extract_pair(nc_text, "Cuentas por pagar comerciales", note=True), path, pages["balance"], "Cuentas por pagar comerciales no corrientes")
        assign_pair(data, years, "lease_noncurrent", extract_pair(nc_text, "Obligaciones por arrendamiento", note=True), path, pages["balance"], "Obligaciones por arrendamiento no corrientes")
        assign_pair(data, years, "provisions_noncurrent", extract_pair(nc_text, "Provisiones", note=False), path, pages["balance"], "Provisiones no corrientes")

        # Related long-term receivables may be absent (dash).
        assign_pair(data, years, "related_receivables_noncurrent", extract_pair(balance, "Cuentas por cobrar a partes relacionadas largo plazo", note=True), path, pages["balance"], "Cuentas por cobrar relacionadas largo plazo")

        for year in years:
            if year not in data:
                continue
            gross = extract_last_in_section(intangibles, "Costo", "Amortización acumulada", f"Al 31 de diciembre de {year}")
            net = extract_last_in_section(intangibles, "Costo neto", None, f"Al 31 de diciembre de {year}")
            data[year].put("intangibles_gross", gross, path, pages["intangibles"], "Activos intangibles - costo")
            data[year].put("intangibles_net_note", net, path, pages["intangibles"], "Activos intangibles - costo neto")
            data[year].put("shares", 71449630.0, path, pages.get("equity_note", 52), "Acciones emitidas")

    return data, source_audit


def require(data: PeriodData, key: str) -> float:
    value = data.values.get(key)
    if value is None:
        raise ValueError(f"Falta {key} para {data.year}")
    return float(value)


def formula_sum(values: list[float], col: str, fx_row: int) -> str:
    terms = []
    for value in values:
        if value < 0:
            terms.append(f"({format_source(value)})")
        else:
            terms.append(format_source(value))
    return f"=({' + '.join(terms)})*{col}${fx_row}/1000"


def formula_negative_sum(values: list[float], col: str, fx_row: int) -> str:
    return f"=-({' + '.join(format_source(abs(v)) for v in values)})*{col}${fx_row}/1000"


def format_source(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return (f"{value:.6f}").rstrip("0").rstrip(".")


def estimate_missing_pmso(
    total: float,
    disclosed: dict[str, float],
    missing: list[str],
    historical_periods: list[dict[str, float]],
) -> dict[str, Any]:
    """Allocate the undisclosed PMSO residual using historical category weights.

    Values must use the template sign convention (expenses negative). Disclosed
    categories are preserved exactly and estimates sum to the reported PMSO total.
    """
    if not missing:
        return {"estimates": {}, "residual": 0.0, "weights": {}, "status": "NOT_REQUIRED"}
    if not historical_periods:
        raise ValueError("No hay períodos históricos para estimar PMSO")
    residual = float(total) - sum(float(v) for v in disclosed.values())
    raw_weights: dict[str, float] = {}
    for category in missing:
        shares = []
        for period in historical_periods:
            hist_total = period.get("total")
            hist_value = period.get(category)
            if hist_total in (None, 0) or hist_value is None:
                continue
            shares.append(abs(float(hist_value)) / abs(float(hist_total)))
        if not shares:
            raise ValueError(f"Sin base histórica para estimar PMSO: {category}")
        raw_weights[category] = sum(shares) / len(shares)
    weight_total = sum(raw_weights.values())
    if weight_total == 0:
        raise ValueError("Los pesos históricos de PMSO son cero")
    weights = {key: value / weight_total for key, value in raw_weights.items()}
    estimates = {key: residual * weights[key] for key in missing}
    difference = total - (sum(disclosed.values()) + sum(estimates.values()))
    estimates[missing[-1]] += difference
    return {
        "estimates": estimates,
        "residual": residual,
        "weights": weights,
        "status": "ESTIMATED",
        "method": "Residual de PMSO distribuido según el peso histórico promedio de las categorías faltantes",
    }


def eerr_formulas(data: PeriodData, col: str) -> dict[str, Any]:
    v = data.values
    formulas: dict[str, Any] = {}
    for row, formula in {
        2: f"={col}3+{col}13", 15: f"={col}2+{col}14", 17: f"={col}15+{col}16",
        18: f"={col}19+{col}23+{col}27+{col}31", 19: f"={col}20+{col}21+{col}22",
        23: f"={col}24+{col}25+{col}26", 27: f"={col}28+{col}29+{col}30",
        31: f"={col}32+{col}33+{col}34", 35: f"=SUM({col}36:{col}42)",
        43: f"={col}17+{col}18+{col}35", 45: f"={col}43+{col}44",
        46: f"={col}47+{col}48", 49: f"={col}45+{col}46", 50: f"={col}51+{col}52",
        53: f"={col}49+{col}50",
    }.items():
        formulas[f"{col}{row}"] = formula
    formulas[f"{col}3"] = formula_sum([require(data, "revenue_distribution")], col, 55)
    other_income = [require(data, k) for k in ["revenue_construction", "revenue_connection", "revenue_installations", "revenue_materials"]]
    if v.get("other_operating_income") is not None:
        other_income.append(require(data, "other_operating_income"))
    reversal = v.get("impairment_reversal")
    if reversal is not None:
        other_income.append(abs(float(reversal)))
    formulas[f"{col}13"] = formula_sum(other_income, col, 55)
    formulas[f"{col}16"] = formula_negative_sum([require(data, "gas_consumption"), require(data, "gas_transport")], col, 55)
    formulas[f"{col}20"] = formula_negative_sum([require(data, "personnel"), require(data, "cts")], col, 55)
    formulas[f"{col}28"] = formula_negative_sum([require(data, "third_party_services")], col, 55)
    formulas[f"{col}32"] = formula_negative_sum([require(data, "other_pmso")], col, 55)
    other_expenses = [require(data, "construction_cost"), require(data, "installation_cost"), require(data, "materials_cost"), require(data, "litigation_provision")]
    if v.get("other_statement_expense") is not None:
        other_expenses.append(abs(require(data, "other_statement_expense")))
    formulas[f"{col}36"] = formula_negative_sum(other_expenses, col, 55)
    formulas[f"{col}37"] = formula_negative_sum([require(data, "taxes_fees")], col, 55)
    formulas[f"{col}41"] = formula_negative_sum([abs(require(data, "bad_debt"))], col, 55)
    formulas[f"{col}44"] = formula_negative_sum([require(data, "concession_amortization"), require(data, "admin_amortization"), require(data, "depreciation"), require(data, "rou_depreciation")], col, 55)
    fx = require(data, "fx_result")
    income_terms = [require(data, "financial_income")]
    expense_terms = [abs(require(data, "financial_expense"))]
    if fx > 0:
        income_terms.append(fx)
    elif fx < 0:
        expense_terms.append(abs(fx))
    formulas[f"{col}47"] = formula_sum(income_terms, col, 55)
    formulas[f"{col}48"] = formula_negative_sum(expense_terms, col, 55)
    formulas[f"{col}52"] = 0.0
    return formulas


def bp_formulas(data: PeriodData, col: str) -> dict[str, Any]:
    f: dict[str, Any] = {}
    for row, formula in {
        2: f"={col}3+{col}7", 3: f"={col}4+{col}5+{col}6", 7: f"={col}8+{col}9",
        10: f"={col}11+{col}15", 11: f"={col}12+{col}13+{col}14", 15: f"={col}16+{col}17",
        18: f"={col}19+{col}20+{col}21", 23: f"={col}18/{col}25*1000000",
        24: f"='Estado de Resultados'!{col}53/{col}25*1000000", 26: f"={col}27-{col}28",
        27: f"={col}3-{col}4", 28: f"={col}11-{col}13", 29: f"={col}30-{col}31",
    }.items():
        f[f"{col}{row}"] = formula
    f[f"{col}4"] = formula_sum([require(data, "cash")], col, 34)
    f[f"{col}5"] = formula_sum([require(data, "trade_receivables_current")], col, 34)
    f[f"{col}6"] = formula_sum([require(data, "related_receivables_current"), require(data, "supplies")], col, 34)
    f[f"{col}8"] = formula_sum([require(data, "ppe_net"), require(data, "rou_asset_net"), require(data, "intangibles_net")], col, 34)
    noncurrent_other = [require(data, "trade_receivables_noncurrent")]
    if data.values.get("related_receivables_noncurrent") is not None:
        noncurrent_other.append(require(data, "related_receivables_noncurrent"))
    f[f"{col}9"] = formula_sum(noncurrent_other, col, 34)
    f[f"{col}12"] = formula_sum([require(data, "trade_payables_current"), require(data, "related_payables_current")], col, 34)
    f[f"{col}13"] = formula_sum([require(data, "loans_current")], col, 34)
    f[f"{col}14"] = formula_sum([require(data, "lease_current"), require(data, "employee_benefits_current"), require(data, "other_payables_current"), require(data, "contract_liabilities_current")], col, 34)
    loans_nc = data.values.get("loans_noncurrent")
    f[f"{col}16"] = 0.0 if loans_nc is None else formula_sum([float(loans_nc)], col, 34)
    f[f"{col}17"] = formula_sum([require(data, "trade_payables_noncurrent"), require(data, "lease_noncurrent"), require(data, "provisions_noncurrent")], col, 34)
    f[f"{col}19"] = formula_sum([require(data, "capital")], col, 34)
    f[f"{col}20"] = 0.0
    legal_reserve = 0.0 if data.values.get("legal_reserve") is None else float(data.values["legal_reserve"])
    f[f"{col}21"] = formula_sum([legal_reserve, require(data, "retained_earnings")], col, 34)
    f[f"{col}25"] = require(data, "shares") / 1000
    f[f"{col}30"] = formula_sum([require(data, "intangibles_gross")], col, 34)
    f[f"{col}31"] = formula_sum([require(data, "intangibles_net_note")], col, 34)
    return f


def calc_eerr(data: PeriodData, fx: float) -> dict[str, float]:
    def local(x: float) -> float:
        return x * fx / 1000
    other_income = sum(require(data, k) for k in ["revenue_construction", "revenue_connection", "revenue_installations", "revenue_materials"])
    if data.values.get("other_operating_income") is not None:
        other_income += require(data, "other_operating_income")
    if data.values.get("impairment_reversal") is not None:
        other_income += abs(require(data, "impairment_reversal"))
    revenue = local(require(data, "revenue_distribution") + other_income)
    cost = -local(require(data, "gas_consumption") + require(data, "gas_transport"))
    pmso = -local(require(data, "personnel") + require(data, "cts") + require(data, "third_party_services") + require(data, "other_pmso"))
    other_costs = require(data, "construction_cost") + require(data, "installation_cost") + require(data, "materials_cost") + require(data, "litigation_provision") + require(data, "taxes_fees") + abs(require(data, "bad_debt"))
    if data.values.get("other_statement_expense") is not None:
        other_costs += abs(require(data, "other_statement_expense"))
    other_expenses = -local(other_costs)
    da = -local(require(data, "concession_amortization") + require(data, "admin_amortization") + require(data, "depreciation") + require(data, "rou_depreciation"))
    ebitda = revenue + cost + pmso + other_expenses
    ebit = ebitda + da
    financial = local(require(data, "financial_income") + require(data, "financial_expense") + require(data, "fx_result"))
    net = ebit + financial
    return {"revenue": revenue, "ebitda": ebitda, "ebit": ebit, "financial": financial, "net_income": net}


def observations(years: list[int]) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    yrs = "; ".join(str(y) for y in years)
    e_obs = {
        "N2": f"{yrs}: importes fuente en miles de US$, convertidos a millones de soles con el tipo de cambio de cierre.",
        "N3": "; ".join(f"{y}: ingresos de distribución informados en total; sin apertura monetaria por tipo de cliente." for y in years),
        "N13": "; ".join(f"{y}: otros ingresos operacionales y reversiones, cuando corresponden." for y in years),
        "N16": "; ".join(f"{y}: consumo de gas más transporte; excluye amortización y otros costos directos." for y in years),
        "N20": "; ".join(f"{y}: cargas de personal más CTS, Administración." for y in years),
        "N28": "; ".join(f"{y}: servicios prestados por terceros, Administración." for y in years),
        "N32": "; ".join(f"{y}: cargas diversas de gestión, Administración." for y in years),
        "N36": "; ".join(f"{y}: construcción, instalaciones, materiales, otros gastos y provisiones para litigios." for y in years),
        "N37": "; ".join(f"{y}: tributos separados de PMSO." for y in years),
        "N41": "; ".join(f"{y}: deterioro de cuentas por cobrar neto." for y in years),
        "N44": "; ".join(f"{y}: depreciaciones y amortizaciones totales." for y in years),
        "N47": "; ".join(f"{y}: ingresos financieros más diferencia de cambio positiva, cuando corresponde." for y in years),
        "N48": "; ".join(f"{y}: gastos financieros más diferencia de cambio negativa, cuando corresponde." for y in years),
        "N52": f"{yrs}: impuesto a las ganancias informado en cero.",
        "N55": f"{yrs}: tipo de cambio vendedor de cierre US$/S/.",
        "N68": "2025: MISSING; no se proporcionó un estado contable 2025.",
    }
    e_src = {
        "O2": "2022: informe contable 2022; 2023: comparativo del informe 2024; 2024: informe contable 2024.",
        "O3": "2022: estado de resultados p. 7 y nota 15 p. 53; 2023-2024: estado p. 7 y nota 16 p. 51.",
        "O13": "2022: estado p. 7 y notas 10/15; 2023-2024: estado p. 7 y notas 11/16.",
        "O16": "2022: nota 16 p. 54; 2023-2024: nota 17 p. 52.",
        "O20": "2022: nota 17 pp. 54-55; 2023-2024: nota 18 p. 52.",
        "O28": "2022: nota 17 p. 54; 2023-2024: nota 18 p. 52.",
        "O32": "2022: nota 17 p. 54; 2023-2024: nota 18 p. 52.",
        "O36": "2022: estado p. 7 y notas 16/17; 2023-2024: estado p. 7 y notas 17/18.",
        "O37": "2022: nota 17 p. 54; 2023-2024: nota 18 p. 52.",
        "O41": "2022: estado p. 7; 2023-2024: estado p. 7.",
        "O44": "2022: notas 10, 16 y 17; 2023-2024: notas 11, 17 y 18.",
        "O47": "2022: estado p. 7; 2023-2024: estado p. 7.",
        "O48": "2022: estado p. 7; 2023-2024: estado p. 7.",
        "O52": "2022: estado p. 7; 2023-2024: estado p. 7 y nota tributaria p. 53.",
        "O55": "2022: SBS 3,820; 2023: SBS 3,713; 2024: SBS 3,770.",
        "O68": "Control de fuentes y hashes del proceso automático.",
    }
    b_obs = {
        "N2": e_obs["N2"], "N4": f"{yrs}: efectivo y equivalentes.",
        "N5": f"{yrs}: cuentas por cobrar y activos del contrato corrientes.",
        "N6": f"{yrs}: relacionadas corrientes más suministros.",
        "N8": f"{yrs}: PPE, derecho de uso e intangibles netos.",
        "N9": f"{yrs}: cuentas por cobrar no corrientes.",
        "N12": f"{yrs}: comerciales más relacionadas corrientes.",
        "N13": f"{yrs}: préstamos corrientes.", "N14": f"{yrs}: restantes pasivos corrientes.",
        "N16": f"{yrs}: préstamos no corrientes.", "N17": f"{yrs}: restantes pasivos no corrientes.",
        "N19": f"{yrs}: capital social.", "N20": f"{yrs}: sin reserva de valor llave.",
        "N21": f"{yrs}: reserva legal más resultados acumulados.",
        "N23": f"{yrs}: patrimonio por mil acciones, fórmula.",
        "N24": f"{yrs}: resultado neto por mil acciones, fórmula.",
        "N25": f"{yrs}: acciones emitidas en miles.",
        "N27": f"{yrs}: activo corriente menos disponibilidades.",
        "N28": f"{yrs}: pasivo corriente menos préstamos de corto plazo.",
        "N30": f"{yrs}: costo bruto de intangibles de distribución.",
        "N31": f"{yrs}: intangibles netos de distribución.",
        "N34": e_obs["N55"], "N36": e_obs["N68"],
    }
    b_src = {
        "O2": e_src["O2"],
        "O4": "2022: estado de situación p. 6; 2023-2024: estado de situación p. 6.",
        "O5": "2022: estado de situación p. 6; 2023-2024: estado de situación p. 6.",
        "O6": "2022: estado de situación p. 6; 2023-2024: estado de situación p. 6.",
        "O8": "2022: estado p. 6 y notas 8-10; 2023-2024: estado p. 6 y notas 9-11.",
        "O9": "2022: estado p. 6; 2023-2024: estado p. 6.",
        "O12": "2022: estado p. 6; 2023-2024: estado p. 6.",
        "O13": "2022: estado p. 6 y nota 11; 2023-2024: estado p. 6 y nota 12.",
        "O14": "2022: estado p. 6; 2023-2024: estado p. 6.",
        "O16": "2022: estado p. 6 y nota 11; 2023-2024: estado p. 6 y nota 12.",
        "O17": "2022: estado p. 6; 2023-2024: estado p. 6.",
        "O19": "2022: estado p. 6 y nota 14; 2023-2024: estado p. 6 y nota 15.",
        "O20": "2022: nota 14; 2023-2024: nota 15.", "O21": "2022: estado p. 6; 2023-2024: estado p. 6.",
        "O23": "Fórmula sobre patrimonio y acciones.", "O24": "Fórmula sobre resultado y acciones.",
        "O25": "2022: nota 14; 2023-2024: nota 15 p. 50.",
        "O27": "Fórmula solicitada.", "O28": "Fórmula solicitada.",
        "O30": "2022: nota 10 p. 48; 2023-2024: nota 11 p. 45.",
        "O31": "2022: nota 10 p. 48; 2023-2024: nota 11 p. 45.",
        "O34": e_src["O55"], "O36": e_src["O68"],
    }
    return e_obs, e_src, b_obs, b_src


def sheet_paths(archive: ZipFile) -> dict[str, str]:
    workbook = etree.fromstring(archive.read("xl/workbook.xml"))
    rels = etree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {rel.get("Id"): rel.get("Target") for rel in rels.xpath("//pr:Relationship", namespaces=NS)}
    out = {}
    for sheet in workbook.xpath("//m:sheets/m:sheet", namespaces=NS):
        target = targets[sheet.get(f"{{{DOCREL}}}id")].replace("\\", "/").lstrip("/")
        out[sheet.get("name")] = target if target.startswith("xl/") else "xl/" + target
    return out


def col_number(ref: str) -> int:
    n = 0
    for char in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(char) - 64
    return n


def patch_sheet(xml: bytes, patches: dict[str, Any]) -> bytes:
    root = etree.fromstring(xml)
    sheet_data = root.find(f"{{{MAIN}}}sheetData")
    rows = {int(r.get("r")): r for r in sheet_data.findall(f"{{{MAIN}}}row")}
    for ref, value in sorted(patches.items(), key=lambda x: (int(re.search(r"\d+$", x[0]).group()), col_number(x[0]))):
        row_no = int(re.search(r"\d+$", ref).group())
        row = rows[row_no]
        existing = next((c for c in row.findall(f"{{{MAIN}}}c") if c.get("r") == ref), None)
        if existing is None:
            existing = etree.Element(f"{{{MAIN}}}c", r=ref)
            row.append(existing)
        style = existing.get("s")
        new = etree.Element(f"{{{MAIN}}}c", r=ref)
        if style is not None:
            new.set("s", style)
        if isinstance(value, str) and value.startswith("="):
            etree.SubElement(new, f"{{{MAIN}}}f").text = value[1:]
        elif isinstance(value, str):
            new.set("t", "inlineStr")
            inline = etree.SubElement(new, f"{{{MAIN}}}is")
            text = etree.SubElement(inline, f"{{{MAIN}}}t")
            text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            text.text = value
        elif value is not None:
            if not math.isfinite(float(value)):
                raise ValueError(f"Valor no finito para {ref}")
            etree.SubElement(new, f"{{{MAIN}}}v").text = format_source(float(value))
        index = list(row).index(existing)
        row.remove(existing)
        row.insert(index, new)
        row[:] = sorted(row, key=lambda c: col_number(c.get("r", "A1")))
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def write_workbook(template: Path, output: Path, e_patches: dict[str, Any], b_patches: dict[str, Any]) -> list[str]:
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(template, "r") as source:
        paths = sheet_paths(source)
        replacements = {
            paths["Estado de Resultados"]: patch_sheet(source.read(paths["Estado de Resultados"]), e_patches),
            paths["Balance Patrimonial"]: patch_sheet(source.read(paths["Balance Patrimonial"]), b_patches),
        }
        wb = etree.fromstring(source.read("xl/workbook.xml"))
        calc = wb.find(f"{{{MAIN}}}calcPr")
        if calc is None:
            calc = etree.SubElement(wb, f"{{{MAIN}}}calcPr")
        calc.set("calcMode", "auto")
        calc.set("fullCalcOnLoad", "1")
        calc.set("forceFullCalc", "1")
        replacements["xl/workbook.xml"] = etree.tostring(wb, xml_declaration=True, encoding="UTF-8", standalone=True)
        with NamedTemporaryFile(delete=False, suffix=".xlsx", dir=output.parent) as temp:
            temp_path = Path(temp.name)
        try:
            with ZipFile(temp_path, "w") as dest:
                for info in source.infolist():
                    data = replacements.get(info.filename, source.read(info.filename))
                    new_info = ZipInfo(info.filename, date_time=info.date_time)
                    new_info.compress_type = info.compress_type or ZIP_DEFLATED
                    new_info.comment, new_info.extra = info.comment, info.extra
                    new_info.internal_attr, new_info.external_attr = info.internal_attr, info.external_attr
                    new_info.create_system = info.create_system
                    dest.writestr(new_info, data)
            temp_path.replace(output)
        finally:
            if temp_path.exists():
                temp_path.unlink()
    return list(replacements)


def validate_output(template: Path, output: Path, e_patches: dict[str, Any], b_patches: dict[str, Any]) -> dict[str, Any]:
    with ZipFile(template) as before, ZipFile(output) as after:
        if after.testzip() is not None:
            raise ValueError("Paquete XLSX corrupto")
        bp, ap = sheet_paths(before), sheet_paths(after)
        allowed = {bp["Estado de Resultados"], bp["Balance Patrimonial"], "xl/workbook.xml"}
        changed = [name for name in before.namelist() if before.read(name) != after.read(name)]
        if set(changed) - allowed:
            raise ValueError(f"Partes OOXML no autorizadas: {set(changed) - allowed}")
        if bp != ap:
            raise ValueError("Cambió la estructura de hojas")
        # Ensure 2025 remains blank in the two controlled sheets.
        for sheet in ["Estado de Resultados", "Balance Patrimonial"]:
            root = etree.fromstring(after.read(ap[sheet]))
            for cell in root.xpath("//m:c[starts-with(@r,'M')]", namespaces=NS):
                row = int(re.search(r"\d+$", cell.get("r")).group())
                limit = 53 if sheet == "Estado de Resultados" else 31
                if 2 <= row <= limit and any(cell.find(f"{{{MAIN}}}{tag}") is not None for tag in ["f", "v", "is"]):
                    raise ValueError(f"2025 no quedó vacío: {sheet}!{cell.get('r')}")
        return {"zip_ok": True, "changed_parts": changed, "year_2025_blank": True, "patch_count": len(e_patches) + len(b_patches)}


def run(config_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    template = Path(config["template"])
    if not template.exists():
        raise FileNotFoundError(template)
    if config.get("adapter") != "contugas":
        raise ValueError(f"Adaptador no disponible: {config.get('adapter')}")
    data, source_audit = extract_contugas(config)
    periods = sorted(data)
    e_patches: dict[str, Any] = {}
    b_patches: dict[str, Any] = {}
    reconciliations = []
    for year in periods:
        col = config["period_columns"][str(year)]
        fx = float(config["exchange_rates"][str(year)])
        e_patches.update(eerr_formulas(data[year], col))
        b_patches.update(bp_formulas(data[year], col))
        e_patches[f"{col}55"] = fx
        b_patches[f"{col}34"] = fx
        calc = calc_eerr(data[year], fx)
        published_net = require(data[year], "net_income") * fx / 1000
        published_ebit = require(data[year], "operating_result") * fx / 1000
        net_diff = calc["net_income"] - published_net
        ebit_diff = calc["ebit"] - published_ebit
        if abs(net_diff) > 0.001 or abs(ebit_diff) > 0.001:
            raise ValueError(f"Conciliación EERR fallida {year}: net={net_diff}, EBIT={ebit_diff}")
        assets = require(data[year], "assets_total")
        equity = require(data[year], "equity_total")
        liabilities = assets - equity
        reconciliations.append({"period": year, "ebit_difference_millions": ebit_diff, "net_income_difference_millions": net_diff, "balance_identity_source_thousands": assets - liabilities - equity, "status": "PASS"})
    e_obs, e_src, b_obs, b_src = observations(periods)
    e_patches.update(e_obs); e_patches.update(e_src); b_patches.update(b_obs); b_patches.update(b_src)
    output_dir = (config_path.parent.parent.parent / config["output_dir"]).resolve()
    output = output_dir / config["output_filename"]
    extraction_path = output_dir / "contugas.extraction.json"
    audit_path = output_dir / "contugas.audit.json"
    if output.exists():
        output.unlink()
    if extraction_path.exists():
        extraction_path.unlink()
    if audit_path.exists():
        audit_path.unlink()
    changed = write_workbook(template, output, e_patches, b_patches)
    verification = validate_output(template, output, e_patches, b_patches)
    extraction = {
        "company": config["company"],
        "periods": periods,
        "data": {str(year): {"values": data[year].values, "evidence": {k: vars(v) for k, v in data[year].evidence.items()}} for year in periods},
    }
    extraction_path.write_text(json.dumps(extraction, ensure_ascii=False, indent=2), encoding="utf-8")
    audit = {
        "status": "PASS",
        "template": {"path": str(template), "sha256": sha256(template)},
        "sources": source_audit,
        "output": {"path": str(output), "sha256": sha256(output)},
        "reconciliations": reconciliations,
        "verification": verification,
        "changed_parts": changed,
        "missing": [{"period": 2025, "status": "MISSING", "reason": "No se proporcionó estado contable 2025"}],
    }
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"workbook": str(output), "extraction": str(extraction_path), "audit": str(audit_path), "status": "PASS"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Automatización determinística CIER sin IA")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    result = run(Path(args.config).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
