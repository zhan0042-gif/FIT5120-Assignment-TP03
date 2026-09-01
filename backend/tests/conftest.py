import os
from copy import deepcopy

# Tests must opt into deterministic providers before application modules load.
os.environ["APP_DATA_MODE"] = "mock"
os.environ["APP_REPOSITORY_MODE"] = "memory"
os.environ["APP_SPATIAL_MODE"] = "mock"

import pytest

from app.schemas.households import HouseholdPlan


@pytest.fixture
def complete_plan_data() -> dict:
    return {
        "members": [
            {
                "member_id": "m_001",
                "display_name": "Maya",
                "is_dependant": False,
                "mobility_support_required": False,
                "support_notes": None,
                "relationship": "self",
                "relationship_other": None,
            },
            {
                "member_id": "m_002",
                "display_name": "Alex",
                "is_dependant": False,
                "mobility_support_required": False,
                "support_notes": None,
                "relationship": "partner",
                "relationship_other": None,
            },
        ],
        "animals": [
            {
                "animal_id": "a_001",
                "category": "pet",
                "display_name": "Buddy",
                "animal_type": "dog",
                "animal_type_other": None,
                "quantity": 1,
                "support_notes": None,
            }
        ],
        "has_private_transport": True,
        "transports": [
            {
                "transport_id": "t_001",
                "transport_type": "car",
                "display_name": "Family Car",
                "transport_type_other": None,
                "driver_member_ids": ["m_001"],
            },
            {
                "transport_id": "t_002",
                "transport_type": "car",
                "display_name": "Backup Car",
                "transport_type_other": None,
                "driver_member_ids": ["m_002"],
            },
        ],
        "arrangements": {
            "primary_transport_id": "t_001",
            "backup_transport_id": "t_002",
            "primary_destination": {
                "destination_id": "d_001",
                "display_name": "Relative's House",
                    "address": "1 Example Road",
                    "unit_number": None,
                    "street_number": "1",
                    "street_name": "Example Road",
                    "suburb_or_locality": "Warrandyte",
                    "state": "VIC",
                    "postcode": "3113",
                    "country": "Australia",
                    "latitude": None,
                    "longitude": None,
            },
            "backup_destination": {
                "destination_id": "d_002",
                "display_name": "Community Centre",
                    "address": "2 Safe Street",
                    "unit_number": None,
                    "street_number": "2",
                    "street_name": "Safe Street",
                    "suburb_or_locality": "Warburton",
                    "state": "VIC",
                    "postcode": "3799",
                    "country": "Australia",
                    "latitude": None,
                    "longitude": None,
            },
            "meeting_point": "Front gate",
        },
        "responsibilities": [
            {
                "responsibility_id": "r_001",
                "task_name": "Drive household",
                "primary_member_id": "m_001",
                "backup_member_id": "m_002",
            }
        ],
    }


@pytest.fixture
def complete_plan(complete_plan_data: dict) -> HouseholdPlan:
    return HouseholdPlan.model_validate(deepcopy(complete_plan_data))
