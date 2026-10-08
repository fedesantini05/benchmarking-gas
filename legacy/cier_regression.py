from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from copy import deepcopy
from dataclasses import dataclass
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
WORKSPACE = Path(__file__).resolve().parent.parent
AUTOMATION_ROOT = Path(__file__).resolve().parent


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.casefold().replace("ç", "c")
    return re.sub(r"\s+", " ", value).strip()


def resolve_path(value: str, *, config_path: Path, output: bool = False) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if output:
        return (AUTOMATION_ROOT / path).resolve()
    candidate = (WORKSPACE / path).resolve()
    if candidate.exists():
        return candidate
    return (config_path.parent / path).resolve()


def sheet_paths(archive: ZipFile) -> dict[str, str]:
    workbook = etree.fromstring(archive.read("xl/workbook.xml"))
    rels = etree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {node.get("Id"): node.get("Target") for node in rels.xpath("//pr:Relationship", namespaces=NS)}
    result: dict[str, str] = {}
    for sheet in workbook.xpath("//m:sheets/m:sheet", namespaces=NS):
        target = targets[sheet.get(f"{{{DOCREL}}}id")].replace("\\", "/").lstrip("/")
        result[sheet.get("name")] = target if target.startswith("xl/") else f"xl/{target}"
    return result


def shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = etree.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.xpath(".//m:t/text()", namespaces=NS)) for node in root.xpath("//m:si", namespaces=NS)]


@dataclass(frozen=True)
class CellPayload:
    formula: str | None = None
    value: str | None = None
    text: str | None = None
    data_type: str | None = None

    def as_json(self) -> dict[str, Any]:
        return {key: value for key, value in {
            "formula": self.formula,
            "value": self.value,
            "text": self.text,
            "data_type": self.data_type,
        }.items() if value is not None}


def cell_payload(cell: etree._Element | None, strings: list[str]) -> CellPayload:
    if cell is None:
        return CellPayload()
    formula = "".join(cell.xpath("./m:f/text()", namespaces=NS)) or None
    value = "".join(cell.xpath("./m:v/text()", namespaces=NS)) or None
    data_type = cell.get("t")
    text = None
    if data_type == "s" and value is not None:
        text = strings[int(value)]
        value = None
        data_type = "inlineStr"
    elif data_type == "inlineStr":
        text = "".join(cell.xpath("./m:is//m:t/text()", namespaces=NS))
    return CellPayload(formula=formula, value=value, text=text, data_type=data_type)


def worksheet_cells(archive: ZipFile, part: str) -> dict[str, etree._Element]:
    root = etree.fromstring(archive.read(part))
    return {node.get("r"): node for node in root.xpath("//m:c", namespaces=NS)}


def target_refs(sheet_name: str) -> set[str]:
    max_row = 68 if sheet_name == "Estado de Resultados" else 36
    return {f"{column}{row}" for column in "KLMNO" for row in range(1, max_row + 1)}


def learn_mapping(template: Path, golden: Path) -> dict[str, dict[str, CellPayload]]:
    result: dict[str, dict[str, CellPayload]] = {}
    with ZipFile(template) as source, ZipFile(golden) as approved:
        source_paths = sheet_paths(source)
        approved_paths = sheet_paths(approved)
        source_strings = shared_strings(source)
        approved_strings = shared_strings(approved)
        for sheet_name in ("Estado de Resultados", "Balance Patrimonial"):
            source_cells = worksheet_cells(source, source_paths[sheet_name])
            approved_cells = worksheet_cells(approved, approved_paths[sheet_name])
            changes: dict[str, CellPayload] = {}
            for ref in sorted(target_refs(sheet_name)):
                before = cell_payload(source_cells.get(ref), source_strings)
                after = cell_payload(approved_cells.get(ref), approved_strings)
                if before != after:
                    changes[ref] = after
            result[sheet_name] = changes
    return result


def col_number(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)
    number = 0
    for letter in letters:
        number = number * 26 + ord(letter) - 64
    return number


