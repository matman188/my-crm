"""Versioned A4 renderer for invoice snapshots and previews."""

from datetime import date
from decimal import Decimal
from html import escape
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

import reportlab
from PIL import Image as PILImage, UnidentifiedImageError
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from django.utils import timezone

FONT_DIRECTORY = Path(reportlab.__file__).parent / "fonts"
for name, filename in (
    ("Invoice", "Vera.ttf"),
    ("InvoiceBold", "VeraBd.ttf"),
    ("InvoiceItalic", "VeraIt.ttf"),
):
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name, str(FONT_DIRECTORY / filename)))
pdfmetrics.registerFontFamily(
    "Invoice",
    normal="Invoice",
    bold="InvoiceBold",
    italic="InvoiceItalic",
    boldItalic="InvoiceBold",
)


def _text(value):
    value = str(value).replace("\r\n", "\n").replace("\r", "\n")
    for char in "\u2010\u2011\u2012\u2013\u2014\u2015":
        value = value.replace(char, "-")
    return escape(
        "".join(char for char in value if char in "\n\t" or ord(char) >= 32)
    ).replace("\n", "<br/>")


def _logo_flowable(logo):
    if not logo:
        return None
    try:
        logo.open("rb")
        logo.seek(0)
        contents = logo.read(2 * 1024 * 1024 + 1)
        if len(contents) > 2 * 1024 * 1024:
            raise ValueError(
                "The saved logo is too large. Upload a smaller PNG or JPEG."
            )
        with PILImage.open(BytesIO(contents)) as image:
            if (
                image.format not in ("PNG", "JPEG")
                or image.width > 4096
                or image.height > 4096
            ):
                raise ValueError(
                    "Choose a PNG or JPEG logo up to 4096 pixels per side."
                )
            image.verify()
        flowable = Image(BytesIO(contents))
        flowable._restrictSize(38 * mm, 20 * mm)
        flowable.hAlign = "LEFT"
        return flowable
    except (OSError, UnidentifiedImageError, PILImage.DecompressionBombError) as exc:
        raise ValueError(
            "The logo could not be opened. Replace or remove it before previewing."
        ) from exc
    finally:
        logo.close()


def build_sample_invoice(settings, *, logo=None, long=False):
    """Return an ephemeral PDF using fictional order/customer data and current inputs."""
    if logo is None:
        logo = settings.invoice_logo
    groups = []
    for index in range(1, (8 if long else 1) + 1):
        product = (
            "Sample item with a longer product name to demonstrate wrapping"
            if long and index % 4 == 0
            else "Sample product"
        )
        finishing = (
            "Finishing service with additional description to check line wrapping"
            if long
            else "Finishing service"
        )
        groups.append(
            {
                "label": f"ITEM {index:02d} - {product}",
                "lines": [
                    {
                        "description": "Standard service",
                        "quantity": 2,
                        "unit_price": "75.00",
                    },
                    {"description": finishing, "quantity": 1, "unit_price": "45.00"},
                ],
            }
        )
    groups.append(
        {
            "label": "ORDER-WIDE EXTRAS",
            "lines": [
                {
                    "description": "Express handling",
                    "quantity": 1,
                    "unit_price": "50.00",
                }
            ],
        }
    )
    snapshot = {
        "business": invoice_business_details(settings),
        "issue_date": timezone.localdate(
            timezone=ZoneInfo(settings.business_timezone)
        ).isoformat(),
        "currency": settings.default_currency,
        "order_reference": "SO-SAMPLE",
        "bill_to": [
            "Sample Customer - Sample Business",
            "10 Example Street, Sample Town",
            "sample.customer@example.com",
        ],
        "groups": groups,
    }
    return render_invoice(
        snapshot, logo=logo, number=f"{settings.invoice_prefix}-PREVIEW", sample=True
    )


def invoice_business_details(settings):
    return {
        name: getattr(settings, name)
        for name in (
            "company_name",
            "invoice_address",
            "invoice_email",
            "invoice_phone",
            "invoice_registration_number",
            "invoice_tax_number",
            "invoice_accent",
            "invoice_bank_details",
            "invoice_payment_instructions",
            "invoice_note",
            "invoice_terms",
        )
    }


