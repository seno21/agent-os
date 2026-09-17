"""Create a `.docx` from a declarative JSON spec.

Spec schema:
    {
      "metadata": {"title": "...", "author": "..."},
      "body": [
        {"kind": "heading", "level": 1, "text": "..."},
        {"kind": "paragraph", "text": "...", "style": "Normal"},
        {"kind": "table", "rows": [["..."]]}
      ]
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from docx import Document


def build(spec: dict[str, Any]) -> Document:
    doc = Document()
    if not isinstance(spec, dict):
        return doc

    meta = spec.get("metadata", {})
    if isinstance(meta, dict):
        core = doc.core_properties
        if "title" in meta:
            core.title = str(meta["title"])
        if "author" in meta:
            core.author = str(meta["author"])

    body = spec.get("body", [])
    if not isinstance(body, list):
        return doc

    for item in body:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        if kind == "heading":
            try:
                level = int(item.get("level", 1))
            except (ValueError, TypeError):
                level = 1
            doc.add_heading(str(item.get("text", "")), level=level)
        elif kind == "paragraph":
            style = item.get("style") or "Normal"
            doc.add_paragraph(str(item.get("text", "")), style=str(style))
        elif kind == "table":
            rows = item.get("rows") or []
            if not isinstance(rows, list) or not rows:
                continue
            valid_rows: list[list[Any]] = [r for r in rows if isinstance(r, list)]
            if not valid_rows:
                continue
            ncols = max((len(r) for r in valid_rows), default=0)
            if ncols == 0:
                continue
            table = doc.add_table(rows=len(valid_rows), cols=ncols)
            for r_idx, row in enumerate(valid_rows):
                for c_idx, value in enumerate(row):
                    table.rows[r_idx].cells[c_idx].text = str(value)
        elif kind == "page_break":
            doc.add_page_break()
    return doc


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a .docx from a JSON spec.")
    parser.add_argument("spec", type=Path, help="Path to a JSON spec file")
    parser.add_argument("--out", type=Path, required=True, help="Output .docx path")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.spec.is_file():
        print(f"error: spec {args.spec} not found", file=sys.stderr)
        return 2
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"error: spec {args.spec} is not valid JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(spec, dict):
        print(
            f"error: spec {args.spec} must be a JSON object, got {type(spec).__name__}",
            file=sys.stderr,
        )
        return 2
    doc = build(spec)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
