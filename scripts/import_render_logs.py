"""Import structured monitoring events exported from Render into SQLite."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scoring_api.monitoring_storage import import_render_export


def parse_arguments() -> argparse.Namespace:
    """Return command-line parameters for a local Render-log import."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("data/monitoring/monitoring.db"),
    )
    return parser.parse_args()


def main() -> int:
    """Run the importer and return a shell-compatible exit status."""
    arguments = parse_arguments()
    if not arguments.input.is_file():
        print(f"Input file does not exist: {arguments.input}", file=sys.stderr)
        return 2

    try:
        imported = import_render_export(arguments.input, arguments.database)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    print(f"Imported {imported} new monitoring event(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
