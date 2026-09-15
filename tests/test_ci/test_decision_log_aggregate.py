"""CI guard: the decision-log aggregate library must stay importable.

`observability.decision_log_aggregate` is consumed by
`skills/bundled/history-explorer/scripts/explore.py` — a subprocess
entrypoint that imports via the `sys.path.insert` bootstrap.

If somebody renames or relocates the module, this test fails loudly
so the duplicated definitions don't drift back into the bundled
script.
"""

from __future__ import annotations


def test_module_importable_with_expected_public_api() -> None:
    from agentos.observability import decision_log_aggregate as agg

    for name in (
        "parse_log_line",
        "within_window",
        "aggregate_co_occurrences",
    ):
        assert hasattr(agg, name), f"public API drifted: missing {name!r}"

    assert name in agg.__all__  # last name from the loop is enough as smoke


def test_history_explorer_script_imports_from_aggregate_module() -> None:
    """The bundled script must not redefine the lifted functions."""

    from pathlib import Path

    script = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "agentos"
        / "skills"
        / "bundled"
        / "history-explorer"
        / "scripts"
        / "explore.py"
    )
    text = script.read_text(encoding="utf-8")
    assert "from agentos.observability.decision_log_aggregate import" in text
    assert "def aggregate_co_occurrences" not in text, (
        "explore.py must import aggregate_co_occurrences, not redefine it"
    )


def test_within_window_handles_naive_and_aware_timestamps() -> None:
    from datetime import UTC, datetime

    from agentos.observability.decision_log_aggregate import within_window

    cutoff = datetime(2026, 9, 10, 0, 0, 0, tzinfo=UTC)

    # UTC with Z
    assert within_window("2026-09-15T12:00:00Z", cutoff) is True
    assert within_window("2026-09-01T12:00:00Z", cutoff) is False

    # Naive ISO string (assumed UTC)
    assert within_window("2026-09-15T12:00:00", cutoff) is True
    assert within_window("2026-09-01T12:00:00", cutoff) is False

    # Explicit timezone offset
    assert within_window("2026-09-15T12:00:00+08:00", cutoff) is True
    assert within_window("2026-09-01T12:00:00-05:00", cutoff) is False

    # Naive cutoff datetime
    naive_cutoff = datetime(2026, 9, 10, 0, 0, 0)
    assert within_window("2026-09-15T12:00:00Z", naive_cutoff) is True
    assert within_window("2026-09-15T12:00:00", naive_cutoff) is True
    assert within_window("2026-09-01T12:00:00", naive_cutoff) is False

    # Invalid or non-string inputs
    assert within_window("", cutoff) is False
    assert within_window("not-a-timestamp", cutoff) is False
    assert within_window("2026-99-99T99:99:99", cutoff) is False


def test_aggregate_co_occurrences_tolerates_naive_timestamps(tmp_path) -> None:
    import json

    from agentos.observability.decision_log_aggregate import aggregate_co_occurrences

    log = tmp_path / "decisions-20260915.jsonl"
    lines = [
        json.dumps(
            {
                "turn_id": "t1",
                "ts": "2026-09-15T12:00:00",  # naive timestamp
                "skills_invoked": ["pdf-toolkit", "summarize"],
                "user_intent": "summarize document",
            }
        ),
        json.dumps(
            {
                "turn_id": "t2",
                "ts": "2026-09-15T12:05:00Z",  # aware timestamp
                "skills_invoked": ["pdf-toolkit", "summarize"],
                "user_intent": "summarize another document",
            }
        ),
        json.dumps(
            {
                "turn_id": "t3",
                "ts": "2020-01-01T00:00:00",  # old naive timestamp
                "skills_invoked": ["weather", "git-diff"],
                "user_intent": "old call",
            }
        ),
    ]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    results = aggregate_co_occurrences(tmp_path, window_days=30, top_k=10)
    assert len(results) == 1
    assert results[0]["skills"] == ["pdf-toolkit", "summarize"]
    assert results[0]["freq"] == 2
