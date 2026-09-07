"""Unit tests for daily maintenance check engine."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from daily_maintenance_check import (
    check_git_cleanliness,
    check_repo_structure,
    check_syntax,
    generate_status_report,
    parse_existing_history,
)
from datetime import datetime, timezone


def test_check_repo_structure(tmp_path: Path):
    # Missing files initially
    ok, count, missing = check_repo_structure(tmp_path)
    assert ok is False
    assert len(missing) > 0

    # Add core files
    (tmp_path / "README.md").write_text("# Test", encoding="utf-8")
    (tmp_path / "LICENSE").write_text("MIT", encoding="utf-8")
    (tmp_path / "CONTRIBUTING.md").write_text("Contrib", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("*.tmp", encoding="utf-8")
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("name: CI", encoding="utf-8")
    (wf / "infra-validation.yml").write_text("name: Infra", encoding="utf-8")
    (wf / "scheduled-health-check.yml").write_text("name: Health", encoding="utf-8")
    sc = tmp_path / ".github" / "scripts"
    sc.mkdir(parents=True)
    (sc / "requirements.txt").write_text("pytest", encoding="utf-8")
    (sc / "lib").mkdir()
    (sc / "lib" / "gh_report.py").write_text("# report", encoding="utf-8")
    (sc / "agents").mkdir()
    (sc / "agents" / "repo_health_agent.py").write_text("# agent1", encoding="utf-8")
    (sc / "agents" / "security_dependency_agent.py").write_text("# agent2", encoding="utf-8")

    ok2, count2, missing2 = check_repo_structure(tmp_path)
    assert ok2 is True
    assert count2 == 11
    assert len(missing2) == 0


def test_check_syntax(tmp_path: Path):
    valid_yml = tmp_path / "valid.yml"
    valid_yml.write_text("name: my-workflow\non: push\n", encoding="utf-8")

    invalid_json = tmp_path / "bad.json"
    invalid_json.write_text("{ unquoted: 123 ", encoding="utf-8")

    ok, count, errors = check_syntax(tmp_path)
    assert ok is False
    assert len(errors) == 1
    assert "bad.json" in errors[0]


def test_generate_status_report(tmp_path: Path):
    log_file = tmp_path / "daily-status.md"
    now = datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)

    report = generate_status_report(
        repo_root=tmp_path,
        target_log=log_file,
        structure_ok=True,
        core_found=11,
        structure_err=[],
        syntax_ok=True,
        syntax_count=5,
        syntax_err=[],
        git_clean=True,
        unexpected_files=[],
        now=now,
    )

    assert "Application Code Integrity Guaranteed" in report
    assert "Zero production code or manifest files touched" in report
    assert "2026-09-02" in report
    assert "16 files" in report


def test_generate_status_report_no_trailing_whitespace(tmp_path: Path):
    log_file = tmp_path / "daily-status.md"
    now = datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)

    report = generate_status_report(
        repo_root=tmp_path,
        target_log=log_file,
        structure_ok=True,
        core_found=11,
        structure_err=[],
        syntax_ok=True,
        syntax_count=5,
        syntax_err=[],
        git_clean=True,
        unexpected_files=[],
        now=now,
    )

    for idx, line in enumerate(report.splitlines(), 1):
        assert line == line.rstrip(), f"Line {idx} contains trailing whitespace: {repr(line)}"
    assert report.endswith("\n"), "Report must end with a newline"


def test_parse_existing_history_no_duplication(tmp_path: Path):
    log_file = tmp_path / "daily-status.md"
    sample_content = (
        "# Automated Daily Repository Maintenance Log\n\n"
        "## 📜 Maintenance Run History (Rolling 14-Day Audit)\n\n"
        "| Date (UTC) | Health Status | Files Inspected | Application Modified? |\n"
        "| :--- | :---: | :---: | :---: |\n"
        "| 2026-09-02 | ✅ Success | 14 files | ❌ NO (0 changes) |\n"
    )
    log_file.write_text(sample_content, encoding="utf-8")

    history = parse_existing_history(log_file)
    assert len(history) == 1
    assert history[0]["files_inspected"] == "14"

    now = datetime(2026, 9, 3, 12, 0, 0, tzinfo=timezone.utc)
    new_report = generate_status_report(
        repo_root=tmp_path,
        target_log=log_file,
        structure_ok=True,
        core_found=11,
        structure_err=[],
        syntax_ok=True,
        syntax_count=5,
        syntax_err=[],
        git_clean=True,
        unexpected_files=[],
        now=now,
    )
    assert "14 files files" not in new_report
    assert "14 files |" in new_report

