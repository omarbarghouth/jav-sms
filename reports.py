# =============================================================================
#  AviaS — AVIATION SMS ENTERPRISE REPORTING ENGINE
#  ICAO Annex 19 / IOSA ISM Compliant — Controlled Document Generation
#  reports.py  |  Rev 01  |  DO NOT MODIFY WITHOUT CHANGE CONTROL
# =============================================================================
"""
Professional PDF report generator for the Aviation SMS platform.
Produces ICAO/IOSA-grade controlled documents with full lifecycle traceability.

Usage:
    from reports import build_pdf
    pdf_bytes = build_pdf('hazard_report', record_id=rid, db=db, models=...)
"""

from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib import colors

# ── Brand palette ─────────────────────────────────────────────────────────────
C_NAVY      = HexColor('#0a1628')
C_NAVY2     = HexColor('#111f3a')
C_GOLD      = HexColor('#c9a84c')
C_GOLD_LITE = HexColor('#f5e9c8')
C_RED       = HexColor('#dc2626')
C_RED_LITE  = HexColor('#fee2e2')
C_GREEN     = HexColor('#16a34a')
C_GREEN_LITE= HexColor('#dcfce7')
C_BLUE      = HexColor('#1d4ed8')
C_BLUE_LITE = HexColor('#dbeafe')
C_ORANGE    = HexColor('#d97706')
C_ORANGE_LT = HexColor('#fef3c7')
C_PURPLE    = HexColor('#7c3aed')
C_PURPLE_LT = HexColor('#ede9fe')
C_GRAY      = HexColor('#6b7280')
C_GRAY_LITE = HexColor('#f3f4f6')
C_BORDER    = HexColor('#e5e7eb')
C_WHITE     = white

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


# =============================================================================
#  STYLE DEFINITIONS
# =============================================================================
def _styles():
    """Return dict of all ParagraphStyles used in reports."""
    base = dict(fontName='Helvetica', fontSize=9, leading=13,
                textColor=HexColor('#1f2937'))
    return {
        'title': ParagraphStyle('title', fontName='Helvetica-Bold',
                                fontSize=16, leading=20,
                                textColor=C_NAVY, alignment=TA_LEFT),
        'subtitle': ParagraphStyle('subtitle', fontName='Helvetica',
                                   fontSize=9, leading=12,
                                   textColor=C_GRAY, alignment=TA_LEFT),
        'section': ParagraphStyle('section', fontName='Helvetica-Bold',
                                  fontSize=8, leading=10,
                                  textColor=C_NAVY, spaceBefore=10,
                                  spaceAfter=4, letterSpacing=0.5,
                                  backColor=C_GRAY_LITE,
                                  borderPad=4),
        'field_label': ParagraphStyle('field_label', fontName='Helvetica-Bold',
                                      fontSize=7.5, leading=11,
                                      textColor=C_GRAY),
        'field_value': ParagraphStyle('field_value', **base),
        'body': ParagraphStyle('body', **base, spaceAfter=4,
                               alignment=TA_JUSTIFY),
        'small': ParagraphStyle('small', fontName='Helvetica',
                                fontSize=7, leading=10,
                                textColor=C_GRAY),
        'mono': ParagraphStyle('mono', fontName='Courier',
                               fontSize=8, leading=12,
                               textColor=HexColor('#374151')),
        'badge_red': ParagraphStyle('badge_red', fontName='Helvetica-Bold',
                                    fontSize=8, textColor=C_RED),
        'badge_green': ParagraphStyle('badge_green', fontName='Helvetica-Bold',
                                      fontSize=8, textColor=C_GREEN),
        'badge_gold': ParagraphStyle('badge_gold', fontName='Helvetica-Bold',
                                     fontSize=8, textColor=C_GOLD),
        'badge_blue': ParagraphStyle('badge_blue', fontName='Helvetica-Bold',
                                     fontSize=8, textColor=C_BLUE),
        'badge_gray': ParagraphStyle('badge_gray', fontName='Helvetica-Bold',
                                     fontSize=8, textColor=C_GRAY),
        'watermark': ParagraphStyle('watermark', fontName='Helvetica-Bold',
                                    fontSize=42, textColor=HexColor('#e5e7eb'),
                                    alignment=TA_CENTER),
        'center': ParagraphStyle('center', **base, alignment=TA_CENTER),
        'right': ParagraphStyle('right', **base, alignment=TA_RIGHT),
        'heading2': ParagraphStyle('heading2', fontName='Helvetica-Bold',
                                   fontSize=10, leading=14,
                                   textColor=C_NAVY, spaceAfter=4),
        'risk_intolerable': ParagraphStyle('risk_intolerable',
                                           fontName='Helvetica-Bold',
                                           fontSize=8, textColor=C_RED),
        'risk_tolerable': ParagraphStyle('risk_tolerable',
                                         fontName='Helvetica-Bold',
                                         fontSize=8, textColor=C_ORANGE),
        'risk_acceptable': ParagraphStyle('risk_acceptable',
                                          fontName='Helvetica-Bold',
                                          fontSize=8, textColor=C_GREEN),
    }


# =============================================================================
#  HEADER / FOOTER CANVAS
# =============================================================================
class _AviaHeader:
    """Page canvas callback for header and footer on every page."""

    def __init__(self, doc_type, control_number, classification,
                 generated_by, report_status):
        self.doc_type       = str(doc_type or 'Document')
        self.control_number = str(control_number or '—')
        self.classification = str(classification or 'INTERNAL')
        self.generated_by   = str(generated_by or 'Safety Department')
        self.report_status  = str(report_status or '—')
        self.timestamp      = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

    def __call__(self, canvas, doc):
        canvas.saveState()
        w, h = A4

        # ── TOP HEADER BAND ───────────────────────────────────────────────────
        canvas.setFillColor(C_NAVY)
        canvas.rect(0, h - 24 * mm, w, 24 * mm, fill=1, stroke=0)

        # Gold accent line
        canvas.setFillColor(C_GOLD)
        canvas.rect(0, h - 25 * mm, w, 1 * mm, fill=1, stroke=0)

        # Company name
        canvas.setFillColor(C_WHITE)
        canvas.setFont('Helvetica-Bold', 12)
        canvas.drawString(MARGIN, h - 10 * mm, 'AviaS')
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(HexColor('#c9a84c'))
        canvas.drawString(MARGIN, h - 15 * mm, 'Safety Management System')

        # Document type — centre
        canvas.setFillColor(C_WHITE)
        canvas.setFont('Helvetica-Bold', 11)
        canvas.drawCentredString(w / 2, h - 10 * mm, self.doc_type.upper())
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(HexColor('#94a3b8'))
        canvas.drawCentredString(w / 2, h - 15 * mm, 'CONTROLLED DOCUMENT — ICAO Annex 19 Compliant')

        # Control number — right
        canvas.setFillColor(C_WHITE)
        canvas.setFont('Helvetica-Bold', 9)
        canvas.drawRightString(w - MARGIN, h - 9 * mm, self.control_number)
        canvas.setFont('Helvetica', 7.5)
        canvas.setFillColor(HexColor('#94a3b8'))
        canvas.drawRightString(w - MARGIN, h - 14 * mm, f'Page {doc.page}')
        canvas.drawRightString(w - MARGIN, h - 19 * mm, self.timestamp)

        # ── BOTTOM FOOTER BAND ────────────────────────────────────────────────
        canvas.setFillColor(C_NAVY2)
        canvas.rect(0, 0, w, 12 * mm, fill=1, stroke=0)
        canvas.setFillColor(C_GOLD)
        canvas.rect(0, 12 * mm, w, 0.5 * mm, fill=1, stroke=0)

        canvas.setFillColor(HexColor('#94a3b8'))
        canvas.setFont('Helvetica', 6.5)
        canvas.drawString(MARGIN, 8 * mm,
                          f'Generated by: {self.generated_by}  |  {self.timestamp}')
        canvas.drawString(MARGIN, 4.5 * mm,
                          'This document is a controlled record of the AviaS '
                          'Safety Management System. Unauthorised alteration is prohibited.')

        # Classification badge — right footer
        cls = self.classification.upper()
        cls_color = C_RED if 'CONFIDENTIAL' in cls else (
                    C_ORANGE if 'RESTRICTED' in cls else C_GREEN)
        canvas.setFillColor(cls_color)
        canvas.roundRect(w - MARGIN - 55, 5 * mm, 55, 7 * mm, 2, fill=1, stroke=0)
        canvas.setFillColor(C_WHITE)
        canvas.setFont('Helvetica-Bold', 6.5)
        canvas.drawCentredString(w - MARGIN - 27.5, 8 * mm, cls)

        canvas.restoreState()


# =============================================================================
#  BUILDER HELPERS
# =============================================================================
def _hr(color=C_BORDER, thickness=0.5, spaceB=4, spaceA=4):
    return HRFlowable(width='100%', thickness=thickness, color=color,
                      spaceAfter=spaceA, spaceBefore=spaceB)


def _section_header(text, S):
    """Dark navy section divider with all-caps label."""
    data = [[Paragraph(f'&nbsp;{text.upper()}', S['section'])]]
    t = Table(data, colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), C_NAVY),
        ('TEXTCOLOR',  (0, 0), (-1, -1), C_WHITE),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING',  (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [C_NAVY]),
    ]))
    return t


def _info_grid(pairs, S, cols=2):
    """
    Render a grid of (label, value) pairs.
    cols=2 → two side-by-side label/value columns
    cols=1 → full-width single column
    """
    if not pairs:
        return Spacer(1, 2)

    col_w = CONTENT_W / cols
    label_w = col_w * 0.36
    value_w = col_w * 0.64

    rows = []
    chunk = cols * 1  # pairs per row

    for i in range(0, len(pairs), chunk):
        row_cells = []
        for j in range(chunk):
            if i + j < len(pairs):
                lbl, val = pairs[i + j]
                val_str = str(val) if val is not None else '—'
                row_cells += [
                    Paragraph(str(lbl), S['field_label']),
                    Paragraph(val_str or '—', S['field_value']),
                ]
            else:
                row_cells += [Paragraph('', S['field_label']),
                              Paragraph('', S['field_value'])]

        rows.append(row_cells)

    col_widths = [label_w, value_w] * cols
    t = Table(rows, colWidths=col_widths, repeatRows=0)
    t.setStyle(TableStyle([
        ('VALIGN',      (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',  (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',(0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [C_WHITE, C_GRAY_LITE]),
        ('LINEBELOW',   (0, 0), (-1, -2), 0.3, C_BORDER),
        ('LINEAFTER',   (1, 0), (1, -1), 0.3, C_BORDER),
    ]))
    return t


def _text_block(label, text, S):
    """Full-width text area with label."""
    if not text:
        text = '— Not provided —'
    items = [
        Paragraph(label.upper(), S['field_label']),
        Spacer(1, 2),
        Paragraph(str(text).replace('\n', '<br/>'), S['body']),
    ]
    data = [[items]]
    t = Table(data, colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), C_WHITE),
        ('BOX',        (0, 0), (-1, -1), 0.5, C_BORDER),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',(0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
    ]))
    return t


def _status_badge(status, S):
    """Colour-coded status badge."""
    s = (status or '').upper()
    if any(x in s for x in ('CLOSED', 'COMPLETED', 'APPROVED', 'EFFECTIVE',
                              'ACCEPTED', 'ACTIVE')):
        style = S['badge_green']
        bg = C_GREEN_LITE
    elif any(x in s for x in ('OPEN', 'SUBMITTED', 'PENDING', 'PLANNED',
                                'DRAFT', 'IN PROGRESS')):
        style = S['badge_gold']
        bg = C_GOLD_LITE
    elif any(x in s for x in ('REJECTED', 'OVERDUE', 'INTOLERABLE', 'CRITICAL',
                                'FAILED')):
        style = S['badge_red']
        bg = C_RED_LITE
    else:
        style = S['badge_blue']
        bg = C_BLUE_LITE

    data = [[Paragraph(f'  {status or "—"}  ', style)]]
    t = Table(data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg),
        ('BOX',        (0, 0), (-1, -1), 0.5, HexColor('#d1d5db')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',(0, 0), (-1, -1), 6),
    ]))
    return t


