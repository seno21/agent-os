"""deep-research scripts — validation of record and plan files."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "src" / "agentos" / "skills" / "bundled" / "deep-research" / "scripts"


def _import_scripts():
    sys.path.insert(0, str(SCRIPTS))
    try:
        import compile as compile_script  # type: ignore[import-not-found]
        import iterate  # type: ignore[import-not-found]
        import plan as plan_script  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)
    return plan_script, iterate, compile_script


def _make_sample_plan(tmp_path: Path) -> Path:
    plan_script, _, _ = _import_scripts()
    plan = plan_script.Plan(
        question="What is the impact of AI on programming?",
        depth="overview",
        created_at="2026-01-01T00:00:00Z",
        subquestions=plan_script.make_subquestions("test", "overview"),
    )
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    return plan_path


@pytest.mark.parametrize(
    "record_text",
    [
        '{"subquestion_id": "sq-001", "url": "https://example.com"}',
        '"evidence"',
        "42",
        "null",
        "true",
    ],
)
def test_iterate_refuses_non_list_record_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    record_text: str,
) -> None:
    _, iterate, _ = _import_scripts()
    plan_path = _make_sample_plan(tmp_path)
    initial_plan = plan_path.read_text(encoding="utf-8")

    record_path = tmp_path / "evidence.json"
    record_path.write_text(record_text, encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["iterate.py", "--plan", str(plan_path), "--round", "1", "--record", str(record_path)],
    )

    assert iterate.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "must be a JSON list of evidence items" in captured.err
    assert plan_path.read_text(encoding="utf-8") == initial_plan, (
        "refused record must not mutate plan"
    )


@pytest.mark.parametrize(
    "record_bytes",
    [
        b'[{"subquestion_id": "sq-001",',
        '[{"subquestion_id": "sq-001"}]'.encode("utf-16"),
    ],
)
def test_iterate_refuses_invalid_json_record_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    record_bytes: bytes,
) -> None:
    _, iterate, _ = _import_scripts()
    plan_path = _make_sample_plan(tmp_path)
    initial_plan = plan_path.read_text(encoding="utf-8")

    record_path = tmp_path / "evidence.json"
    record_path.write_bytes(record_bytes)

    monkeypatch.setattr(
        sys,
        "argv",
        ["iterate.py", "--plan", str(plan_path), "--round", "1", "--record", str(record_path)],
    )

    assert iterate.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "is not valid JSON" in captured.err
    assert plan_path.read_text(encoding="utf-8") == initial_plan


def test_iterate_refuses_invalid_plan_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, iterate, _ = _import_scripts()
    plan_path = tmp_path / "corrupt_plan.json"
    plan_path.write_text('{"bad": "schema"}', encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["iterate.py", "--plan", str(plan_path), "--round", "1", "--print-fetches"],
    )

    assert iterate.main() == 2
    captured = capsys.readouterr()
    assert "is not valid JSON or plan schema" in captured.err


def test_compile_refuses_invalid_plan_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, _, compile_script = _import_scripts()
    plan_path = tmp_path / "corrupt_plan.json"
    plan_path.write_text('{"bad": "schema"}', encoding="utf-8")
    out_path = tmp_path / "report.md"

    monkeypatch.setattr(
        sys,
        "argv",
        ["compile.py", "--plan", str(plan_path), "--out", str(out_path)],
    )

    assert compile_script.main() == 2
    captured = capsys.readouterr()
    assert "is not valid JSON or plan schema" in captured.err
    assert not out_path.exists()


def test_iterate_records_evidence_with_null_and_string_relevance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plan_script, iterate, _ = _import_scripts()
    plan_path = _make_sample_plan(tmp_path)

    evidence_data = [
        {
            "subquestion_id": "sq-001",
            "url": "https://example.com/1",
            "relevance": None,
            "title": None,
            "excerpt": None,
            "fetched_at": None,
        },
        {
            "subquestion_id": "sq-002",
            "url": "https://example.com/2",
            "relevance": "0.85",
            "title": "Example 2",
        },
        {
            "subquestion_id": "sq-003",
            "url": "https://example.com/3",
            "relevance": "high",
            "title": "Example 3",
        },
        {
            "subquestion_id": "sq-001",
            "url": "https://example.com/4",
            "relevance": True,
        },
    ]
    record_path = tmp_path / "evidence.json"
    record_path.write_text(
        __import__("json").dumps(evidence_data),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        ["iterate.py", "--plan", str(plan_path), "--round", "1", "--record", str(record_path)],
    )

    assert iterate.main() == 0
    updated_plan = plan_script.Plan.model_validate_json(plan_path.read_text(encoding="utf-8"))

    sq1 = next(sq for sq in updated_plan.subquestions if sq.id == "sq-001")
    assert len(sq1.sources) == 2
    assert sq1.sources[0].url == "https://example.com/1"
    assert sq1.sources[0].title == ""
    assert sq1.sources[0].excerpt == ""
    assert sq1.sources[0].fetched_at == ""
    assert sq1.sources[0].relevance == 0.0
    assert sq1.sources[1].relevance == 0.0

    sq2 = next(sq for sq in updated_plan.subquestions if sq.id == "sq-002")
    assert len(sq2.sources) == 1
    assert sq2.sources[0].relevance == 0.85
    assert sq2.sources[0].title == "Example 2"

    sq3 = next(sq for sq in updated_plan.subquestions if sq.id == "sq-003")
    assert len(sq3.sources) == 1
    assert sq3.sources[0].relevance == 0.0
    assert sq3.sources[0].title == "Example 3"


def test_iterate_skips_non_dict_evidence_items(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plan_script, iterate, _ = _import_scripts()
    plan_path = _make_sample_plan(tmp_path)

    evidence_data = [
        {"subquestion_id": "sq-001", "url": "https://example.com/1"},
        "invalid-item",
        None,
        42,
        {"subquestion_id": "sq-002", "url": "https://example.com/2"},
    ]
    record_path = tmp_path / "evidence.json"
    record_path.write_text(
        __import__("json").dumps(evidence_data),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        ["iterate.py", "--plan", str(plan_path), "--round", "1", "--record", str(record_path)],
    )

    assert iterate.main() == 0
    updated_plan = plan_script.Plan.model_validate_json(plan_path.read_text(encoding="utf-8"))

    sq1 = next(sq for sq in updated_plan.subquestions if sq.id == "sq-001")
    assert len(sq1.sources) == 1
    assert sq1.sources[0].url == "https://example.com/1"

    sq2 = next(sq for sq in updated_plan.subquestions if sq.id == "sq-002")
    assert len(sq2.sources) == 1
    assert sq2.sources[0].url == "https://example.com/2"
