"""Conecta annual PDF adapter. All monetary facts originate in the input PDF.

No completed workbook is imported here. Unknown rows, unsupported periods and
ambiguous matches fail closed. Amounts remain integer UYU until workbook mapping.
"""
from dataclasses import dataclass, asdict
import hashlib
import re
import unicodedata
from pathlib import Path
from pypdf import PdfReader

TOKEN = r"(?:\((?:\d{1,3}(?:\.\d{3})+|\d+)\)|\d{1,3}(?:\.\d{3})+|\d+|-)"
PAIR = re.compile(rf"^(.+?)\s+({TOKEN})\s+({TOKEN})\s*$")


def norm(text):
    text = unicodedata.normalize("NFKD", text)
    return re.sub(r"[^a-z0-9]", "", text.encode("ascii", "ignore").decode().lower())


def amount(raw):
    if not re.fullmatch(TOKEN, raw):
        raise ValueError(f"Importe no reconocido: {raw}")
    return 0 if raw == "-" else int(raw.replace(".", "").replace("(", "-").replace(")", ""))


@dataclass
class Fact:
    value: int
    page: int
    label: str
    raw: str
    comparative: int | None = None
    note: str = ""
    # Dash interpretation is restricted to complete published monetary tables.
    basis: str = "published_current_column"


