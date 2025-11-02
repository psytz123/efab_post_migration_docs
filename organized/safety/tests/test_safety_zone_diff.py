import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from organized.safety import safety_zone_diff


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "task_file,edge_file,expected_status",
    [
        ("task_zones_match.json", "edge_zones_match.json", "ok"),
        ("task_zones_missing.json", "edge_zones_match.json", "action_required"),
    ],
)
def test_generate_report_summary(task_file: str, edge_file: str, expected_status: str) -> None:
    task = load(task_file)
    edge = load(edge_file)

    report = safety_zone_diff.generate_report(task, edge)

    assert report["summary"]["status"] == expected_status


def test_remediation_suggestions_for_missing_edge_zone() -> None:
    task = load("task_zones_match.json")
    edge = load("edge_zone_missing.json")

    report = safety_zone_diff.generate_report(task, edge)
    remediation = {item["path"]: item["suggestion"] for item in report["remediations"]}

    assert "safe_zone_a" in remediation
    assert "Edge configuration" in remediation["safe_zone_a"]


def test_fail_on_diff_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    task_file = tmp_path / "task.json"
    edge_file = tmp_path / "edge.json"
    task_file.write_text(json.dumps({"safety_zones": {"zone1": {"radius": 1}}}), encoding="utf-8")
    edge_file.write_text(json.dumps({"safety_zones": {"zone1": {"radius": 2}}}), encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        monkeypatch.setattr(
            safety_zone_diff,
            "parse_args",
            lambda: argparse.Namespace(
                task_api=task_file,
                edge=edge_file,
                pretty=False,
                fail_on_diff=True,
                summary=False,
            ),
        )
        safety_zone_diff.main()

    assert exc.value.code == 2
