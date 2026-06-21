"""
compliance_pdf.py — Compliance Report PDF Generator
=====================================================
Generates a branded, multi-page ChainMed compliance PDF for a given batch.
Uses reportlab (pure Python, no system deps).

Usage:
    buf = generate_compliance_pdf(batch, manufacturer, logs)
    return StreamingResponse(buf, media_type="application/pdf", ...)
"""

import io
from datetime import datetime, timezone
from typing import List

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


# ── Brand colours ─────────────────────────────────────────────────────────────
CYAN        = colors.HexColor("#0891b2")
DARK_CYAN   = colors.HexColor("#0e7490")
VIOLET      = colors.HexColor("#7c3aed")
BG_LIGHT    = colors.HexColor("#f0f9ff")
TEXT_DARK   = colors.HexColor("#0f172a")
TEXT_MID    = colors.HexColor("#334155")
TEXT_LIGHT  = colors.HexColor("#64748b")
BORDER_CLR  = colors.HexColor("#e2e8f0")
SUCCESS_CLR = colors.HexColor("#059669")
WHITE       = colors.white


# ── Page geometry ─────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


# ── Header / Footer drawn on every page ───────────────────────────────────────
def _on_page(canvas, doc, batch_number: str, total_pages_ref: list):
    """Draw running header and footer on each page."""
    canvas.saveState()

    # Top stripe
    canvas.setFillColor(DARK_CYAN)
    canvas.rect(0, PAGE_H - 12 * mm, PAGE_W, 12 * mm, fill=1, stroke=0)

    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(WHITE)
    canvas.drawString(MARGIN, PAGE_H - 8.5 * mm, "ChainMed  ·  Compliance Report")
    canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 8.5 * mm, f"Batch: {batch_number}")

    # Bottom strip
    canvas.setFillColor(BORDER_CLR)
    canvas.rect(0, 0, PAGE_W, 10 * mm, fill=1, stroke=0)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(TEXT_LIGHT)
    canvas.drawString(MARGIN, 3.5 * mm, "CONFIDENTIAL  ·  ChainMed Pharmaceutical Supply Chain")
    canvas.drawRightString(PAGE_W - MARGIN, 3.5 * mm, f"Page {doc.page}")

    canvas.restoreState()


def _make_doc(buf: io.BytesIO, batch_number: str) -> BaseDocTemplate:
    """Create the BaseDocTemplate with a single page template."""
    total_pages_ref: list = []

    def on_page(canvas, doc):
        _on_page(canvas, doc, batch_number, total_pages_ref)

    frame = Frame(
        MARGIN,
        12 * mm,   # bottom: above footer strip
        PAGE_W - 2 * MARGIN,
        PAGE_H - 12 * mm - 14 * mm,   # top: below header stripe + small gap
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    template = PageTemplate(id="main", frames=[frame], onPage=on_page)
    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        pageTemplates=[template],
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=12 * mm + 8 * mm,
        bottomMargin=12 * mm + 4 * mm,
        title=f"ChainMed Compliance Report — Batch {batch_number}",
        author="ChainMed Platform",
        subject="Pharmaceutical Supply Chain Compliance Report",
    )
    return doc


# ── Style helpers ─────────────────────────────────────────────────────────────
def _styles():
    base = getSampleStyleSheet()

    heading1 = ParagraphStyle(
        "CM_H1", parent=base["Normal"],
        fontSize=24, fontName="Helvetica-Bold",
        textColor=TEXT_DARK, spaceAfter=4,
    )
    heading2 = ParagraphStyle(
        "CM_H2", parent=base["Normal"],
        fontSize=14, fontName="Helvetica-Bold",
        textColor=CYAN, spaceBefore=12, spaceAfter=4,
    )
    body = ParagraphStyle(
        "CM_Body", parent=base["Normal"],
        fontSize=9, fontName="Helvetica",
        textColor=TEXT_MID, leading=14,
    )
    body_small = ParagraphStyle(
        "CM_BodySm", parent=base["Normal"],
        fontSize=7.5, fontName="Helvetica",
        textColor=TEXT_LIGHT, leading=11,
    )
    mono = ParagraphStyle(
        "CM_Mono", parent=base["Normal"],
        fontSize=7, fontName="Courier",
        textColor=TEXT_DARK, leading=10,
    )
    label = ParagraphStyle(
        "CM_Label", parent=base["Normal"],
        fontSize=7.5, fontName="Helvetica-Bold",
        textColor=TEXT_LIGHT, spaceAfter=1,
        textTransform="uppercase",
    )
    center = ParagraphStyle(
        "CM_Center", parent=base["Normal"],
        fontSize=9, fontName="Helvetica",
        textColor=TEXT_MID, alignment=TA_CENTER,
    )
    return {
        "h1": heading1, "h2": heading2, "body": body,
        "small": body_small, "mono": mono, "label": label, "center": center,
    }


