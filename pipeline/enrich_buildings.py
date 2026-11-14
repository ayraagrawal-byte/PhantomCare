from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pandas as pd

from pipeline.enrichment import (
    LookupRequest,
    MatterportModelsClient,
    VexcelPropertyClient,
    costar_provider,
    matterport_provider,
    vexcel_provider,
)


def _provider(name: str, cache_dir: Path, cache_only: bool):
    if cache_only:
        client = None
    elif name == "vexcel":
        client = VexcelPropertyClient(api_key=os.environ.get("VEXCEL_API_KEY", ""))
    elif name == "matterport":
        client = MatterportModelsClient(
            token_id=os.environ.get("MATTERPORT_API_KEY", ""),
            token_secret=os.environ.get("MATTERPORT_API_TOKEN", ""),
        )
    else:
        raise ValueError(
            "CoStar is supplied as an encrypted data extract, not a live API. "
            "Import the kit before running CoStar enrichment."
        )
    factories = {
        "costar": costar_provider,
        "vexcel": vexcel_provider,
        "matterport": matterport_provider,
    }
    factory = factories[name]
    return factory(cache_dir=cache_dir, client=client, cache_only=cache_only)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cache CoStar or Vexcel building enrichment.")
    parser.add_argument(
        "--provider", choices=("costar", "vexcel", "matterport"), required=True
    )
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