def render_invoice(
    snapshot, *, logo=None, number=None, sample=False, template_version=1
):
    if template_version != 1:
        raise ValueError("This invoice's PDF template is unavailable.")
    business_details = snapshot["business"]
    currency = snapshot["currency"]
    order_reference = snapshot["order_reference"]
    issue_date = date.fromisoformat(snapshot["issue_date"])
    preview = sample or number is None
    document_title = (
        "Sample invoice preview"
        if sample
        else f"Invoice preview for {order_reference}"
        if preview
        else f"Invoice {number}"
    )
    accent = colors.HexColor(business_details["invoice_accent"])
    ink = colors.HexColor("#203340")
    muted = colors.HexColor("#647782")
    light = colors.HexColor("#f1f5f7")
    border = colors.HexColor("#dae3e8")
    width = 170 * mm
    styles = {
        "body": ParagraphStyle(
            "body",
            fontName="Invoice",
            fontSize=9,
            leading=13,
            textColor=ink,
            spaceAfter=3,
        ),
        "small": ParagraphStyle(
            "small",
            fontName="Invoice",
            fontSize=8,
            leading=12,
            textColor=muted,
            spaceAfter=2,
        ),
        "name": ParagraphStyle(
            "name",
            fontName="InvoiceBold",
            fontSize=19,
            leading=24,
            textColor=ink,
            spaceAfter=7,
        ),
        "title": ParagraphStyle(
            "title",
            fontName="InvoiceBold",
            fontSize=26,
            leading=32,
            textColor=accent,
            alignment=TA_RIGHT,
        ),
        "right": ParagraphStyle(
            "right",
            fontName="Invoice",
            fontSize=8,
            leading=13,
            textColor=ink,
            alignment=TA_RIGHT,
        ),
        "label": ParagraphStyle(
            "label",
            fontName="InvoiceBold",
            fontSize=8,
            leading=12,
            textColor=accent,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "group": ParagraphStyle(
            "group", fontName="InvoiceBold", fontSize=9, leading=13, textColor=accent
        ),
        "column": ParagraphStyle(
            "column",
            fontName="InvoiceBold",
            fontSize=8,
            leading=11,
            textColor=colors.white,
        ),
        "number": ParagraphStyle(
            "number",
            fontName="Invoice",
            fontSize=9,
            leading=13,
            textColor=ink,
            alignment=TA_RIGHT,
        ),
        "total": ParagraphStyle(
            "total",
            fontName="InvoiceBold",
            fontSize=13,
            leading=18,
            textColor=ink,
            alignment=TA_RIGHT,
        ),
    }

    def p(value, style="body"):
        return Paragraph(_text(value), styles[style])

    def money(amount):
        return f"{amount:,.2f}"

    story = []
    business = []
    image = _logo_flowable(logo)
    if image:
        business.extend([image, Spacer(1, 7)])
    business.append(p(business_details["company_name"], "name"))
    if business_details["invoice_address"]:
        business.append(p(business_details["invoice_address"], "small"))
    contacts = " | ".join(
        business_details[name]
        for name in ("invoice_email", "invoice_phone")
        if business_details[name]
    )
    if contacts:
        business.append(p(contacts, "small"))
    for label, value in (
        ("Registration", business_details["invoice_registration_number"]),
        ("Tax number", business_details["invoice_tax_number"]),
    ):
        if value:
            business.append(p(f"{label}: {value}", "small"))
    identity = [p("INVOICE", "title")]
    if preview:
        identity.append(
            p("PREVIEW - FICTIONAL SAMPLE" if sample else "PREVIEW", "right")
        )
    identity.append(Spacer(1, 10))
    if number:
        identity.append(p(number, "right"))
    identity.extend(
        [
            p(
                f"{'Preview date' if preview and not sample else 'Issue date'}: {issue_date:%d %b %Y}",
                "right",
            ),
            p(f"Currency: {currency}", "right"),
        ]
    )
    header = Table([[business, identity]], colWidths=[106 * mm, 64 * mm])
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LINEBELOW", (0, 0), (-1, 0), 2, accent),
            ]
        )
    )
    story.extend([header, Spacer(1, 10)])
    billing = Table(
        [
            [
                [
                    p("BILL TO", "label"),
                    *[
                        p(line, "body" if index == 0 else "small")
                        for index, line in enumerate(snapshot["bill_to"])
                    ],
                ],
                [
                    p("SERVICE ORDER", "label"),
                    p(order_reference),
                ],
            ]
        ],
        colWidths=[106 * mm, 64 * mm],
    )
    billing.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), light),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([billing, Spacer(1, 12)])
    rows = [
        [
            p("SERVICE / DESCRIPTION", "column"),
            p("QTY", "column"),
            p("UNIT PRICE", "column"),
            p("AMOUNT", "column"),
        ]
    ]
    rules = [
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ]
    total = Decimal("0")
    for group in snapshot["groups"]:
        group_row = len(rows)
        rows.append([p(group["label"], "group"), "", "", ""])
        rules.extend(
            [
                ("SPAN", (0, group_row), (-1, group_row)),
                ("BACKGROUND", (0, group_row), (-1, group_row), light),
                ("NOSPLIT", (0, group_row), (-1, group_row + 1)),
            ]
        )
        for line in group["lines"]:
            quantity = line["quantity"]
            price = Decimal(line["unit_price"])
            amount = price * quantity
            total += amount
            rows.append(
                [
                    p(line["description"]),
                    p(quantity, "number"),
                    p(money(price), "number"),
                    p(money(amount), "number"),
                ]
            )
            rules.append(
                ("LINEBELOW", (0, len(rows) - 1), (-1, len(rows) - 1), 0.4, border)
            )
    charges = LongTable(
        rows,
        colWidths=[94 * mm, 16 * mm, 30 * mm, 30 * mm],
        repeatRows=1,
        hAlign="LEFT",
    )
    charges.setStyle(TableStyle(rules))
    story.extend([charges, Spacer(1, 12)])
    totals = Table(
        [
            [p("Subtotal", "right"), p(money(total), "number")],
            [
                p(f"TOTAL {currency}", "total"),
                p(money(total), "total"),
            ],
        ],
        colWidths=[48 * mm, 37 * mm],
        hAlign="RIGHT",
    )
    totals.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LINEABOVE", (0, 1), (-1, 1), 1, accent),
            ]
        )
    )
    story.append(totals)
    for blocks in (
        (
            ("BANKING DETAILS", business_details["invoice_bank_details"]),
            ("PAYMENT INSTRUCTIONS", business_details["invoice_payment_instructions"]),
        ),
        (
            ("INVOICE NOTE", business_details["invoice_note"]),
            ("TERMS AND DISCLAIMER", business_details["invoice_terms"]),
        ),
    ):
        cells = [
            [p(label, "label"), p(value, "small")] for label, value in blocks if value
        ]
        if not cells:
            continue
        # Very long wording remains ordinary flowable text so it can span pages.
        if any(len(value) > 500 or len(value.splitlines()) > 10 for _, value in blocks):
            for label, value in blocks:
                if value:
                    story.extend([Spacer(1, 12), p(label, "label"), p(value, "small")])
        else:
            footer = Table(
                [cells], colWidths=[width / len(cells)] * len(cells), hAlign="LEFT"
            )
            footer.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )
            story.extend([Spacer(1, 12), footer])

    def page(canvas, doc):
        canvas.setTitle(document_title)
        canvas.setAuthor(business_details["company_name"])
        if preview:
            canvas.saveState()
            canvas.setFillColor(colors.HexColor("#edf0f2"))
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(40)
            canvas.setFont("InvoiceBold", 64)
            canvas.drawCentredString(0, 0, "PREVIEW")
            canvas.restoreState()
        canvas.saveState()
        canvas.setFont("Invoice", 8)
        canvas.setFillColor(muted)
        if doc.page > 1:
            company = business_details["company_name"]
            while pdfmetrics.stringWidth(company, "Invoice", 8) > width - 140:
                company = company[:-5] + "..."
            canvas.drawString(20 * mm, A4[1] - 13 * mm, company)
            canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 13 * mm, document_title)
        canvas.setStrokeColor(border)
        canvas.line(20 * mm, 17 * mm, A4[0] - 20 * mm, 17 * mm)
        footer_label = (
            "Sample only - not issued"
            if sample
            else ("Preview - not issued" if preview else number)
        )
        canvas.drawString(20 * mm, 12 * mm, footer_label)
        canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"Page {doc.page}")
        canvas.restoreState()

    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=24 * mm,
    )
    document.build(story, onFirstPage=page, onLaterPages=page)
    return output.getvalue()
