from copy import deepcopy
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Table

from app.core.dependencies import (
    get_explanation_client,
    get_household_repository,
    get_routing_client,
)
from app.main import app
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.households import HouseholdLocation, HouseholdPlan
from app.services.preparedness_pdf import (
    ACTION_RECORD_WIDTHS,
    CFA_EMERGENCY_KIT_ITEMS,
    CFA_KIT_SOURCE_URL,
    CFA_PLANNING_QUESTIONS,
    CFA_PLAN_SOURCE_URL,
    KEY_LOCATION_WIDTHS,
    PreparednessPdfService,
)
from app.services.rendezvous import RendezvousSimulationService


def _flowable_text(value) -> str:
    if isinstance(value, Paragraph):
        return value.getPlainText()
    if isinstance(value, Table):
        return "\n".join(_flowable_text(cell) for row in value._cellvalues for cell in row)
    if isinstance(value, KeepTogether):
        return _flowable_text(value._content)
    if isinstance(value, (list, tuple)):
        return "\n".join(_flowable_text(item) for item in value)
    return ""


def _capture_story(monkeypatch, plan, *, advice=None):
    captured = []

    def capture(_document, story, **_kwargs):
        captured.extend(story)

    monkeypatch.setattr(SimpleDocTemplate, "build", capture)
    PreparednessPdfService().generate(
        plan,
        household_address="84 Wattle Track, Warburton VIC 3799",
        preparedness_advice=advice,
        generated_at=datetime(2026, 9, 16, tzinfo=timezone.utc),
    )
    return captured


def test_pdf_generation_returns_valid_non_empty_content(complete_plan) -> None:
    content = PreparednessPdfService().generate(
        complete_plan,
        generated_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
    )

    assert content.startswith(b"%PDF-")
    assert len(content) > 1_000


def test_missing_optional_plan_values_do_not_crash_pdf_generation() -> None:
    content = PreparednessPdfService().generate(HouseholdPlan())

    assert content.startswith(b"%PDF-")
    assert len(content) > 1_000


def test_header_positions_brand_date_and_centred_title_without_address() -> None:
    service = PreparednessPdfService()
    styles = service._styles()
    header = service._document_header(
        datetime(2026, 9, 16, tzinfo=timezone.utc),
        styles,
    )

    assert header._cellvalues[0][0].getPlainText() == "FIREBREAK"
    assert header._cellvalues[0][1].getPlainText() == "Generated: 16 September 2026"
    assert styles["PdfBrand"].alignment == TA_LEFT
    assert styles["PdfMeta"].alignment == TA_RIGHT
    assert styles["PdfTitle"].alignment == TA_CENTER
    assert "Household address" not in _flowable_text(header)


def test_supplied_advice_appears_exactly_once_and_missing_advice_is_absent(
    complete_plan,
    monkeypatch,
) -> None:
    accepted = "Maya arrives last. Review the pickup plan."
    with_advice = _flowable_text(
        _capture_story(monkeypatch, complete_plan, advice=accepted)
    )

    assert "FIREBREAK" in with_advice
    assert "Household Bushfire Preparedness Plan" in with_advice
    assert "Generated: 16 September 2026" in with_advice
    assert "Household address:" not in with_advice
    assert with_advice.count("Preparedness Advice") == 1
    assert with_advice.count(accepted) == 1

    without_advice = _flowable_text(
        _capture_story(monkeypatch, complete_plan, advice=None)
    )
    assert "Preparedness Advice" not in without_advice
    assert accepted not in without_advice


def test_member_rows_use_only_saved_name_daytime_location_and_address(
    complete_plan_data: dict,
) -> None:
    data = deepcopy(complete_plan_data)
    data["members"][0]["usual_location"] = {
        "kind": "work",
        "address": "1 Treasury Place, East Melbourne VIC 3002",
    }
    plan = HouseholdPlan.model_validate(data)
    service = PreparednessPdfService()

    assert service._member_rows(plan)[0] == [
        "Maya",
        "Work",
        "1 Treasury Place, East Melbourne VIC 3002",
    ]
    assert not hasattr(service, "_animal_rows")
    assert not hasattr(service, "_transport_rows")


