from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.cms import import_cms_bundle, write_bundle


def _read_zip_allowlist(path: Path | None) -> set[str] | None:
    if path is None:
        return None
    return {
        line.strip()[:5]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import and validate CMS hospice CSV files.")
    parser.add_argument("--enrollments", required=True)
    parser.add_argument("--owners", required=True)
    parser.add_argument("--additional-addresses", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--la-county-zip-file",
        type=Path,
        help="Required when the enrollment file does not contain an authoritative county column.",
    )
    args = parser.parse_args()

    result = import_cms_bundle(
        args.enrollments,
        args.owners,
        args.additional_addresses,
        la_county_zip_codes=_read_zip_allowlist(args.la_county_zip_file),
    )
    write_bundle(result, args.output)


if __name__ == "__main__":
    main()