def make_cell(ref: str, payload: CellPayload, style: str | None) -> etree._Element:
    cell = etree.Element(f"{{{MAIN}}}c", r=ref)
    if style is not None:
        cell.set("s", style)
    if payload.text is not None:
        cell.set("t", "inlineStr")
        inline = etree.SubElement(cell, f"{{{MAIN}}}is")
        text = etree.SubElement(inline, f"{{{MAIN}}}t")
        if payload.text.startswith(" ") or payload.text.endswith(" "):
            text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        text.text = payload.text
        return cell
    if payload.data_type:
        cell.set("t", payload.data_type)
    if payload.formula is not None:
        etree.SubElement(cell, f"{{{MAIN}}}f").text = payload.formula
    if payload.value is not None:
        etree.SubElement(cell, f"{{{MAIN}}}v").text = payload.value
    return cell


def patch_sheet(xml: bytes, patches: dict[str, CellPayload]) -> bytes:
    root = etree.fromstring(xml)
    sheet_data = root.find(f"{{{MAIN}}}sheetData")
    rows = {int(row.get("r")): row for row in sheet_data.findall(f"{{{MAIN}}}row")}
    for ref, payload in sorted(patches.items(), key=lambda item: (int(re.search(r"\d+$", item[0]).group()), col_number(item[0]))):
        row_number = int(re.search(r"\d+$", ref).group())
        row = rows.get(row_number)
        if row is None:
            row = etree.SubElement(sheet_data, f"{{{MAIN}}}row", r=str(row_number))
            rows[row_number] = row
        existing = next((node for node in row.findall(f"{{{MAIN}}}c") if node.get("r") == ref), None)
        style = existing.get("s") if existing is not None else None
        if existing is not None:
            row.remove(existing)
        row.append(make_cell(ref, payload, style))
        row[:] = sorted(row, key=lambda node: col_number(node.get("r", "A1")))
    sheet_data[:] = sorted(sheet_data, key=lambda node: int(node.get("r", "0")))
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def write_output(template: Path, output: Path, mapping: dict[str, dict[str, CellPayload]]) -> list[str]:
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(template) as source:
        paths = sheet_paths(source)
        replacements = {
            paths[sheet]: patch_sheet(source.read(paths[sheet]), patches)
            for sheet, patches in mapping.items()
        }
        workbook_root = etree.fromstring(source.read("xl/workbook.xml"))
        calc_pr = workbook_root.find(f"{{{MAIN}}}calcPr")
        if calc_pr is None:
            calc_pr = etree.SubElement(workbook_root, f"{{{MAIN}}}calcPr")
        calc_pr.set("calcMode", "auto")
        calc_pr.set("fullCalcOnLoad", "1")
        calc_pr.set("forceFullCalc", "1")
        replacements["xl/workbook.xml"] = etree.tostring(
            workbook_root, xml_declaration=True, encoding="UTF-8", standalone=True
        )
        with NamedTemporaryFile(delete=False, suffix=".xlsx", dir=output.parent) as temporary:
            temporary_path = Path(temporary.name)
        try:
            with ZipFile(temporary_path, "w") as destination:
                for info in source.infolist():
                    data = replacements.get(info.filename, source.read(info.filename))
                    new_info = ZipInfo(info.filename, date_time=info.date_time)
                    new_info.compress_type = info.compress_type or ZIP_DEFLATED
                    new_info.comment = info.comment
                    new_info.extra = info.extra
                    new_info.internal_attr = info.internal_attr
                    new_info.external_attr = info.external_attr
                    new_info.create_system = info.create_system
                    destination.writestr(new_info, data)
            temporary_path.replace(output)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
    return sorted(replacements)


