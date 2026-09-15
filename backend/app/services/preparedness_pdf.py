"""Printable export of the latest saved household plan."""

from collections.abc import Sequence
from datetime import datetime, timezone
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas.households import Destination, HouseholdPlan


NOT_RECORDED = "Not recorded"
LOCATION_LABELS = {"home": "Home", "work": "Work", "school": "School", "other": "Other"}


class PreparednessPdfService:
    """Render a saved plan without mutating or enriching it."""

    def generate(
        self,
        plan: HouseholdPlan,
        *,
        household_address: str = "",
        preparedness_advice: str | None = None,
        official_checklist: Sequence[str] = (),
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
        members = {member.member_id: member.display_name.strip() for member in plan.members}

        story = [
            Paragraph("FIREBREAK", styles["PdfBrand"]),
            Paragraph("Household Bushfire Preparedness Plan", styles["PdfTitle"]),
            Paragraph(f"<b>Household address:</b> {escape(address)}", styles["PdfMeta"]),
            Paragraph(f"Generated {escape(generated.strftime('%d %B %Y'))}", styles["PdfMeta"]),
            Spacer(1, 6 * mm),
        ]
        if preparedness_advice:
            story.extend(self._advice_section(preparedness_advice, styles))
        story.extend(
            [
                *self._household_members_section(plan, address, styles),
                self._section(
                    "2. Key Locations",
                    ["Location", "Destination / Address"],
                    self._key_location_rows(plan, address),
                    [43 * mm, 121 * mm],
                    styles,
                ),
                self._responsibilities_section(plan, members, styles),
                self._action_record(plan, styles),
            ]
        )
        # Verified official checklist content is not yet present in the repository.
        # This optional seam keeps the print layout ready without inventing advice.
        if official_checklist:
            story.append(self._official_checklist(official_checklist, styles))

        document.build(story, onFirstPage=self._page_footer, onLaterPages=self._page_footer)
        return output.getvalue()

    @staticmethod
    def _styles():
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="PdfBrand", parent=styles["Heading2"], alignment=TA_CENTER, textColor=colors.HexColor("#E6532F"), fontSize=13, leading=16, spaceAfter=3))
        styles.add(ParagraphStyle(name="PdfTitle", parent=styles["Title"], alignment=TA_CENTER, textColor=colors.HexColor("#25211E"), fontSize=20, leading=24, spaceAfter=5))
        styles.add(ParagraphStyle(name="PdfMeta", parent=styles["Normal"], alignment=TA_CENTER, textColor=colors.HexColor("#6B625C"), fontSize=9, leading=12))
        styles.add(ParagraphStyle(name="PdfSection", parent=styles["Heading2"], textColor=colors.HexColor("#25211E"), fontSize=13, leading=16, spaceBefore=5, spaceAfter=6))
        styles.add(ParagraphStyle(name="PdfSubsection", parent=styles["Heading3"], textColor=colors.HexColor("#4A423D"), fontSize=10, leading=12, spaceAfter=4))
        styles.add(ParagraphStyle(name="PdfCell", parent=styles["BodyText"], textColor=colors.HexColor("#25211E"), fontSize=8, leading=10, spaceAfter=3))
        styles.add(ParagraphStyle(name="PdfHeaderCell", parent=styles["BodyText"], textColor=colors.HexColor("#25211E"), fontName="Helvetica-Bold", fontSize=8, leading=10))
        return styles

    def _advice_section(self, advice: str, styles) -> list:
        return [KeepTogether([Paragraph("Preparedness Advice", styles["PdfSection"]), Paragraph(self._safe(advice), styles["PdfCell"]), Spacer(1, 5 * mm)])]

    def _household_members_section(self, plan: HouseholdPlan, household_address: str, styles) -> list:
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
            content.extend([Spacer(1, 4 * mm), Paragraph("Who needs support", styles["PdfSubsection"])])
            for name, needs in support_entries:
                details = "<br/>".join(escape(line) for line in needs)
                content.append(Paragraph(f"<b>{escape(name)}</b><br/>{details}", styles["PdfCell"]))
        content.append(Spacer(1, 5 * mm))
        return [KeepTogether(content)]

    def _section(self, title, headers, rows, widths, styles):
        return KeepTogether([Paragraph(title, styles["PdfSection"]), self._table(headers, rows, widths, styles), Spacer(1, 5 * mm)])

    def _table(self, headers, rows, widths, styles) -> Table:
        data = [[Paragraph(escape(header), styles["PdfHeaderCell"]) for header in headers]]
        data.extend([Paragraph(self._safe(value), styles["PdfCell"]) for value in row] for row in rows)
        table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F6F2ED")),
            ("BACKGROUND", (0, 1), (-1, -1), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D8D1CA")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return table

    def _member_rows(self, plan: HouseholdPlan, household_address: str = "") -> list[list[str]]:
        if not plan.members:
            return [[NOT_RECORDED] * 3]
        rows = []
        for member in plan.members:
            location = member.usual_location
            daytime_location = LOCATION_LABELS.get(location.kind, "Other") if location else NOT_RECORDED
            daytime_address = NOT_RECORDED
            if location:
                daytime_address = (
                    household_address.strip() or NOT_RECORDED
                    if location.kind == "home"
                    else location.address.strip() or NOT_RECORDED
                )
            rows.append([member.display_name.strip() or NOT_RECORDED, daytime_location, daytime_address])
        return rows

    @staticmethod
    def _support_entries(plan: HouseholdPlan) -> list[tuple[str, list[str]]]:
        entries = []
        for member in plan.members:
            needs = []
            if member.is_dependant:
                needs.append("Dependent household member.")
            if member.mobility_support_required:
                needs.append("Mobility support required.")
            if member.support_notes and member.support_notes.strip():
                needs.append(member.support_notes.strip())
            if needs:
                entries.append((member.display_name.strip() or NOT_RECORDED, needs))
        return entries

    @staticmethod
    def _key_location_rows(plan: HouseholdPlan, household_address: str) -> list[list[str]]:
        rows = [["Home", household_address.strip() or NOT_RECORDED]]
        rows.append(["Primary destination", PreparednessPdfService._destination(plan.arrangements.primary_destination)])
        backups = plan.arrangements.backup_arrangements
        if not backups:
            rows.append(["Backup destination", NOT_RECORDED])
        else:
            for index, backup in enumerate(backups, start=1):
                label = "Backup destination" if len(backups) == 1 else f"Backup destination {index}"
                rows.append([label, PreparednessPdfService._destination(backup.destination)])
        rows.append(["Meeting point", plan.arrangements.meeting_point or NOT_RECORDED])
        return rows

    def _responsibilities_section(self, plan: HouseholdPlan, members: dict[str, str], styles):
        return self._section(
            "3. Responsibilities Checklist",
            ["Done", "Responsibility", "Primary person", "Backup person"],
            self._responsibility_rows(plan, members),
            [13 * mm, 67 * mm, 42 * mm, 42 * mm],
            styles,
        )

    @staticmethod
    def _responsibility_rows(plan: HouseholdPlan, members: dict[str, str]) -> list[list[str]]:
        if not plan.responsibilities:
            return [["", NOT_RECORDED, NOT_RECORDED, NOT_RECORDED]]
        return [[
            "",
            responsibility.task_name.strip() or NOT_RECORDED,
            members.get(responsibility.primary_member_id or "") or NOT_RECORDED,
            members.get(responsibility.backup_member_id or "") or NOT_RECORDED,
        ] for responsibility in plan.responsibilities]

    def _action_record(self, plan: HouseholdPlan, styles):
        heading = Paragraph("4. Household Action Record", styles["PdfSection"])
        intro = Paragraph("Use this section to record where each household member has gone and when.", styles["PdfCell"])
        headers = ["Member", "Destination / Location", "Time", "Notes"]
        names = [member.display_name.strip() or NOT_RECORDED for member in plan.members] or [NOT_RECORDED]
        data = [[Paragraph(escape(item), styles["PdfHeaderCell"]) for item in headers]]
        data.extend([[Paragraph(escape(name), styles["PdfCell"]), "", "", ""] for name in names])
        table = Table(data, colWidths=[34 * mm, 60 * mm, 25 * mm, 45 * mm], repeatRows=1, hAlign="LEFT", rowHeights=[None] + [13 * mm] * len(names))
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F6F2ED")),
            ("BACKGROUND", (0, 1), (-1, -1), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8D1CA")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        return KeepTogether([heading, intro, Spacer(1, 3 * mm), table])

    def _official_checklist(self, items: Sequence[str], styles):
        return self._section(
            "5. Official Bushfire Checklist",
            ["Done", "Checklist item"],
            [["", item] for item in items],
            [13 * mm, 151 * mm],
            styles,
        )

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
        canvas.drawString(18 * mm, 10 * mm, "Keep a printed copy somewhere easy to find.")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {document.page}")
        canvas.restoreState()