def _fmt_dt(value) -> str:
    if not value:
        return "—"
    try:
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        return value.strftime("%d %b %Y, %H:%M UTC")
    except Exception:
        return str(value)


def _fmt_date(value) -> str:
    if not value:
        return "—"
    try:
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        return value.strftime("%d %b %Y")
    except Exception:
        return str(value)


def _truncate(s: str, n: int = 32) -> str:
    if not s:
        return "—"
    return s[:n] + "…" if len(s) > n else s


# ── Section builders ──────────────────────────────────────────────────────────

def _cover_section(batch, manufacturer, generated_at: str, styles: dict) -> list:
    """Cover page content."""
    story = []

    story.append(Spacer(1, 20 * mm))

    # Big logo text
    story.append(Paragraph("⛓ ChainMed", ParagraphStyle(
        "logo", fontSize=32, fontName="Helvetica-Bold",
        textColor=CYAN, alignment=TA_CENTER,
    )))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "Pharmaceutical Supply Chain Compliance Report",
        ParagraphStyle("sub", fontSize=13, fontName="Helvetica",
                       textColor=TEXT_MID, alignment=TA_CENTER),
    ))
    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=CYAN))
    story.append(Spacer(1, 10 * mm))

    # Info table
    info_data = [
        ["Batch Name",     batch.name or "—"],
        ["Batch Number",   batch.batch_number or "—"],
        ["Manufacturer",   manufacturer.name or "—"],
        ["License No.",    manufacturer.license_number or "—"],
        ["Country",        manufacturer.country or "—"],
        ["Generated At",   generated_at],
    ]
    info_table = Table(
        [[Paragraph(r[0], styles["label"]), Paragraph(r[1], styles["body"])]
         for r in info_data],
        colWidths=[55 * mm, PAGE_W - 2 * MARGIN - 55 * mm],
        hAlign="LEFT",
    )
    info_table.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [BG_LIGHT, WHITE]),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("BOX",           (0, 0), (-1, -1), 0.5, BORDER_CLR),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, BORDER_CLR),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 10 * mm))

    story.append(Paragraph(
        "This document was generated on-demand from live ChainMed database records. "
        "It reflects the state of the supply chain at the exact moment of generation.",
        ParagraphStyle("note", fontSize=8, fontName="Helvetica-Oblique",
                       textColor=TEXT_LIGHT, alignment=TA_CENTER, leading=13),
    ))

    story.append(PageBreak())
    return story


def _metadata_section(batch, styles: dict) -> list:
    """Batch metadata table."""
    story = []
    story.append(Paragraph("📦 Batch Metadata", styles["h2"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_CLR))
    story.append(Spacer(1, 4 * mm))

    rows = [
        ("Medicine Name",           batch.name or "—"),
        ("Batch Number",            batch.batch_number or "—"),
        ("Medicine Type",           batch.medicine_type or "—"),
        ("Pack Size",               batch.pack_size or "—"),
        ("Number of Packs",         str(batch.number_of_packs or "—")),
        ("Pieces Per Pack",         str(batch.pieces_per_pack or "—")),
        ("Total Units",             str(batch.quantity or "—")),
        ("Manufacturing Date",      _fmt_date(batch.manufacturing_date)),
        ("Expiry Date",             _fmt_date(batch.expiry_date)),
        ("Storage Temp Declared",   f"{batch.storage_temp_declared} °C" if batch.storage_temp_declared else "—"),
        ("Blockchain Hash",         batch.blockchain_hash or "Not yet recorded"),
    ]

    table_data = [
        [Paragraph(label, styles["label"]), Paragraph(value, styles["body"])]
        for label, value in rows
    ]
    t = Table(table_data, colWidths=[60 * mm, PAGE_W - 2 * MARGIN - 60 * mm], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [BG_LIGHT, WHITE]),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("BOX",           (0, 0), (-1, -1), 0.5, BORDER_CLR),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, BORDER_CLR),
    ]))
    story.append(t)
    story.append(PageBreak())
    return story


