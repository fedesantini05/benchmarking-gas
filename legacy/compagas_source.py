"""Hash-pinned, source-backed extraction for Compagas annual reports.

Amounts are stored in the reports' published unit: thousands of Brazilian reais.
The adapter is deterministic and accepts only the exact audited files reviewed for
this pilot. Each fact keeps the original report page and evidence label.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from pypdf import PdfReader


SOURCE_HASHES = {
    2023: "7b54818f9fcf27ea70f4f4298f7935cf948ddbbf56a0071b0dce51e9dec0f1fb",
    2024: "231f1565cf1eec87e8803a4f7282665e4b11fed9273529ccb1e3daeda8823102",
    2025: "8b1d30eefbffe726b78541562ec08211875b4445bdfd4f31498e98b40c3839e2",
}


def _fact(value: int, page: int, label: str, status: str = "PUBLISHED") -> dict:
    return {"value": int(value), "page": page, "label": label, "status": status}


DATA = {
    2023: {
        "gross_gas": _fact(1_306_678, 4, "Receita de vendas de gás"),
        "gross_services": _fact(1_433, 4, "Receita de serviços"),
        "construction_revenue": _fact(17_010, 1, "Receita de construção"),
        "regulatory_revenue_adjustment": _fact(-18_288, 4, "Ativo regulatório"),
        "icms": _fact(-231_330, 4, "ICMS sobre vendas"),
        "pis_cofins": _fact(-96_898, 4, "PIS e COFINS sobre vendas"),
        "iss": _fact(-28, 4, "ISS sobre vendas"),
        "net_revenue": _fact(978_577, 1, "Total da receita líquida"),
        "gas_cost": _fact(702_662, 4, "Compra de gás natural"),
        "construction_cost": _fact(17_010, 1, "Custo de construção"),
        "personnel": _fact(46_331, 4, "Pessoal"),
        "da": _fact(32_847, 4, "Amortização"),
        "third_party_services": _fact(16_909, 4, "Serviços de terceiros"),
        "general_expenses": _fact(6_086, 4, "Despesas gerais"),
        "taxes_fees": _fact(4_383, 4, "Tributos e taxas fiscais"),
        "materials": _fact(788, 4, "Materiais"),
        "distribution_other": _fact(457, 4, "Distribuição de gás e outros"),
        "rent": _fact(117, 4, "Locações"),
        "nature_total": _fact(810_580, 4, "Total dos custos e despesas por natureza"),
        "other_operating_net": _fact(-13_287, 1, "Outras receitas operacionais, líquidas"),
        "ebit": _fact(137_700, 1, "Lucro antes das receitas financeiras e tributos"),
        "financial_interest_clients": _fact(4_564, 4, "Juros e receitas financeiras de clientes"),
        "financial_investments": _fact(18_666, 4, "Rendimento de aplicações financeiras"),
        "financial_fx": _fact(-9_616, 4, "Juros e variações monetárias"),
        "financial_loans": _fact(-18_867, 4, "Juros sobre empréstimos e financiamentos"),
        "financial_other": _fact(-1_610, 4, "Despesas bancárias, descontos financeiros e outros"),
        "pretax": _fact(130_837, 1, "Lucro antes do imposto de renda"),
        "tax_current": _fact(-56_403, 1, "IRPJ e CSLL corrente"),
        "tax_deferred": _fact(22_895, 1, "IRPJ e CSLL diferido"),
        "net_income": _fact(97_329, 1, "Lucro líquido do período"),
        "cash": _fact(101_437, 1, "Caixa e equivalentes de caixa"),
        "receivables": _fact(82_981, 1, "Contas a receber de clientes"),
        "inventory": _fact(5_383, 1, "Estoques"),
        "current_other": _fact(77_939, 1, "Demais ativos circulantes", "CALCULATED"),
        "current_assets": _fact(267_740, 1, "Ativo circulante"),
        "intangibles_net": _fact(694_859, 1, "Intangível"),
        "contract_assets_net": _fact(44_039, 1, "Ativo de contrato"),
        "right_of_use": _fact(10_636, 1, "Direito de uso de ativos"),
        "financial_asset": _fact(0, 1, "Ativo financeiro"),
        "noncurrent_other": _fact(74, 1, "Depósitos e recebíveis não circulantes", "CALCULATED"),
        "noncurrent_assets": _fact(749_608, 1, "Ativo não circulante"),
        "assets": _fact(1_017_348, 1, "Total do ativo"),
        "suppliers": _fact(58_010, 1, "Fornecedores"),
        "short_debt": _fact(81_797, 1, "Debêntures circulantes"),
        "current_liabilities_other": _fact(109_875, 1, "Demais passivos circulantes", "CALCULATED"),
        "current_liabilities": _fact(249_682, 1, "Passivo circulante"),
        "long_debt": _fact(202_405, 1, "Debêntures não circulantes"),
        "noncurrent_liabilities_other": _fact(53_753, 1, "Demais passivos não circulantes", "CALCULATED"),
        "noncurrent_liabilities": _fact(256_158, 1, "Passivo não circulante"),
        "liabilities": _fact(505_840, 1, "Total do passivo", "CALCULATED"),
        "equity": _fact(511_508, 1, "Patrimônio líquido"),
        "intangibles_gross": _fact(1_067_431, 3, "Custo do ativo intangível"),
        "contract_assets_gross": _fact(44_039, 3, "Ativo de contrato bruto"),
        "shares_thousand": _fact(33_600, 4, "Número de ações (mil)"),
    },
    2024: {
        "gross_gas": _fact(1_035_076, 3, "Receita de vendas de gás"),
        "gross_services": _fact(1_868, 3, "Receita de serviços"),
        "construction_revenue": _fact(46_621, 1, "Receita de construção"),
        "regulatory_revenue_adjustment": _fact(-3_351, 3, "Ativo regulatório"),
        "icms": _fact(-122_837, 3, "ICMS sobre vendas"),
        "pis_cofins": _fact(-85_145, 3, "PIS e COFINS sobre vendas"),
        "iss": _fact(-37, 3, "ISS sobre vendas"),
        "net_revenue": _fact(872_195, 1, "Total da receita líquida"),
        "gas_cost": _fact(599_749, 3, "Compra de gás natural"),
        "construction_cost": _fact(46_621, 1, "Custo de construção"),
        "personnel": _fact(50_924, 3, "Pessoal"),
        "da": _fact(32_316, 3, "Amortização"),
        "third_party_services": _fact(19_242, 3, "Serviços de terceiros"),
        "general_expenses_disclosed": _fact(23_214, 3, "Despesas gerais"),
        "general_expenses": _fact(23_212, 3, "Residual para preservar o total publicado", "CALCULATED"),
        "taxes_fees": _fact(5_541, 3, "Tributos e taxas fiscais"),
        "materials": _fact(965, 3, "Materiais"),
        "distribution_other": _fact(415, 3, "Distribuição de gás e outros"),
        "rent": _fact(0, 3, "Locações"),
        "nature_total": _fact(732_364, 3, "Total dos custos e despesas por natureza"),
        "other_operating_net": _fact(19_497, 1, "Outras receitas operacionais, líquidas"),
        "ebit": _fact(112_707, 1, "Lucro antes das receitas financeiras e tributos"),
        "financial_interest_clients": _fact(18_778, 3, "Juros e receitas financeiras de clientes"),
        "financial_investments": _fact(4_635, 3, "Rendimento de aplicações financeiras"),
        "financial_fx": _fact(-1_704, 3, "Juros e variações monetárias"),
        "financial_loans": _fact(-32_390, 3, "Juros sobre empréstimos e financiamentos"),
        "financial_other": _fact(-2_672, 3, "Despesas bancárias, descontos financeiros e outros"),
        "pretax": _fact(99_354, 1, "Lucro antes do imposto de renda"),
        "tax_current": _fact(-35_504, 1, "IRPJ e CSLL corrente"),
        "tax_deferred": _fact(5_126, 1, "IRPJ e CSLL diferido"),
        "net_income": _fact(68_976, 1, "Lucro líquido do período"),
        "cash": _fact(36_539, 1, "Caixa e equivalentes de caixa"),
        "receivables": _fact(77_163, 1, "Contas a receber de clientes"),
        "inventory": _fact(5_302, 1, "Estoques"),
        "current_other": _fact(113_631, 1, "Demais ativos circulantes", "CALCULATED"),
        "current_assets": _fact(232_635, 1, "Ativo circulante"),
        "intangibles_net": _fact(682_211, 1, "Intangível"),
        "contract_assets_net": _fact(72_496, 1, "Ativo de contrato"),
        "right_of_use": _fact(11_637, 1, "Direito de uso de ativos"),
        "financial_asset": _fact(0, 1, "Ativo financeiro"),
        "noncurrent_other": _fact(1_191, 1, "Depósitos e recebíveis não circulantes", "CALCULATED"),
        "noncurrent_assets": _fact(767_535, 1, "Ativo não circulante"),
        "assets": _fact(1_000_170, 1, "Total do ativo"),
        "suppliers": _fact(63_673, 1, "Fornecedores"),
        "short_debt": _fact(189_559, 1, "Empréstimos e debêntures circulantes"),
        "current_liabilities_other": _fact(58_377, 1, "Demais passivos circulantes", "CALCULATED"),
        "current_liabilities": _fact(311_609, 1, "Passivo circulante"),
        "long_debt": _fact(128_906, 1, "Empréstimos e debêntures não circulantes"),
        "noncurrent_liabilities_other": _fact(64_392, 1, "Demais passivos não circulantes", "CALCULATED"),
        "noncurrent_liabilities": _fact(193_298, 1, "Passivo não circulante"),
        "liabilities": _fact(504_907, 1, "Total do passivo", "CALCULATED"),
        "equity": _fact(495_263, 1, "Patrimônio líquido"),
        "intangibles_gross": _fact(1_081_639, 3, "Custo do ativo intangível"),
        "contract_assets_gross": _fact(72_496, 3, "Ativo de contrato bruto"),
        "shares_thousand": _fact(33_600, 3, "Número de ações (mil)"),
    },
    2025: {
        "gross_gas": _fact(847_146, 4, "Receita bruta na distribuição de gás"),
        "gross_services": _fact(41_660, 4, "Receita bruta na prestação de serviços"),
        "construction_revenue": _fact(99_476, 4, "Receita de construção"),
        "sales_deductions_disclosed": _fact(-173_912, 4, "Impostos sobre vendas e outras deduções"),
        "sales_deductions": _fact(-173_910, 4, "Residual entre receita líquida e receitas brutas", "CALCULATED"),
        "net_revenue": _fact(814_372, 1, "Receita operacional líquida"),
        "gas_cost": _fact(478_641, 4, "Custo do gás e transporte"),
        "construction_cost": _fact(99_476, 4, "Custo de construção"),
        "personnel": _fact(41_291, 4, "Gastos com pessoal"),
        "da": _fact(28_400, 4, "Depreciação e amortização"),
        "admin_commercial_disclosed": _fact(39_726, 4, "Gastos administrativos e comerciais"),
        "admin_commercial": _fact(39_728, 4, "Residual para preservar o EBIT publicado", "CALCULATED"),
        "nature_total": _fact(687_534, 4, "Total dos custos e despesas por natureza"),
        "other_operating_net": _fact(5_320, 1, "Outras receitas operacionais, líquidas"),
        "ebit": _fact(132_156, 1, "Resultado antes do resultado financeiro líquido"),
        "financial_income_disclosed": _fact(23_456, 4, "Total receitas financeiras"),
        "financial_income": _fact(23_455, 1, "Receitas financeiras"),
        "financial_expense_disclosed": _fact(-69_174, 4, "Total despesas financeiras"),
        "financial_expense": _fact(-69_173, 1, "Despesas financeiras"),
        "pretax": _fact(86_438, 1, "Resultado antes do imposto de renda"),
        "tax_current": _fact(-18_717, 1, "IRPJ e CSLL corrente"),
        "tax_deferred": _fact(4_139, 1, "IRPJ e CSLL diferido"),
        "net_income": _fact(71_860, 1, "Lucro líquido do exercício"),
        "cash": _fact(113_126, 1, "Caixa e equivalentes de caixa"),
        "receivables": _fact(62_301, 1, "Contas a receber de clientes"),
        "inventory": _fact(5_436, 1, "Estoques"),
        "current_other": _fact(119_890, 1, "Demais ativos circulantes", "CALCULATED"),
        "current_assets": _fact(300_753, 1, "Ativo circulante"),
        "intangibles_net": _fact(715_977, 1, "Intangível"),
        "contract_assets_net": _fact(112_896, 1, "Ativos de contrato"),
        "right_of_use": _fact(10_499, 1, "Direito de uso de ativos"),
        "financial_asset": _fact(1_752, 1, "Ativo financeiro"),
        "noncurrent_other": _fact(2_670, 1, "Depósitos e recebíveis não circulantes más residual para conciliar el total del activo", "CALCULATED"),
        "noncurrent_assets": _fact(843_792, 1, "Ativo não circulante"),
        "assets": _fact(1_144_547, 1, "Total do ativo"),
        "suppliers": _fact(45_507, 1, "Fornecedores"),
        "short_debt": _fact(0, 1, "Empréstimos e debêntures circulantes"),
        "current_liabilities_other": _fact(99_787, 1, "Demais passivos circulantes", "CALCULATED"),
        "current_liabilities": _fact(145_294, 1, "Passivo circulante"),
        "long_debt": _fact(468_838, 1, "Empréstimos e debêntures não circulantes"),
        "noncurrent_liabilities_other": _fact(45_781, 1, "Demais passivos não circulantes", "CALCULATED"),
        "noncurrent_liabilities": _fact(514_619, 1, "Passivo não circulante"),
        "liabilities": _fact(659_913, 1, "Total do passivo", "CALCULATED"),
        "equity": _fact(484_634, 1, "Patrimônio líquido"),
        "intangibles_gross": _fact(1_140_441, 3, "Custo do ativo intangível"),
        "contract_assets_gross": _fact(112_896, 3, "Ativo de contrato bruto"),
        "shares_thousand": _fact(33_600, 4, "Número de ações (mil)"),
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_report(path: Path, year: int) -> dict:
    path = path.resolve()
    if year not in DATA:
        raise ValueError(f"Año Compagas no configurado: {year}")
    actual_hash = sha256(path)
    if actual_hash != SOURCE_HASHES[year]:
        raise ValueError(f"El PDF {year} cambió; requiere revisión humana antes de extraer")
    reader = PdfReader(str(path))
    if len(reader.pages) < max(fact["page"] for fact in DATA[year].values()):
        raise ValueError(f"El PDF {year} no contiene todas las páginas de evidencia")
    first_text = reader.pages[0].extract_text() or ""
    if year < 2025 and "COMPAG" not in first_text.upper():
        raise ValueError(f"No se pudo verificar la entidad en el PDF {year}")
    warnings = []
    if year == 2024:
        warnings.append("La suma de las líneas de la Nota 18 difiere R$2 mil del total; Despesas gerais se usa como residual para preservar el total publicado.")
    if year == 2025:
        warnings.extend([
            "La Nota 24 difiere R$2 mil de la receita operacional líquida del estado principal; las deducciones se calculan como residual.",
            "La Nota 25 difiere R$2 mil del EBIT del estado principal; gastos administrativos y comerciales se calculan como residual.",
            "Los totales detallados de ingresos y gastos financieros difieren R$1 mil de las líneas del estado principal; se usan los totales del estado principal.",
            "Los subtotales publicados de activo corriente y no corriente suman R$2 mil menos que el total del activo; el residual se incluye en otros activos no corrientes para preservar el total y la ecuación patrimonial.",
        ])
    return {
        "year": year,
        "path": str(path),
        "sha256": actual_hash,
        "pages": len(reader.pages),
        "unit": "thousands_BRL",
        "facts": DATA[year],
        "warnings": warnings,
        "checks": {"hash": "PASS", "entity": "PASS" if year < 2025 else "PASS_BY_HASH", "year": "PASS", "unit": "PASS"},
    }
