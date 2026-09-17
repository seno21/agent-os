"""Tests for the bundled text-file-read skill's scripts/read.py."""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "agentos"
    / "skills"
    / "bundled"
    / "text-file-read"
    / "scripts"
    / "read.py"
)


def _load_read_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("read_module", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_reads_utf8_file_verbatim(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    read_mod = _load_read_module()
    content = "line 1\nline 2 with some structured: yaml / srt\n"
    sample = tmp_path / "sample.txt"
    sample.write_text(content, encoding="utf-8")

    code = read_mod.main(["--input", str(sample)])
    assert code == 0

    captured = capsys.readouterr()
    assert captured.out == content
    assert captured.err == ""


def test_reads_non_ascii_and_emoji_content(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    read_mod = _load_read_module()
    content = "Hello 世界 🌍 日本語 café ñ\n"
    sample = tmp_path / "unicode.txt"
    sample.write_text(content, encoding="utf-8")

    code = read_mod.main(["--input", str(sample)])
    assert code == 0

    captured = capsys.readouterr()
    assert captured.out == content


def test_write_bytes_falls_back_when_stdout_has_no_buffer() -> None:
    read_mod = _load_read_module()

    class NoBufferStream(io.StringIO):
        encoding = "utf-8"

    stream = NoBufferStream()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(sys, "stdout", stream)
    try:
        read_mod._write_bytes(b"Hello World from fallback\n")
    finally:
        monkeypatch.undo()

    assert stream.getvalue() == "Hello World from fallback\n"


def test_file_not_found(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    read_mod = _load_read_module()
    non_existent = tmp_path / "missing.txt"
    code = read_mod.main(["--input", str(non_existent)])
    assert code == 1

    captured = capsys.readouterr()
    assert "Error: file not found" in captured.err
    assert captured.out == ""


def test_directory_path_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    read_mod = _load_read_module()
    d = tmp_path / "somedir"
    d.mkdir()

    code = read_mod.main(["--input", str(d)])
    assert code == 1

    captured = capsys.readouterr()
    assert "Error: not a regular file" in captured.err
    assert captured.out == ""


def test_max_bytes_exceeded(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    read_mod = _load_read_module()
    sample = tmp_path / "large.txt"
    sample.write_bytes(b"a" * 500)

    code = read_mod.main(["--input", str(sample), "--max-bytes", "100"])
    assert code == 1

    captured = capsys.readouterr()
    assert "exceeds --max-bytes 100" in captured.err
    assert captured.out == ""


def test_invalid_max_bytes_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    read_mod = _load_read_module()
    sample = tmp_path / "sample.txt"
    sample.write_text("content", encoding="utf-8")

    code_zero = read_mod.main(["--input", str(sample), "--max-bytes", "0"])
    assert code_zero == 2

    captured_zero = capsys.readouterr()
    assert "Error: --max-bytes must be greater than 0" in captured_zero.err

    code_neg = read_mod.main(["--input", str(sample), "--max-bytes", "-5"])
    assert code_neg == 2

    captured_neg = capsys.readouterr()
    assert "Error: --max-bytes must be greater than 0" in captured_neg.err


def test_invalid_utf8_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    read_mod = _load_read_module()
    sample = tmp_path / "binary.bin"
    sample.write_bytes(b"\x80\x81\xff\xfe")

    code = read_mod.main(["--input", str(sample)])
    assert code == 1

    captured = capsys.readouterr()
    assert "Error: not valid UTF-8" in captured.err
    assert captured.out == ""


def test_subprocess_cli_execution(tmp_path: Path) -> None:
    content = "subprocess test line\n"
    sample = tmp_path / "cli.txt"
    sample.write_text(content, encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), "--input", str(sample)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert proc.stdout == content
