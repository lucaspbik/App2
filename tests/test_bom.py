from pathlib import Path

from stp_bom.bom import AssemblyGraph
from stp_bom.parser import StepParser


def load_model():
    path = Path(__file__).parent / "data" / "simple_assembly.stp"
    content = path.read_text(encoding="utf-8")
    parser = StepParser()
    return parser.parse(content)


def test_bom_flattened_quantities():
    model = load_model()
    graph = AssemblyGraph(model)
    root = graph.resolve_root()
    entries = graph.build_bom(root)
    quantities = {
        entry.product.identifier: entry.normalized_quantity() for entry in entries
    }
    assert quantities == {"PART-A": 2, "PART-B": 1}


def test_bom_includes_assemblies_when_requested():
    model = load_model()
    graph = AssemblyGraph(model)
    root = graph.resolve_root()
    entries = graph.build_bom(root, include_assemblies=True)
    quantities = {
        entry.product.identifier: entry.normalized_quantity() for entry in entries
    }
    assert quantities == {"PART-A": 2, "SUB-ASM": 1, "PART-B": 1}