def test_member_table_keeps_exact_columns_and_wraps_a_long_address(
    complete_plan_data: dict,
) -> None:
    data = deepcopy(complete_plan_data)
    data["members"][0]["usual_location"] = {
        "kind": "work",
        "address": (
            "Level 14, 123 Extremely Long Workplace Boulevard, "
            "East Melbourne VIC 3002"
        ),
    }
    service = PreparednessPdfService()
    section = service._household_members_section(
        HouseholdPlan.model_validate(data),
        "84 Wattle Track, Warburton VIC 3799",
        service._styles(),
    )
    table = section[1]
    headers = [cell.getPlainText() for cell in table._cellvalues[0]]
    address = table._cellvalues[1][2].getPlainText()
    table.wrap(164 * mm, 500 * mm)

    assert headers == [
        "Name",
        "Daytime location",
        "Daytime address",
    ]
    assert address.endswith("East Melbourne VIC 3002")
    assert table._rowHeights[1] > table._rowHeights[0]


def test_home_daytime_location_uses_saved_household_address(
    complete_plan_data: dict,
) -> None:
    data = deepcopy(complete_plan_data)
    data["members"][0]["usual_location"] = {"kind": "home"}
    plan = HouseholdPlan.model_validate(data)
    service = PreparednessPdfService()

    assert service._member_rows(plan, "84 Wattle Track, Warburton VIC 3799")[0][
        2
    ] == "84 Wattle Track, Warburton VIC 3799"
    assert service._member_rows(plan)[0][2] == "Not recorded"


def test_support_entries_are_conditional_and_include_only_relevant_members(
    complete_plan_data: dict,
) -> None:
    service = PreparednessPdfService()
    no_support = HouseholdPlan.model_validate(deepcopy(complete_plan_data))
    assert service._support_entries(no_support) == []

    data = deepcopy(complete_plan_data)
    data["members"][0].update(
        {
            "is_dependant": True,
            "mobility_support_required": True,
            "support_notes": "Keep medication close.",
        }
    )
    plan = HouseholdPlan.model_validate(data)

    assert service._support_entries(plan) == [
        "Maya is a dependent household member, requires mobility support, "
        "and needs support with keep medication close."
    ]


def test_multiple_support_members_use_one_readable_sentence_each(
    complete_plan_data: dict,
) -> None:
    data = deepcopy(complete_plan_data)
    data["members"][0].update(
        {
            "mobility_support_required": True,
            "support_notes": "Medication",
        }
    )
    data["members"][1]["is_dependant"] = True

    entries = PreparednessPdfService()._support_entries(
        HouseholdPlan.model_validate(data)
    )

    assert entries == [
        "Maya requires mobility support and needs support with medication.",
        "Alex is a dependent household member.",
    ]
    assert all(entry.count("Maya") <= 1 and entry.count("Alex") <= 1 for entry in entries)
    assert not any(
        raw in " ".join(entries)
        for raw in ("mobility_support_required", "is_dependant", "true", "false")
    )


def test_support_section_is_absent_when_no_member_needs_support(
    complete_plan,
) -> None:
    service = PreparednessPdfService()
    section = service._household_members_section(
        complete_plan,
        "84 Wattle Track, Warburton VIC 3799",
        service._styles(),
    )

    assert "Who needs support" not in _flowable_text(section)


def test_key_locations_and_responsibility_checklist_preserve_saved_values(
    complete_plan,
) -> None:
    service = PreparednessPdfService()
    members = {member.member_id: member.display_name for member in complete_plan.members}

    assert service._key_location_rows(complete_plan) == [
        ["Primary destination", "Relative's House\n1 Example Road"],
        ["Backup destination", "Community Centre\n2 Safe Street"],
        ["Meeting point", "Front gate"],
    ]
    assert service._responsibility_rows(complete_plan, members) == [
        ["", "Drive household", "Maya", "Alex"]
    ]


def test_responsibilities_use_natural_headers_and_unassigned_backup(
    complete_plan_data: dict,
) -> None:
    data = deepcopy(complete_plan_data)
    data["responsibilities"][0]["backup_member_id"] = None
    plan = HouseholdPlan.model_validate(data)
    service = PreparednessPdfService()
    members = {member.member_id: member.display_name for member in plan.members}
    section = service._responsibilities_section(plan, members, service._styles())
    table = section._content[1]

    assert [cell.getPlainText() for cell in table._cellvalues[0]] == [
        "Done",
        "Task",
        "Person responsible",
        "Backup person",
    ]
    assert service._responsibility_rows(plan, members) == [
        ["", "Drive household", "Maya", "Not assigned"]
    ]
    assert "Primary person" not in _flowable_text(table)


