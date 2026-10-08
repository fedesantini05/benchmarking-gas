"""Hash-pinned source facts for Southwest Gas Corporation 2020-2025.

All figures come from the original annual report for the corresponding year.
Source units are thousands of US dollars, except shares (thousands of shares).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from pypdf import PdfReader


REPORTS = {
    2020: {"sha256": "e63ad3236ba9f3cad5e4861491cd5dd4a6ecfb1bc1e18c5996c5ed9bc2d8485b", "pages": 144},
    2021: {"sha256": "1c63a6fe506821bdf841c5c388d9852c5d5f686b62fb5ab768ae87464852fd59", "pages": 128},
    2022: {"sha256": "9f8d5c55493a060c1bd03814ecab628116efdae9729d1294d72d8de66c8cab44", "pages": 112},
    2023: {"sha256": "459d627053fd5bd7280408dfa2d40ae1d0804af566b45786800df10a69b73ea0", "pages": 134},
    2024: {"sha256": "71a178fe091aea0c62e0ff0b7a8b5a290f802eb8a1500ef58d25096b7aff360a", "pages": 133},
    2025: {"sha256": "d47d4ac35e75f3b61fa3254e36e5fa9a2eb7463db0d58dd358a8477f1fcc607d", "pages": 137},
}


def _f(value: int, page: int, label: str) -> dict:
    return {"value": int(value), "page": page, "label": label, "status": "PUBLISHED"}


def _year(*, income_page: int, balance_page: int, revenue_page: int,
          revenue: tuple[int, int, int, int, int, int, int],
          income: tuple[int, int, int, int, int, int, int, int, int],
          plant: tuple[int, int, int, int, int], current_assets: tuple[int, ...],
          noncurrent: tuple[int, int], liabilities: tuple[int, ...], equity: int) -> dict:
    residential, small_commercial, large_commercial, industrial, transportation, alt_revenue, other_revenue = revenue
    gas_revenue, gas_cost, om, da, taxes, interest, other_income, income_tax, net_income = income
    gas_plant, accumulated_dep, cwip, net_plant, other_property = plant
    (cash, receivables, accrued_revenue, tax_receivable, deferred_gas_asset,
     parent_receivable, inventory, prepaid_other, held_for_sale, total_current_assets) = current_assets
    goodwill, deferred_other_assets = noncurrent
    (current_debt, short_debt, suppliers, customer_deposits, accrued_taxes,
     accrued_interest, deferred_gas_liability, parent_payable, dividends,
     other_current_liabilities, total_current_liabilities, long_debt,
     deferred_tax, removal_costs, other_long_liabilities) = liabilities
    facts = {
        "residential": _f(residential, revenue_page, "Residential"),
        "small_commercial": _f(small_commercial, revenue_page, "Small commercial"),
        "large_commercial": _f(large_commercial, revenue_page, "Large commercial"),
        "industrial_other": _f(industrial, revenue_page, "Industrial/other"),
        "transportation": _f(transportation, revenue_page, "Transportation"),
        "alternative_revenue": _f(alt_revenue, revenue_page, "Alternative revenue program revenues (deferrals)"),
        "other_revenue": _f(other_revenue, revenue_page, "Other revenues"),
        "gas_operating_revenue": _f(gas_revenue, income_page, "Regulated operations revenues"),
        "gas_cost": _f(gas_cost, income_page, "Net cost of gas sold"),
        "operations_maintenance": _f(om, income_page, "Operations and maintenance"),
        "da": _f(da, income_page, "Depreciation and amortization"),
        "taxes_other_income": _f(taxes, income_page, "Taxes other than income taxes"),
        "interest_deductions": _f(interest, income_page, "Net interest deductions"),
        "other_income_deductions": _f(other_income, income_page, "Other income (deductions)"),
        "income_tax": _f(income_tax, income_page, "Income tax expense"),
        "net_income": _f(net_income, income_page, "Net income"),
        "gas_plant_gross": _f(gas_plant, balance_page, "Gas plant"),
        "accumulated_depreciation": _f(accumulated_dep, balance_page, "Accumulated depreciation"),
        "construction_work_progress": _f(cwip, balance_page, "Construction work in progress"),
        "net_utility_plant": _f(net_plant, balance_page, "Net regulated operations plant"),
        "other_property_investments": _f(other_property, balance_page, "Other property and investments"),
        "cash": _f(cash, balance_page, "Cash and cash equivalents"),
        "receivables": _f(receivables, balance_page, "Accounts receivable, net"),
        "accrued_utility_revenue": _f(accrued_revenue, balance_page, "Accrued utility revenue"),
        "income_tax_receivable": _f(tax_receivable, balance_page, "Income taxes receivable, net"),
        "deferred_gas_cost_asset": _f(deferred_gas_asset, balance_page, "Deferred purchased gas costs"),
        "receivable_parent": _f(parent_receivable, balance_page, "Receivable from parent"),
        "inventory": _f(inventory, balance_page, "Materials, supplies, and gas inventories"),
        "prepaid_other_current": _f(prepaid_other, balance_page, "Prepaid and other current assets"),
        "held_for_sale": _f(held_for_sale, balance_page, "Current assets held for sale"),
        "current_assets": _f(total_current_assets, balance_page, "Total current assets"),
        "goodwill": _f(goodwill, balance_page, "Goodwill"),
        "deferred_other_assets": _f(deferred_other_assets, balance_page, "Deferred charges and other assets"),
        "equity": _f(equity, balance_page, "Total equity"),
        "current_debt_maturities": _f(current_debt, balance_page + 1, "Current maturities of long-term debt"),
        "short_debt": _f(short_debt, balance_page + 1, "Short-term debt"),
        "suppliers": _f(suppliers, balance_page + 1, "Accounts payable"),
        "customer_deposits": _f(customer_deposits, balance_page + 1, "Customer deposits"),
        "accrued_taxes": _f(accrued_taxes, balance_page + 1, "Accrued general taxes"),
        "accrued_interest": _f(accrued_interest, balance_page + 1, "Accrued interest"),
        "deferred_gas_cost_liability": _f(deferred_gas_liability, balance_page + 1, "Deferred purchased gas costs"),
        "payable_parent": _f(parent_payable, balance_page + 1, "Payable to parent"),
        "dividends_declared": _f(dividends, balance_page + 1, "Dividends declared"),
        "other_current_liabilities": _f(other_current_liabilities, balance_page + 1, "Other current liabilities"),
        "current_liabilities": _f(total_current_liabilities, balance_page + 1, "Total current liabilities"),
        "long_debt": _f(long_debt, balance_page + 1, "Long-term debt, less current maturities"),
        "deferred_tax_credits": _f(deferred_tax, balance_page + 1, "Deferred income taxes and investment tax credits"),
        "removal_costs": _f(removal_costs, balance_page + 1, "Accumulated removal costs"),
        "other_long_liabilities": _f(other_long_liabilities, balance_page + 1, "Other deferred credits and other long-term liabilities"),
        "shares_thousand": _f(47_482, income_page + 4, "Common stock shares (thousands)"),
    }
    return facts


FACTS = {
    2020: _year(income_page=80, balance_page=78, revenue_page=99,
        revenue=(958520,221541,44633,26242,88215,12140,-706), income=(1350585,342837,406382,235295,63460,101148,-6590,35755,159118),
        plant=(8384000,2419348,211429,6176081,143611), current_assets=(41070,146861,82400,11155,2053,0,0,152748,0,436287),
        noncurrent=(10095,490562), liabilities=(0,57000,161646,67920,48640,20495,54636,142,0,146046,556525,2438206,581100,404000,1043337), equity=2233468),
    2021: _year(income_page=52, balance_page=50, revenue_page=73,
        revenue=(1035612,270214,57371,42313,92240,13181,10859), income=(1521790,430907,438550,253398,80343,97560,-4559,29338,187135),
        plant=(8901575,2538508,183485,6546552,153093), current_assets=(38691,169666,84900,7826,291145,1031,0,242243,0,835502),
        noncurrent=(10095,405021), liabilities=(275000,250000,234070,56127,53064,22926,0,0,0,146422,1037609,2440603,638828,424000,881286), equity=2527937),
    2022: _year(income_page=62, balance_page=60, revenue_page=76,
        revenue=(1324794,378520,85234,50894,100642,-18478,13463), income=(1935069,789216,491928,263043,83197,115880,-6884,30541,154380),
        plant=(9453907,2674157,244750,7024500,169397), current_assets=(51823,234081,88100,103,450120,2130,0,401789,0,1228146),
        noncurrent=(11155,370483), liabilities=(0,225000,497046,51182,67094,29569,0,0,0,150817,1020708,3251296,683948,445000,833554), equity=2569175),
    2023: _year(income_page=72, balance_page=71, revenue_page=88,
        revenue=(1725223,513366,117973,75219,104298,-52365,15850), income=(2499564,1246901,511646,295462,87261,149830,70661,36899,242226),
        plant=(10140362,2822669,200549,7518242,152658), current_assets=(71154,269195,93000,26,552885,0,0,188138,21376,1195774),
        noncurrent=(11155,390742), liabilities=(0,0,215744,48460,58053,34955,0,1711,0,271899,630822,3501543,749836,458000,744755), equity=3183615),
    2024: _year(income_page=74, balance_page=73, revenue_page=89,
        revenue=(1654685,493709,111350,62997,115782,23055,13638), income=(2475216,1150005,520820,303095,88965,162257,54276,43174,261176),
        plant=(10844895,2914457,178647,8109085,159678), current_assets=(311073,202947,96600,0,13937,0,0,234628,0,859185),
        noncurrent=(11155,394852), liabilities=(0,0,190612,63876,59353,35460,242259,370,0,177226,769156,3504477,819973,472000,696487), equity=3271862),
    2025: _year(income_page=77, balance_page=76, revenue_page=93,
        revenue=(1276677,333408,72367,44941,116579,86593,9815), income=(1942480,497636,537644,330724,94070,181677,52402,52823,300308),
        plant=(11517031,3063363,236871,8690539,169947), current_assets=(56408,170524,101600,1007,5214,105550,93823,234003,0,768129),
        noncurrent=(11155,354221), liabilities=(75000,0,225337,67249,54384,35319,310085,0,0,117350,884724,3433012,1027921,496000,627368), equity=3524966),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_report(path: Path, year: int) -> dict:
    path = path.resolve()
    expected = REPORTS[year]
    actual_hash = sha256(path)
    if actual_hash != expected["sha256"]:
        raise ValueError(f"El PDF Southwest Gas Corporation {year} cambió; requiere revisión")
    reader = PdfReader(str(path))
    if len(reader.pages) != expected["pages"]:
        raise ValueError(f"Cantidad de páginas inesperada para Southwest Gas Corporation {year}")
    sample = " ".join((page.extract_text() or "") for page in reader.pages[:12]).upper()
    if "SOUTHWEST GAS" not in sample or str(year) not in sample:
        raise ValueError(f"No se pudo validar entidad y período {year}")
    return {
        "year": year, "path": str(path), "sha256": actual_hash,
        "pages": len(reader.pages), "unit": "thousands_USD", "facts": FACTS[year],
        "checks": {"hash": "PASS", "entity": "PASS", "year": "PASS", "unit": "PASS"},
        "warnings": [
            "Operations and maintenance se publica como total sin desglose PMSO por naturaleza.",
            "Se usa el informe original de cada año, no los comparativos revisados en informes posteriores.",
        ],
    }
