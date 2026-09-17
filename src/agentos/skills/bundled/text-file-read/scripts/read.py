#!/usr/bin/env python3
"""Read a UTF-8 text file and print its content to stdout, verbatim.

Pairs with meta-skill review pauses that need to round-trip an
artefact through disk: the artefact is written before the pause
(typically with the builtin write_file tool), the user may hand-
edit it, and this script reads it back so the next step honours
the (possibly edited) version rather than the in-context copy.

Unlike AgentOS's builtin read_file tool — which prepends each
line with `lineno\\t` for LLM display — this returns bytes
unmodified, so structured artefacts (scripts, SRT, YAML) survive
the round-trip without their parsers breaking.

Usage:
    python read.py --input path/to/file.txt [--max-bytes 200000]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _write_bytes(data: bytes) -> None:
    """Write bytes to stdout, falling back to text stream when buffer is absent."""
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        try:
            buffer.write(data)
            buffer.flush()
            return
        except (AttributeError, OSError, ValueError):
            pass

    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    sys.stdout.write(data.decode(encoding, errors="replace"))
    sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", "-i", required=True)
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=200_000,
        help="Refuse to read files larger than this many bytes.",
    )
    args = parser.parse_args(argv)

    if args.max_bytes <= 0:
        print(
            f"Error: --max-bytes must be greater than 0, got {args.max_bytes}",
            file=sys.stderr,
        )
        return 2

    path = Path(args.input)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 1
    if not path.is_file():
        print(f"Error: not a regular file: {path}", file=sys.stderr)
        return 1

    try:
        size = path.stat().st_size
    except OSError as exc:
        print(f"Error: could not stat {path}: {exc}", file=sys.stderr)
        return 1

    if size > args.max_bytes:
        print(
            f"Error: file size {size} exceeds --max-bytes {args.max_bytes}: {path}",
            file=sys.stderr,
        )
        return 1

    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        print(f"Error: could not read {path}: {exc}", file=sys.stderr)
        return 1

    try:
        raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        print(f"Error: not valid UTF-8: {path} ({exc})", file=sys.stderr)
        return 1

    # Write through the binary buffer to bypass the Windows console
    # cp936 encoder — meta-skills capture stdout as bytes and decode
    # explicitly upstream. Falls back to text stream when buffer is absent.
    _write_bytes(raw_bytes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
