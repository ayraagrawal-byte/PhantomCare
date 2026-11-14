from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def square_wkt(latitude: float, longitude: float, half_meters: float = 40) -> str:
    delta_latitude = half_meters / 111_320
    delta_longitude = half_meters / (111_320 * math.cos(math.radians(latitude)))
    west, east = longitude - delta_longitude, longitude + delta_longitude
    south, north = latitude - delta_latitude, latitude + delta_latitude
    return f"POLYGON(({west} {south},{east} {south},{east} {north},{west} {north},{west} {south}))"


def fetch_ortho(*, api_key: str, latitude: float, longitude: float) -> bytes:
    body = json.dumps(
        {
            "wkt": square_wkt(latitude, longitude),
            "srid": 4326,
            "layer": "urban,urban-r,wide-area,urban-g",
            "crop": "bounding_box",
            "image-format": "jpeg",
            "destination-dimensions": "900,900",
        }
    ).encode()
    request = Request(
        "https://api.vexcelgroup.com/v2/ortho/extract",
        data=body,
        method="POST",
        headers={
            "X-API-KEY": api_key,
            "Accept": "image/jpeg",
            "Content-Type": "application/json",
            "User-Agent": "PhantomCare/0.1",
        },
    )
    try:
        with urlopen(request, timeout=300) as response:
            content = response.read()
    except HTTPError as error:
        detail = error.read(500).decode("utf-8", errors="replace")
        raise RuntimeError(f"Vexcel ortho extract returned HTTP {error.code}: {detail}") from error
    except (TimeoutError, URLError) as error:
        raise RuntimeError(f"Vexcel ortho extract failed: {error}") from error
    if not content.startswith(b"\xff\xd8\xff"):
        raise RuntimeError("Vexcel ortho extract did not return a JPEG image")
    return content


def write_evidence(
    *,
    target_id: str,
    address: str,
    latitude: float,
    longitude: float,
    output_dir: Path,
    content: bytes,
) -> dict[str, object]:
    image_dir = output_dir / "vexcel"
    image_dir.mkdir(parents=True, exist_ok=True)
    image_name = f"{target_id}.jpg"
    (image_dir / image_name).write_bytes(content)
    record = {
        "target_id": target_id,
        "address": address,
        "latitude": latitude,
        "longitude": longitude,
        "provider": "vexcel",
        "kind": "ortho",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "image_filename": image_name,
        "image_sha256": hashlib.sha256(content).hexdigest(),
        "limitations": [
            "Aerial imagery provides geographic context and is not evidence of improper conduct.",
            "The image covers an 80-meter square centered on the geocoded address.",
        ],
    }
    manifest_path = output_dir / "vexcel_evidence.json"
    existing = []
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    existing = [item for item in existing if item.get("target_id") != target_id]
    existing.append(record)
    manifest_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and cache Vexcel ortho evidence.")
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--address", required=True)
    parser.add_argument("--latitude", type=float, required=True)
    parser.add_argument("--longitude", type=float, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    api_key = os.environ.get("VEXCEL_API_KEY", "")
    if not api_key:
        raise RuntimeError("VEXCEL_API_KEY is required")
    content = fetch_ortho(api_key=api_key, latitude=args.latitude, longitude=args.longitude)
    record = write_evidence(
        target_id=args.target_id,
        address=args.address,
        latitude=args.latitude,
        longitude=args.longitude,
        output_dir=args.output_dir,
        content=content,
    )
    print(json.dumps({"target_id": record["target_id"], "bytes": len(content)}))


if __name__ == "__main__":
    main()
