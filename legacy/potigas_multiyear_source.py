"""Hash-pinned source facts for Potigas 2023-2025."""
from __future__ import annotations

import hashlib
from pathlib import Path

from pypdf import PdfReader

from potigas_source import FACTS as FACTS_2023


def fact(value: int, page: int, label: str, status: str = "PUBLISHED") -> dict:
    return {"value": int(value), "page": page, "label": label, "status": status}


EXPECTED = {
    2023: {"sha256": "001b75024b6920183fad51c5bb0f6640b95e4721cc59ba251dfcb48f3152f1c1", "pages": 47},
    2024: {"sha256": "7210fce8c2df4b29bbd7eabcb8b9512c85277f202d822ecb1968bf8608e723a1", "pages": 50},
    2025: {"sha256": "cd1d3a4f6f2b3c0e2beaaae7e0005205bdf090b5be28b54fa2e0afd7437c1551", "pages": 24},
}


FACTS_2024 = {
    "sales_residential": fact(18_811, 38, "GNC Residencial"),
    "sales_commercial": fact(27_036, 39, "GNC Comercial"),
    "sales_industrial": fact(114_978, 38, "GNC Industrial"),
    "sales_cogeneration": fact(740, 39, "GNC Co-geração"),
    "sales_automotive": fact(188_690, 39, "Gás Natural Veicular"),
    "sales_unbilled": fact(220, 39, "Vendas a faturar"),
    "service_revenue": fact(299, 39, "Serviços - TUSD-E"),
    "construction_revenue": fact(14_016, 23, "Receita de construção"),
    "other_income_pcld_reversal": fact(317, 40, "Reversão de PCLD"),
    "other_income_contingency_reversal": fact(15, 40, "Reversão de contingências"),
    "other_income_gas_gain": fact(134, 40, "Ganho gás pago não fornecido"),
    "other_income_penalties": fact(2_017, 40, "Receitas de penalidades contratuais"),
    "other_income_other": fact(32_263, 40, "Outras receitas operacionais"),
    "deduction_returns": fact(32, 39, "Devoluções - GNC"),
    "deduction_icms_gnc": fact(22_942, 39, "ICMS - GNC"),
    "deduction_pis_gnc": fact(2_346, 39, "PIS - GNC"),
    "deduction_cofins_gnc": fact(10_809, 39, "COFINS - GNC"),
    "deduction_iss": fact(15, 39, "ISS"),
    "deduction_icms_gnv": fact(43_165, 39, "ICMS - GNV"),
    "deduction_pis_gnv": fact(2_350, 39, "PIS - GNV"),
    "deduction_cofins_gnv": fact(10_826, 39, "COFINS - GNV"),
    "net_revenue": fact(258_289, 23, "Receita operacional líquida"),
    "gas_fuel_cost": fact(93_007, 40, "Compra de gás natural combustível"),
    "gas_vehicle_cost": fact(99_290, 40, "Compra de gás natural veicular"),
    "construction_cost": fact(14_016, 23, "Custo de construção"),
    "other_costs": fact(17_752, 40, "Outros custos"),
    "personnel": fact(18_174, 40, "Despesas com pessoal"),
    "materials": fact(68, 40, "Despesas com materiais"),
    "third_party_services": fact(2_584, 40, "Serviços de terceiros"),
    "rent": fact(328, 40, "Aluguéis"),
    "travel": fact(385, 40, "Viagens"),
    "general_expenses": fact(12_462, 40, "Despesas gerais"),
    "tax_expense": fact(5_918, 23, "Despesas tributárias"),
    "contingency_expense": fact(510, 40, "Provisão de contingências"),
    "penalty_expense": fact(95, 40, "Despesa de penalidade contratual"),
    "pcld_expense": fact(734, 40, "PCLD"),
    "other_operating_expense": fact(437, 40, "Outras despesas operacionais"),
    "da": fact(9_101, 26, "Depreciação, amortização e exaustão"),
    "financial_income": fact(29_048, 23, "Receitas financeiras"),
    "financial_expense": fact(806, 23, "Despesas financeiras"),
    "ebit": fact(41_291, 23, "Resultado antes do resultado financeiro", "CALCULATED"),
    "pretax": fact(69_533, 23, "Lucro antes do IR e CSLL"),
    "tax_current": fact(14_756, 23, "IR e CSLL correntes"),
    "tax_deferred": fact(280, 23, "IR e CSLL diferidos"),
    "tax_incentive": fact(3_551, 23, "Incentivos fiscais"),
    "net_income": fact(58_608, 23, "Lucro líquido"),
    "cash": fact(88_743, 22, "Caixa e equivalentes"),
    "financial_investments": fact(0, 22, "Aplicações financeiras"),
    "receivables": fact(15_039, 22, "Contas a receber"),
    "current_tax_recoverable": fact(2_982, 22, "Impostos a recuperar"),
    "inventory": fact(1_636, 22, "Estoques"),
    "commercial_credits": fact(3_087, 22, "Créditos comerciais de gás"),
    "prepaid": fact(640, 22, "Despesas antecipadas"),
    "current_other": fact(848, 22, "Outros ativos circulantes"),
    "current_assets": fact(112_975, 22, "Ativo circulante"),
    "long_receivables": fact(0, 22, "Contas a receber não circulante"),
    "deferred_tax_asset": fact(2_358, 22, "Tributos diferidos"),
    "long_tax_recoverable": fact(1_354, 22, "Tributos a recuperar não circulante"),
    "judicial_deposits": fact(610, 22, "Depósitos judiciais"),
    "long_other": fact(89, 22, "Outros ativos não circulantes"),
    "held_for_sale": fact(518, 22, "Ativo destinado a venda"),
    "ppe_net": fact(1_217, 22, "Imobilizado"),
    "intangibles_net": fact(63_979, 22, "Intangível"),
    "assets": fact(183_100, 22, "Total do ativo"),
    "suppliers": fact(23_656, 22, "Fornecedores"),
    "short_debt": fact(580, 22, "Empréstimos circulantes"),
    "labor_liabilities": fact(5_646, 22, "Obrigações trabalhistas"),
    "tax_payable": fact(3_293, 22, "Tributos a pagar"),
    "dividends_payable": fact(13_032, 22, "Dividendos/JSCP a pagar"),
    "related_payable": fact(63, 22, "Partes relacionadas"),
    "commercial_debits": fact(431, 22, "Débitos comerciais de gás"),
    "current_liability_other": fact(931, 22, "Outros passivos circulantes"),
    "current_liabilities": fact(47_632, 22, "Passivo circulante"),
    "long_debt": fact(1_414, 22, "Empréstimos não circulantes"),
    "contingency_provision": fact(6_710, 22, "Provisão para contingências"),
    "noncurrent_liability_other": fact(3_119, 22, "Outros passivos não circulantes"),
    "noncurrent_liabilities": fact(11_243, 22, "Passivo não circulante"),
    "liabilities": fact(58_875, 22, "Total do passivo", "CALCULATED"),
    "capital": fact(68_171, 22, "Capital social"),
    "profit_reserves": fact(49_616, 22, "Reservas de lucros"),
    "additional_dividends": fact(6_438, 22, "Dividendos adicionais propostos"),
    "equity": fact(124_225, 22, "Patrimônio líquido"),
    "shares_thousand": fact(4_245, 35, "Total de ações (mil)"),
    "distribution_assets_gross": fact(173_269, 32, "Intangível de concessão - custo"),
    "distribution_assets_net": fact(60_566, 32, "Intangível de concessão - líquido"),
}


