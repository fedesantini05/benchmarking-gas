"""Hash-pinned source facts for Potigas 2023."""
from __future__ import annotations

import hashlib
from pathlib import Path

from pypdf import PdfReader


EXPECTED_HASH = "001b75024b6920183fad51c5bb0f6640b95e4721cc59ba251dfcb48f3152f1c1"


def fact(value: int, page: int, label: str, status: str = "PUBLISHED") -> dict:
    return {"value": int(value), "page": page, "label": label, "status": status}


FACTS = {
    # Income statement and notes 14-18; source unit is thousands of BRL.
    "sales_residential": fact(15_381, 35, "GNC Residencial"),
    "sales_commercial": fact(21_336, 35, "GNC Comercial"),
    "sales_industrial": fact(94_100, 35, "GNC Industrial"),
    "sales_cogeneration": fact(412, 35, "GNC Co-geração"),
    "sales_automotive": fact(188_518, 35, "Gás Natural Veicular"),
    "sales_unbilled": fact(323, 35, "Vendas a faturar"),
    "service_revenue": fact(3_091, 35, "Serviços - TUSD-E"),
    "construction_revenue": fact(12_103, 19, "Receita de construção"),
    "other_income_pcld_reversal": fact(128, 37, "Reversão de PCLD"),
    "other_income_contingency_reversal": fact(36, 37, "Reversão de contingências"),
    "other_income_gas_gain": fact(38, 37, "Ganho gás pago não fornecido"),
    "other_income_penalties": fact(8_298, 37, "Receitas de penalidades contratuais"),
    "other_income_other": fact(114, 37, "Outras receitas operacionais"),
    "deduction_returns": fact(14, 35, "Devoluções - GNC"),
    "deduction_icms_gnc": fact(19_658, 35, "ICMS - GNC"),
    "deduction_pis_gnc": fact(1_945, 35, "PIS - GNC"),
    "deduction_cofins_gnc": fact(8_959, 35, "COFINS - GNC"),
    "deduction_iss": fact(155, 35, "ISS"),
    "deduction_icms_gnv": fact(49_501, 35, "ICMS - GNV"),
    "deduction_pis_gnv": fact(1_207, 35, "PIS - GNV"),
    "deduction_cofins_gnv": fact(5_557, 35, "COFINS - GNV"),
    "net_revenue": fact(236_165, 19, "Receita operacional líquida"),
    "gas_fuel_cost": fact(67_753, 36, "Compra de gás natural combustível"),
    "gas_vehicle_cost": fact(104_974, 36, "Compra de gás natural veicular"),
    "construction_cost": fact(12_103, 19, "Custo de construção"),
    "other_costs": fact(16_409, 36, "Outros custos"),
    "personnel": fact(16_866, 36, "Despesas com pessoal"),
    "materials": fact(51, 36, "Despesas com materiais"),
    "third_party_services": fact(1_762, 36, "Serviços de terceiros"),
    "rent": fact(293, 36, "Aluguéis"),
    "travel": fact(412, 36, "Viagens"),
    "general_expenses": fact(3_265, 36, "Despesas gerais"),
    "tax_expense": fact(5_366, 19, "Despesas tributárias"),
    "contingency_expense": fact(924, 37, "Provisão de contingências"),
    "penalty_expense": fact(77, 37, "Despesa de penalidade contratual"),
    "pcld_expense": fact(292, 37, "Provisões de créditos de liquidação duvidosa"),
    "da": fact(8_047, 22, "Depreciação, amortização e exaustão"),
    "financial_income": fact(7_320, 19, "Receitas financeiras"),
    "financial_expense": fact(653, 19, "Despesas financeiras"),
    "ebit": fact(26_335, 19, "Resultado antes do resultado financeiro", "CALCULATED"),
    "pretax": fact(33_002, 19, "Lucro antes do IR e CSLL"),
    "tax_current": fact(9_533, 19, "IR e CSLL correntes"),
    "tax_deferred": fact(406, 19, "IR e CSLL diferidos"),
    "tax_incentive": fact(4_278, 19, "Incentivos fiscais"),
    "net_income": fact(28_153, 19, "Lucro líquido do exercício"),
    # Balance sheet and notes 9 and 12.
    "cash": fact(58_243, 18, "Caixa e equivalentes"),
    "receivables": fact(14_150, 18, "Contas a receber"),
    "current_tax_recoverable": fact(1_891, 18, "Impostos e contribuições a recuperar"),
    "inventory": fact(1_880, 18, "Estoques"),
    "commercial_credits": fact(4_917, 18, "Créditos nas operações comerciais de gás"),
    "prepaid": fact(193, 18, "Despesas antecipadas"),
    "current_other": fact(331, 18, "Outros ativos circulantes"),
    "current_assets": fact(81_605, 18, "Ativo circulante"),
    "long_receivables": fact(18, 18, "Contas a receber não circulante"),
    "deferred_tax_asset": fact(2_078, 18, "Tributos diferidos"),
    "long_tax_recoverable": fact(1_089, 18, "Tributos a recuperar não circulante"),
    "judicial_deposits": fact(610, 18, "Depósitos judiciais"),
    "long_other": fact(69, 18, "Outros ativos não circulantes"),
    "held_for_sale": fact(518, 18, "Ativo não circulante destinado a venda"),
    "ppe_net": fact(1_618, 18, "Imobilizado"),
    "intangibles_net": fact(57_072, 18, "Intangível"),
    "noncurrent_assets": fact(63_072, 18, "Ativo não circulante", "CALCULATED"),
    "assets": fact(144_677, 18, "Total do ativo"),
    "suppliers": fact(19_763, 18, "Fornecedores"),
    "short_debt": fact(503, 18, "Empréstimos e financiamentos circulantes"),
    "labor_liabilities": fact(4_476, 18, "Obrigações trabalhistas"),
    "tax_payable": fact(4_026, 18, "Tributos a pagar"),
    "dividends_payable": fact(5_617, 18, "Dividendos/JSCP a pagar"),
    "related_payable": fact(110, 18, "Contas a pagar partes relacionadas"),
    "commercial_debits": fact(1_386, 18, "Débitos nas operações comerciais de gás"),
    "current_liability_other": fact(2_489, 18, "Outros passivos circulantes"),
    "current_liabilities": fact(38_370, 18, "Passivo circulante"),
    "long_debt": fact(1_979, 18, "Empréstimos e financiamentos não circulantes"),
    "contingency_provision": fact(6_213, 18, "Provisão para contingências"),
    "noncurrent_liability_other": fact(2_589, 18, "Outros passivos não circulantes"),
    "noncurrent_liabilities": fact(10_781, 18, "Passivo não circulante"),
    "liabilities": fact(49_151, 18, "Total do passivo", "CALCULATED"),
    "capital": fact(63_893, 18, "Capital social"),
    "profit_reserves": fact(15_550, 18, "Reservas de lucros"),
    "additional_dividends": fact(16_083, 18, "Dividendos adicionais propostos"),
    "equity": fact(95_526, 18, "Patrimônio líquido"),
    "shares_thousand": fact(4_245, 31, "Total de ações (mil)"),
    "distribution_assets_gross": fact(158_133, 28, "Intangível de concessão - custo"),
    "distribution_assets_net": fact(53_679, 28, "Intangível de concessão - valor líquido"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_report(path: Path) -> dict:
    path = path.resolve()
    actual_hash = sha256(path)
    if actual_hash != EXPECTED_HASH:
        raise ValueError("El PDF Potigas 2023 cambió; requiere revisión antes de extraer")
    reader = PdfReader(str(path))
    if len(reader.pages) != 47:
        raise ValueError("Cantidad de páginas inesperada para Potigas 2023")
    first_text = (reader.pages[0].extract_text() or "").upper()
    if "COMPANHIA POTIGUAR DE GÁS" not in first_text or "2023" not in first_text:
        raise ValueError("No se pudo validar entidad y período de Potigas")
    return {
        "year": 2023,
        "path": str(path),
        "sha256": actual_hash,
        "pages": len(reader.pages),
        "unit": "thousands_BRL",
        "facts": FACTS,
        "checks": {"hash": "PASS", "entity": "PASS", "year": "PASS", "unit": "PASS"},
        "warnings": [
            "Otros costos del CPV se separan entre amortización publicada (R$8.047 mil) y PMSO residual exacto (R$8.362 mil).",
            "Las filas 30 y 31 usan exclusivamente el intangible de concesión bruto y neto, por ser los activos asociados al negocio de distribución.",
        ],
    }
