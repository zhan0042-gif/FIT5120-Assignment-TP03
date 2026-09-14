"""Printable export of the latest saved household plan."""

from datetime import datetime, timezone
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas.households import Destination, HouseholdPlan, Transport


NOT_RECORDED = "Not recorded"
RELATIONSHIP_LABELS = {
    "self": "Self",
    "partner": "Partner / spouse",
    "child": "Child",
    "parent": "Parent",
    "grandparent": "Grandparent",
    "sibling": "Sibling",
    "other_relative": "Other relative",
    "friend_or_housemate": "Friend / housemate",
    "carer": "Carer",
    "other": "Other",
}
LOCATION_LABELS = {
    "home": "Home",
    "work": "Work",
    "school": "School",
    "other": "Other",
}


class PreparednessPdfService:
    """Render a saved plan without mutating or enriching it."""

    def generate(
        self,
        plan: HouseholdPlan,
        *,
        household_address: str = "",
        generated_at: datetime | None = None,
    ) -> bytes:
        output = BytesIO()
        document = SimpleDocTemplate(
            output,
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            title="FIREBREAK Household Bushfire Preparedness Plan",
            author="FIREBREAK",
        )
        styles = self._styles()
        generated = generated_at or datetime.now(timezone.utc)
        members = {
            member.member_id: member.display_name.strip() for member in plan.members
        }
        transports = {item.transport_id: item for item in plan.transports}

        story = [
            Paragraph("FIREBREAK", styles["PdfBrand"]),
            Paragraph("Household Bushfire Preparedness Plan", styles["PdfTitle"]),
            Paragraph(
                f"Exported {escape(generated.strftime('%d %B %Y'))}",
                styles["PdfMeta"],
            ),
            Spacer(1, 6 * mm),
            *self._household_section(plan, household_address, styles),
            self._section(
                "2. Transport",
                ["Arrangement", "Vehicle", "Type", "Driver"],
                self._transport_rows(plan, transports, members),
                [29 * mm, 48 * mm, 35 * mm, 52 * mm],
                styles,
            ),
            self._section(
                "3. Evacuation Arrangements",
                ["Arrangement", "Destination / Address"],
                self._arrangement_rows(plan),
                [48 * mm, 116 * mm],
                styles,
            ),
            self._section(
                "4. Responsibilities",
                ["Responsibility", "Primary person", "Backup person"],
                self._responsibility_rows(plan, members),
                [76 * mm, 44 * mm, 44 * mm],
                styles,
            ),
            self._action_record(plan, styles),
        ]
        document.build(
            story,
            onFirstPage=self._page_footer,
            onLaterPages=self._page_footer,
        )
        return output.getvalue()

    @staticmethod
    def _styles():
        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="PdfBrand",
                parent=styles["Heading2"],
                alignment=TA_CENTER,
                textColor=colors.HexColor("#E6532F"),
                fontSize=13,
                leading=16,
                spaceAfter=3,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PdfTitle",
                parent=styles["Title"],
                alignment=TA_CENTER,
                textColor=colors.HexColor("#25211E"),
                fontSize=20,
                leading=24,
                spaceAfter=5,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PdfMeta",
                parent=styles["Normal"],
                alignment=TA_CENTER,
                textColor=colors.HexColor("#6B625C"),
                fontSize=9,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PdfSection",
                parent=styles["Heading2"],
                textColor=colors.HexColor("#25211E"),
                fontSize=13,
                leading=16,
                spaceBefore=5,
                spaceAfter=6,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PdfSubsection",
                parent=styles["Heading3"],
                textColor=colors.HexColor("#4A423D"),
                fontSize=10,
                leading=12,
                spaceAfter=4,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PdfCell",
                parent=styles["BodyText"],
                textColor=colors.HexColor("#25211E"),
                fontSize=8,
                leading=10,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PdfHeaderCell",
                parent=styles["BodyText"],
                textColor=colors.HexColor("#25211E"),
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=10,
            )
        )
        return styles

    def _household_section(
        self, plan: HouseholdPlan, household_address: str, styles
    ) -> list:
        members = self._table(
            [
                "Name",
                "Relationship",
                "Support needs",
                "Daytime location",
                "Daytime address",
            ],
            self._member_rows(plan, household_address),
            [23 * mm, 23 * mm, 33 * mm, 26 * mm, 59 * mm],
            styles,
        )
        animals = self._table(
            ["Pet type", "Name", "Quantity"],
            self._animal_rows(plan),
            [55 * mm, 79 * mm, 30 * mm],
            styles,
        )
        return [
            KeepTogether(
                [
                    Paragraph("1. Household", styles["PdfSection"]),
                    Paragraph("Household members", styles["PdfSubsection"]),
                    members,
                    Spacer(1, 4 * mm),
                ]
            ),
            KeepTogether(
                [
                    Paragraph("Animals / pets", styles["PdfSubsection"]),
                    animals,
                    Spacer(1, 5 * mm),
                ]
            ),
        ]

    def _section(
        self,
        title: str,
        headers: list[str],
        rows: list[list[str]],
        widths: list[float],
        styles,
    ):
        table = self._table(headers, rows, widths, styles)
        return KeepTogether(
            [Paragraph(title, styles["PdfSection"]), table, Spacer(1, 5 * mm)]
        )

    def _table(self, headers, rows, widths, styles) -> Table:
        data = [
            [Paragraph(escape(header), styles["PdfHeaderCell"]) for header in headers]
        ]
        data.extend(
            [Paragraph(self._safe(value), styles["PdfCell"]) for value in row]
            for row in rows
        )
        table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F6F2ED")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D8D1CA")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return table

    def _member_rows(
        self, plan: HouseholdPlan, household_address: str = ""
    ) -> list[list[str]]:
        if not plan.members:
            return [[NOT_RECORDED] * 5]
        rows = []
        for member in plan.members:
            location = member.usual_location
            relationship = RELATIONSHIP_LABELS.get(
                member.relationship or "", NOT_RECORDED
            )
            if member.relationship == "other" and member.relationship_other:
                relationship = member.relationship_other.strip() or relationship
            needs = []
            if member.is_dependant:
                needs.append("Needs help from another household member")
            if member.mobility_support_required:
                needs.append("Mobility support required")
            if member.support_notes and member.support_notes.strip():
                needs.append(member.support_notes.strip())
            daytime_location = (
                LOCATION_LABELS.get(location.kind, "Other")
                if location
                else NOT_RECORDED
            )
            daytime_address = NOT_RECORDED
            if location:
                daytime_address = (
                    household_address.strip() or NOT_RECORDED
                    if location.kind == "home"
                    else location.address.strip() or NOT_RECORDED
                )
            rows.append(
                [
                    member.display_name.strip() or NOT_RECORDED,
                    relationship,
                    ", ".join(needs) if needs else NOT_RECORDED,
                    daytime_location,
                    daytime_address,
                ]
            )
        return rows

    @staticmethod
    def _animal_rows(plan: HouseholdPlan) -> list[list[str]]:
        if not plan.animals:
            return [[NOT_RECORDED, NOT_RECORDED, NOT_RECORDED]]
        rows = []
        for animal in plan.animals:
            animal_type = (
                animal.animal_type_other.strip()
                if animal.animal_type == "other" and animal.animal_type_other
                else animal.animal_type.replace("_", " ").title()
            )
            rows.append(
                [
                    animal_type or NOT_RECORDED,
                    animal.display_name.strip() or NOT_RECORDED,
                    str(animal.quantity),
                ]
            )
        return rows

    def _transport_rows(
        self,
        plan: HouseholdPlan,
        transports: dict[str, Transport],
        members: dict[str, str],
    ) -> list[list[str]]:
        primary = transports.get(plan.arrangements.primary_transport_id or "")
        rows = [self._transport_row("Primary", primary, members)]
        backups = plan.arrangements.backup_arrangements
        if not backups:
            rows.append(self._transport_row("Backup", None, members))
        else:
            for index, backup in enumerate(backups, start=1):
                label = "Backup" if len(backups) == 1 else f"Backup {index}"
                rows.append(
                    self._transport_row(
                        label,
                        transports.get(backup.transport_id or ""),
                        members,
                    )
                )
        return rows

    def _transport_row(
        self, arrangement: str, transport: Transport | None, members: dict[str, str]
    ) -> list[str]:
        if transport is None:
            return [arrangement, NOT_RECORDED, NOT_RECORDED, NOT_RECORDED]
        transport_type = (
            transport.transport_type_other.strip()
            if transport.transport_type == "other" and transport.transport_type_other
            else transport.transport_type.replace("_", " ").title()
        )
        return [
            arrangement,
            (transport.display_name or "").strip() or NOT_RECORDED,
            transport_type or NOT_RECORDED,
            self._drivers(transport, members),
        ]

    @staticmethod
    def _arrangement_rows(plan: HouseholdPlan) -> list[list[str]]:
        rows = [
            ["Meeting point", plan.arrangements.meeting_point or NOT_RECORDED],
            [
                "Primary destination",
                PreparednessPdfService._destination(
                    plan.arrangements.primary_destination
                ),
            ],
        ]
        backups = plan.arrangements.backup_arrangements
        if not backups:
            rows.append(["Backup destination", NOT_RECORDED])
        else:
            for index, backup in enumerate(backups, start=1):
                label = (
                    "Backup destination"
                    if len(backups) == 1
                    else f"Backup destination {index}"
                )
                rows.append(
                    [label, PreparednessPdfService._destination(backup.destination)]
                )
        return rows

    @staticmethod
    def _responsibility_rows(
        plan: HouseholdPlan, members: dict[str, str]
    ) -> list[list[str]]:
        if not plan.responsibilities:
            return [[NOT_RECORDED, NOT_RECORDED, NOT_RECORDED]]
        return [
            [
                responsibility.task_name.strip() or NOT_RECORDED,
                members.get(responsibility.primary_member_id or "") or NOT_RECORDED,
                members.get(responsibility.backup_member_id or "") or NOT_RECORDED,
            ]
            for responsibility in plan.responsibilities
        ]

    def _action_record(self, plan: HouseholdPlan, styles):
        heading = Paragraph("5. Household Action Record", styles["PdfSection"])
        intro = Paragraph(
            "Use this section to record where each household member has gone and when.",
            styles["PdfCell"],
        )
        headers = ["Member", "Destination / Location", "Time", "Notes"]
        names = [member.display_name.strip() or NOT_RECORDED for member in plan.members]
        if not names:
            names = [NOT_RECORDED]
        data = [[Paragraph(escape(item), styles["PdfHeaderCell"]) for item in headers]]
        for name in names:
            data.append(
                [
                    Paragraph(escape(name), styles["PdfCell"]),
                    "",
                    "",
                    "",
                ]
            )
        table = Table(
            data,
            colWidths=[34 * mm, 60 * mm, 25 * mm, 45 * mm],
            repeatRows=1,
            hAlign="LEFT",
            rowHeights=[None] + [13 * mm] * len(names),
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F6F2ED")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8D1CA")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return KeepTogether([heading, intro, Spacer(1, 3 * mm), table])

    @staticmethod
    def _drivers(transport: Transport, members: dict[str, str]) -> str:
        names = [
            members.get(member_id) or NOT_RECORDED
            for member_id in transport.driver_member_ids
        ]
        return ", ".join(names) if names else NOT_RECORDED

    @staticmethod
    def _destination(destination: Destination | None) -> str:
        if destination is None:
            return NOT_RECORDED
        name = destination.display_name.strip()
        address = (destination.canonical_address or destination.address or "").strip()
        return "\n".join(item for item in (name, address) if item) or NOT_RECORDED

    @staticmethod
    def _safe(value: str) -> str:
        return escape(str(value)).replace("\n", "<br/>")

    @staticmethod
    def _page_footer(canvas, document) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6B625C"))
        canvas.drawString(
            18 * mm,
            10 * mm,
            "Keep a printed copy somewhere easy to find.",
        )
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {document.page}")
        canvas.restoreState()