def test_key_locations_include_all_backups_but_not_home_or_member_locations(
    complete_plan_data: dict,
) -> None:
    data = deepcopy(complete_plan_data)
    data["members"][0]["usual_location"] = {
        "kind": "work",
        "address": "1 Treasury Place, East Melbourne VIC 3002",
    }
    data["arrangements"]["backup_arrangements"].append(
        {
            "transport_id": "t_001",
            "destination": {
                "destination_id": "d_003",
                "display_name": "Family farm",
                "address": "999 Very Long Country Road, Healesville VIC 3777",
            },
        }
    )
    rows = PreparednessPdfService()._key_location_rows(
        HouseholdPlan.model_validate(data)
    )

    assert rows == [
        ["Primary destination", "Relative's House\n1 Example Road"],
        ["Backup destination 1", "Community Centre\n2 Safe Street"],
        [
            "Backup destination 2",
            "Family farm\n999 Very Long Country Road, Healesville VIC 3777",
        ],
        ["Meeting point", "Front gate"],
    ]
    flattened = "\n".join(value for row in rows for value in row)
    assert "Home" not in flattened
    assert "Treasury Place" not in flattened
    assert KEY_LOCATION_WIDTHS == (42 * mm, 122 * mm)
    assert KEY_LOCATION_WIDTHS[0] / sum(KEY_LOCATION_WIDTHS) < 0.27


def test_blank_meeting_point_is_shown_as_not_recorded(
    complete_plan_data: dict,
) -> None:
    data = deepcopy(complete_plan_data)
    data["arrangements"]["meeting_point"] = "   "

    rows = PreparednessPdfService()._key_location_rows(
        HouseholdPlan.model_validate(data)
    )

    assert rows[-1] == ["Meeting point", "Not set yet"]


def test_pdf_tables_use_light_printable_colours() -> None:
    service = PreparednessPdfService()
    table = service._table(
        ["Header"],
        [["Saved value"]],
        [100],
        service._styles(),
    )

    assert ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDE4D8")) in table._bkgrndcmds
    assert ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FAF8F3")) in table._bkgrndcmds
    assert all(command[3] != colors.black for command in table._bkgrndcmds)


def test_action_record_gives_notes_more_space_and_narrows_member_column(
    complete_plan,
) -> None:
    service = PreparednessPdfService()
    action_record = service._action_record(complete_plan, service._styles())
    table = action_record._content[-1]

    assert tuple(table._colWidths) == ACTION_RECORD_WIDTHS
    assert ACTION_RECORD_WIDTHS[0] < 34 * mm
    assert ACTION_RECORD_WIDTHS[3] >= ACTION_RECORD_WIDTHS[1]
    assert ACTION_RECORD_WIDTHS[3] > 45 * mm


def test_action_record_uses_natural_helper_and_destination_label(
    complete_plan,
) -> None:
    service = PreparednessPdfService()
    action_record = service._action_record(complete_plan, service._styles())
    intro = action_record._content[1].getPlainText()
    table = action_record._content[-1]

    assert intro == (
        "Use this section to note where each household member has gone and when."
    )
    assert [cell.getPlainText() for cell in table._cellvalues[0]] == [
        "Member",
        "Where they went",
        "Time",
        "Notes",
    ]
    assert "Use this section to record" not in intro
    assert "Destination / Location" not in _flowable_text(table)


def test_official_cfa_guidance_uses_only_fixed_supplied_content() -> None:
    expected_questions = (
        "Which Fire Danger Rating is your trigger to leave?",
        "Will you leave early that morning or the night before?",
        "Where will you go?",
        "What route will you take - and what is your alternative in the event that a fire is already in the area?",
        "What will you take with you?",
        "What do you need to organise for your pets or livestock?",
        "Who do you need to keep informed of your movements?",
        "Is there anyone outside your household who you need to help or check up on?",
        "How will you stay informed about warnings and updates?",
        "What will you do if there is a fire in the area and you cannot leave?",
    )
    expected_kit = (
        "Overnight bag with change of clothes and toiletries",
        "Medicines and first aid kit",
        "Important information, such as passport, will, photos, jewellery",
        "Mobile phone and charger",
        "Adequate amount of water",
        "Wool blankets",
        "Contact information for your doctor, council and power company",
        "Additional masks",
        "Hand sanitiser",
        "Antibacterial wipes",
    )

    assert CFA_PLANNING_QUESTIONS == expected_questions
    assert CFA_EMERGENCY_KIT_ITEMS == expected_kit
    assert len(CFA_PLANNING_QUESTIONS) == 10
    assert len(CFA_EMERGENCY_KIT_ITEMS) == 10

    service = PreparednessPdfService()
    guidance = _flowable_text(service._official_cfa_guidance(service._styles()))
    for question in expected_questions:
        assert question in guidance
    for item in expected_kit:
        assert item in guidance
    assert "CFA Bushfire Planning Checklist" in guidance
    assert 'Based on CFA\'s "How to plan" questions' in guidance
    assert "Emergency Kit" in guidance
    assert "CFA: What to take with you" in guidance
    assert "Store your kit in an easy-to-access location." in guidance
    assert "Your Bushfire Plan" in guidance
    assert "What to take with you" in guidance
    assert CFA_PLAN_SOURCE_URL in guidance
    assert CFA_KIT_SOURCE_URL in guidance


