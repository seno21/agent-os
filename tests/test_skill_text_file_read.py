"""Tests for the bundled text-file-read skill."""

from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUNDLED = ROOT / "src" / "agentos" / "skills" / "bundled"


def _load(relative: str, name: str) -> Any:
    """Import a bundled script by path."""
    spec = importlib.util.spec_from_file_location(name, BUNDLED / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def read_module() -> Any:
    return _load("text-file-read/scripts/read.py", "text_file_read")


def test_read_utf8_file_verbatim(
    read_module: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sample_text = "line 1\nline 2\n\nline 4\twith tab and trailing newline\n"
    target = tmp_path / "sample.txt"
    target.write_text(sample_text, encoding="utf-8")

    code = read_module.main(["--input", str(target)])
    assert code == 0
    captured = capsys.readouterr()
    assert captured.out == sample_text
    assert captured.err == ""


def test_read_non_ascii_unicode(
    read_module: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    unicode_text = "日本語のテキスト cổ phiếu 🚀 💡"
    target = tmp_path / "unicode.txt"
    target.write_text(unicode_text, encoding="utf-8")

    code = read_module.main(["--input", str(target)])
    assert code == 0
    captured = capsys.readouterr()
    assert captured.out == unicode_text


def test_read_missing_file_fails(
    read_module: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "does_not_exist.txt"
    code = read_module.main(["--input", str(missing)])
    assert code == 1
    captured = capsys.readouterr()
    assert "file not found" in captured.err


def test_read_file_exceeding_max_bytes_fails(
    read_module: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "large.txt"
    target.write_bytes(b"A" * 500)

    code = read_module.main(["--input", str(target), "--max-bytes", "100"])
    assert code == 1
    captured = capsys.readouterr()
    assert "exceeds --max-bytes 100" in captured.err


def test_read_negative_max_bytes_fails(
    read_module: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("hello", encoding="utf-8")

    code = read_module.main(["--input", str(target), "--max-bytes", "-1"])
    assert code == 1
    captured = capsys.readouterr()
    assert "must be non-negative" in captured.err


def test_read_invalid_utf8_fails(
    read_module: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "corrupt.bin"
    target.write_bytes(b"\xff\xfe\x00\x00\x80\x81")

    code = read_module.main(["--input", str(target)])
    assert code == 1
    captured = capsys.readouterr()
    assert "not valid UTF-8" in captured.err


def test_stdout_without_buffer_attribute_fallback(
    read_module: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("plain text without buffer", encoding="utf-8")

    fake_stdout = io.StringIO()
    # StringIO does not have a 'buffer' attribute
    assert not hasattr(fake_stdout, "buffer")
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    code = read_module.main(["--input", str(target)])
    assert code == 0
    assert fake_stdout.getvalue() == "plain text without buffer"


def test_stdout_failing_buffer_fallback(
    read_module: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "fallback.txt"
    target.write_text("fallback test", encoding="utf-8")

    class FailingBuffer:
        def write(self, _b: bytes) -> int:
            raise OSError("buffer closed or unavailable")

        def flush(self) -> None:
            pass

    class FailingBufferStdout:
        def __init__(self) -> None:
            self.buffer = FailingBuffer()
            self.written: list[str] = []

        def write(self, s: str) -> int:
            self.written.append(s)
            return len(s)

        def flush(self) -> None:
            pass

    fake_stdout = FailingBufferStdout()
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    code = read_module.main(["--input", str(target)])
    assert code == 0
    assert "".join(fake_stdout.written) == "fallback test"