def _risk_matrix_cell(risk_index, S):
    """Render a risk index value with INTOLERABLE/TOLERABLE/ACCEPTABLE colour."""
    INTOLERABLE = {'5A','5B','5C','4A','4B','3A'}
    TOLERABLE   = {'5D','5E','4C','4D','4E','3B','3C','3D','2A','2B','2C','1A'}
    ri = (risk_index or '').upper()
    if ri in INTOLERABLE:
        bg, style = C_RED_LITE, S['risk_intolerable']
        label = f'{ri} — INTOLERABLE'
    elif ri in TOLERABLE:
        bg, style = C_ORANGE_LT, S['risk_tolerable']
        label = f'{ri} — TOLERABLE'
    else:
        bg, style = C_GREEN_LITE, S['risk_acceptable']
        label = f'{ri} — ACCEPTABLE' if ri else '— Not Assessed'

    data = [[Paragraph(label, style)]]
    t = Table(data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg),
        ('BOX',        (0, 0), (-1, -1), 0.5, HexColor('#d1d5db')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',(0, 0), (-1, -1), 6),
    ]))
    return t


def _timeline_table(events, S):
    """Render an audit timeline as a bordered table."""
    if not events:
        return Paragraph('No timeline events recorded.', S['small'])

    rows = [[
        Paragraph('DATE / TIME', S['field_label']),
        Paragraph('EVENT', S['field_label']),
        Paragraph('USER', S['field_label']),
        Paragraph('NOTES', S['field_label']),
    ]]
    for ev in events:
        rows.append([
            Paragraph(str(ev.get('date', '—')), S['small']),
            Paragraph(str(ev.get('event', '—')), S['mono']),
            Paragraph(str(ev.get('user', '—')), S['small']),
            Paragraph(str(ev.get('notes', '')), S['small']),
        ])

    col_w = [32 * mm, 60 * mm, 35 * mm, CONTENT_W - 32 * mm - 60 * mm - 35 * mm]
    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (-1, 0),  C_NAVY),
        ('TEXTCOLOR',   (0, 0), (-1, 0),  C_WHITE),
        ('FONTNAME',    (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, 0),  7),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_WHITE, C_GRAY_LITE]),
        ('GRID',        (0, 0), (-1, -1), 0.3, C_BORDER),
        ('VALIGN',      (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',  (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',(0,0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',(0, 0), (-1, -1), 5),
    ]))
    return t


def _actions_table(actions, S):
    """Render linked actions/CAPs as a table."""
    if not actions:
        return Paragraph('No corrective actions linked.', S['small'])

    rows = [[
        Paragraph('REF', S['field_label']),
        Paragraph('DESCRIPTION', S['field_label']),
        Paragraph('OWNER', S['field_label']),
        Paragraph('DUE', S['field_label']),
        Paragraph('PRIORITY', S['field_label']),
        Paragraph('STATUS', S['field_label']),
    ]]
    for a in actions:
        rows.append([
            Paragraph(str(a.get('id', '—')), S['mono']),
            Paragraph(str(a.get('description', '—'))[:120], S['small']),
            Paragraph(str(a.get('owner', '—')), S['small']),
            Paragraph(str(a.get('due_date', '—')), S['small']),
            Paragraph(str(a.get('priority', '—')), S['small']),
            Paragraph(str(a.get('status', '—')), S['small']),
        ])

    col_w = [22*mm, CONTENT_W-22*mm-28*mm-18*mm-18*mm-22*mm, 28*mm, 18*mm, 18*mm, 22*mm]
    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (-1, 0),  C_NAVY),
        ('TEXTCOLOR',   (0, 0), (-1, 0),  C_WHITE),
        ('FONTNAME',    (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, 0),  7),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_WHITE, C_GRAY_LITE]),
        ('GRID',        (0, 0), (-1, -1), 0.3, C_BORDER),
        ('VALIGN',      (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',  (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',(0,0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',(0, 0), (-1, -1), 5),
    ]))
    return t


def _signature_block(signers, S):
    """
    Render a multi-column signature block.
    signers: list of {'role': str, 'name': str, 'date': str}
    """
    if not signers:
        return Spacer(1, 2)

    col_w = CONTENT_W / len(signers)
    cells = []
    for sig in signers:
        block = [
            Paragraph(str(sig.get('role', '')).upper(), S['field_label']),
            Spacer(1, 12),
            _hr(C_NAVY, thickness=0.8, spaceB=2, spaceA=2),
            Paragraph(str(sig.get('name', '')) or '________________________', S['field_value']),
            Paragraph(f"Date: {sig.get('date', '') or '____________'}", S['small']),
        ]
        cells.append(block)

    t = Table([cells], colWidths=[col_w] * len(signers))
    t.setStyle(TableStyle([
        ('VALIGN',      (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',  (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING',(0,0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',(0, 0), (-1, -1), 8),
        ('LINEAFTER',   (0, 0), (-2, -1), 0.5, C_BORDER),
        ('BOX',         (0, 0), (-1, -1), 0.5, C_NAVY),
        ('BACKGROUND',  (0, 0), (-1, -1), C_GRAY_LITE),
    ]))
    return t


def _cover_banner(title, ref, doc_type, status, dept, date_str, classification, S):
    """Full-width cover banner rendered as the first flowable after header."""
    data = [[
        [
            Spacer(1, 2),
            Paragraph(doc_type.upper(), S['small']),
            Paragraph(title or doc_type, S['title']),
            Spacer(1, 4),
            _hr(C_GOLD, thickness=1.5, spaceB=2, spaceA=4),
            _info_grid([
                ('Reference', ref or '—'),
                ('Status', status or '—'),
                ('Department', dept or '—'),
                ('Date', date_str or '—'),
                ('Classification', classification),
                ('Generated', datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')),
            ], S, cols=2),
        ]
    ]]
    t = Table(data, colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), C_WHITE),
        ('BOX',        (0, 0), (-1, -1), 1, C_NAVY),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING',(0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING',(0,0), (-1, -1), 10),
        ('LINEBELOW',  (0, 0), (-1, 0),  3, C_GOLD),
    ]))
    return t


# =============================================================================
#  CORE PDF BUILDER
# =============================================================================
def _build_doc(flowables, doc_type, control_number, classification,
               generated_by, report_status):
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=28 * mm, bottomMargin=18 * mm,
        title=f'{doc_type} — {control_number}',
        author='AviaS Safety Management System',
        subject='ICAO Annex 19 Controlled Document',
        creator='AviaS SMS v2.0',
    )
    hf = _AviaHeader(doc_type, control_number, classification,
                     generated_by, report_status)
    doc.build(flowables, onFirstPage=hf, onLaterPages=hf)
    return buf.getvalue()


# =============================================================================
#  INDIVIDUAL REPORT GENERATORS
# =============================================================================

def pdf_hazard_report(hr, hazard, actions, history, risks, investigation,
                      ra, generated_by='Safety Department'):
    """
    Generate a complete Hazard Report PDF.
    hr         : HazardReport model instance
    hazard     : Hazard model instance (or None)
    actions    : list of Action instances
    history    : list of ActionHistory instances
    risks      : list of Risk instances
    investigation : Investigation instance (or None)
    ra         : RiskAssessment instance (or None)
    """
    S = _styles()
    dept_name = (hr.department.name if hr.department else '—') if hr else '—'
    ref = hr.id if hr else '—'
    status = hr.status if hr else '—'
    title = (hr.generic_hazard or hr.description or 'Hazard Report')[:80] if hr else 'Hazard Report'

    E = []  # flowables

    # Cover banner
    E.append(_cover_banner(
        title=title, ref=ref, doc_type='Hazard Report',
        status=status, dept=dept_name,
        date_str=hr.date if hr else '—',
        classification='RESTRICTED — SAFETY SENSITIVE', S=S
    ))
    E.append(Spacer(1, 6))

    # ── SECTION 1: REPORT INFORMATION ────────────────────────────────────────
    E.append(_section_header('1. Report Information', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Report Reference', ref),
        ('Report Type',      hr.report_type or 'Hazard Report'),
        ('Date of Occurrence', hr.date or '—'),
        ('Location',         hr.location or '—'),
        ('Classification',   hr.classification or '—'),
        ('Reporter',         hr.reporter or 'Anonymous'),
        ('Reporter Severity',hr.reporter_severity or '—'),
        ('Workflow Status',  hr.status or '—'),
        ('Linked Hazard',    hr.hazard_id or '—'),
        ('Department',       dept_name),
    ], S, cols=2))
    E.append(Spacer(1, 6))

    # ── SECTION 2: HAZARD DESCRIPTION ────────────────────────────────────────
    E.append(_section_header('2. Hazard Description', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Generic Hazard / Event Title',
                         hr.generic_hazard if hr else '', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Detailed Description', hr.description if hr else '', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Potential Consequences', hr.consequences if hr else '', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Immediate Action Taken', hr.immediate_action if hr else '', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Suggested Mitigation', hr.suggested_mitigation if hr else '', S))
    E.append(Spacer(1, 6))

    # ── SECTION 3: HAZARD LOG ENTRY ───────────────────────────────────────────
    if hazard:
        E.append(_section_header('3. Hazard Log Entry', S))
        E.append(Spacer(1, 4))
        E.append(_info_grid([
            ('Hazard ID',        hazard.id),
            ('Source',           hazard.source or '—'),
            ('Classification',   hazard.classification or '—'),
            ('Type of Activity', hazard.type_of_activity or '—'),
            ('Generic Hazard',   hazard.generic_hazard or '—'),
            ('Status',           hazard.status or '—'),
            ('Owner',            hazard.owner or '—'),
            ('Department',       hazard.department.name if hazard.department else '—'),
        ], S, cols=2))
        E.append(Spacer(1, 4))
        E.append(_text_block('Specific Components', hazard.specific_components, S))
        E.append(Spacer(1, 4))
        E.append(_text_block('Consequences', hazard.consequences, S))
        E.append(Spacer(1, 6))

    # ── SECTION 4: RISK ASSESSMENT ────────────────────────────────────────────
    if risks:
        E.append(_section_header('4. Risk Assessment', S))
        E.append(Spacer(1, 4))
        risk_rows = [[
            Paragraph('RISK ID',           S['field_label']),
            Paragraph('DESCRIPTION',       S['field_label']),
            Paragraph('INITIAL RISK',      S['field_label']),
            Paragraph('RESIDUAL RISK',     S['field_label']),
            Paragraph('TOLERANCE',         S['field_label']),
        ]]
        for r in risks:
            risk_rows.append([
                Paragraph(r.id or '—', S['mono']),
                Paragraph((r.description or '—')[:100], S['small']),
                Paragraph(f'{r.initial_risk_index or "—"}', S['small']),
                Paragraph(f'{r.residual_risk_index or "—"}', S['small']),
                Paragraph(r.residual_tolerance or '—', S['small']),
            ])
        col_w = [22*mm, CONTENT_W-22*mm-30*mm-30*mm-35*mm, 30*mm, 30*mm, 35*mm]
        rt = Table(risk_rows, colWidths=col_w, repeatRows=1)
        rt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), C_NAVY),
            ('TEXTCOLOR',  (0, 0), (-1, 0), C_WHITE),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_WHITE, C_GRAY_LITE]),
            ('GRID',       (0, 0), (-1, -1), 0.3, C_BORDER),
            ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING',(0, 0), (-1, -1), 5),
        ]))
        E.append(rt)
        E.append(Spacer(1, 6))

    # ── SECTION 5: INVESTIGATION ──────────────────────────────────────────────
    if investigation:
        E.append(_section_header('5. Investigation Summary', S))
        E.append(Spacer(1, 4))
        E.append(_info_grid([
            ('Investigation ID',  investigation.id),
            ('Investigator',      investigation.investigator or '—'),
            ('Date of Occurrence', investigation.date_of_occurrence or '—'),
            ('Status',            investigation.status or '—'),
        ], S, cols=2))
        E.append(Spacer(1, 4))
        E.append(_text_block('Investigation Description', investigation.description, S))
        E.append(Spacer(1, 4))
        E.append(_text_block('Root Cause Analysis', investigation.root_cause, S))
        E.append(Spacer(1, 4))
        # 5-Whys
        whys = [(f'Why {i}', getattr(investigation, f'why{i}', None))
                for i in range(1, 6)
                if getattr(investigation, f'why{i}', None)]
        if whys:
            E.append(_text_block('5-Whys Analysis',
                                 '\n'.join(f'WHY {i}: {v}' for (_, _), (i, v)
                                            in zip(whys, enumerate(whys, 1))), S))
        E.append(Spacer(1, 4))
        E.append(_text_block('Recommendations', investigation.recommendations, S))
        E.append(Spacer(1, 6))

    # ── SECTION 6: CORRECTIVE ACTIONS ─────────────────────────────────────────
    E.append(_section_header('6. Corrective Actions & Follow-Up', S))
    E.append(Spacer(1, 4))
    action_data = [{
        'id':          a.id,
        'description': a.description,
        'owner':       a.owner,
        'due_date':    a.due_date,
        'priority':    a.priority,
        'status':      a.status,
    } for a in (actions or [])]
    E.append(_actions_table(action_data, S))
    E.append(Spacer(1, 6))

    # ── SECTION 7: AUDIT TRAIL ────────────────────────────────────────────────
    E.append(_section_header('7. Audit Trail & Timeline', S))
    E.append(Spacer(1, 4))
    timeline_events = []
    for h in (history or []):
        timeline_events.append({
            'date':  h.changed_at.strftime('%Y-%m-%d %H:%M') if h.changed_at else '—',
            'event': f'{h.from_status or "—"} → {h.to_status or "—"}',
            'user':  h.changed_by or '—',
            'notes': h.notes or '',
        })
    E.append(_timeline_table(timeline_events, S))
    E.append(Spacer(1, 6))

    # ── SECTION 8: SIGNATURES ─────────────────────────────────────────────────
    E.append(_section_header('8. Approval & Signature Block', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Reporter',         'name': hr.reporter if hr else '', 'date': hr.date if hr else ''},
        {'role': 'Safety Officer',   'name': '', 'date': ''},
        {'role': 'Safety Manager',   'name': '', 'date': ''},
        {'role': 'Accountable Mgr',  'name': '', 'date': ''},
    ], S))

    return _build_doc(E, 'Hazard Report', ref, 'RESTRICTED — SAFETY SENSITIVE',
                      generated_by, status)