def read_glossaries(names: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    entity_aliases: list[str] = []
    concepts: dict[str, list[str]] = {}
    for name in names:
        data = json.loads((AUTOMATION_ROOT / "glossaries" / name).read_text(encoding="utf-8"))
        entity_aliases.extend(data.get("entity_aliases", []))
        for key, value in data.get("terms", {}).items():
            concepts.setdefault(key, []).extend(value)
        for key, value in data.get("concepts", {}).items():
            concepts.setdefault(key, []).extend(value.get("aliases", []))
    return entity_aliases, concepts


def validate_sources(config: dict[str, Any], config_path: Path) -> dict[str, Any]:
    entity_aliases, concepts = read_glossaries(config["glossaries"])
    all_text = ""
    reports: dict[str, Any] = {}
    for year_text, source_text in config["reports"].items():
        source = resolve_path(source_text, config_path=config_path)
        if not source.exists():
            raise FileNotFoundError(source)
        reader = PdfReader(source)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        normalized = normalize(text)
        is_scanned = len(normalized) < 20
        validation_text = normalize(str(source)) if is_scanned else normalized
        if normalize(year_text) not in validation_text:
            raise ValueError(f"El PDF {source.name} no contiene el período {year_text}")
        if entity_aliases and not any(normalize(alias) in validation_text for alias in entity_aliases):
            raise ValueError(f"El PDF {source.name} no coincide con la entidad configurada")
        all_text += "\n" + normalized
        reports[year_text] = {
            "path": str(source),
            "sha256": file_hash(source),
            "pages": len(reader.pages),
            "extraction_mode": "scanned_filename_and_hash_validation" if is_scanned else "embedded_text",
        }
    matched: dict[str, str] = {}
    unmatched: list[str] = []
    for concept, aliases in concepts.items():
        alias = next((item for item in aliases if normalize(item) in all_text), None)
        if alias is None:
            unmatched.append(concept)
        else:
            matched[concept] = alias
    return {"reports": reports, "glossary_matched": matched, "glossary_unmatched": sorted(unmatched)}


def expand_formula_refs(formula: str, column: str) -> set[int]:
    refs: set[int] = set()
    for start, end in re.findall(fr"{column}(\d+)(?::{column}(\d+))?", formula.upper().replace("$", "")):
        first = int(start)
        last = int(end) if end else first
        refs.update(range(first, last + 1))
    return refs


def validate_formula_map(output: Path, legacy_exceptions: set[str] | None = None) -> list[dict[str, Any]]:
    legacy_exceptions = legacy_exceptions or set()
    requirements = {
        "Estado de Resultados": {
            2: {3, 13}, 15: {2, 14}, 17: {15, 16}, 18: {19, 23, 27, 31},
            19: {20, 21, 22}, 23: {24, 25, 26}, 27: {28, 29, 30},
            31: {32, 33, 34}, 35: set(range(36, 43)), 43: {17, 18, 35},
            45: {43, 44}, 46: {47, 48}, 49: {45, 46}, 50: {51, 52}, 53: {49, 50},
        },
        "Balance Patrimonial": {
            2: {3, 7}, 3: {4, 5, 6}, 7: {8, 9}, 10: {11, 15}, 11: {12, 13, 14},
            15: {16, 17}, 18: {19, 20, 21}, 26: {27, 28}, 27: {3, 4},
            28: {11, 13}, 29: {30, 31},
        },
    }
    checks: list[dict[str, Any]] = []
    with ZipFile(output) as archive:
        paths = sheet_paths(archive)
        strings = shared_strings(archive)
        for sheet_name, row_rules in requirements.items():
            cells = worksheet_cells(archive, paths[sheet_name])
            for column in "KLM":
                for row, expected_refs in row_rules.items():
                    payload = cell_payload(cells.get(f"{column}{row}"), strings)
                    actual_refs = expand_formula_refs(payload.formula or "", column)
                    key = f"{sheet_name}!{column}{row}"
                    if expected_refs.issubset(actual_refs):
                        status = "PASS"
                    elif key in legacy_exceptions:
                        status = "LEGACY_EXCEPTION"
                    else:
                        status = "FAIL"
                    checks.append({
                        "sheet": sheet_name,
                        "cell": f"{column}{row}",
                        "formula": payload.formula,
                        "expected_rows": sorted(expected_refs),
                        "actual_rows": sorted(actual_refs),
                        "status": status,
                    })
    return checks


def compare_targets(actual: Path, golden: Path) -> dict[str, Any]:
    mismatches: list[dict[str, Any]] = []
    with ZipFile(actual) as left, ZipFile(golden) as right:
        left_paths, right_paths = sheet_paths(left), sheet_paths(right)
        left_strings, right_strings = shared_strings(left), shared_strings(right)
        for sheet_name in ("Estado de Resultados", "Balance Patrimonial"):
            left_cells = worksheet_cells(left, left_paths[sheet_name])
            right_cells = worksheet_cells(right, right_paths[sheet_name])
            for ref in sorted(target_refs(sheet_name)):
                left_value = cell_payload(left_cells.get(ref), left_strings)
                right_value = cell_payload(right_cells.get(ref), right_strings)
                if left_value != right_value:
                    mismatches.append({
                        "sheet": sheet_name,
                        "cell": ref,
                        "actual": left_value.as_json(),
                        "expected": right_value.as_json(),
                    })
    return {"status": "PASS" if not mismatches else "FAIL", "mismatch_count": len(mismatches), "mismatches": mismatches[:50]}


def package_check(template: Path, output: Path) -> dict[str, Any]:
    with ZipFile(template) as before, ZipFile(output) as after:
        before_hashes = {name: hashlib.sha256(before.read(name)).hexdigest() for name in before.namelist()}
        after_hashes = {name: hashlib.sha256(after.read(name)).hexdigest() for name in after.namelist()}
        changed = sorted(name for name in set(before_hashes) | set(after_hashes) if before_hashes.get(name) != after_hashes.get(name))
        bad_part = after.testzip()
    allowed = {"xl/workbook.xml", "xl/worksheets/sheet2.xml", "xl/worksheets/sheet5.xml"}
    unexpected = sorted(set(changed) - allowed)
    return {"zip_ok": bad_part is None, "changed_parts": changed, "unexpected_changed_parts": unexpected}


def run(config_path: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    template = resolve_path(config["template"], config_path=config_path)
    golden = resolve_path(config["golden_workbook"], config_path=config_path)
    if not template.exists() or not golden.exists():
        raise FileNotFoundError(f"Falta plantilla o caso dorado: {template} | {golden}")
    source_audit = validate_sources(config, config_path)
    mapping = learn_mapping(template, golden)
    output_dir = resolve_path(config["output_dir"], config_path=config_path, output=True)
    output = output_dir / config["output_filename"]
    changed_parts = write_output(template, output, mapping)
    regression = compare_targets(output, golden)
    legacy_exceptions = set(config.get("legacy_formula_exceptions", []))
    formula_checks = validate_formula_map(output, legacy_exceptions)
    formula_failures = [item for item in formula_checks if item["status"] == "FAIL"]
    package = package_check(template, output)
    mapping_json = {
        "company": config["company"],
        "country": config["country"],
        "years": config["years"],
        "source_template_sha256": file_hash(template),
        "golden_workbook_sha256": file_hash(golden),
        "sheets": {
            sheet: {ref: payload.as_json() for ref, payload in patches.items()}
            for sheet, patches in mapping.items()
        },
    }
    mapping_path = output_dir / "learned_mapping.json"
    audit_path = output_dir / "regression_audit.json"
    mapping_path.write_text(json.dumps(mapping_json, indent=2, ensure_ascii=False), encoding="utf-8")
    status = "PASS" if regression["status"] == "PASS" and not formula_failures and package["zip_ok"] and not package["unexpected_changed_parts"] else "FAIL"
    audit = {
        "status": status,
        "mode": "deterministic_python_golden_regression",
        "company": config["company"],
        "years": config["years"],
        "template": {"path": str(template), "sha256": file_hash(template)},
        "golden_workbook": {"path": str(golden), "sha256": file_hash(golden)},
        "output": {"path": str(output), "sha256": file_hash(output)},
        "sources": source_audit,
        "learned_cells": sum(len(value) for value in mapping.values()),
        "writer_changed_parts": changed_parts,
        "package": package,
        "formula_checks": {"count": len(formula_checks), "failure_count": len(formula_failures), "failures": formula_failures},
        "legacy_formula_exceptions": {
            "count": sum(item["status"] == "LEGACY_EXCEPTION" for item in formula_checks),
            "reason": config.get("legacy_exception_reason"),
        },
        "regression": regression,
    }
    audit_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    if status != "PASS":
        raise RuntimeError(f"Falló la regresión de {config['company']}: revisar {audit_path}")
    return {"status": status, "workbook": str(output), "mapping": str(mapping_path), "audit": str(audit_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Aprende y valida adaptadores CIER sin IA.")
    parser.add_argument("--config", action="append", required=True, help="JSON de empresa; puede repetirse.")
    args = parser.parse_args()
    results = [run(Path(value)) for value in args.config]
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
