import hashlib
import json
from pathlib import Path

from scripts.verify_sponsor_overlap import verify

ADDRESS = "100 SYNTHETIC ST LOS ANGELES CA 90012"
IMAGE = b"\xff\xd8\xff synthetic jpeg bytes"


def _write_fixture(root: Path, *, vexcel_address: str = ADDRESS, sha: str | None = None) -> None:
    (root / "vexcel").mkdir(parents=True)
    (root / "vexcel" / "bldg_syn.jpg").write_bytes(IMAGE)
    building = {
        "building_id": "bldg_syn",
        "building_key": ADDRESS,
        "hospice_count": 3,
        "costar_match_status": "exact_match",
        "latitude": 34.05,
        "longitude": -118.25,
        "priority": {"score": {"level": "worth_a_look"}},
        "building_context": {"property_id": "SYN-1", "matterport_model_ids": []},
    }
    (root / "building_analysis.json").write_text(json.dumps([building]))
    (root / "vexcel_evidence.json").write_text(json.dumps([{
        "target_id": "bldg_syn",
        "address": vexcel_address,
        "latitude": 34.0501,
        "longitude": -118.2501,
        "retrieved_at": "2026-11-14T00:00:00+00:00",
        "image_filename": "bldg_syn.jpg",
        "image_sha256": sha or hashlib.sha256(IMAGE).hexdigest(),
    }]))
    (root / "cams_geocodes.json").write_text(json.dumps({"results": {"bldg_syn": {
        "location": {"latitude": 34.0502, "longitude": -118.2500}}}}))


def test_synthetic_same_building_overlap_is_detected(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    report = verify(tmp_path)

    assert report["overlap_found"] is True
    assert report["genuine_overlaps"][0]["costar_property_id"] == "SYN-1"


def test_different_address_is_not_an_overlap(tmp_path: Path) -> None:
    _write_fixture(tmp_path, vexcel_address="102 SYNTHETIC ST LOS ANGELES CA 90012")

    assert verify(tmp_path)["overlap_found"] is False


def test_tampered_image_is_not_an_overlap(tmp_path: Path) -> None:
    _write_fixture(tmp_path, sha="0" * 64)

    report = verify(tmp_path)

    assert report["vexcel_evidence"][0]["image_sha256_verified"] is False
    assert report["overlap_found"] is False


def test_published_artifacts_have_no_genuine_overlap() -> None:
    report = verify(Path("data/runtime"))

    assert [m["building_id"] for m in report["costar_exact_matches"]] == ["bldg_1161264fd5dbc223"]
    assert [v["building_id"] for v in report["vexcel_evidence"]] == ["bldg_793ac00ed2ae2571"]
    assert report["overlap_found"] is False
    assert report["next_actions"][0]["required_environment"] == ["VEXCEL_API_KEY"]
