from pathlib import Path

from stp_bom.parser import StepParser


def load_sample() -> str:
    path = Path(__file__).parent / "data" / "simple_assembly.stp"
    return path.read_text(encoding="utf-8")


def test_parse_products() -> None:
    parser = StepParser()
    model = parser.parse(load_sample())
    products = {entity.entity_id: entity for entity in model.by_type("PRODUCT")}
    assert len(products) == 4
    assembly = products[10]
    assert assembly.params[0] == "ASM-001"
    assert assembly.params[1] == "Assembly"
    assert assembly.params[3] == [11]


def test_parse_next_assembly_usage() -> None:
    parser = StepParser()
    model = parser.parse(load_sample())
    relations = model.by_type("NEXT_ASSEMBLY_USAGE_OCCURRENCE")
    assert len(relations) == 4
    first = relations[0]
    assert first.params[2] == 14  # parent product definition
    assert first.params[3] == 19  # child product definition


def test_parse_complex_entity() -> None:
    parser = StepParser()
    content = "#205=(MASS_UNIT() NAMED_UNIT(*) SI_UNIT(.KILO.,.GRAM.));"
    model = parser.parse(content)
    entity = model.get(205)
    assert entity is not None
    assert entity.type == "MASS_UNIT"
    assert entity.types == ("MASS_UNIT", "NAMED_UNIT", "SI_UNIT")
    by_secondary = model.by_type("SI_UNIT")
    assert len(by_secondary) == 1
    assert by_secondary[0].entity_id == 205
