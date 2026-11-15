"""Fixed A4 sample renderer. It reads settings only and never issues an invoice."""

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
    accent = colors.HexColor(settings.invoice_accent)
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

    date = timezone.localdate(timezone=ZoneInfo(settings.business_timezone))

    def money(amount):
        return f"{amount:,.2f}"

    story = []
    business = []
    image = _logo_flowable(logo)
    if image:
        business.extend([image, Spacer(1, 7)])
    business.append(p(settings.company_name, "name"))
    if settings.invoice_address:
        business.append(p(settings.invoice_address, "small"))
    contacts = " | ".join(
        value for value in (settings.invoice_email, settings.invoice_phone) if value
    )
    if contacts:
        business.append(p(contacts, "small"))
    for label, value in (
        ("Registration", settings.invoice_registration_number),
        ("Tax number", settings.invoice_tax_number),
    ):
        if value:
            business.append(p(f"{label}: {value}", "small"))
    identity = [
        p("INVOICE", "title"),
        p("PREVIEW - FICTIONAL SAMPLE", "right"),
        Spacer(1, 10),
        p(f"{settings.invoice_prefix}-PREVIEW", "right"),
        p(f"Issue date: {date:%d %b %Y}", "right"),
        p(f"Currency: {settings.default_currency}", "right"),
    ]
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
                    p("Sample Customer - Sample Business"),
                    p("10 Example Street, Sample Town", "small"),
                    p("sample.customer@example.com", "small"),
                ],
                [
                    p("SERVICE ORDER", "label"),
                    p("SO-SAMPLE"),
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
    groups = 8 if long else 1
    for index in range(1, groups + 1):
        group_row = len(rows)
        product = (
            "Sample item with a longer product name to demonstrate wrapping"
            if long and index % 4 == 0
            else "Sample product"
        )
        rows.append([p(f"ITEM {index:02d} - {product}", "group"), "", "", ""])
        rules.extend(
            [
                ("SPAN", (0, group_row), (-1, group_row)),
                ("BACKGROUND", (0, group_row), (-1, group_row), light),
                ("NOSPLIT", (0, group_row), (-1, group_row + 2)),
            ]
        )
        for name, quantity, price in (
            ("Standard service", 2, Decimal("75.00")),
            (
                (
                    "Finishing service with additional description to check line wrapping"
                    if long
                    else "Finishing service"
                ),
                1,
                Decimal("45.00"),
            ),
        ):
            amount = price * quantity
            total += amount
            rows.append(
                [
                    p(name),
                    p(quantity, "number"),
                    p(money(price), "number"),
                    p(money(amount), "number"),
                ]
            )
            rules.append(
                ("LINEBELOW", (0, len(rows) - 1), (-1, len(rows) - 1), 0.4, border)
            )
    extra_row = len(rows)
    rows.append([p("ORDER-WIDE EXTRAS", "group"), "", "", ""])
    rows.append(
        [
            p("Express handling"),
            p(1, "number"),
            p("50.00", "number"),
            p("50.00", "number"),
        ]
    )
    rules.extend(
        [
            ("SPAN", (0, extra_row), (-1, extra_row)),
            ("BACKGROUND", (0, extra_row), (-1, extra_row), light),
            ("NOSPLIT", (0, extra_row), (-1, extra_row + 1)),
        ]
    )
    total += Decimal("50.00")
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
                p(f"TOTAL {settings.default_currency}", "total"),
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
            ("BANKING DETAILS", settings.invoice_bank_details),
            ("PAYMENT INSTRUCTIONS", settings.invoice_payment_instructions),
        ),
        (
            ("INVOICE NOTE", settings.invoice_note),
            ("TERMS AND DISCLAIMER", settings.invoice_terms),
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
        canvas.saveState()
        canvas.setTitle("Sample invoice preview")
        canvas.setAuthor(settings.company_name)
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
            company = settings.company_name
            while pdfmetrics.stringWidth(company, "Invoice", 8) > width - 140:
                company = company[:-5] + "..."
            canvas.drawString(20 * mm, A4[1] - 13 * mm, company)
            canvas.drawRightString(
                A4[0] - 20 * mm, A4[1] - 13 * mm, "Sample invoice preview"
            )
        canvas.setStrokeColor(border)
        canvas.line(20 * mm, 17 * mm, A4[0] - 20 * mm, 17 * mm)
        canvas.drawString(20 * mm, 12 * mm, "Sample only - not issued")
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