class Report:
    def __init__(self, path, year):
        if year not in (2023, 2024, 2025):
            raise ValueError("Periodo sin validar para este adaptador: ejecutar primero una nueva prueba")
        self.path, self.year = Path(path), year
        self.pages = [p.extract_text() or "" for p in PdfReader(path).pages]
        self.facts, self.checks, self.warnings = {}, [], []
        first = "\n".join(self.pages[:8])
        if not re.search(r"Conecta\s+S\.?A\.?", first, re.I):
            raise ValueError("REVIEW: entidad legal no coincide con Conecta S.A.")
        if not re.search(rf"Estados financieros al 31 de diciembre de {year}", first, re.I):
            raise ValueError("REVIEW: fecha del informe no coincide")

    def page_with(self, *phrases):
        found = [(i + 1, t) for i, t in enumerate(self.pages)
                 if all(norm(s) in norm(t) for s in phrases)]
        if len(found) != 1:
            raise ValueError(f"REVIEW: pagina ambigua o ausente {phrases}: {[i for i,_ in found]}")
        return found[0]

    def pair(self, key, text, page, label, note="", optional=False):
        found = []
        for line in text.splitlines():
            match = PAIR.fullmatch(line.strip())
            if not match:
                continue
            source_label = re.sub(r"\s+(?:\d{1,2}(?:,\d+)*|#)$", "", match[1])
            source_label = re.sub(r"\s*\((?:Nota|Notas)[^)]*\)", "", source_label)
            if norm(source_label) == norm(label):
                found.append(match)
        if optional and not found:
            return None
        if len(found) != 1:
            raise ValueError(f"REVIEW: {self.year} {key}: {len(found)} coincidencias, pagina {page}")
        m = found[0]
        self.facts[key] = Fact(amount(m[2]), page, label, m[0], amount(m[3]), note,
                               "printed_dash_in_complete_table" if m[2] == "-" else "published_current_column")
        return self.facts[key].value

    def check(self, name, actual, expected, tolerance=1):
        difference = actual - expected
        self.checks.append({"name": name, "difference_UYU": difference,
                            "tolerance_UYU": tolerance, "status": "PASS" if abs(difference) <= tolerance else "FAIL"})
        if abs(difference) > tolerance:
            raise ValueError(f"Conciliacion {self.year} {name}: diferencia {difference} UYU")

    def value(self, key):
        return self.facts[key].value

    def sum(self, *keys):
        return sum(self.value(k) for k in keys)

    def annual_header(self, text):
        if not re.search(rf"Dic-{self.year % 100:02d}\s+Dic-{(self.year - 1) % 100:02d}", text):
            raise ValueError("REVIEW: encabezados anuales ausentes o invertidos")

    def statements(self):
        page, text = self.page_with("TOTAL PASIVO Y PATRIMONIO", "Estado de situación financiera")
        self.annual_header(text)
        if "enpesosuruguayos" not in norm(text):
            raise ValueError("REVIEW: no se confirma presentacion en pesos uruguayos")
        labels = {
            "cash": "Efectivo y equivalentes de efectivo", "receivables_total": "Deudores comerciales y otras cuentas por cobrar",
            "inventory": "Inventarios", "assets_current": "Total Activo Corriente",
            "deposits": "Deudores comerciales y otras cuentas por cobrar LP", "ppe_net": "Propiedades, planta y equipo",
            "intangibles_net": "Activos intangibles", "assets_noncurrent": "Total Activo No Corriente",
            "assets": "TOTAL ACTIVO", "liabilities_current": "Total Pasivo Corriente",
            "liabilities_noncurrent": "Total Pasivo No Corriente", "liabilities": "TOTAL PASIVO",
            "capital": "Capital integrado", "legal_reserve": "Reserva legal", "retained_prior": "Resultado ejercicios anteriores",
            "net_balance": "Resultado del ejercicio", "equity": "TOTAL PATRIMONIO", "liabilities_equity": "TOTAL PASIVO Y PATRIMONIO",
        }
        for key, label in labels.items():
            self.pair(key, text, page, label, "Estado de situacion financiera")
        self.check("activo corriente", self.sum("cash", "receivables_total", "inventory"), self.value("assets_current"))
        self.check("activo no corriente", self.sum("ppe_net", "intangibles_net", "deposits"), self.value("assets_noncurrent"))
        self.check("activo total", self.sum("assets_current", "assets_noncurrent"), self.value("assets"))
        self.check("pasivo total", self.sum("liabilities_current", "liabilities_noncurrent"), self.value("liabilities"))
        self.check("patrimonio", self.sum("capital", "legal_reserve", "retained_prior", "net_balance"), self.value("equity"))
        self.check("identidad patrimonial", self.sum("liabilities", "equity"), self.value("assets"))
        page, text = self.page_with("Estado de resultados por el ejercicio", "Ingresos Operativos Netos")
        self.annual_header(text)
        if "enpesosuruguayos" not in norm(text):
            raise ValueError("REVIEW: unidad de resultados no confirmada")
        labels = {"revenue_net": "Ingresos Operativos Netos", "cogs": "Costo de los Bienes Vendidos y Servicios Prestados",
                  "gross_profit": "RESULTADO BRUTO", "selling_cost": "Gastos de Distribución y Ventas",
                  "admin_cost": "Gastos de Administración", "other_income": "Otros ingresos",
                  "ebit": "RESULTADO OPERATIVO", "financial_income": "Ingresos financieros",
                  "financial_expense": "Costos financieros", "pretax": "RESULTADO ANTES DE IMPUESTOS",
                  "income_tax": "Impuesto a la Renta", "net_income": "RESULTADO DEL PERÍODO"}
        for key, label in labels.items():
            self.pair(key, text, page, label, "Estado de resultados")
        self.check("resultado bruto publicado", self.sum("revenue_net", "cogs"), self.value("gross_profit"))
        self.check("EBIT publicado", self.sum("gross_profit", "selling_cost", "admin_cost", "other_income"), self.value("ebit"))
        self.check("antes de impuestos", self.sum("ebit", "financial_income", "financial_expense"), self.value("pretax"))
        self.check("resultado neto", self.sum("pretax", "income_tax"), self.value("net_income"))
        self.check("resultado contra balance", self.value("net_income"), self.value("net_balance"))

    def revenues(self):
        page, text = self.page_with("Venta de gas", "Descuentos, bonificaciones e impuestos", "Nota 11")
        self.annual_header(text)
        for key, label in {"gas_sales": "Venta de gas", "goods_sales": "Venta de bienes",
                           "services_sales": "Servicios prestados", "tariff_penalties": "Ingresos por multas de tarifas",
                           "sales_deductions": "Descuentos, bonificaciones e impuestos"}.items():
            self.pair(key, text, page, label, "11")
        self.check("nota 11", self.sum("gas_sales", "goods_sales", "services_sales", "tariff_penalties", "sales_deductions"), self.value("revenue_net"))

    def costs(self):
        page, text = self.page_with("Nota 12 - Gastos por naturaleza", "Compras de gas", "Locomoción y transporte")
        # In the embedded table's text stream the annual header follows its total.
        # Restrict to that explicit annual block; never take a first row across years.
        start = re.search(r"^Compras de gas", text, re.M)
        end = re.search(rf"^Dic-{self.year % 100:02d}\s*$", text[start.start():], re.M)
        if not end:
            raise ValueError("REVIEW: limite anual de tabla de costos no identificado")
        block = text[start.start():start.start()+end.start()]
        block = re.sub(r"(Retribuciones personales y cargas sociales)\s*\n\s*", r"\1 ", block)
        aliases = {"Compras de gas": "gas_purchase", "Ganancia por reversión deterioro": "reversal",
                   "Canon MIEM": "canon", "Amortizaciones y depreciaciones": "da", "Otros costos": "other_cost",
                   "Retribuciones personales y cargas sociales": "personnel", "Honorarios profesionales": "fees",
                   "Servicios contratados": "services", "Arrendamientos": "rent", "Impuestos": "taxes",
                   "Deudores incobrables": "bad_debt", "Locomoción y transporte": "transport", "Otros gastos": "other"}
        aliases = {norm(k): v for k, v in aliases.items()}
        seen, published_total = set(), None
        for line in block.splitlines():
            line = line.strip()
            if not line:
                continue
            tokens = line.split()
            if len(tokens) == 4 and all(re.fullmatch(TOKEN, t) for t in tokens):
                if published_total is not None:
                    raise ValueError("REVIEW: total de costos duplicado")
                published_total = [amount(t) for t in tokens]
                continue
            line_no_notes = re.sub(r"\s*\((?:Notas?\s+[^)]*|\*)\)", "", line)
            m = re.fullmatch(rf"(.+?)\s+((?:{TOKEN}\s+){{2,}}{TOKEN})", line_no_notes)
            if not m or norm(m[1]) not in aliases:
                raise ValueError(f"REVIEW: concepto de costos no mapeado: {line}")
            key, raw_values = aliases[norm(m[1])], m[2].split()
            if key in seen:
                raise ValueError(f"REVIEW: costo duplicado {key}")
            seen.add(key)
            basis = "published_table_components"
            if key == "canon" and len(raw_values) == 3 and raw_values[1] == "-" and raw_values[0] == raw_values[2]:
                # 2024/2025 print a blank administration cell. Inspected source layout.
                raw_values.insert(2, "-")
                basis = "blank_admin_cell_in_published_canon_table_checked_by_total"
            if len(raw_values) != 4:
                raise ValueError(f"REVIEW: columnas de costo ambiguas {line}")
            values = [amount(v) for v in raw_values]
            if key != "reversal" and any(v < 0 for v in values):
                raise ValueError(f"REVIEW: reversion nueva en {key}; requiere clasificacion")
            if key == "reversal" and any(v > 0 for v in values):
                raise ValueError("REVIEW: deterioro positivo, no reversion")
            self.check(f"apertura {key}", sum(values[:3]), values[3])
            for column, value in zip(("operations", "commercial", "admin", "total"), values):
                self.facts[f"{key}_{column}"] = Fact(value, page, m[1], line, None, "12", basis)
        required = set(aliases.values()) - {"reversal", "other_cost"}
        if required - seen or published_total is None:
            raise ValueError(f"REVIEW: costos incompletos {required - seen}")
        for column, total in zip(("operations", "commercial", "admin", "total"), published_total):
            self.check(f"suma nota 12 {column}", sum(self.value(f"{k}_{column}") for k in seen), total)
        for column, control in zip(range(3), ("cogs", "selling_cost", "admin_cost")):
            self.check(f"nota 12 contra {control}", -published_total[column], self.value(control))

    def financial(self):
        page, text = self.page_with("Nota 15 - Resultados financieros", "Intereses ganados")
        self.annual_header(text)
        for key, label in {"interest_income": "Intereses ganados", "fx_gain": "Diferencia de cambio ganada",
                           "fx_loss": "Diferencia de cambio perdida", "other_financial_cost": "Otros gastos financieros"}.items():
            self.pair(key, text, page, label, "15", optional=key == "fx_gain")
        income = self.value("interest_income") + (self.value("fx_gain") if "fx_gain" in self.facts else 0)
        self.check("ingresos financieros", income, self.value("financial_income"))
        self.check("gastos financieros", self.sum("fx_loss", "other_financial_cost"), self.value("financial_expense"))

    def canon_split(self):
        page, text = self.page_with("Canon", "Ministerio de Industria Energía y Minería (MIEM)",
                                    "Unidad de Regulación Servicios de Energía y Agua (URSEA)")
        blocks = re.findall(r"(?:^|\n)Canon\s*\n(.+?)(?=\nGastos refacturados por)", text, re.S)
        if len(blocks) != 1:
            raise ValueError("REVIEW: apertura anual del canon ambigua")
        block = blocks[0]
        self.pair("canon_miem", block, page, "Ministerio de Industria Energía y Minería (MIEM)", "17")
        self.pair("canon_ursea", block, page, "Unidad de Regulación Servicios de Energía y Agua (URSEA)", "17")
        self.check("apertura canon", self.sum("canon_miem", "canon_ursea"), self.value("canon_total"))

    def asset_notes(self):
        for key, heading, split in [("ppe_gross", "Nota 8 - Propiedades, planta y equipo", "Depreciación y pérdida"),
                                    ("intangibles_gross", "Nota 9 - Activos intangibles", "Amortización y pérdidas")]:
            page, text = self.page_with(heading, "Costo", "Saldos al")
            cost = text.split("Costo", 1)[1].split(split, 1)[0]
            rows = re.findall(rf"^Saldos al 31\s+de diciembre de {self.year}\s+(.+)$", cost, re.M)
            if len(rows) != 1:
                raise ValueError(f"REVIEW: cierre bruto {key} ambiguo")
            tokens = rows[0].split()
            if not all(re.fullmatch(TOKEN, t) for t in tokens):
                raise ValueError(f"REVIEW: formato bruto {key}")
            vals = [amount(t) for t in tokens]
            self.check(key, sum(vals[:-1]), vals[-1])
            self.facts[key] = Fact(vals[-1], page, f"Costo al cierre {self.year}", rows[0], None, "8" if key == "ppe_gross" else "9")

    def balance_notes(self):
        page, text = self.page_with("Nota 6 - Deudores comerciales", "Deudores simples plaza")
        self.annual_header(text)
        receivable_labels = {"receivable_customers": "Deudores simples plaza", "receivable_related": "Partes relacionadas",
                             "receivable_documents": "Documentos a cobrar", "tax_credits": "Créditos fiscales",
                             "supplier_advances": "Anticipos a proveedores", "receivable_other": "Deudores varios",
                             "allowance": "Menos: Previsión para deudores incobrables"}
        for key, label in receivable_labels.items():
            self.pair(key, text, page, label, "6")
        self.check("nota 6", self.sum(*receivable_labels), self.value("receivables_total"))
        page, text = self.page_with("Nota 10 - Acreedores comerciales", "Proveedores del exterior")
        self.annual_header(text)
        current = re.split(r"\nNo corriente", text, flags=re.I)[0]
        payable_labels = {"suppliers_foreign": "Proveedores del exterior", "suppliers_local": "Proveedores de plaza",
                          "payroll_payable": "Retribuciones al personal", "tax_payable": "Acreedores fiscales",
                          "social_payable": "Acreedores por cargas sociales", "related_payable": "Partes relacionadas",
                          "other_payable": "Otras deudas"}
        for key, label in payable_labels.items():
            self.pair(key, current, page, label, "10", optional=key == "tax_payable")
        present = [key for key in payable_labels if key in self.facts]
        self.check("nota 10", self.sum(*present), self.value("liabilities_current"))
        if "tax_payable" not in self.facts:
            self.warnings.append({"field": "tax_payable", "status": "NOT_PRESENT",
                                  "page": page, "message": "La tabla completa no publica la fila; no se crea un importe fuente."})

    def extract(self):
        self.statements()
        self.revenues()
        self.costs()
        self.financial()
        self.canon_split()
        self.asset_notes()
        self.balance_notes()
        used = sorted({fact.page for fact in self.facts.values()})
        return {"year": self.year, "company": "Conecta S.A.", "currency": "UYU", "source_unit": "pesos",
                "path": str(self.path.resolve()), "sha256": hashlib.sha256(self.path.read_bytes()).hexdigest(),
                "facts": {k: asdict(v) for k, v in self.facts.items()}, "checks": self.checks,
                "warnings": self.warnings, "pages": {str(p): self.pages[p-1] for p in used}}


def extract_report(path, year):
    return Report(path, year).extract()
