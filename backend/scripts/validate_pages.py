"""Validate generated page frontmatter against the contract schema.

Usage:
    python scripts/validate_pages.py <path-with-md-files>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schema" / "page.frontmatter.schema.json"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        print("usage: python scripts/validate_pages.py <dir>")
        return 2
    target = Path(sys.argv[1])
    if not target.exists():
        print("path not found:", target)
        return 2

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    files = sorted(target.rglob("*.md"))
    errors = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            print("SKIP (no frontmatter)", path)
            continue
        front = yaml.safe_load(text.split("---", 2)[1])
        problems = sorted(validator.iter_errors(front), key=lambda e: list(e.path))
        if problems:
            errors += 1
            print("FAIL", path)
            for problem in problems:
                print("  -", "/".join(map(str, problem.path)), problem.message)
        else:
            print("ok", path.name)

    print(f"\n{len(files)} files, {errors} failed")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