# ─────────────────────────────────────────────────────────────────────────────

def pdf_asr_report(asr, hazard, hr, actions, generated_by='Safety Department'):
    """Air Safety Report (ASR) PDF."""
    S = _styles()
    ref = asr.id if asr else '—'
    status = 'Submitted'
    title = (asr.occurrence_type or 'Air Safety Report') if asr else 'Air Safety Report'

    E = []
    E.append(_cover_banner(
        title=title, ref=ref, doc_type='Air Safety Report (ASR)',
        status=status, dept='Flight Operations',
        date_str=asr.date if asr else '—',
        classification='RESTRICTED — SAFETY SENSITIVE', S=S
    ))
    E.append(Spacer(1, 6))

    E.append(_section_header('1. Report Identification', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('ASR Reference',     ref),
        ('Report Type',       asr.report_type or '—'),
        ('Occurrence Type',   asr.occurrence_type or '—'),
        ('Date',              asr.date or '—'),
        ('Time Local',        asr.time_local or '—'),
        ('Time UTC',          asr.time_utc or '—'),
        ('Flight Number',     asr.flight_no or '—'),
        ('Route',             f"{asr.route_from or '—'} → {asr.route_to or '—'}"),
        ('Aircraft Type',     asr.aircraft_type or '—'),
        ('Registration',      asr.registration or '—'),
        ('Flight Phase',      asr.flight_phase or '—'),
        ('Altitude (ft)',     str(asr.altitude_ft or '—')),
        ('PAX',               str(asr.pax or '—')),
        ('Crew',              str(asr.crew or '—')),
    ], S, cols=2))
    E.append(Spacer(1, 6))

    E.append(_section_header('2. Crew Information', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Captain / Reporter', asr.captain or '—'),
        ('Staff No.',          asr.captain_staff_no or '—'),
        ('Co-Pilot',           asr.copilot or '—'),
        ('Co-Pilot Staff No.', asr.copilot_staff_no or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 6))

    E.append(_section_header('3. Meteorological Conditions', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Wind',     asr.weather_wind or '—'),
        ('Vis/RVR',  asr.weather_vis_rvr or '—'),
        ('Clouds',   asr.weather_clouds or '—'),
        ('Temp (°C)',str(asr.weather_temp_c or '—')),
        ('QNH',      str(asr.weather_qnh or '—')),
        ('Runway',   asr.runway or '—'),
        ('Rwy State',asr.runway_state or '—'),
        ('Squawk',   asr.squawk or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 6))

    E.append(_section_header('4. Event Description & Actions Taken', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Event Description', asr.event_description, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Immediate Actions Taken', asr.action_taken, S))
    E.append(Spacer(1, 6))

    E.append(_section_header('5. Risk Index', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Severity',     asr.severity or '—'),
        ('Likelihood',   str(asr.likelihood or '—')),
        ('Risk Index',   asr.risk_index or '—'),
        ('Linked Hazard',asr.hazard_id or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 4))
    if asr.risk_index:
        E.append(_risk_matrix_cell(asr.risk_index, S))
    E.append(Spacer(1, 6))

    E.append(_section_header('6. Corrective Actions', S))
    E.append(Spacer(1, 4))
    action_data = [{'id': a.id, 'description': a.description,
                    'owner': a.owner, 'due_date': a.due_date,
                    'priority': a.priority, 'status': a.status}
                   for a in (actions or [])]
    E.append(_actions_table(action_data, S))
    E.append(Spacer(1, 6))

    E.append(_section_header('7. Signatures', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Captain / Reporter', 'name': asr.captain or '', 'date': asr.date or ''},
        {'role': 'Safety Officer',     'name': '', 'date': ''},
        {'role': 'Safety Manager',     'name': '', 'date': ''},
    ], S))

    return _build_doc(E, 'Air Safety Report', ref, 'RESTRICTED — SAFETY SENSITIVE',
                      generated_by, 'Submitted')


# ─────────────────────────────────────────────────────────────────────────────

def pdf_investigation(inv, hazard, actions, generated_by='Safety Department'):
    """Investigation Report PDF."""
    S = _styles()
    ref = inv.id if inv else '—'
    status = inv.status if inv else '—'
    title = inv.title or 'Investigation Report'
    dept = inv.department.name if inv and inv.department else '—'

    E = []
    E.append(_cover_banner(
        title=title, ref=ref, doc_type='Investigation Report',
        status=status, dept=dept,
        date_str=inv.date_of_occurrence if inv else '—',
        classification='RESTRICTED — SAFETY SENSITIVE', S=S
    ))
    E.append(Spacer(1, 6))

    E.append(_section_header('1. Investigation Details', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Investigation Ref',    ref),
        ('Title',                inv.title or '—'),
        ('Linked Report',        inv.linked_report_id or '—'),
        ('Linked Hazard',        inv.hazard_id or '—'),
        ('Date of Occurrence',   inv.date_of_occurrence or '—'),
        ('Investigator',         inv.investigator or '—'),
        ('Department',           dept),
        ('Status',               status),
    ], S, cols=2))
    E.append(Spacer(1, 6))

    E.append(_section_header('2. Event Description', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Description of Event', inv.description, S))
    E.append(Spacer(1, 6))

    E.append(_section_header('3. Root Cause Analysis — 5-Whys', S))
    E.append(Spacer(1, 4))
    for i in range(1, 6):
        why_text = getattr(inv, f'why{i}', None)
        if why_text:
            E.append(_text_block(f'Why {i}', why_text, S))
            E.append(Spacer(1, 3))
    E.append(Spacer(1, 4))
    E.append(_text_block('Root Cause Determination', inv.root_cause, S))
    E.append(Spacer(1, 6))

    E.append(_section_header('4. Contributing Factors', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Human Factors',         inv.human_factors or '—'),
        ('Technical Factors',     inv.technical_factors or '—'),
        ('Organizational Factors',inv.organizational_factors or '—'),
        ('Environmental Factors', inv.environmental_factors or '—'),
    ], S, cols=1))
    E.append(Spacer(1, 6))

    E.append(_section_header('5. Recommendations & Corrective Actions', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Recommendations', inv.recommendations, S))
    E.append(Spacer(1, 4))
    action_data = [{'id': a.id, 'description': a.description,
                    'owner': a.owner, 'due_date': a.due_date,
                    'priority': a.priority, 'status': a.status}
                   for a in (actions or [])]
    E.append(_actions_table(action_data, S))
    E.append(Spacer(1, 6))

    E.append(_section_header('6. Signatures', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Investigator',   'name': inv.investigator or '', 'date': ''},
        {'role': 'Safety Manager', 'name': '', 'date': ''},
        {'role': 'Accountable Mgr','name': '', 'date': ''},
    ], S))

    return _build_doc(E, 'Investigation Report', ref, 'RESTRICTED — SAFETY SENSITIVE',
                      generated_by, status)


# ─────────────────────────────────────────────────────────────────────────────

def pdf_risk_assessment(ra, hazard, rows, mitigations, reviews,
                        generated_by='Safety Department'):
    """Risk Assessment PDF — mirrors AviaS RA Form pages 1-5."""
    S = _styles()
    ref = ra.control_number or ra.id if ra else '—'
    status = ra.status if ra else '—'
    title = ra.title or 'Risk Assessment'
    dept = ra.department.name if ra and ra.department else '—'
    rev = f'REV{ra.revision}' if ra else 'REV0'

    E = []
    E.append(_cover_banner(
        title=title, ref=ref, doc_type=f'Risk Assessment — {rev}',
        status=status, dept=dept,
        date_str=ra.assessment_date if ra else '—',
        classification='RESTRICTED — SAFETY SENSITIVE', S=S
    ))
    E.append(Spacer(1, 6))

    # Page 1 — Administration
    E.append(_section_header('1. Administration', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Control Number',    ref),
        ('Revision',          rev),
        ('Assessment Date',   ra.assessment_date or '—'),
        ('Next Review Date',  ra.next_review_date or '—'),
        ('Responsible Name',  ra.responsible_name or '—'),
        ('Assessors',         ra.assessors_names or '—'),
        ('Status',            status),
        ('Management Accept.',ra.management_acceptance or 'Pending'),
        ('Acceptance Date',   ra.acceptance_date or '—'),
        ('Linked Hazard',     ra.hazard_id or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 6))

    # Page 2 — General Information
    E.append(_section_header('2. General Information', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Risk Level Before Controls', ra.risk_level_prior or '—'),
        ('Risk Level After Controls',  ra.risk_level_after or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 4))
    E.append(_text_block('General Description', ra.general_description, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Reasons for Risk Assessment', ra.reasons, S))
    E.append(Spacer(1, 6))

    # Page 3 — Risk Table
    if rows:
        E.append(_section_header('3. Risk Table', S))
        E.append(Spacer(1, 4))
        risk_rows = [[
            Paragraph('#',          S['field_label']),
            Paragraph('ACTIVITY',   S['field_label']),
            Paragraph('HAZARD',     S['field_label']),
            Paragraph('CONSEQUENCE',S['field_label']),
            Paragraph('INIT RISK',  S['field_label']),
            Paragraph('CONTROLS',   S['field_label']),
            Paragraph('RES RISK',   S['field_label']),
            Paragraph('TOLERANCE',  S['field_label']),
        ]]
        for row in rows:
            risk_rows.append([
                Paragraph(str(row.seq_num or ''), S['mono']),
                Paragraph((row.type_of_activity or '—')[:40], S['small']),
                Paragraph((row.generic_hazard or '—')[:40], S['small']),
                Paragraph((row.consequences or '—')[:60], S['small']),
                Paragraph(row.risk_index_initial or '—', S['small']),
                Paragraph((row.current_defenses or '—')[:60], S['small']),
                Paragraph(row.risk_index_residual or '—', S['small']),
                Paragraph(row.risk_tolerance_residual or '—', S['small']),
            ])
        col_w = [8*mm, 28*mm, 28*mm, 35*mm, 16*mm, 38*mm, 16*mm, 24*mm]
        rt = Table(risk_rows, colWidths=col_w, repeatRows=1)
        rt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), C_NAVY),
            ('TEXTCOLOR',  (0, 0), (-1, 0), C_WHITE),
            ('FONTSIZE',   (0, 0), (-1, 0), 6.5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_WHITE, C_GRAY_LITE]),
            ('GRID',       (0, 0), (-1, -1), 0.3, C_BORDER),
            ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
            ('FONTSIZE',   (0, 1), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING',(0,0),(-1, -1), 3),
            ('LEFTPADDING',(0, 0), (-1, -1), 3),
        ]))
        E.append(rt)
        E.append(Spacer(1, 6))

    # Page 4 — Mitigations
    if mitigations:
        E.append(_section_header('4. Mitigation Responsibilities', S))
        E.append(Spacer(1, 4))
        mit_rows = [[
            Paragraph('SEQ', S['field_label']),
            Paragraph('MITIGATION', S['field_label']),
            Paragraph('RESPONSIBLE MANAGER', S['field_label']),
            Paragraph('DUE DATE', S['field_label']),
            Paragraph('STATUS', S['field_label']),
        ]]
        for m in mitigations:
            mit_rows.append([
                Paragraph(str(m.hazard_seq or '—'), S['mono']),
                Paragraph((m.mitigation or '—')[:100], S['small']),
                Paragraph(m.responsible_manager or '—', S['small']),
                Paragraph(m.due_date or '—', S['small']),
                Paragraph(m.status or '—', S['small']),
            ])
        col_w = [12*mm, CONTENT_W-12*mm-45*mm-22*mm-25*mm, 45*mm, 22*mm, 25*mm]
        mt = Table(mit_rows, colWidths=col_w, repeatRows=1)
        mt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), C_NAVY),
            ('TEXTCOLOR',  (0, 0), (-1, 0), C_WHITE),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_WHITE, C_GRAY_LITE]),
            ('GRID',       (0, 0), (-1, -1), 0.3, C_BORDER),
            ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING',(0,0),(-1, -1), 4),
            ('LEFTPADDING',(0, 0), (-1, -1), 4),
        ]))
        E.append(mt)
        E.append(Spacer(1, 6))

    # Page 5 — Reviews
    if reviews:
        E.append(_section_header('5. Mitigation Effectiveness Review', S))
        E.append(Spacer(1, 4))
        rev_rows = [[
            Paragraph('MITIGATION', S['field_label']),
            Paragraph('EFFECTIVENESS REVIEW', S['field_label']),
            Paragraph('RATING', S['field_label']),
            Paragraph('DATE', S['field_label']),
            Paragraph('ACTIONER', S['field_label']),
        ]]
        for rv in reviews:
            rev_rows.append([
                Paragraph((rv.risk_mitigation or '—')[:60], S['small']),
                Paragraph((rv.review_of_effectiveness or '—')[:100], S['small']),
                Paragraph(rv.effectiveness_rating or '—', S['small']),
                Paragraph(rv.date_completed or '—', S['small']),
                Paragraph(rv.actioner or '—', S['small']),
            ])
        col_w = [40*mm, CONTENT_W-40*mm-30*mm-22*mm-30*mm, 30*mm, 22*mm, 30*mm]
        rvt = Table(rev_rows, colWidths=col_w, repeatRows=1)
        rvt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), C_NAVY),
            ('TEXTCOLOR',  (0, 0), (-1, 0), C_WHITE),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_WHITE, C_GRAY_LITE]),
            ('GRID',       (0, 0), (-1, -1), 0.3, C_BORDER),
            ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING',(0,0),(-1, -1), 4),
            ('LEFTPADDING',(0, 0), (-1, -1), 4),
        ]))
        E.append(rvt)
        E.append(Spacer(1, 6))

    # Signatures
    E.append(_section_header('6. Signatures', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Prepared By',     'name': ra.prepared_by_name or '', 'date': ra.assessment_date or ''},
        {'role': 'Reviewed By',     'name': ra.reviewed_by_name or '',  'date': ''},
        {'role': 'Approved By',     'name': ra.approved_by_name or '',  'date': ''},
        {'role': 'Accountable Mgr', 'name': '', 'date': ''},
    ], S))

    return _build_doc(E, f'Risk Assessment {rev}', ref,
                      'RESTRICTED — SAFETY SENSITIVE', generated_by, status)


