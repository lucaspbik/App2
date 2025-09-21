import json
from pathlib import Path

from stp_bom import cli


def sample_path() -> Path:
    return Path(__file__).parent / "data" / "simple_assembly.stp"


def test_cli_table_output(capsys):
    exit_code = cli.main([str(sample_path())])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Wurzelprodukt" in out
    assert "PART-A" in out
    assert "PART-B" in out


def test_cli_json_output(capsys):
    exit_code = cli.main([str(sample_path()), "--format", "json"])
    assert exit_code == 0
    out = capsys.readouterr().out.strip()
    data = json.loads(out)
    assert any(item["part_number"] == "PART-A" for item in data)
    assert any(item["part_number"] == "PART-B" for item in data)