def test_whitespace_advice_is_omitted(
    complete_plan,
    monkeypatch,
) -> None:
    service = PreparednessPdfService()

    def unexpected_advice(*_args, **_kwargs):
        raise AssertionError("Blank advice must not create an advice section")

    monkeypatch.setattr(service, "_advice_section", unexpected_advice)
    content = service.generate(complete_plan, preparedness_advice="   ")

    assert content.startswith(b"%PDF-")


def test_pdf_endpoint_passes_saved_canonical_household_address(
    complete_plan_data: dict, monkeypatch
) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    repository.save_plan(
        household_id, HouseholdPlan.model_validate(deepcopy(complete_plan_data))
    )
    repository.save_location(
        household_id,
        HouseholdLocation(
            address="84 wattle track",
            canonical_address="84 Wattle Track, Warburton VIC 3799",
        ),
    )
    received = {}

    def generate(
        _self,
        _plan,
        *,
        household_address="",
        preparedness_advice=None,
        generated_at=None,
    ):
        received["household_address"] = household_address
        received["preparedness_advice"] = preparedness_advice
        return b"%PDF-test"

    monkeypatch.setattr(PreparednessPdfService, "generate", generate)
    app.dependency_overrides[get_household_repository] = lambda: repository
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/households/{household_id}/preparedness-plan.pdf"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert received["household_address"] == "84 Wattle Track, Warburton VIC 3799"
    assert received["preparedness_advice"] is None


def test_pdf_endpoint_includes_bounded_existing_advice_without_regenerating(
    complete_plan_data: dict, monkeypatch
) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    repository.save_plan(
        household_id, HouseholdPlan.model_validate(deepcopy(complete_plan_data))
    )
    received = {}

    def generate(
        _self,
        _plan,
        *,
        household_address="",
        preparedness_advice=None,
        generated_at=None,
    ):
        received["preparedness_advice"] = preparedness_advice
        return b"%PDF-test"

    monkeypatch.setattr(PreparednessPdfService, "generate", generate)
    def unexpected_provider_call():
        raise AssertionError("PDF export must not resolve AI or routing providers")

    def unexpected_rendezvous(*_args, **_kwargs):
        raise AssertionError("PDF export must not rerun rendezvous")

    app.dependency_overrides[get_household_repository] = lambda: repository
    app.dependency_overrides[get_explanation_client] = unexpected_provider_call
    app.dependency_overrides[get_routing_client] = unexpected_provider_call
    monkeypatch.setattr(
        RendezvousSimulationService,
        "simulate",
        unexpected_rendezvous,
    )
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/households/{household_id}/preparedness-plan.pdf",
                json={
                    "preparedness_advice": (
                        "Maya arrives last. Review who can help with the pickup."
                    )
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert received["preparedness_advice"] == (
        "Maya arrives last. Review who can help with the pickup."
    )


def test_pdf_endpoint_rejects_unbounded_advice(complete_plan_data: dict) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    repository.save_plan(
        household_id, HouseholdPlan.model_validate(deepcopy(complete_plan_data))
    )
    app.dependency_overrides[get_household_repository] = lambda: repository
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/households/{household_id}/preparedness-plan.pdf",
                json={"preparedness_advice": "word " * 121},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_pdf_export_has_download_headers_and_does_not_modify_saved_plan(
    complete_plan_data: dict,
) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    plan = HouseholdPlan.model_validate(deepcopy(complete_plan_data))
    repository.save_plan(household_id, plan)
    before = repository.get_plan(household_id).model_dump()
    app.dependency_overrides[get_household_repository] = lambda: repository

    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/households/{household_id}/preparedness-plan.pdf"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        'attachment; filename="firebreak-household-plan.pdf"'
    )
    assert response.content.startswith(b"%PDF-")
    assert repository.get_plan(household_id).model_dump() == before


def test_pdf_export_for_missing_household_uses_existing_404_behaviour() -> None:
    repository = InMemoryHouseholdRepository()
    app.dependency_overrides[get_household_repository] = lambda: repository

    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/households/hh_missing/preparedness-plan.pdf"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Household 'hh_missing' was not found."
    }


def test_pdf_export_for_household_without_plan_uses_existing_404_behaviour() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    app.dependency_overrides[get_household_repository] = lambda: repository

    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/households/{household_id}/preparedness-plan.pdf"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Household '{household_id}' does not have a plan."
    }