def _audit_trail_section(logs: list, styles: dict) -> list:
    """Full audit trail table — one row per ApprovalLog entry."""
    story = []
    story.append(Paragraph("🔍 Immutable Audit Trail", styles["h2"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_CLR))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        f"Total entries: {len(logs)}  ·  Append-only, cryptographically signed",
        styles["small"],
    ))
    story.append(Spacer(1, 4 * mm))

    if not logs:
        story.append(Paragraph("No audit log entries found for this batch.", styles["body"]))
        story.append(PageBreak())
        return story

    col_w = [22 * mm, 28 * mm, 35 * mm, 35 * mm, 42 * mm]   # timestamp | actor | action | sig | tx
    header = [
        Paragraph("Timestamp", styles["label"]),
        Paragraph("Actor", styles["label"]),
        Paragraph("Action", styles["label"]),
        Paragraph("ECDSA Sig (32 chars)", styles["label"]),
        Paragraph("Blockchain Tx ID", styles["label"]),
    ]
    rows = [header]

    for log in logs:
        sig_short = _truncate(log.signature or "", 32) if log.signature else "—"
        tx_short  = _truncate(log.blockchain_hash or "", 32) if log.blockchain_hash else "—"
        rows.append([
            Paragraph(_fmt_dt(log.created_at), styles["mono"]),
            Paragraph(f"{log.actor_name}\n({log.actor_role})", styles["mono"]),
            Paragraph((log.action_type or "").replace("_", " "), styles["mono"]),
            Paragraph(sig_short, styles["mono"]),
            Paragraph(tx_short, styles["mono"]),
        ])

    t = Table(rows, colWidths=col_w, hAlign="LEFT", repeatRows=1)
    row_colors = []
    for i in range(1, len(rows)):
        bg = BG_LIGHT if i % 2 == 1 else WHITE
        row_colors.append(("BACKGROUND", (0, i), (-1, i), bg))

    t.setStyle(TableStyle([
        # Header row
        ("BACKGROUND",   (0, 0), (-1, 0), DARK_CYAN),
        ("TEXTCOLOR",    (0, 0), (-1, 0), WHITE),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0), 7.5),
        ("TOPPADDING",   (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING",(0, 0), (-1, 0), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING",   (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 1), (-1, -1), 4),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("BOX",          (0, 0), (-1, -1), 0.5, BORDER_CLR),
        ("INNERGRID",    (0, 0), (-1, -1), 0.25, BORDER_CLR),
        *row_colors,
    ]))
    story.append(t)
    story.append(PageBreak())
    return story


def _integrity_footer_section(batch, generated_at: str, styles: dict) -> list:
    """Final page — integrity attestation."""
    story = []
    story.append(Spacer(1, 15 * mm))

    story.append(Paragraph("🔐 Cryptographic Integrity Attestation", styles["h2"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_CLR))
    story.append(Spacer(1, 6 * mm))

    attestation_lines = [
        ("Signature Algorithm",
         "ECDSA (secp256k1) — Each handoff action is signed with the acting entity's private key. "
         "Signatures are stored in the Audit Trail above and can be independently verified using "
         "the corresponding public key."),
        ("Blockchain Record",
         "Key lifecycle events are recorded on the Ethereum Sepolia testnet. "
         "Transaction IDs shown in the Audit Trail can be looked up on any Ethereum block explorer "
         "(e.g. sepolia.etherscan.io) to confirm immutable on-chain storage."),
        ("Data Provenance",
         "All data in this report was queried directly from the ChainMed operational database "
         f"at generation time ({generated_at}). No caching or offline copies are used."),
        ("Report Authenticity",
         "This PDF was generated on-demand by the ChainMed platform. "
         "It is not digitally signed at the PDF level. For cryptographic proof, "
         "refer to the ECDSA signatures and blockchain transaction IDs in the Audit Trail."),
    ]

    for title, body_text in attestation_lines:
        story.append(Paragraph(title, styles["label"]))
        story.append(Paragraph(body_text, styles["body"]))
        story.append(Spacer(1, 4 * mm))

    story.append(Spacer(1, 8 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=CYAN))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        f"Report generated: {generated_at}  ·  Batch: {batch.batch_number}  ·  "
        "ChainMed AI + Blockchain Pharmaceutical Supply Chain Platform",
        ParagraphStyle("footer_note", fontSize=7.5, fontName="Helvetica",
                       textColor=TEXT_LIGHT, alignment=TA_CENTER),
    ))

    return story


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_compliance_pdf(batch, manufacturer, logs: list) -> io.BytesIO:
    """
    Generate a branded compliance PDF for a medicine batch.

    Args:
        batch:        MedicineBatch ORM instance
        manufacturer: Manufacturer ORM instance
        logs:         List of ApprovalLog ORM instances (sorted by created_at asc)

    Returns:
        BytesIO buffer positioned at the start, ready to stream.
    """
    generated_at = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    buf = io.BytesIO()
    styles = _styles()

    doc = _make_doc(buf, batch.batch_number or "—")

    story = []
    story += _cover_section(batch, manufacturer, generated_at, styles)
    story += _metadata_section(batch, styles)
    story += _audit_trail_section(logs, styles)
    story += _integrity_footer_section(batch, generated_at, styles)

    doc.build(story)
    buf.seek(0)
    return buf
