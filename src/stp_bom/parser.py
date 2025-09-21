"""Parser für STEP-Dateien (ISO-10303-21) mit Fokus auf Baugruppenstrukturen."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Dict, Iterable, List, Sequence, Tuple


@dataclass(frozen=True)
class StepEntity:
    """Repräsentiert eine einzelne STEP-Entity."""

    entity_id: int
    components: Tuple[Tuple[str, Sequence[Any]], ...]

    @property
    def type(self) -> str:
        """Primärer STEP-Typ (erstes Element einer komplexen Entity)."""

        return self.components[0][0]

    @property
    def params(self) -> Sequence[Any]:
        """Parameter des primären Typs."""

        return self.components[0][1]

    @property
    def types(self) -> Tuple[str, ...]:
        """Alle zugehörigen STEP-Typen (bei komplexen Entities)."""

        return tuple(component[0] for component in self.components)


class StepParseError(RuntimeError):
    """Signalisiert Fehler beim Einlesen oder Interpretieren einer STEP-Datei."""


class StepModel:
    """Enthält alle eingelesenen STEP-Entities."""

    def __init__(self, entities: Dict[int, StepEntity]):
        self._entities = entities

    def get(self, entity_id: int) -> StepEntity | None:
        return self._entities.get(entity_id)

    def entities(self) -> Iterable[StepEntity]:
        return self._entities.values()

    def by_type(self, type_name: str) -> List[StepEntity]:
        target = type_name.upper()
        return [
            entity
            for entity in self._entities.values()
            if target in entity.types
        ]


class StepParser:
    """Liest eine STEP-Datei ein und liefert ein :class:`StepModel`."""

    _entity_pattern = re.compile(
        r"#(\d+)\s*=\s*([A-Z0-9_]+)\s*\((.*)\)", re.IGNORECASE
    )
    _complex_entity_pattern = re.compile(r"#(\d+)\s*=\s*\((.*)\)", re.IGNORECASE)
    _inline_comment_pattern = re.compile(r"/\*.*?\*/")

    def parse(self, content: str) -> StepModel:
        """Parst den gegebenen STEP-Inhalt."""

        entities: Dict[int, StepEntity] = {}
        for statement in self._statements(content):
            if not statement.startswith("#"):
                continue
            entity = self._parse_entity(statement)
            entities[entity.entity_id] = entity
        return StepModel(entities)

    def _statements(self, content: str) -> Iterable[str]:
        buffer = ""
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            line = self._remove_comments(line)
            if not line:
                continue
            buffer = f"{buffer} {line}".strip() if buffer else line
            while ";" in buffer:
                index = buffer.index(";")
                statement = buffer[:index].strip()
                if statement:
                    yield statement
                buffer = buffer[index + 1 :].strip()
        if buffer:
            yield buffer

    def _remove_comments(self, line: str) -> str:
        return re.sub(self._inline_comment_pattern, " ", line)

    def _parse_entity(self, statement: str) -> StepEntity:
        match = self._entity_pattern.fullmatch(statement)
        if match:
            entity_id = int(match.group(1))
            type_name = match.group(2).upper()
            params_raw = match.group(3).strip()
            params = self._parse_params(params_raw) if params_raw else []
            return StepEntity(
                entity_id=entity_id,
                components=((type_name, params),),
            )
        complex_match = self._complex_entity_pattern.fullmatch(statement)
        if complex_match:
            entity_id = int(complex_match.group(1))
            body = complex_match.group(2).strip()
            components = self._parse_complex_components(body)
            if not components:
                raise StepParseError(
                    f"Kann Entity nicht interpretieren: {statement}"
                )
            return StepEntity(entity_id=entity_id, components=tuple(components))
        raise StepParseError(f"Kann Entity nicht interpretieren: {statement}")

    def _parse_complex_components(
        self, body: str
    ) -> List[Tuple[str, Sequence[Any]]]:
        components: List[Tuple[str, Sequence[Any]]] = []
        index = 0
        length = len(body)
        while index < length:
            while index < length and body[index].isspace():
                index += 1
            if index >= length:
                break
            start = index
            while index < length and (body[index].isalnum() or body[index] == "_"):
                index += 1
            if start == index:
                raise StepParseError(
                    f"Kann komplexe Entity nicht interpretieren: {body}"
                )
            type_name = body[start:index].upper()
            while index < length and body[index].isspace():
                index += 1
            if index >= length or body[index] != "(":
                raise StepParseError(
                    f"Erwarte Parameterliste für komplexen Typ '{type_name}'"
                )
            params_raw, index = self._consume_parenthesized(body, index)
            params = self._parse_params(params_raw) if params_raw else []
            components.append((type_name, params))
        return components

    def _consume_parenthesized(self, text: str, start: int) -> Tuple[str, int]:
        if text[start] != "(":
            raise StepParseError("Interner Fehler: erwartete öffnende Klammer")
        index = start + 1
        depth = 1
        in_string = False
        buffer: List[str] = []
        length = len(text)
        while index < length and depth > 0:
            ch = text[index]
            if in_string:
                buffer.append(ch)
                if ch == "'":
                    next_char = text[index + 1] if index + 1 < length else ""
                    if next_char == "'":
                        buffer.append("'")
                        index += 1
                    else:
                        in_string = False
                index += 1
                continue
            if ch == "'":
                in_string = True
                buffer.append(ch)
            elif ch == "(":
                depth += 1
                buffer.append(ch)
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    index += 1
                    break
                buffer.append(ch)
            else:
                buffer.append(ch)
            index += 1
        if depth != 0:
            raise StepParseError("Fehlende schließende Klammer in Parameterliste")
        return "".join(buffer).strip(), index

    def _parse_params(self, params: str) -> List[Any]:
        tokens = self._split_parameters(params)
        return [self._parse_value(token) for token in tokens]

    def _split_parameters(self, params: str) -> List[str]:
        if not params:
            return []
        result: List[str] = []
        current: List[str] = []
        depth = 0
        in_string = False
        i = 0
        while i < len(params):
            ch = params[i]
            if in_string:
                current.append(ch)
                if ch == "'":
                    next_char = params[i + 1] if i + 1 < len(params) else ""
                    if next_char == "'":
                        current.append("'")
                        i += 1
                    else:
                        in_string = False
                i += 1
                continue
            if ch == "'":
                in_string = True
                current.append(ch)
            elif ch == "(":
                depth += 1
                current.append(ch)
            elif ch == ")":
                depth -= 1
                current.append(ch)
            elif ch == "," and depth == 0:
                token = "".join(current).strip()
                if token:
                    result.append(token)
                current = []
                i += 1
                continue
            else:
                current.append(ch)
            i += 1
        token = "".join(current).strip()
        if token:
            result.append(token)
        return result

    def _parse_value(self, token: str) -> Any:
        token = token.strip()
        if not token:
            return ""
        upper = token.upper()
        if upper == ".T.":
            return True
        if upper == ".F.":
            return False
        if token == "$":
            return None
        if token.startswith("#") and token[1:].isdigit():
            return int(token[1:])
        if token.startswith("'") and token.endswith("'"):
            inner = token[1:-1].replace("''", "'")
            return inner
        if token.startswith("(") and token.endswith(")"):
            inner = token[1:-1].strip()
            if not inner:
                return []
            return [self._parse_value(part) for part in self._split_parameters(inner)]
        if self._is_number(token):
            return self._parse_number(token)
        return token

    def _parse_number(self, token: str) -> Any:
        if any(ch in token for ch in ".eE"):
            try:
                value = float(token)
            except ValueError as exc:  # pragma: no cover - defensive fallback
                raise StepParseError(f"Kann Zahl nicht lesen: {token}") from exc
            return value
        try:
            return int(token)
        except ValueError:
            try:
                return float(token)
            except ValueError as exc:  # pragma: no cover - defensive fallback
                raise StepParseError(f"Kann Zahl nicht lesen: {token}") from exc

    def _is_number(self, token: str) -> bool:
        try:
            float(token)
        except ValueError:
            return False
        return math.isfinite(float(token))


__all__ = ["StepParser", "StepParseError", "StepModel", "StepEntity"]
