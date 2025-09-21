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
