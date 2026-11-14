from __future__ import annotations

import pandas as pd
import pytest

from engine.ownership import OwnershipDataError, build_ownership_network


def inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    owners = pd.DataFrame(
        [
            {
                "ENROLLMENT_ID": "E-1",
                "OWNER_ASSOCIATE_ID": "PERSON-SECRET",
                "OWNER_TYPE": "I",
                "OWNER_FIRST_NAME": "Private",
                "OWNER_LAST_NAME": "Person",
                "OWNER_ADDRESS_LINE_1": "1 Main St",
                "OWNER_CITY": "Los Angeles",
                "OWNER_STATE": "CA",
                "OWNER_ZIP_CODE": "90012",
                "PERCENTAGE_OWNERSHIP": "50",
                "_ROW_HASH": "row-1",
            },
            {
                "ENROLLMENT_ID": "E-2",
                "OWNER_ASSOCIATE_ID": "PERSON-SECRET",
                "OWNER_TYPE": "INDIVIDUAL",
                "OWNER_FIRST_NAME": "Private",
                "OWNER_LAST_NAME": "Person",
                "OWNER_ADDRESS_LINE_1": "1 Main St",
                "OWNER_CITY": "Los Angeles",
                "OWNER_STATE": "CA",
                "OWNER_ZIP_CODE": "90012",
                "PERCENTAGE_OWNERSHIP": "50%",
                "_ROW_HASH": "row-2",
            },
            {
                "ENROLLMENT_ID": "E-2",
                "OWNER_ASSOCIATE_ID": "ORG-1",
                "OWNER_TYPE": "O",
                "OWNER_ORGANIZATION_NAME": "Care Group LLC",
                "OWNER_ADDRESS_LINE_1": "1 Main St",
                "OWNER_CITY": "Los Angeles",
                "OWNER_STATE": "CA",
                "OWNER_ZIP_CODE": "90012",
            },
            {
                "ENROLLMENT_ID": "OUTSIDE",
                "OWNER_ASSOCIATE_ID": "ORG-OUTSIDE",
                "OWNER_TYPE": "O",
            },
        ]
    )
    enrollments = pd.DataFrame(
        [
            {"ENROLLMENT_ID": "E-1", "BUILDING_KEY": "100 TEST ST"},
            {"ENROLLMENT_ID": "E-2", "BUILDING_KEY": "100 TEST ST"},
        ]
    )
    buildings = pd.DataFrame(
        [{"BUILDING_ID": "bldg_1", "BUILDING_KEY": "100 TEST ST"}]
    )
    return owners, enrollments, buildings


def test_builds_masked_network_and_expected_metrics() -> None:
    network = build_ownership_network(*inputs())

    assert len(network.owners) == 2
    individual = next(owner for owner in network.owners if owner.owner_type == "individual")
    assert individual.is_masked is True
    assert individual.display_name.startswith("Individual owner ")
    assert individual.hospice_count == 2
    organization = next(owner for owner in network.owners if owner.owner_type == "organization")
    assert organization.display_name == "Care Group LLC"
    metrics = network.buildings[0].metrics
    assert metrics.max_hospices_per_owner == 2
    assert metrics.owners_shared_across_hospices == 1
    assert metrics.shared_owner_address_count == 1


def test_output_excludes_private_names_and_source_owner_ids() -> None:
    payload = str(build_ownership_network(*inputs()).to_dict())

    assert "Private" not in payload
    assert "Person" not in payload
    assert "PERSON-SECRET" not in payload
    assert "ORG-1" not in payload


def test_filters_owners_outside_retained_enrollments() -> None:
    network = build_ownership_network(*inputs())

    assert len(network.edges) == 3
    assert all(edge.enrollment_id != "OUTSIDE" for edge in network.edges)


def test_supports_building_membership_json() -> None:
    owners, enrollments, _ = inputs()
    enrollments = enrollments[["ENROLLMENT_ID"]]
    buildings = pd.DataFrame(
        [{"BUILDING_ID": "bldg_1", "ENROLLMENT_IDS": '["E-1", "E-2"]'}]
    )

    network = build_ownership_network(owners, enrollments, buildings)

    assert network.buildings[0].building_id == "bldg_1"
    assert len(network.buildings[0].owner_keys) == 2


def test_rejects_invalid_percentage() -> None:
    owners, enrollments, buildings = inputs()
    owners.loc[0, "PERCENTAGE_OWNERSHIP"] = "101"

    with pytest.raises(OwnershipDataError, match="outside 0-100"):
        build_ownership_network(owners, enrollments, buildings)


def test_rejects_missing_required_owner_columns() -> None:
    owners, enrollments, buildings = inputs()

    with pytest.raises(OwnershipDataError, match="OWNER_TYPE"):
        build_ownership_network(owners.drop(columns="OWNER_TYPE"), enrollments, buildings)
