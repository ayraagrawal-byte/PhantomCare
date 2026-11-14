from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from urllib.request import Request, urlopen


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "PhantomCare/0.1"})
    with urlopen(request, timeout=60) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download a configured public CMS file to a reproducible local path."
    )
    parser.add_argument("url", help="Official CMS CSV URL")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    download(args.url, args.destination)


if __name__ == "__main__":
    main()

