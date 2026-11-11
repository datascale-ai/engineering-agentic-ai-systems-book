"""Check subprocess recovery, drift rejection and strict configuration boundaries."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from book_reference.cli import load_manifest, verify_inventory
from book_reference.contracts import Rejected

CH36 = Path(__file__).resolve().parents[2] / "ch36"


def test_three_project_slices_in_separate_processes(tmp_path):
    result = subprocess.run([sys.executable, str(CH36 / "run.py"), "reproduce", "--output", str(tmp_path / "run")],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    report = json.loads((tmp_path / "run/reproduction.json").read_text(encoding="utf-8"))
    assert report["passed"]
    assert [item["exit_code"] for item in report["commands"]] == [0, 0, 42, 0]
    summary = json.loads((tmp_path / "run/PRJ-3/summary.json").read_text(encoding="utf-8"))
    assert summary["ticket_count"] == 1
    assert summary["oracle_passed"]
    assert "outcome_resolved" in summary["event_kinds"]


@pytest.mark.parametrize("change", ("changed_fixture", "missing_fixture", "changed_lock", "extra_code"))
def test_asset_drift_fails_closed(change, tmp_path):
    target = tmp_path / "baseline"
    shutil.copytree(CH36, target, ignore=shutil.ignore_patterns(".venv", "__pycache__", "outputs", "reports"))
    if change == "changed_fixture":
        with (target / "fixtures/policy.json").open("a", encoding="utf-8") as handle:
            handle.write("\n ")
    elif change == "missing_fixture":
        (target / "fixtures/policy.json").unlink()
    elif change == "changed_lock":
        with (target / "uv.lock").open("a", encoding="utf-8") as handle:
            handle.write("\n# controlled drift\n")
    else:
        (target / "src/unreviewed.py").write_text("pass\n", encoding="utf-8")
    with pytest.raises((Rejected, FileNotFoundError)):
        verify_inventory(target)


def test_unknown_secret_config_field_is_rejected(tmp_path):
    shutil.copytree(CH36 / "fixtures", tmp_path / "fixtures")
    text = (CH36 / "run_manifest.toml").read_text(encoding="utf-8")
    # Fixed fake marker only; never inspect a user's real credentials.
    (tmp_path / "run_manifest.toml").write_text('api_key = "FAKE-TEST-ONLY"\n' + text, encoding="utf-8")
    with pytest.raises(Rejected, match="manifest_fields"):
        load_manifest(tmp_path)


def test_cli_preserves_existing_output(tmp_path):
    marker = tmp_path / "user-notes.txt"
    marker.write_text("keep", encoding="utf-8")
    result = subprocess.run([sys.executable, str(CH36 / "run.py"), "run", "--output", str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 2
    assert "output_not_empty" in result.stderr
    assert marker.read_text(encoding="utf-8") == "keep"