# ─────────────────────────────────────────────────────────────────────────────

def pdf_action(action, history, generated_by='Safety Department'):
    """Corrective / Preventive Action Record PDF."""
    S = _styles()
    ref = action.id if action else '—'
    status = action.status if action else '—'
    title = (action.description or 'Action Record')[:80] if action else 'Action Record'

    E = []
    E.append(_cover_banner(
        title=title, ref=ref, doc_type='Corrective / Preventive Action Record',
        status=status, dept='—',
        date_str=action.created_at.strftime('%Y-%m-%d') if action and action.created_at else '—',
        classification='INTERNAL — SAFETY RECORD', S=S
    ))
    E.append(Spacer(1, 6))

    E.append(_section_header('1. Action Details', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Action Reference', ref),
        ('Action Type',      action.action_type or 'Corrective'),
        ('Source',           action.source or '—'),
        ('Linked Hazard',    action.hazard_id or '—'),
        ('Owner',            action.owner or '—'),
        ('Assigned By',      action.assigned_by or '—'),
        ('Priority',         action.priority or '—'),
        ('Status',           status),
        ('Due Date',         action.due_date or '—'),
        ('Closed Date',      action.closed_date or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 6))

    E.append(_section_header('2. Description & Root Cause', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Action Description', action.description, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Root Cause', action.root_cause, S))
    E.append(Spacer(1, 6))

    E.append(_section_header('3. Mitigation & Corrective Work', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Mitigation Description', action.mitigation_description, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Corrective Action Details', action.corrective_description, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Evidence', action.evidence, S))
    E.append(Spacer(1, 6))

    E.append(_section_header('4. Safety Review', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Reviewed By',     action.safety_reviewer or '—'),
        ('Review Date',     action.safety_review_date or '—'),
        ('Effectiveness',   action.effectiveness or '—'),
        ('Verified By',     action.verified_by or '—'),
        ('Verified Date',   action.verified_date or '—'),
        ('Implementation Date', action.implementation_date or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 4))
    E.append(_text_block('Safety Review Notes', action.safety_review_notes, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Effectiveness Review', action.effectiveness_review, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Safety Notes', action.safety_notes, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Follow-Up Notes', action.follow_up_notes, S))
    E.append(Spacer(1, 6))

    E.append(_section_header('5. Audit Trail', S))
    E.append(Spacer(1, 4))
    timeline_events = [{
        'date':  h.changed_at.strftime('%Y-%m-%d %H:%M') if h.changed_at else '—',
        'event': f'{h.from_status or "—"} → {h.to_status or "—"}',
        'user':  h.changed_by or '—',
        'notes': h.notes or '',
    } for h in (history or [])]
    E.append(_timeline_table(timeline_events, S))
    E.append(Spacer(1, 6))

    E.append(_section_header('6. Signatures', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Action Owner',   'name': action.owner or '', 'date': action.closed_date or ''},
        {'role': 'Safety Reviewer','name': action.safety_reviewer or '', 'date': action.safety_review_date or ''},
        {'role': 'Verified By',    'name': action.verified_by or '', 'date': action.verified_date or ''},
    ], S))

    return _build_doc(E, 'Action Record', ref, 'INTERNAL — SAFETY RECORD',
                      generated_by, status)


# ─────────────────────────────────────────────────────────────────────────────

def pdf_moc(moc, generated_by='Safety Department',
            milestones=None, stakeholders=None, updates=None,
            actions=None, linked_ra=None, investigations=None, avis=None):
    """
    Full Management of Change Record PDF — all related modules included.
    Sections:
      1  Change Identification
      2  Change Description
      3  Impact Assessment
      4  Regulatory Compliance
      5  Approval Chain
      6  Safety Risk Assessment (linked RA summary)
      7  Stakeholder Consultation
      8  Implementation Planning & Milestones
      9  Actions Taken
     10  Investigations
     11  Post-Implementation Review (PIR)
     12  Audit Verification Items (AVI)
     13  Activity Log
     14  Signatures
    """
    S = _styles()
    ref    = (moc.moc_number or moc.id) if moc else '—'
    status = moc.status or moc.approval_status or '—'
    title  = moc.title or 'Management of Change'
    dept   = moc.department.name if moc and moc.department else '—'

    milestones    = milestones    or []
    stakeholders  = stakeholders  or []
    updates       = updates       or []
    actions       = actions       or []
    investigations= investigations or []
    avis          = avis          or []

    E = []

    # ── Cover banner ─────────────────────────────────────────────────────────
    E.append(_cover_banner(
        title=title, ref=ref, doc_type='Management of Change Record',
        status=status, dept=dept,
        date_str=moc.date_raised or moc.planned_date or '—',
        classification='INTERNAL — CONTROLLED CHANGE', S=S
    ))
    E.append(Spacer(1, 8))

    # ── 1. Change Identification ─────────────────────────────────────────────
    E.append(_section_header('1. Change Identification', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('MOC Reference',      ref),
        ('MOC Number',         moc.moc_number or moc.id),
        ('Change Category',    moc.change_category or moc.change_type or '—'),
        ('Department',         dept),
        ('Initiator',          moc.initiator or '—'),
        ('Date Raised',        moc.date_raised or '—'),
        ('Target Completion',  moc.target_completion_date or '—'),
        ('Lifecycle Status',   status),
        ('Approval Status',    moc.approval_status or '—'),
        ('Approved By',        moc.approved_by or '—'),
        ('Approved Date',      moc.approved_date or '—'),
        ('Implemented Date',   moc.implemented_date or '—'),
        ('Closed Date',        moc.closed_date or '—'),
        ('Linked Hazard',      moc.hazard_id or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 8))

    # ── 2. Change Description ────────────────────────────────────────────────
    E.append(_section_header('2. Change Description', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Current Situation', moc.current_situation or moc.pre_change_risk, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Proposed Change / Description', moc.proposed_change or moc.description, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Reason for Change', moc.reason_for_change, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Expected Benefits', moc.expected_benefits, S))
    E.append(Spacer(1, 8))

    # ── 3. Impact Assessment ─────────────────────────────────────────────────
    E.append(_section_header('3. Impact Assessment', S))
    E.append(Spacer(1, 4))
    impact_fields = [
        ('Aircraft Operations',  moc.impact_aircraft_ops),
        ('Flight Crew',          moc.impact_flight_crew),
        ('Cabin Crew',           moc.impact_cabin_crew),
        ('Ground Operations',    moc.impact_ground_ops),
        ('Maintenance',          moc.impact_maintenance),
        ('Operations Control',   moc.impact_occ),
        ('Training',             moc.impact_training),
        ('Safety Reporting',     moc.impact_safety_reporting),
        ('Emergency Response',   moc.impact_erp),
        ('Security',             moc.impact_security),
        ('Regulatory',           moc.impact_regulatory),
        ('Contractors',          moc.impact_contractor),
    ]
    impact_rows = [[
        Paragraph('AREA', S['field_label']),
        Paragraph('IMPACTED', S['field_label']),
        Paragraph('AREA', S['field_label']),
        Paragraph('IMPACTED', S['field_label']),
    ]]
    for i in range(0, len(impact_fields), 2):
        row = []
        for k in range(2):
            if i + k < len(impact_fields):
                area, val = impact_fields[i + k]
                hit = bool(val)
                row.append(Paragraph(area, S['field_value']))
                clr = C_GREEN if hit else C_GRAY
                row.append(Paragraph('YES' if hit else 'No',
                    ParagraphStyle('imp', fontName='Helvetica-Bold',
                                   fontSize=8, textColor=clr)))
            else:
                row += [Paragraph('', S['field_value']), Paragraph('', S['field_value'])]
        impact_rows.append(row)
    hw = CONTENT_W / 2
    imp_t = Table(impact_rows, colWidths=[hw * 0.65, hw * 0.35, hw * 0.65, hw * 0.35],
                  repeatRows=1)
    imp_t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), C_NAVY),
        ('TEXTCOLOR',     (0, 0), (-1, 0), C_WHITE),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [C_WHITE, C_GRAY_LITE]),
        ('GRID',          (0, 0), (-1, -1), 0.3, C_BORDER),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
    ]))
    E.append(imp_t)
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Safety Impact Level',        moc.safety_impact_level or '—'),
        ('Risk Assessment Required',   'Yes' if moc.risk_assessment_required else 'No'),
        ('Training Required',          'Yes' if moc.training_required else 'No'),
        ('Documentation Update',       'Yes' if moc.documentation_update_required else 'No'),
        ('SOP Revision Required',      'Yes' if moc.sop_revision_required else 'No'),
        ('ERP Update Required',        'Yes' if moc.erp_update_required else 'No'),
    ], S, cols=2))
    E.append(Spacer(1, 8))

    # ── 4. Regulatory Compliance ─────────────────────────────────────────────
    E.append(_section_header('4. Regulatory Compliance', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('ICAO Impact',              'Yes' if moc.icao_impact else 'No'),
        ('IOSA Impact',              'Yes' if moc.iosa_impact else 'No'),
        ('EASA Impact',              'Yes' if moc.easa_impact else 'No'),
        ('National Authority Impact','Yes' if moc.national_authority_impact else 'No'),
        ('Company Manual Impact',    'Yes' if moc.company_manual_impact else 'No'),
        ('Regulatory Approval Req.', 'Yes' if moc.regulatory_approval_required else 'No'),
        ('Regulatory Approval Ref',  moc.regulatory_approval_ref or '—'),
        ('Regulatory Approval Date', moc.regulatory_approval_date or '—'),
    ], S, cols=2))
    if moc.regulatory_evidence:
        E.append(Spacer(1, 4))
        E.append(_text_block('Regulatory Evidence / Notes', moc.regulatory_evidence, S))
    E.append(Spacer(1, 8))

    # ── 5. Approval Chain ───────────────────────────────────────────────────
    E.append(_section_header('5. Approval Chain', S))
    E.append(Spacer(1, 4))
    approval_rows = [[
        Paragraph('STEP', S['field_label']),
        Paragraph('APPROVER', S['field_label']),
        Paragraph('DECISION', S['field_label']),
        Paragraph('DATE', S['field_label']),
        Paragraph('COMMENTS', S['field_label']),
    ]]
    approval_steps = [
        ('1. Department Manager', moc.dept_manager_name,   moc.dept_manager_status,  moc.dept_manager_date,  moc.dept_manager_comments),
        ('2. Safety Review',      moc.safety_reviewer_name,moc.safety_review_status, moc.safety_review_date, moc.safety_review_comments),
        ('3. Safety Manager',     moc.sm_name,             moc.sm_approval_status,   moc.sm_date,            moc.sm_comments),
    ]
    if moc.ae_approval_required:
        approval_steps.append(
            ('4. Accountable Executive', moc.ae_name, moc.ae_approval_status, moc.ae_date, moc.ae_comments)
        )
    for step, name, decision, date, comments in approval_steps:
        dec = (decision or 'Pending').upper()
        dec_clr = C_GREEN if 'APPROVED' in dec else (C_RED if 'REJECT' in dec else C_GRAY)
        approval_rows.append([
            Paragraph(step, S['field_value']),
            Paragraph(name or '—', S['field_value']),
            Paragraph(decision or 'Pending',
                      ParagraphStyle('apdec', fontName='Helvetica-Bold',
                                     fontSize=8, textColor=dec_clr)),
            Paragraph(date or '—', S['small']),
            Paragraph((comments or '—')[:120], S['small']),
        ])
    ap_col = [38*mm, 38*mm, 28*mm, 22*mm, CONTENT_W - 38*mm - 38*mm - 28*mm - 22*mm]
    ap_t = Table(approval_rows, colWidths=ap_col, repeatRows=1)
    ap_t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  C_NAVY),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  C_WHITE),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [C_WHITE, C_GRAY_LITE]),
        ('GRID',          (0, 0), (-1, -1), 0.3, C_BORDER),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
    ]))
    E.append(ap_t)
    E.append(Spacer(1, 8))

    # ── 6. Safety Risk Assessment ────────────────────────────────────────────
    E.append(_section_header('6. Safety Risk Assessment', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('RA Required',   'Yes' if moc.risk_assessment_required else 'No'),
        ('RA Status',     moc.ra_status or '—'),
        ('Linked RA Ref', moc.linked_ra_id or '—'),
    ], S, cols=2))
    if linked_ra:
        E.append(Spacer(1, 4))
        E.append(_info_grid([
            ('RA Control Number', linked_ra.control_number or linked_ra.id),
            ('RA Title',          linked_ra.title or '—'),
            ('RA Status',         linked_ra.status or '—'),
            ('Responsible',       linked_ra.responsible_name or '—'),
            ('Assessment Date',   linked_ra.assessment_date or '—'),
            ('Next Review Date',  linked_ra.next_review_date or '—'),
        ], S, cols=2))
        # RA Rows (risk table)
        if hasattr(linked_ra, 'rows') and linked_ra.rows:
            E.append(Spacer(1, 4))
            ra_rows_data = [[
                Paragraph('SEQ', S['field_label']),
                Paragraph('HAZARD / ACTIVITY', S['field_label']),
                Paragraph('CONSEQUENCES', S['field_label']),
                Paragraph('INITIAL RISK', S['field_label']),
                Paragraph('RESIDUAL RISK', S['field_label']),
                Paragraph('FURTHER MITIGATIONS', S['field_label']),
            ]]
            for row in linked_ra.rows:
                init_ri = row.risk_index_initial or '—'
                res_ri  = row.risk_index_residual or '—'
                INTOLER = {'5A','5B','5C','4A','4B','3A'}
                ra_rows_data.append([
                    Paragraph(str(row.seq_num or '—'), S['small']),
                    Paragraph(row.generic_hazard or row.type_of_activity or '—', S['small']),
                    Paragraph(row.consequences or '—', S['small']),
                    Paragraph(init_ri,
                              ParagraphStyle('ri', fontName='Helvetica-Bold',
                                             fontSize=8,
                                             textColor=C_RED if init_ri in INTOLER else C_ORANGE)),
                    Paragraph(res_ri,
                              ParagraphStyle('rr', fontName='Helvetica-Bold',
                                             fontSize=8, textColor=C_GREEN)),
                    Paragraph(row.further_mitigations or row.current_defenses or '—', S['small']),
                ])
            ra_col = [10*mm, 38*mm, 38*mm, 16*mm, 16*mm, CONTENT_W - 10*mm - 38*mm - 38*mm - 16*mm - 16*mm]
            ra_t = Table(ra_rows_data, colWidths=ra_col, repeatRows=1)
            ra_t.setStyle(TableStyle([
                ('BACKGROUND',    (0, 0), (-1, 0),  C_NAVY),
                ('TEXTCOLOR',     (0, 0), (-1, 0),  C_WHITE),
                ('ROWBACKGROUNDS',(0, 1), (-1, -1), [C_WHITE, C_GRAY_LITE]),
                ('GRID',          (0, 0), (-1, -1), 0.3, C_BORDER),
                ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING',    (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('LEFTPADDING',   (0, 0), (-1, -1), 4),
            ]))
            E.append(ra_t)
        # RA Mitigations
        if hasattr(linked_ra, 'mitigations') and linked_ra.mitigations:
            E.append(Spacer(1, 4))
            mit_rows = [[
                Paragraph('HAZARD REF', S['field_label']),
                Paragraph('MITIGATION', S['field_label']),
                Paragraph('RESPONSIBLE', S['field_label']),
                Paragraph('DUE DATE', S['field_label']),
                Paragraph('STATUS', S['field_label']),
            ]]
            for mit in linked_ra.mitigations:
                mit_rows.append([
                    Paragraph(mit.hazard_seq or '—', S['small']),
                    Paragraph(mit.mitigation or '—', S['small']),
                    Paragraph(mit.responsible_manager or '—', S['small']),
                    Paragraph(mit.due_date or '—', S['small']),
                    Paragraph(mit.status or '—',
                              ParagraphStyle('ms', fontName='Helvetica-Bold',
                                             fontSize=8,
                                             textColor=C_GREEN if mit.status == 'Closed' else C_ORANGE)),
                ])
            mc = [18*mm, CONTENT_W - 18*mm - 38*mm - 22*mm - 20*mm, 38*mm, 22*mm, 20*mm]
            mt = Table(mit_rows, colWidths=mc, repeatRows=1)
            mt.setStyle(TableStyle([
                ('BACKGROUND',    (0, 0), (-1, 0),  C_NAVY),
                ('TEXTCOLOR',     (0, 0), (-1, 0),  C_WHITE),
                ('ROWBACKGROUNDS',(0, 1), (-1, -1), [C_WHITE, C_GRAY_LITE]),
                ('GRID',          (0, 0), (-1, -1), 0.3, C_BORDER),
                ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING',    (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('LEFTPADDING',   (0, 0), (-1, -1), 4),
            ]))
            E.append(mt)
    else:
        E.append(Spacer(1, 4))
        E.append(Paragraph('No linked Risk Assessment found.', S['small']))
    E.append(Spacer(1, 8))

    # ── 7. Stakeholder Consultation ──────────────────────────────────────────
    E.append(_section_header('7. Stakeholder Consultation', S))
    E.append(Spacer(1, 4))
    if moc.stakeholder_summary:
        E.append(_text_block('Consultation Summary', moc.stakeholder_summary, S))
        E.append(Spacer(1, 4))
    if stakeholders:
        sk_rows = [[
            Paragraph('CONTACT NAME', S['field_label']),
            Paragraph('DEPARTMENT', S['field_label']),
            Paragraph('DATE', S['field_label']),
            Paragraph('COMMENTS', S['field_label']),
        ]]
        for sk in stakeholders:
            sk_rows.append([
                Paragraph(getattr(sk, 'contact_name', None) or getattr(sk, 'name', None) or '—', S['field_value']),
                Paragraph(getattr(sk, 'department_name', None) or getattr(sk, 'department', None) or '—', S['small']),
                Paragraph(getattr(sk, 'consultation_date', None) or getattr(sk, 'consulted_date', None) or '—', S['small']),
                Paragraph(getattr(sk, 'comments', None) or getattr(sk, 'feedback', None) or '—', S['small']),
            ])
        sk_col = [45*mm, 40*mm, 22*mm, CONTENT_W - 45*mm - 40*mm - 22*mm]
        sk_t = Table(sk_rows, colWidths=sk_col, repeatRows=1)
        sk_t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0),  C_NAVY),
            ('TEXTCOLOR',     (0, 0), (-1, 0),  C_WHITE),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [C_WHITE, C_GRAY_LITE]),
            ('GRID',          (0, 0), (-1, -1), 0.3, C_BORDER),
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING',    (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ]))
        E.append(sk_t)
    else:
        E.append(Paragraph('No individual stakeholder records. See summary above.', S['small']))
    E.append(Spacer(1, 8))

    # ── 8. Implementation Planning & Milestones ──────────────────────────────
    E.append(PageBreak())
    E.append(_section_header('8. Implementation Planning & Milestones', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Implementation Start',   moc.implementation_start_date or '—'),
        ('Target Completion',      moc.target_completion_date or '—'),
        ('Implementation Status',  moc.implementation_status or '—'),
        ('Implemented Date',       moc.implemented_date or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 4))
    if milestones:
        ms_rows = [[
            Paragraph('MILESTONE', S['field_label']),
            Paragraph('RESPONSIBLE', S['field_label']),
            Paragraph('TARGET DATE', S['field_label']),
            Paragraph('STATUS', S['field_label']),
            Paragraph('COMPLETED', S['field_label']),
            Paragraph('NOTES', S['field_label']),
        ]]
        for ms in milestones:
            st_clr = C_GREEN if ms.status == 'Complete' else (
                     C_RED if ms.status == 'Overdue' else
                     C_BLUE if ms.status == 'In Progress' else C_GRAY)
            ms_rows.append([
                Paragraph(ms.description or '—', S['field_value']),
                Paragraph(ms.responsible_person or '—', S['small']),
                Paragraph(ms.target_date or '—', S['small']),
                Paragraph(ms.status or '—',
                          ParagraphStyle('mst', fontName='Helvetica-Bold',
                                         fontSize=8, textColor=st_clr)),
                Paragraph(ms.completed_date or '—', S['small']),
                Paragraph(ms.notes or '—', S['small']),
            ])
        ms_col = [50*mm, 30*mm, 20*mm, 18*mm, 18*mm,
                  CONTENT_W - 50*mm - 30*mm - 20*mm - 18*mm - 18*mm]
        ms_t = Table(ms_rows, colWidths=ms_col, repeatRows=1)
        ms_t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0),  C_NAVY),
            ('TEXTCOLOR',     (0, 0), (-1, 0),  C_WHITE),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [C_WHITE, C_GRAY_LITE]),
            ('GRID',          (0, 0), (-1, -1), 0.3, C_BORDER),
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING',    (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ]))
        E.append(ms_t)
        done = sum(1 for m in milestones if m.status == 'Complete')
        E.append(Spacer(1, 4))
        E.append(Paragraph(f'Milestones: {done}/{len(milestones)} complete',
                           S['field_label']))
    else:
        E.append(Paragraph('No milestones recorded.', S['small']))
    E.append(Spacer(1, 8))

    # ── 9. Actions Taken ────────────────────────────────────────────────────
    E.append(_section_header('9. Actions Taken (Corrective & Preventive)', S))
    E.append(Spacer(1, 4))
    if actions:
        act_rows = [[
            Paragraph('ACTION ID', S['field_label']),
            Paragraph('DESCRIPTION', S['field_label']),
            Paragraph('STATUS', S['field_label']),
            Paragraph('PRIORITY', S['field_label']),
            Paragraph('ASSIGNED TO', S['field_label']),
            Paragraph('DUE DATE', S['field_label']),
            Paragraph('CLOSED DATE', S['field_label']),
            Paragraph('EFFECTIVENESS', S['field_label']),
        ]]
        for a in actions:
            st_clr = C_GREEN if a.status == 'Closed' else (
                     C_RED if a.status == 'Overdue' else
                     C_ORANGE if a.status in ('Assigned', 'In Progress') else C_GRAY)
            act_rows.append([
                Paragraph(str(a.id), S['mono']),
                Paragraph(a.description or '—', S['small']),
                Paragraph(a.status or '—',
                          ParagraphStyle('ast', fontName='Helvetica-Bold',
                                         fontSize=8, textColor=st_clr)),
                Paragraph(a.priority or '—', S['small']),
                Paragraph(a.sag_member or a.owner or '—', S['small']),
                Paragraph(a.due_date or '—', S['small']),
                Paragraph(a.closed_date or '—', S['small']),
                Paragraph(a.effectiveness or '—', S['small']),
            ])
        a_col = [20*mm, 55*mm, 20*mm, 16*mm, 28*mm, 18*mm, 18*mm,
                 CONTENT_W - 20*mm - 55*mm - 20*mm - 16*mm - 28*mm - 18*mm - 18*mm]
        a_t = Table(act_rows, colWidths=a_col, repeatRows=1)
        a_t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0),  C_NAVY),
            ('TEXTCOLOR',     (0, 0), (-1, 0),  C_WHITE),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [C_WHITE, C_GRAY_LITE]),
            ('GRID',          (0, 0), (-1, -1), 0.3, C_BORDER),
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING',    (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING',   (0, 0), (-1, -1), 3),
        ]))
        E.append(a_t)
        closed = sum(1 for a in actions if a.status == 'Closed')
        E.append(Spacer(1, 4))
        E.append(Paragraph(f'Actions: {closed}/{len(actions)} closed',
                           S['field_label']))
    else:
        E.append(Paragraph('No actions recorded for this MOC.', S['small']))
    E.append(Spacer(1, 8))

    # ── 10. Linked Investigations ────────────────────────────────────────────
    E.append(_section_header('10. Linked Investigations', S))
    E.append(Spacer(1, 4))
    if investigations:
        inv_rows = [[
            Paragraph('REFERENCE', S['field_label']),
            Paragraph('TITLE', S['field_label']),
            Paragraph('CLASSIFICATION', S['field_label']),
            Paragraph('STATUS', S['field_label']),
            Paragraph('INVESTIGATOR', S['field_label']),
            Paragraph('CLOSED DATE', S['field_label']),
        ]]
        for inv in investigations:
            inv_rows.append([
                Paragraph(str(inv.id), S['mono']),
                Paragraph(inv.title or '—', S['small']),
                Paragraph(getattr(inv, 'classification', None) or getattr(inv, 'investigation_type', None) or '—', S['small']),
                Paragraph(inv.status or '—', S['small']),
                Paragraph(getattr(inv, 'investigator', None) or getattr(inv, 'lead_investigator', None) or '—', S['small']),
                Paragraph(inv.closed_date or '—', S['small']),
            ])
        inv_col = [22*mm, 60*mm, 25*mm, 20*mm, 38*mm,
                   CONTENT_W - 22*mm - 60*mm - 25*mm - 20*mm - 38*mm]
        inv_t = Table(inv_rows, colWidths=inv_col, repeatRows=1)
        inv_t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0),  C_NAVY),
            ('TEXTCOLOR',     (0, 0), (-1, 0),  C_WHITE),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [C_WHITE, C_GRAY_LITE]),
            ('GRID',          (0, 0), (-1, -1), 0.3, C_BORDER),
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING',    (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ]))
        E.append(inv_t)
    else:
        E.append(Paragraph('No linked investigations.', S['small']))
    E.append(Spacer(1, 8))

    # ── 11. Post-Implementation Review (PIR) ─────────────────────────────────
    E.append(_section_header('11. Post-Implementation Review (PIR)', S))
    E.append(Spacer(1, 4))
    if moc.pir_actual_outcome:
        E.append(_info_grid([
            ('PIR Date',          moc.pir_date or '—'),
            ('Reviewer',          moc.pir_reviewer or '—'),
            ('Effectiveness',     moc.pir_effectiveness or '—'),
            ('Additional Actions', moc.pir_additional_actions or '—'),
        ], S, cols=2))
        E.append(Spacer(1, 4))
        E.append(_text_block('Actual Outcome', moc.pir_actual_outcome, S))
        if moc.pir_new_hazards:
            E.append(Spacer(1, 4))
            E.append(_text_block('New Hazards Identified', moc.pir_new_hazards, S))
        if moc.pir_lessons_learned:
            E.append(Spacer(1, 4))
            E.append(_text_block('Lessons Learned', moc.pir_lessons_learned, S))
    else:
        E.append(Paragraph('Post-Implementation Review not yet completed.', S['small']))
    E.append(Spacer(1, 8))

    # ── 12. Audit Verification Items (AVI) ──────────────────────────────────
    E.append(_section_header('12. Audit Verification Items (AVI)', S))
    E.append(Spacer(1, 4))
    if avis:
        avi_rows = [[
            Paragraph('AVI ID', S['field_label']),
            Paragraph('OBJECTIVE', S['field_label']),
            Paragraph('STATUS', S['field_label']),
            Paragraph('VERIFIED DATE', S['field_label']),
            Paragraph('VERIFIED BY', S['field_label']),
        ]]
        for avi in avis:
            st_clr = C_GREEN if avi.status == 'Verified' else (
                     C_RED if avi.status in ('Ineffective', 'Escalated') else C_ORANGE)
            avi_rows.append([
                Paragraph(avi.id, S['mono']),
                Paragraph(avi.verification_objective or '—', S['small']),
                Paragraph(avi.status or '—',
                          ParagraphStyle('avst', fontName='Helvetica-Bold',
                                         fontSize=8, textColor=st_clr)),
                Paragraph(avi.verified_date or '—', S['small']),
                Paragraph(avi.verified_by or '—', S['small']),
            ])
        av_col = [22*mm, CONTENT_W - 22*mm - 25*mm - 25*mm - 30*mm, 25*mm, 25*mm, 30*mm]
        av_t = Table(avi_rows, colWidths=av_col, repeatRows=1)
        av_t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0),  C_NAVY),
            ('TEXTCOLOR',     (0, 0), (-1, 0),  C_WHITE),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [C_WHITE, C_GRAY_LITE]),
            ('GRID',          (0, 0), (-1, -1), 0.3, C_BORDER),
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING',    (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ]))
        E.append(av_t)
    else:
        E.append(Paragraph('AVIs are auto-generated when the change is marked Implemented.', S['small']))
    E.append(Spacer(1, 8))

    # ── 13. Activity Log ────────────────────────────────────────────────────
    if updates:
        E.append(PageBreak())
        E.append(_section_header('13. Activity Log', S))
        E.append(Spacer(1, 4))
        upd_rows = [[
            Paragraph('DATE', S['field_label']),
            Paragraph('TYPE', S['field_label']),
            Paragraph('BY', S['field_label']),
            Paragraph('UPDATE', S['field_label']),
        ]]
        for upd in updates[:50]:
            upd_rows.append([
                Paragraph(upd.created_at.strftime('%Y-%m-%d %H:%M') if upd.created_at else '—', S['small']),
                Paragraph(upd.update_type or '—', S['small']),
                Paragraph(upd.update_by or '—', S['small']),
                Paragraph((upd.update_text or '—')[:120], S['small']),
            ])
        upd_col = [24*mm, 22*mm, 30*mm, CONTENT_W - 24*mm - 22*mm - 30*mm]
        upd_t = Table(upd_rows, colWidths=upd_col, repeatRows=1)
        upd_t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0),  C_NAVY),
            ('TEXTCOLOR',     (0, 0), (-1, 0),  C_WHITE),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [C_WHITE, C_GRAY_LITE]),
            ('GRID',          (0, 0), (-1, -1), 0.3, C_BORDER),
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING',    (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ]))
        E.append(upd_t)
        E.append(Spacer(1, 8))

    # ── 14. Signatures ───────────────────────────────────────────────────────
    E.append(PageBreak())
    E.append(_section_header('14. Signatures & Authorisation', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Initiator',          'name': moc.initiator or '',       'date': moc.date_raised or ''},
        {'role': 'Department Manager', 'name': moc.dept_manager_name or '','date': moc.dept_manager_date or ''},
        {'role': 'Safety Manager',     'name': moc.sm_name or '',          'date': moc.sm_date or ''},
        {'role': 'Accountable Mgr',    'name': moc.ae_name or moc.approved_by or '', 'date': moc.ae_date or moc.approved_date or ''},
    ], S))

    return _build_doc(E, 'Management of Change', ref,
                      'INTERNAL — CONTROLLED CHANGE', generated_by, status)