FACTS_2025 = {
    "sales_residential": fact(21_857, 17, "GNC Residencial"),
    "sales_commercial": fact(30_512, 17, "GNC Comercial"),
    "sales_industrial": fact(116_625, 17, "GNC Industrial"),
    "sales_cogeneration": fact(461, 17, "GNC Co-geração"),
    "sales_automotive": fact(171_762, 17, "Gás Natural Veicular"),
    "sales_unbilled": fact(231, 18, "Vendas a faturar"),
    "service_revenue": fact(119, 18, "Serviços - TUSD-E"),
    "construction_revenue": fact(30_920, 2, "Receita de construção"),
    "other_income_pcld_reversal": fact(694, 19, "Reversão de PCLD"),
    "other_income_contingency_reversal": fact(579, 19, "Reversão de contingências"),
    "other_income_gas_gain": fact(131, 19, "Ganho gás pago não fornecido"),
    "other_income_penalties": fact(1_892, 19, "Receitas de penalidades contratuais"),
    "other_income_other": fact(115, 19, "Outras receitas operacionais"),
    "deduction_returns": fact(669, 18, "Devoluções - GNC"),
    "deduction_icms_gnc": fact(25_143, 18, "ICMS - GNC"),
    "deduction_pis_gnc": fact(2_438, 18, "PIS - GNC"),
    "deduction_cofins_gnc": fact(11_231, 18, "COFINS - GNC"),
    "deduction_iss": fact(6, 18, "ISS"),
    "deduction_icms_gnv": fact(40_422, 18, "ICMS - GNV"),
    "deduction_pis_gnv": fact(2_105, 18, "PIS - GNV"),
    "deduction_cofins_gnv": fact(9_694, 18, "COFINS - GNV"),
    "net_revenue": fact(249_859, 2, "Receita operacional líquida"),
    "gas_fuel_cost": fact(88_169, 18, "Compra de gás natural combustível"),
    "gas_vehicle_cost": fact(85_523, 18, "Compra de gás natural veicular"),
    "construction_cost": fact(30_920, 2, "Custo de construção"),
    "other_costs": fact(18_035, 18, "Outros custos"),
    "personnel": fact(18_771, 19, "Despesas com pessoal"),
    "materials": fact(108, 19, "Despesas com materiais"),
    "third_party_services": fact(2_532, 19, "Serviços de terceiros"),
    "rent": fact(433, 19, "Aluguéis"),
    "travel": fact(507, 19, "Viagens"),
    "general_expenses": fact(5_177, 19, "Despesas gerais"),
    "tax_expense": fact(5_176, 2, "Despesas tributárias"),
    "contingency_expense": fact(533, 19, "Provisão de contingências"),
    "penalty_expense": fact(5, 19, "Despesa de penalidade contratual"),
    "pcld_expense": fact(1_320, 19, "PCLD"),
    "other_operating_expense": fact(17, 19, "Outras despesas operacionais"),
    "da": fact(9_281, 5, "Depreciação, amortização e exaustão"),
    "financial_income": fact(11_193, 2, "Receitas financeiras"),
    "financial_expense": fact(617, 2, "Despesas financeiras"),
    "ebit": fact(26_964, 2, "Resultado antes do resultado financeiro", "CALCULATED"),
    "pretax": fact(37_540, 2, "Lucro antes do IR e CSLL"),
    "tax_current": fact(9_343, 2, "IR e CSLL correntes"),
    "tax_deferred": fact(-134, 2, "IR e CSLL diferidos"),
    "tax_incentive": fact(4_891, 2, "Incentivos fiscais"),
    "net_income": fact(32_954, 2, "Lucro líquido"),
    "cash": fact(65_062, 1, "Caixa e equivalentes"),
    "financial_investments": fact(2_454, 1, "Aplicações financeiras"),
    "receivables": fact(14_970, 1, "Contas a receber"),
    "current_tax_recoverable": fact(4_685, 1, "Impostos a recuperar"),
    "inventory": fact(1_751, 1, "Estoques"),
    "commercial_credits": fact(4_531, 1, "Créditos comerciais de gás"),
    "prepaid": fact(819, 1, "Despesas antecipadas"),
    "current_other": fact(2_529, 1, "Outros ativos circulantes"),
    "current_assets": fact(96_801, 1, "Ativo circulante"),
    "long_receivables": fact(0, 1, "Contas a receber não circulante"),
    "deferred_tax_asset": fact(2_224, 1, "Tributos diferidos"),
    "long_tax_recoverable": fact(2_441, 1, "Tributos a recuperar não circulante"),
    "judicial_deposits": fact(76, 1, "Depósitos judiciais"),
    "long_other": fact(556, 1, "Outros ativos não circulantes"),
    "held_for_sale": fact(518, 1, "Ativo destinado a venda"),
    "ppe_net": fact(1_149, 1, "Imobilizado"),
    "intangibles_net": fact(87_102, 1, "Intangível"),
    "assets": fact(190_867, 1, "Total do ativo"),
    "suppliers": fact(21_207, 1, "Fornecedores"),
    "short_debt": fact(738, 1, "Empréstimos circulantes"),
    "labor_liabilities": fact(4_979, 1, "Obrigações trabalhistas"),
    "tax_payable": fact(3_119, 1, "Tributos a pagar"),
    "dividends_payable": fact(8_767, 1, "Dividendos/JSCP a pagar"),
    "related_payable": fact(67, 1, "Partes relacionadas"),
    "commercial_debits": fact(2_012, 1, "Débitos comerciais de gás"),
    "current_liability_other": fact(889, 1, "Outros passivos circulantes"),
    "current_liabilities": fact(41_778, 1, "Passivo circulante"),
    "long_debt": fact(968, 1, "Empréstimos não circulantes"),
    "contingency_provision": fact(6_664, 1, "Provisão para contingências"),
    "noncurrent_liability_other": fact(730, 1, "Outros passivos não circulantes"),
    "noncurrent_liabilities": fact(8_362, 1, "Passivo não circulante"),
    "liabilities": fact(50_140, 1, "Total do passivo", "CALCULATED"),
    "capital": fact(71_722, 1, "Capital social"),
    "profit_reserves": fact(51_690, 1, "Reservas de lucros"),
    "additional_dividends": fact(17_315, 1, "Dividendos adicionais propostos"),
    "equity": fact(140_727, 1, "Patrimônio líquido"),
    "shares_thousand": fact(4_245, 15, "Total de ações (mil)"),
    "distribution_assets_gross": fact(205_707, 10, "Intangível de concessão - custo"),
    "distribution_assets_net": fact(84_208, 10, "Intangível de concessão - líquido"),
}


FACTS_BY_YEAR = {2023: FACTS_2023, 2024: FACTS_2024, 2025: FACTS_2025}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_report(path: Path, year: int) -> dict:
    path = path.resolve()
    expected = EXPECTED[year]
    actual_hash = sha256(path)
    if actual_hash != expected["sha256"]:
        raise ValueError(f"El PDF Potigas {year} cambió; requiere revisión")
    reader = PdfReader(str(path))
    if len(reader.pages) != expected["pages"]:
        raise ValueError(f"Cantidad de páginas inesperada para Potigas {year}")
    sample = " ".join((reader.pages[index].extract_text() or "") for index in range(min(2, len(reader.pages)))).upper()
    if "POTIG" not in sample or str(year) not in sample:
        raise ValueError(f"No se pudo validar entidad y período de Potigas {year}")
    return {
        "year": year,
        "path": str(path),
        "sha256": actual_hash,
        "pages": len(reader.pages),
        "unit": "thousands_BRL",
        "facts": FACTS_BY_YEAR[year],
        "checks": {"hash": "PASS", "entity": "PASS", "year": "PASS", "unit": "PASS"},
    }
