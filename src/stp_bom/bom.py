"""Erzeugt eine Stückliste aus den eingelesenen STEP-Entities."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
from typing import Dict, Iterable, List, Optional

from .parser import StepEntity, StepModel


@dataclass(frozen=True)
class Product:
    """Repräsentiert ein Produkt bzw. Bauteil innerhalb der STEP-Datei."""

    entity_id: int
    identifier: Optional[str]
    name: Optional[str]
    description: Optional[str]

    def display_name(self) -> str:
        parts = [part for part in (self.identifier, self.name) if part]
        return " - ".join(parts) if parts else f"#{self.entity_id}"


@dataclass(frozen=True)
class BomEntry:
    """Ein Eintrag der Stückliste."""

    product: Product
    quantity: float

    def normalized_quantity(self) -> float | int:
        if math.isclose(self.quantity, round(self.quantity)):
            return int(round(self.quantity))
        return self.quantity


@dataclass(frozen=True)
class _NextAssemblyUsage:
    parent_definition: int
    child_definition: int
    identifier: Optional[str]
    description: Optional[str]


class AssemblyGraph:
    """Bereitet die STEP-Entities so auf, dass eine Stückliste generiert werden kann."""

    def __init__(self, model: StepModel):
        self._model = model
        self._products: Dict[int, Product] = {}
        self._definition_to_product: Dict[int, int] = {}
        self._assembly_usage: List[_NextAssemblyUsage] = []
        self._child_map: Dict[int, List[int]] = defaultdict(list)
        self._prepare()

    def _prepare(self) -> None:
        formations: Dict[int, int] = {}
        for entity in self._model.entities():
            if entity.type == "PRODUCT":
                identifier = self._extract_string(entity, 0)
                name = self._extract_string(entity, 1)
                description = self._extract_string(entity, 2)
                self._products[entity.entity_id] = Product(
                    entity_id=entity.entity_id,
                    identifier=identifier,
                    name=name,
                    description=description,
                )
            elif entity.type == "PRODUCT_DEFINITION_FORMATION":
                product_ref = self._extract_ref(entity, 2)
                if product_ref is not None:
                    formations[entity.entity_id] = product_ref
            elif entity.type == "PRODUCT_DEFINITION":
                formation_ref = self._extract_ref(entity, 2)
                if formation_ref is not None:
                    product_ref = formations.get(formation_ref)
                    if product_ref is not None:
                        self._definition_to_product[entity.entity_id] = product_ref
            elif entity.type == "NEXT_ASSEMBLY_USAGE_OCCURRENCE":
                parent = self._extract_ref(entity, 2)
                child = self._extract_ref(entity, 3)
                identifier = self._extract_string(entity, 0)
                description = self._extract_string(entity, 1)
                if parent is not None and child is not None:
                    self._assembly_usage.append(
                        _NextAssemblyUsage(parent, child, identifier, description)
                    )
        for usage in self._assembly_usage:
            parent_product = self._definition_to_product.get(usage.parent_definition)
            child_product = self._definition_to_product.get(usage.child_definition)
            if parent_product is not None and child_product is not None:
                self._child_map[parent_product].append(child_product)

    def products(self) -> Iterable[Product]:
        return self._products.values()

    def product(self, product_id: int) -> Optional[Product]:
        return self._products.get(product_id)

    def resolve_root(self, selector: str | None = None) -> int:
        if selector is None:
            roots = self.root_products()
            if len(roots) == 1:
                return roots[0]
            if not roots:
                raise ValueError(
                    "Konnte kein Wurzelprodukt bestimmen. Bitte '--root' angeben."
                )
            raise ValueError(
                "Mehrere mögliche Wurzeln gefunden: "
                + ", ".join(self._describe_product(pid) for pid in roots)
            )
        product_id = self._resolve_selector(selector)
        if product_id is None:
            raise ValueError(f"Kein Produkt gefunden für Selektor '{selector}'.")
        return product_id

    def root_products(self) -> List[int]:
        parents = set(self._child_map.keys())
        children = {child for values in self._child_map.values() for child in values}
        roots = sorted(parents - children)
        if roots:
            return roots
        if len(self._products) == 1:
            return [next(iter(self._products.keys()))]
        return sorted(self._products.keys())

    def build_bom(self, root_product: int, include_assemblies: bool = False) -> List[BomEntry]:
        counts: Dict[int, float] = defaultdict(float)

        def visit(product_id: int, multiplier: float, stack: List[int]) -> None:
            if product_id in stack:
                cycle = " -> ".join(self._describe_product(pid) for pid in stack + [product_id])
                raise ValueError(f"Zyklische Baugruppenstruktur erkannt: {cycle}")
            stack.append(product_id)
            children = self._child_map.get(product_id, [])
            if children:
                if include_assemblies and product_id != root_product:
                    counts[product_id] += multiplier
                aggregated = Counter(children)
                for child_id, qty in aggregated.items():
                    visit(child_id, multiplier * qty, stack)
            else:
                if product_id != root_product or include_assemblies:
                    counts[product_id] += multiplier
            stack.pop()

        visit(root_product, 1.0, [])
        entries = []
        for product_id, quantity in counts.items():
            product = self._products.get(product_id)
            if not product:
                continue
            entries.append(
                BomEntry(
                    product=product,
                    quantity=self._normalize_quantity(quantity),
                )
            )
        entries.sort(key=lambda entry: (
            entry.product.identifier or "",
            entry.product.name or "",
            entry.product.entity_id,
        ))
        return entries

    def _normalize_quantity(self, quantity: float) -> float:
        rounded = round(quantity)
        if math.isclose(quantity, rounded):
            return float(rounded)
        return quantity

    def _describe_product(self, product_id: int) -> str:
        product = self._products.get(product_id)
        if not product:
            return f"#{product_id}"
        return product.display_name()

    def _resolve_selector(self, selector: str) -> int | None:
        selector = selector.strip()
        if selector.startswith("#") and selector[1:].isdigit():
            candidate = int(selector[1:])
            if candidate in self._products:
                return candidate
        if selector.isdigit():
            candidate = int(selector)
            if candidate in self._products:
                return candidate
        matches = [
            product_id
            for product_id, product in self._products.items()
            if (product.identifier and product.identifier == selector)
            or (product.name and product.name == selector)
        ]
        if len(matches) == 1:
            return matches[0]
        if matches:
            raise ValueError(
                "Selektor ist mehrdeutig, mehrere Produkte gefunden: "
                + ", ".join(self._describe_product(pid) for pid in matches)
            )
        lower = selector.lower()
        matches = [
            product_id
            for product_id, product in self._products.items()
            if (product.identifier and product.identifier.lower() == lower)
            or (product.name and product.name.lower() == lower)
        ]
        if len(matches) == 1:
            return matches[0]
        if matches:
            raise ValueError(
                "Selektor ist mehrdeutig, mehrere Produkte gefunden: "
                + ", ".join(self._describe_product(pid) for pid in matches)
            )
        return None

    def _extract_string(self, entity: StepEntity, index: int) -> Optional[str]:
        try:
            value = entity.params[index]
        except IndexError:
            return None
        if isinstance(value, str) and value:
            return value
        return None

    def _extract_ref(self, entity: StepEntity, index: int) -> Optional[int]:
        try:
            value = entity.params[index]
        except IndexError:
            return None
        if isinstance(value, int):
            return value
        return None


__all__ = ["AssemblyGraph", "Product", "BomEntry"]
