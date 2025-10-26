"""Kommandozeilenwerkzeug zur Erstellung einer Stückliste aus STEP-Dateien."""

from __future__ import annotations

import argparse
import csv
import json
import math
from io import StringIO
from pathlib import Path
import sys
from typing import Iterable, List

from .bom import AssemblyGraph, BomEntry
from .parser import StepParser, StepParseError


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step_file", help="Pfad zur STEP/STP-Datei")
    parser.add_argument("--root", help="Top-Level-Produkt (Name, Nummer oder #ID)")
    parser.add_argument(
        "--format",
        choices=("table", "csv", "json"),
        default="table",
        help="Ausgabeformat",
    )
    parser.add_argument("--output", help="Dateipfad für die Ausgabe")
    parser.add_argument(
        "--include-assemblies",
        action="store_true",
        help="Zwischenbaugruppen in die Ausgabe aufnehmen",
    )
    args = parser.parse_args(argv)

    step_path = Path(args.step_file)
    try:
        content = step_path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        print(f"Fehler beim Lesen der Datei: {exc}", file=sys.stderr)
        return 1

    parser_instance = StepParser()
    try:
        model = parser_instance.parse(content)
    except StepParseError as exc:
        print(f"Fehler beim Interpretieren der STEP-Datei: {exc}", file=sys.stderr)
        return 2

    graph = AssemblyGraph(model)
    try:
        root_id = graph.resolve_root(args.root)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 3

    entries = graph.build_bom(root_id, include_assemblies=args.include_assemblies)
    output = _render_output(entries, args.format)
    if args.format == "table":
        root_product = graph.product(root_id)
        header_lines = []
        if root_product is not None:
            header_lines.append(
                f"Wurzelprodukt: {root_product.display_name()} (#{root_product.entity_id})"
            )
        if args.include_assemblies:
            header_lines.append("Einschließlich Zwischenbaugruppen")
        if header_lines:
            output = "\n".join(header_lines + ["", output])

    if args.output:
        out_path = Path(args.output)
        try:
            out_path.write_text(output, encoding="utf-8")
        except OSError as exc:
            print(f"Fehler beim Schreiben der Ausgabe: {exc}", file=sys.stderr)
            return 4
    else:
        print(output)
    return 0


def _render_output(entries: Iterable[BomEntry], format_name: str) -> str:
    if format_name == "table":
        return _render_table(entries)
    if format_name == "csv":
        return _render_csv(entries)
    if format_name == "json":
        return _render_json(entries)
    raise ValueError(f"Unbekanntes Format: {format_name}")


def _render_table(entries: Iterable[BomEntry]) -> str:
    headers = ["Part Number", "Name", "Quantity", "Description"]
    rows = [
        [
            entry.product.identifier or "",
            entry.product.name or "",
            _format_quantity(entry.quantity),
            entry.product.description or "",
        ]
        for entry in entries
    ]
    widths = [len(header) for header in headers]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))
    lines: List[str] = []
    header_line = " | ".join(
        value.rjust(widths[idx]) if idx == 2 else value.ljust(widths[idx])
        for idx, value in enumerate(headers)
    )
    separator = "-+-".join("-" * width for width in widths)
    lines.append(header_line)
    lines.append(separator)
    for row in rows:
        line = " | ".join(
            value.rjust(widths[idx]) if idx == 2 else value.ljust(widths[idx])
            for idx, value in enumerate(row)
        )
        lines.append(line)
    if not rows:
        lines.append("(keine Einträge)")
    return "\n".join(lines)


def _render_csv(entries: Iterable[BomEntry]) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["part_number", "name", "quantity", "description", "entity_id"])
    for entry in entries:
        writer.writerow(
            [
                entry.product.identifier or "",
                entry.product.name or "",
                _format_quantity(entry.quantity),
                entry.product.description or "",
                entry.product.entity_id,
            ]
        )
    return buffer.getvalue().strip()


def _render_json(entries: Iterable[BomEntry]) -> str:
    data = [
        {
            "part_number": entry.product.identifier,
            "name": entry.product.name,
            "quantity": _parse_quantity(entry.quantity),
            "description": entry.product.description,
            "entity_id": entry.product.entity_id,
        }
        for entry in entries
    ]
    return json.dumps(data, indent=2, ensure_ascii=False)


def _format_quantity(quantity: float) -> str:
    parsed = _parse_quantity(quantity)
    return str(parsed)


def _parse_quantity(quantity: float) -> float | int:
    rounded = round(quantity)
    if math.isclose(quantity, rounded):
        return int(rounded)
    return quantity


if __name__ == "__main__":  # pragma: no cover - CLI Einstiegspunkt
    raise SystemExit(main())
