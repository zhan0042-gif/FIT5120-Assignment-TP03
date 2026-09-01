from copy import deepcopy

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
            },
            {
                "member_id": "m_002",
                "display_name": "Alex",
                "is_dependant": False,
                "mobility_support_required": False,
                "support_notes": None,
            },
        ],
        "animals": [
            {
                "animal_id": "a_001",
                "category": "pet",
                "display_name": "Buddy",
                "animal_type": "dog",
                "support_notes": None,
            }
        ],
        "has_private_transport": True,
        "transports": [
            {
                "transport_id": "t_001",
                "transport_type": "car",
                "display_name": "Family Car",
                "driver_member_ids": ["m_001"],
            },
            {
                "transport_id": "t_002",
                "transport_type": "car",
                "display_name": "Backup Car",
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
            },
            "backup_destination": {
                "destination_id": "d_002",
                "display_name": "Community Centre",
                "address": "2 Safe Street",
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
