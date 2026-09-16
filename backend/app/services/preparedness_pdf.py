"""Printable export of the latest saved household plan."""

from datetime import datetime, timezone
from html import escape
from io import BytesIO

from reportlab.graphics.shapes import Drawing, Rect
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas.households import Destination, HouseholdPlan


NOT_RECORDED = "Not recorded"
LOCATION_LABELS = {
    "home": "Home",
    "work": "Work",
    "school": "School",
    "other": "Other",
}
CFA_PLANNING_QUESTIONS = (
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
CFA_EMERGENCY_KIT_ITEMS = (
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
CFA_PLAN_SOURCE_URL = (
    "https://www.cfa.vic.gov.au/plan-prepare/before-and-during-a-fire/"
    "your-bushfire-plan"
)
CFA_KIT_SOURCE_URL = (
    "https://www.cfa.vic.gov.au/plan-prepare/before-and-during-a-fire/"
    "leave-early/what-to-take-with-you"
)
KEY_LOCATION_WIDTHS = (42 * mm, 122 * mm)
ACTION_RECORD_WIDTHS = (24.5 * mm, 57 * mm, 24.5 * mm, 58 * mm)


class PreparednessPdfService:
    """Render a saved plan without mutating or enriching it."""

    def generate(
        self,
        plan: HouseholdPlan,
        *,
        household_address: str = "",
        preparedness_advice: str | None = None,
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
        address = household_address.strip() or NOT_RECORDED
        members = {
            member.member_id: member.display_name.strip()
            for member in plan.members
        }

        story = [
            self._document_header(generated, styles),
            Spacer(1, 2 * mm),
            Paragraph("Household Bushfire Preparedness Plan", styles["PdfTitle"]),
            Spacer(1, 4 * mm),
        ]
        advice = preparedness_advice.strip() if preparedness_advice else ""
        if advice:
            story.extend(self._advice_section(advice, styles))
        story.extend(
            [
                *self._household_members_section(plan, address, styles),
                self._section(
                    "2. Key Locations",
                    ["Location", "Destination / Address"],
                    self._key_location_rows(plan),
                    KEY_LOCATION_WIDTHS,
                    styles,
                ),
                self._responsibilities_section(plan, members, styles),
                self._action_record(plan, styles),
                PageBreak(),
                self._official_cfa_guidance(styles),
            ]
        )
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
                alignment=TA_LEFT,
                textColor=colors.HexColor("#E6532F"),
                fontSize=10,
                leading=12,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PdfTitle",
                parent=styles["Title"],
                alignment=TA_CENTER,
                textColor=colors.HexColor("#241F1B"),
                fontSize=20,
                leading=24,
                spaceAfter=5,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PdfMeta",
                parent=styles["Normal"],
                alignment=TA_RIGHT,
                textColor=colors.HexColor("#5F554D"),
                fontSize=8,
                leading=10,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PdfSection",
                parent=styles["Heading2"],
                textColor=colors.HexColor("#241F1B"),
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
                textColor=colors.HexColor("#5F554D"),
                fontSize=10,
                leading=12,
                spaceAfter=4,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PdfCell",
                parent=styles["BodyText"],
                textColor=colors.HexColor("#241F1B"),
                fontSize=8,
                leading=10,
                spaceAfter=3,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PdfHeaderCell",
                parent=styles["BodyText"],
                textColor=colors.HexColor("#241F1B"),
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=10,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PdfSupport",
                parent=styles["BodyText"],
                textColor=colors.HexColor("#241F1B"),
                fontSize=8,
                leading=10,
                spaceAfter=2,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PdfGuidance",
                parent=styles["BodyText"],
                textColor=colors.HexColor("#241F1B"),
                fontSize=7.4,
                leading=9.2,
                spaceAfter=2,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PdfGuidanceTitle",
                parent=styles["Heading3"],
                textColor=colors.HexColor("#241F1B"),
                fontSize=10,
                leading=12,
                spaceAfter=2,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PdfGuidanceMeta",
                parent=styles["BodyText"],
                textColor=colors.HexColor("#5F554D"),
                fontSize=7.2,
                leading=9,
                spaceAfter=4,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PdfSource",
                parent=styles["BodyText"],
                textColor=colors.HexColor("#5F554D"),
                fontSize=7,
                leading=9,
                spaceAfter=2,
            )
        )
        return styles

    @staticmethod
    def _document_header(generated: datetime, styles) -> Table:
        table = Table(
            [[
                Paragraph("FIREBREAK", styles["PdfBrand"]),
                Paragraph(
                    f"Generated: {escape(generated.strftime('%d %B %Y'))}",
                    styles["PdfMeta"],
                ),
            ]],
            colWidths=[82 * mm, 82 * mm],
        )
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return table

    def _advice_section(self, advice: str, styles) -> list:
        box = Table(
            [[[
                Paragraph("Preparedness Advice", styles["PdfGuidanceTitle"]),
                Paragraph(self._safe(advice), styles["PdfCell"]),
            ]]],
            colWidths=[164 * mm],
            hAlign="LEFT",
        )
        box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAF8F3")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8CCBE")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        return [box, Spacer(1, 4 * mm)]

    def _household_members_section(
        self,
        plan: HouseholdPlan,
        household_address: str,
        styles,
    ) -> list:
        content = [
            Paragraph("1. Household Members", styles["PdfSection"]),
            self._table(
                ["Name", "Daytime location", "Daytime address"],
                self._member_rows(plan, household_address),
                [35 * mm, 39 * mm, 90 * mm],
                styles,
            ),
        ]
        support_entries = self._support_entries(plan)
        if support_entries:
            content.extend(
                [
                    Spacer(1, 2.5 * mm),
                    Paragraph("Who needs support", styles["PdfSubsection"]),
                ]
            )
            content.extend(
                Paragraph(self._safe(sentence), styles["PdfSupport"])
                for sentence in support_entries
            )
        content.append(Spacer(1, 5 * mm))
        return content

    def _section(self, title, headers, rows, widths, styles):
        return KeepTogether(
            [
                Paragraph(title, styles["PdfSection"]),
                self._table(headers, rows, widths, styles),
                Spacer(1, 5 * mm),
            ]
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
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDE4D8")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FAF8F3")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D8CCBE")),
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
        self,
        plan: HouseholdPlan,
        household_address: str = "",
    ) -> list[list[str]]:
        if not plan.members:
            return [[NOT_RECORDED] * 3]
        rows = []
        for member in plan.members:
            location = member.usual_location
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
                    daytime_location,
                    daytime_address,
                ]
            )
        return rows

    @staticmethod
    def _support_entries(plan: HouseholdPlan) -> list[str]:
        entries = []
        for member in plan.members:
            needs: list[str] = []
            if member.is_dependant:
                needs.append("is a dependent household member")
            if member.mobility_support_required:
                needs.append("requires mobility support")
            if member.support_notes and member.support_notes.strip():
                note = member.support_notes.strip().rstrip(".")
                if (
                    note
                    and note[0].isupper()
                    and not any(character.isupper() for character in note[1:])
                ):
                    note = note[0].lower() + note[1:]
                needs.append(f"needs support with {note}")
            if needs:
                name = member.display_name.strip() or NOT_RECORDED
                if len(needs) == 1:
                    detail = needs[0]
                elif len(needs) == 2:
                    detail = " and ".join(needs)
                else:
                    detail = f"{', '.join(needs[:-1])}, and {needs[-1]}"
                entries.append(f"{name} {detail}.")
        return entries

    @staticmethod
    def _key_location_rows(plan: HouseholdPlan) -> list[list[str]]:
        rows = [
            [
                "Primary destination",
                PreparednessPdfService._destination(
                    plan.arrangements.primary_destination
                ),
            ]
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
        meeting_point = plan.arrangements.meeting_point
        rows.append(
            [
                "Meeting point",
                meeting_point.strip()
                if meeting_point and meeting_point.strip()
                else "Not set yet",
            ]
        )
        return rows

    def _responsibilities_section(
        self,
        plan: HouseholdPlan,
        members: dict[str, str],
        styles,
    ):
        return self._section(
            "3. Responsibilities Checklist",
            ["Done", "Task", "Person responsible", "Backup person"],
            self._responsibility_rows(plan, members),
            [13 * mm, 67 * mm, 42 * mm, 42 * mm],
            styles,
        )

    @staticmethod
    def _responsibility_rows(
        plan: HouseholdPlan,
        members: dict[str, str],
    ) -> list[list[str]]:
        if not plan.responsibilities:
            return [["", NOT_RECORDED, NOT_RECORDED, NOT_RECORDED]]
        return [
            [
                "",
                responsibility.task_name.strip() or NOT_RECORDED,
                members.get(responsibility.primary_member_id or "")
                or NOT_RECORDED,
                members.get(responsibility.backup_member_id or "")
                or "Not assigned",
            ]
            for responsibility in plan.responsibilities
        ]

    def _action_record(self, plan: HouseholdPlan, styles):
        heading = Paragraph("4. Household Action Record", styles["PdfSection"])
        intro = Paragraph(
            "Use this section to note where each household member has gone and when.",
            styles["PdfCell"],
        )
        headers = ["Member", "Where they went", "Time", "Notes"]
        names = [
            member.display_name.strip() or NOT_RECORDED for member in plan.members
        ] or [NOT_RECORDED]
        data = [
            [Paragraph(escape(item), styles["PdfHeaderCell"]) for item in headers]
        ]
        data.extend(
            [Paragraph(escape(name), styles["PdfCell"]), "", "", ""]
            for name in names
        )
        table = Table(
            data,
            colWidths=ACTION_RECORD_WIDTHS,
            repeatRows=1,
            hAlign="LEFT",
            rowHeights=[None] + [13 * mm] * len(names),
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDE4D8")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FAF8F3")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8CCBE")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return KeepTogether([heading, intro, Spacer(1, 3 * mm), table])

    def _official_cfa_guidance(self, styles):
        planning_rows = [
            [
                Paragraph(f"{index}.", styles["PdfGuidance"]),
                Paragraph(self._safe(question), styles["PdfGuidance"]),
            ]
            for index, question in enumerate(CFA_PLANNING_QUESTIONS, start=1)
        ]
        planning = Table(
            planning_rows,
            colWidths=[6 * mm, 68 * mm],
            hAlign="LEFT",
        )
        planning.setStyle(self._compact_list_style())

        kit_rows = [
            [
                self._empty_checkbox(),
                Paragraph(self._safe(item), styles["PdfGuidance"]),
            ]
            for item in CFA_EMERGENCY_KIT_ITEMS
        ]
        kit = Table(kit_rows, colWidths=[6 * mm, 68 * mm], hAlign="LEFT")
        kit.setStyle(self._compact_list_style())

        left = [
            Paragraph("CFA Bushfire Planning Checklist", styles["PdfGuidanceTitle"]),
            Paragraph(
                'Based on CFA\'s "How to plan" questions',
                styles["PdfGuidanceMeta"],
            ),
            planning,
        ]
        right = [
            Paragraph("Emergency Kit", styles["PdfGuidanceTitle"]),
            Paragraph("CFA: What to take with you", styles["PdfGuidanceMeta"]),
            kit,
            Spacer(1, 2 * mm),
            Paragraph(
                "Store your kit in an easy-to-access location.",
                styles["PdfGuidance"],
            ),
        ]
        columns = Table([[left, right]], colWidths=[82 * mm, 82 * mm], hAlign="LEFT")
        columns.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAF8F3")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8CCBE")),
                    ("LINEBEFORE", (1, 0), (1, 0), 0.5, colors.HexColor("#D8CCBE")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        sources = Paragraph(
            "<b>Sources:</b><br/>"
            "Country Fire Authority (CFA), <i>Your Bushfire Plan</i><br/>"
            f"{escape(CFA_PLAN_SOURCE_URL)}<br/>"
            "Country Fire Authority (CFA), <i>What to take with you</i><br/>"
            f"{escape(CFA_KIT_SOURCE_URL)}",
            styles["PdfSource"],
        )
        return KeepTogether(
            [
                Paragraph("Official CFA Bushfire Guidance", styles["PdfSection"]),
                columns,
                Spacer(1, 4 * mm),
                sources,
            ]
        )

    @staticmethod
    def _compact_list_style() -> TableStyle:
        return TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
            ]
        )

    @staticmethod
    def _empty_checkbox() -> Drawing:
        checkbox = Drawing(8, 8)
        checkbox.add(
            Rect(
                0.75,
                0.75,
                6.5,
                6.5,
                strokeColor=colors.HexColor("#5F554D"),
                fillColor=None,
                strokeWidth=0.7,
            )
        )
        return checkbox

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
        canvas.setFillColor(colors.HexColor("#5F554D"))
        canvas.drawString(
            18 * mm,
            10 * mm,
            "Keep a printed copy somewhere easy to find.",
        )
        canvas.drawRightString(
            A4[0] - 18 * mm,
            10 * mm,
            f"Page {document.page}",
        )
        canvas.restoreState()