# ─────────────────────────────────────────────────────────────────────────────

def pdf_audit(schedule, findings, checklist, generated_by='Safety Department'):
    """Audit Report PDF."""
    S = _styles()
    ref = schedule.id if schedule else '—'
    status = schedule.status if schedule else '—'
    dept = schedule.department.name if schedule and schedule.department else '—'
    title = f'{schedule.audit_type or "Internal"} Audit — {dept}' if schedule else 'Audit Report'

    E = []
    E.append(_cover_banner(
        title=title, ref=ref, doc_type='Audit Report',
        status=status, dept=dept,
        date_str=schedule.scheduled_date if schedule else '—',
        classification='INTERNAL — AUDIT RECORD', S=S
    ))
    E.append(Spacer(1, 6))

    E.append(_section_header('1. Audit Details', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Audit Reference',  ref),
        ('Audit Type',       schedule.audit_type or '—'),
        ('Department',       dept),
        ('Scheduled Date',   schedule.scheduled_date or '—'),
        ('Actual Date',      schedule.actual_date or '—'),
        ('Lead Auditor',     schedule.lead_auditor or '—'),
        ('Audit Team',       schedule.audit_team or '—'),
        ('Status',           status),
        ('Opening Meeting',  schedule.opening_meeting or '—'),
        ('Closing Meeting',  schedule.closing_meeting or '—'),
        ('Closure Date',     schedule.closure_date or '—'),
        ('Closed By',        schedule.closed_by or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 6))

    E.append(_section_header('2. Scope & Objectives', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Scope', schedule.scope, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Objectives', schedule.objectives, S))
    E.append(Spacer(1, 6))

    # Findings
    if findings:
        E.append(_section_header(f'3. Findings ({len(findings)} total)', S))
        E.append(Spacer(1, 4))
        for f in findings:
            sev_color = C_RED if f.severity == 'Major' else (
                        C_ORANGE if f.severity == 'Minor' else C_BLUE)
            sev_bg = C_RED_LITE if f.severity == 'Major' else (
                     C_ORANGE_LT if f.severity == 'Minor' else C_BLUE_LITE)

            fdata = [[
                Paragraph(f'Finding {f.finding_ref or f.id}', S['heading2']),
                Paragraph(f.severity or '—',
                          ParagraphStyle('fsev', fontName='Helvetica-Bold',
                                         fontSize=8, textColor=sev_color)),
            ]]
            ft = Table(fdata, colWidths=[CONTENT_W * 0.8, CONTENT_W * 0.2])
            ft.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), sev_bg),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING',(0,0),(-1, -1), 6),
                ('LEFTPADDING',(0, 0), (-1, -1), 8),
                ('BOX',        (0, 0), (-1, -1), 0.5, sev_color),
                ('ALIGN',      (1, 0), (1, 0), 'RIGHT'),
            ]))
            E.append(ft)
            E.append(Spacer(1, 3))
            E.append(_info_grid([
                ('Finding Ref',      f.finding_ref or f.id),
                ('Category',         f.category or '—'),
                ('Standard Ref',     f.standard_ref or '—'),
                ('Status',           f.status or '—'),
                ('Assigned To',      f.assigned_to or '—'),
                ('CAP Due Date',     f.cap_due_date or '—'),
                ('Reviewed By',      f.reviewed_by or '—'),
                ('Closure Date',     f.closure_date or '—'),
            ], S, cols=2))
            E.append(Spacer(1, 3))
            E.append(_text_block('Finding Description', f.description, S))
            E.append(Spacer(1, 3))
            E.append(_text_block('Root Cause', f.root_cause, S))
            E.append(Spacer(1, 3))
            E.append(_text_block('Immediate Action', f.immediate_action, S))
            E.append(Spacer(1, 3))
            E.append(_text_block('Long-Term Action', f.longterm_action, S))
            E.append(Spacer(1, 3))
            E.append(_text_block('Safety Review Notes', f.review_notes, S))
            E.append(Spacer(1, 8))

    # Checklist summary
    if checklist:
        E.append(PageBreak())
        E.append(_section_header('4. Audit Checklist', S))
        E.append(Spacer(1, 4))
        cl_rows = [[
            Paragraph('REF',      S['field_label']),
            Paragraph('QUESTION', S['field_label']),
            Paragraph('RESPONSE', S['field_label']),
            Paragraph('COMMENT',  S['field_label']),
        ]]
        for item in checklist:
            resp_color = C_GREEN if item.response == 'Yes' else (
                         C_RED if item.response == 'No' else C_GRAY)
            cl_rows.append([
                Paragraph(item.item_ref or '—', S['mono']),
                Paragraph((item.question or '—')[:120], S['small']),
                Paragraph(item.response or '—',
                          ParagraphStyle('cr', fontName='Helvetica-Bold',
                                         fontSize=8, textColor=resp_color)),
                Paragraph((item.comment or '')[:80], S['small']),
            ])
        col_w = [18*mm, CONTENT_W-18*mm-18*mm-50*mm, 18*mm, 50*mm]
        clt = Table(cl_rows, colWidths=col_w, repeatRows=1)
        clt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), C_NAVY),
            ('TEXTCOLOR',  (0, 0), (-1, 0), C_WHITE),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_WHITE, C_GRAY_LITE]),
            ('GRID',       (0, 0), (-1, -1), 0.3, C_BORDER),
            ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING',(0,0),(-1, -1), 3),
            ('LEFTPADDING',(0, 0), (-1, -1), 4),
        ]))
        E.append(clt)
        E.append(Spacer(1, 6))

    E.append(_section_header('5. Audit Summary & Final Remarks', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Audit Summary', schedule.summary, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Final Remarks', schedule.final_remarks, S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Audit Result',      schedule.audit_result or '—'),
        ('Follow-Up Required',schedule.followup_required or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 6))

    E.append(_section_header('6. Signatures', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Lead Auditor',   'name': schedule.lead_auditor or '', 'date': schedule.actual_date or ''},
        {'role': 'Dept. Manager',  'name': '', 'date': ''},
        {'role': 'Safety Manager', 'name': '', 'date': ''},
    ], S))

    return _build_doc(E, 'Audit Report', ref, 'INTERNAL — AUDIT RECORD',
                      generated_by, status)


