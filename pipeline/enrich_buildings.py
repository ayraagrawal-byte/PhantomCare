from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pandas as pd

from pipeline.enrichment import HttpJsonClient, LookupRequest, costar_provider, vexcel_provider


def _provider(name: str, cache_dir: Path, cache_only: bool):
    if cache_only:
        client = None
    else:
        endpoint = os.environ.get(f"{name.upper()}_API_URL", "")
        api_key = os.environ.get(f"{name.upper()}_API_KEY", "")
        if not endpoint:
            raise ValueError(f"{name.upper()}_API_URL is required outside cache-only mode")
        client = HttpJsonClient(
            provider=name,
            endpoint=endpoint,
            api_key=api_key,
        )
    factory = costar_provider if name == "costar" else vexcel_provider
    return factory(cache_dir=cache_dir, client=client, cache_only=cache_only)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cache CoStar or Vexcel building enrichment.")
    parser.add_argument("--provider", choices=("costar", "vexcel"), required=True)
    parser.add_argument("--buildings", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path("cache"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--cache-only", action="store_true")
    args = parser.parse_args()

    buildings = pd.read_csv(args.buildings).head(args.limit)
    provider = _provider(args.provider, args.cache_dir, args.cache_only)
    records = []
    for _, building in buildings.iterrows():
        request = LookupRequest(
            address=str(building["BUILDING_KEY"]),
            latitude=(
                float(building["LATITUDE"])
                if "LATITUDE" in building and pd.notna(building["LATITUDE"])
                else None
            ),
            longitude=(
                float(building["LONGITUDE"])
                if "LONGITUDE" in building and pd.notna(building["LONGITUDE"])
                else None
            ),
        )
        records.append(provider.lookup(request))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps([record.__dict__ for record in records], indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