# ─────────────────────────────────────────────────────────────────────────────

def pdf_erp(erp, generated_by='Safety Department'):
    """Emergency Response Plan PDF."""
    S = _styles()
    ref = erp.erp_ref or erp.id if erp else '—'
    status = erp.status if erp else '—'
    title = erp.title or 'Emergency Response Plan'
    rev = erp.version if erp else 'REV0'

    E = []
    E.append(_cover_banner(
        title=title, ref=ref, doc_type=f'Emergency Response Plan — {rev}',
        status=status, dept='Safety Department',
        date_str='—',
        classification='RESTRICTED — EMERGENCY OPERATIONS', S=S
    ))
    E.append(Spacer(1, 6))

    E.append(_section_header('1. ERP Identification', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('ERP Reference',    ref),
        ('Scenario Type',    erp.scenario_type or '—'),
        ('Version',          rev),
        ('Status',           status),
        ('Review Date',      erp.review_date or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 6))

    E.append(_section_header('2. Description', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Scenario Description', erp.description, S))
    E.append(Spacer(1, 6))

    E.append(_section_header('3. Activation Criteria', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Activation Criteria', erp.activation_criteria, S))
    E.append(Spacer(1, 6))

    E.append(_section_header('4. Response Procedures', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Step-by-Step Response Procedures', erp.response_procedures, S))
    E.append(Spacer(1, 6))

    E.append(_section_header('5. Roles & Contacts', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Responsible Roles', erp.responsible_roles, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Emergency Contacts', erp.emergency_contacts, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Notification List', erp.notification_list, S))
    E.append(Spacer(1, 6))

    E.append(_section_header('6. Resources', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Resources Required', erp.resources_required, S))
    E.append(Spacer(1, 6))

    E.append(_section_header('7. Signatures', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Safety Manager',    'name': '', 'date': ''},
        {'role': 'Accountable Manager','name': '', 'date': ''},
        {'role': 'Operations Manager', 'name': '', 'date': ''},
    ], S))

    return _build_doc(E, f'Emergency Response Plan {rev}', ref,
                      'RESTRICTED — EMERGENCY OPERATIONS', generated_by, status)


# ─────────────────────────────────────────────────────────────────────────────

def pdf_voluntary(report, generated_by='Safety Department'):
    """Voluntary Safety Report PDF."""
    S = _styles()
    ref = report.ref_number or str(report.id) if report else '—'
    status = report.status if report else '—'
    dept = report.department.name if report and report.department else '—'

    E = []
    E.append(_cover_banner(
        title='Voluntary Safety Report', ref=ref,
        doc_type='Voluntary Safety Report',
        status=status, dept=dept,
        date_str=report.date if report else '—',
        classification='INTERNAL — SAFETY REPORT', S=S
    ))
    E.append(Spacer(1, 6))

    E.append(_section_header('1. Report Details', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Reference',     ref),
        ('Report Type',   report.report_type or '—'),
        ('Date',          report.date or '—'),
        ('Location',      report.location or '—'),
        ('Department',    dept),
        ('Status',        status),
        ('Reporter',      report.reporter_name or 'Anonymous'),
        ('Position',      report.position or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 6))

    E.append(_section_header('2. Report Content', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Description of Safety Concern', report.description, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Potential Consequences', report.consequences, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Suggestion / Recommendation', report.suggestion, S))
    E.append(Spacer(1, 6))

    E.append(_section_header('3. Safety Review', S))
    E.append(Spacer(1, 4))
    E.append(Paragraph(
        'This report has been received by the Safety Department and will be reviewed '
        'in accordance with AviaS SMS procedures. Reporter confidentiality '
        'is protected under the Just Culture policy.',
        S['body']))
    E.append(Spacer(1, 6))

    E.append(_section_header('4. Signatures', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Safety Officer',  'name': '', 'date': ''},
        {'role': 'Safety Manager',  'name': '', 'date': ''},
    ], S))

    return _build_doc(E, 'Voluntary Safety Report', ref,
                      'INTERNAL — SAFETY REPORT', generated_by, status)


# ─────────────────────────────────────────────────────────────────────────────

def pdf_confidential(report, generated_by='Safety Department'):
    """Confidential Safety Report PDF — identity-protected."""
    S = _styles()
    ref = report.ref_number or str(report.id) if report else '—'
    status = report.status if report else '—'

    E = []
    E.append(_cover_banner(
        title='Confidential Safety Report', ref=ref,
        doc_type='Confidential Safety Report',
        status=status, dept='Safety Department',
        date_str=report.date if report else '—',
        classification='CONFIDENTIAL — REPORTER IDENTITY PROTECTED', S=S
    ))
    E.append(Spacer(1, 6))

    E.append(Paragraph(
        '⚠  CONFIDENTIALITY NOTICE: This report was submitted under the AviaS '
        'Confidential Reporting Programme. The identity of the reporter '
        'is known only to the Safety Manager and is protected by company policy '
        'and applicable aviation regulations. This document must not be shared '
        'beyond the Safety Management System team.',
        ParagraphStyle('notice', fontName='Helvetica-Bold', fontSize=8,
                       leading=12, textColor=C_RED,
                       backColor=C_RED_LITE, borderPad=6)))
    E.append(Spacer(1, 8))

    E.append(_section_header('1. Report Details', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Reference', ref),
        ('Date',      report.date or '—'),
        ('Location',  report.location or '—'),
        ('Status',    status),
    ], S, cols=2))
    E.append(Spacer(1, 6))

    E.append(_section_header('2. Report Content', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Description of Safety Concern', report.description, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Potential Consequences', report.consequences, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Suggestion / Recommendation', report.suggestion, S))
    E.append(Spacer(1, 6))

    E.append(_section_header('3. Safety Manager Acknowledgement', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Safety Manager', 'name': '', 'date': ''},
        {'role': 'Accountable Mgr','name': '', 'date': ''},
    ], S))

    return _build_doc(E, 'Confidential Safety Report', ref,
                      'CONFIDENTIAL — REPORTER IDENTITY PROTECTED',
                      generated_by, status)


# ─────────────────────────────────────────────────────────────────────────────

def pdf_training(training, generated_by='Safety Department'):
    """Training Record PDF."""
    S = _styles()
    ref = f'TRN-{training.id}' if training else '—'
    status = training.status if training else '—'
    dept = training.department.name if training and training.department else '—'

    E = []
    E.append(_cover_banner(
        title=training.training_program or 'Training Record' if training else 'Training Record',
        ref=ref, doc_type='Training Record',
        status=status, dept=dept,
        date_str=training.training_date or training.scheduled_date if training else '—',
        classification='INTERNAL — TRAINING RECORD', S=S
    ))
    E.append(Spacer(1, 6))

    E.append(_section_header('1. Employee Information', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Employee Name',   training.employee_name or '—'),
        ('Employee ID',     training.employee_id or '—'),
        ('Department',      dept),
        ('Position',        training.position or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 6))

    E.append(_section_header('2. Training Details', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Training Type',     training.training_type or '—'),
        ('Programme',         training.training_program or '—'),
        ('Course Code',       training.course_code or '—'),
        ('Instructor',        training.instructor or '—'),
        ('Location',          training.location or '—'),
        ('Duration (hrs)',    str(training.duration_hours or '—')),
        ('Scheduled Date',    training.scheduled_date or '—'),
        ('Training Date',     training.training_date or '—'),
        ('Completion Date',   training.completion_date or '—'),
        ('Expiry Date',       training.expiry_date or '—'),
        ('Status',            status),
        ('Recurrent',         'Yes' if training.is_recurrent else 'No'),
    ], S, cols=2))
    E.append(Spacer(1, 4))
    E.append(_text_block('Notes', training.notes, S))
    E.append(Spacer(1, 6))

    E.append(_section_header('3. Signatures', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Employee',     'name': training.employee_name or '', 'date': training.completion_date or ''},
        {'role': 'Instructor',   'name': training.instructor or '', 'date': training.completion_date or ''},
        {'role': 'Training Mgr', 'name': '', 'date': ''},
    ], S))

    return _build_doc(E, 'Training Record', ref, 'INTERNAL — TRAINING RECORD',
                      generated_by, status)


# ─────────────────────────────────────────────────────────────────────────────

def pdf_audit_finding(finding, audit, generated_by='Safety Department'):
    """Single Audit Finding / NCR / CAP PDF."""
    S = _styles()
    ref = finding.finding_ref or finding.id if finding else '—'
    status = finding.status if finding else '—'
    title = finding.finding_title or f'Finding {ref}'
    dept = audit.department.name if audit and audit.department else '—'

    E = []
    E.append(_cover_banner(
        title=title, ref=ref, doc_type='Audit Finding / CAP Record',
        status=status, dept=dept,
        date_str=finding.assigned_date if finding else '—',
        classification='INTERNAL — AUDIT FINDING', S=S
    ))
    E.append(Spacer(1, 6))

    E.append(_section_header('1. Finding Details', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Finding Reference', ref),
        ('Severity',          finding.severity or '—'),
        ('Category',          finding.category or '—'),
        ('Standard Reference',finding.standard_ref or '—'),
        ('Audit Reference',   finding.schedule_id or '—'),
        ('Assigned To',       finding.assigned_to or '—'),
        ('Assigned Dept',     finding.assigned_dept or '—'),
        ('Assigned Date',     finding.assigned_date or '—'),
        ('CAP Responsible',   finding.cap_responsible or '—'),
        ('CAP Due Date',      finding.cap_due_date or '—'),
        ('Status',            status),
        ('Closure Date',      finding.closure_date or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 6))

    E.append(_section_header('2. Requirement & Evidence', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Regulatory/Standard Requirement', finding.requirement, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Auditor Evidence', finding.evidence, S))
    E.append(Spacer(1, 6))

    E.append(_section_header('3. Root Cause Analysis', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Root Cause', finding.root_cause, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Investigation Notes', finding.investigation_notes, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Contributing Factors', finding.contributing_factors, S))
    E.append(Spacer(1, 6))

    E.append(_section_header('4. Corrective Action Plan (CAP)', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Immediate Action', finding.immediate_action, S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Long-Term / Preventive Action', finding.longterm_action, S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('CAP Completion %', f'{finding.cap_completion_pct or 0}%'),
        ('CAP Status',       finding.cap_status or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 6))

    E.append(_section_header('5. Safety Review', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Review Notes', finding.review_notes, S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Reviewed By',   finding.reviewed_by or '—'),
        ('Review Date',   finding.review_date or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 6))

    E.append(_section_header('6. Closure', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Closure Notes', finding.closure_notes, S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Closure Verified By', finding.closure_verified_by or '—'),
        ('Closure Date',        finding.closure_date or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 6))

    E.append(_section_header('7. Signatures', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Dept Manager',   'name': finding.sig_dept_manager or '', 'date': finding.sig_date or ''},
        {'role': 'Lead Auditor',   'name': finding.sig_auditor or '',       'date': finding.sig_date or ''},
        {'role': 'Safety Manager', 'name': finding.sig_safety_manager or '', 'date': finding.sig_date or ''},
    ], S))

    return _build_doc(E, 'Audit Finding / CAP', ref,
                      'INTERNAL — AUDIT FINDING', generated_by, status)


# ─────────────────────────────────────────────────────────────────────────────

def pdf_spi_summary(indicators, data_by_spi, generated_by='Safety Department'):
    """SPI/SPT Performance Summary Report PDF."""
    S = _styles()
    month_str = datetime.utcnow().strftime('%B %Y')
    ref = f'SPI-{datetime.utcnow().strftime("%Y%m")}'

    E = []
    E.append(_cover_banner(
        title=f'Safety Performance Indicators — {month_str}',
        ref=ref, doc_type='SPI / SPT Performance Report',
        status='Current', dept='Safety Department',
        date_str=datetime.utcnow().strftime('%Y-%m-%d'),
        classification='INTERNAL — PERFORMANCE REPORT', S=S
    ))
    E.append(Spacer(1, 6))

    E.append(_section_header('Safety Performance Indicators Summary', S))
    E.append(Spacer(1, 4))

    if not indicators:
        E.append(Paragraph('No SPI indicators configured.', S['small']))
    else:
        rows = [[
            Paragraph('CODE',       S['field_label']),
            Paragraph('INDICATOR',  S['field_label']),
            Paragraph('CATEGORY',   S['field_label']),
            Paragraph('CALC TYPE',  S['field_label']),
            Paragraph('SPT TARGET', S['field_label']),
            Paragraph('L1 YELLOW',  S['field_label']),
            Paragraph('L2 ORANGE',  S['field_label']),
            Paragraph('L3 RED',     S['field_label']),
            Paragraph('LATEST',     S['field_label']),
            Paragraph('STATUS',     S['field_label']),
        ]]
        for ind in indicators:
            entries = data_by_spi.get(ind.id, [])
            latest = entries[-1].value if entries else None
            latest_str = f'{latest:.2f}' if latest is not None else '—'

            # Determine alert status
            if latest is not None:
                if ind.alert_l3 and latest >= ind.alert_l3:
                    alert = 'RED L3'
                    ac = C_RED
                elif ind.alert_l2 and latest >= ind.alert_l2:
                    alert = 'ORANGE L2'
                    ac = C_ORANGE
                elif ind.alert_l1 and latest >= ind.alert_l1:
                    alert = 'YELLOW L1'
                    ac = C_GOLD
                else:
                    alert = 'GREEN'
                    ac = C_GREEN
            else:
                alert = 'NO DATA'
                ac = C_GRAY

            rows.append([
                Paragraph(ind.code or '—', S['mono']),
                Paragraph((ind.name or '—')[:40], S['small']),
                Paragraph(ind.category or '—', S['small']),
                Paragraph(ind.calc_type or '—', S['small']),
                Paragraph(str(ind.spt_target or '—'), S['small']),
                Paragraph(str(ind.alert_l1 or '—'), S['small']),
                Paragraph(str(ind.alert_l2 or '—'), S['small']),
                Paragraph(str(ind.alert_l3 or '—'), S['small']),
                Paragraph(latest_str, S['small']),
                Paragraph(alert, ParagraphStyle('as', fontName='Helvetica-Bold',
                                                fontSize=7, textColor=ac)),
            ])

        col_w = [16*mm, 38*mm, 22*mm, 16*mm, 18*mm, 16*mm, 18*mm, 14*mm, 14*mm, 22*mm]
        spi_t = Table(rows, colWidths=col_w, repeatRows=1)
        spi_t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), C_NAVY),
            ('TEXTCOLOR',  (0, 0), (-1, 0), C_WHITE),
            ('FONTSIZE',   (0, 0), (-1, 0), 6.5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_WHITE, C_GRAY_LITE]),
            ('GRID',       (0, 0), (-1, -1), 0.3, C_BORDER),
            ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING',(0,0),(-1, -1), 3),
            ('LEFTPADDING',(0, 0), (-1, -1), 3),
            ('FONTSIZE',   (0, 1), (-1, -1), 7),
        ]))
        E.append(spi_t)

    E.append(Spacer(1, 8))
    E.append(Paragraph(
        'This SPI Summary Report is produced automatically from the AviaS '
        'Safety Management System. Data reflects the most recent monthly entries. '
        'Trend analysis and statistical monitoring are performed in accordance with '
        'ICAO Doc 9859 §10 and the approved SPI/SPT Framework.',
        S['small']))

    return _build_doc(E, 'SPI/SPT Summary', ref,
                      'INTERNAL — PERFORMANCE REPORT', generated_by, 'Current')
