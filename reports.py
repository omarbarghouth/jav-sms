# =============================================================================
#  AviaS — CORPORATE AVIATION DOCUMENT DESIGN SYSTEM v2.0
#  ICAO Annex 19 / IOSA ISM Compliant  |  Corporate Edition
#  Every document produced by AviaS meets airline executive presentation standards.
# =============================================================================
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

# ── Brand Palette ─────────────────────────────────────────────────────────────
C_NAVY      = HexColor('#0A1628')
C_NAVY2     = HexColor('#111F3A')
C_NAVY3     = HexColor('#1A2E4A')
C_GOLD      = HexColor('#C9A84C')
C_GOLD_LITE = HexColor('#F5E9C8')
C_RED       = HexColor('#DC2626')
C_RED_LITE  = HexColor('#FEE2E2')
C_GREEN     = HexColor('#15803D')
C_GREEN_LITE= HexColor('#DCFCE7')
C_BLUE      = HexColor('#1D4ED8')
C_BLUE_LITE = HexColor('#DBEAFE')
C_ORANGE    = HexColor('#D97706')
C_ORANGE_LT = HexColor('#FEF3C7')
C_GRAY      = HexColor('#6B7280')
C_GRAY_LITE = HexColor('#F8F9FC')
C_BORDER    = HexColor('#E5E7EB')
C_DIVIDER   = HexColor('#D1D5DB')
C_TEXT      = HexColor('#111827')
C_MUTED     = HexColor('#6B7280')
C_WHITE     = white

# ── Page Constants ─────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
MARGIN    = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN   # 174 mm on A4


# =============================================================================
#  TYPOGRAPHY SYSTEM
# =============================================================================
def _styles():
    return {
        # Document title (inside cover banner)
        'doc_title': ParagraphStyle('doc_title', fontName='Helvetica-Bold',
                                    fontSize=17, leading=22, textColor=C_WHITE,
                                    alignment=TA_LEFT),
        # Section-level heading (H2)
        'section_text': ParagraphStyle('section_text', fontName='Helvetica-Bold',
                                       fontSize=8.5, leading=11, textColor=C_NAVY),
        # Subsection heading (H3)
        'heading3': ParagraphStyle('heading3', fontName='Helvetica-Bold',
                                   fontSize=8, leading=11, textColor=C_NAVY3,
                                   spaceBefore=4, spaceAfter=2),
        # Standard body text
        'body': ParagraphStyle('body', fontName='Helvetica', fontSize=9,
                               leading=13, textColor=C_TEXT, alignment=TA_JUSTIFY,
                               spaceAfter=3),
        # Field label (uppercase, muted)
        'field_label': ParagraphStyle('field_label', fontName='Helvetica-Bold',
                                      fontSize=7, leading=10, textColor=C_MUTED),
        # Field value
        'field_value': ParagraphStyle('field_value', fontName='Helvetica',
                                      fontSize=8.5, leading=12, textColor=C_TEXT),
        # Table header cell
        'th': ParagraphStyle('th', fontName='Helvetica-Bold', fontSize=7.5,
                             leading=10, textColor=C_WHITE),
        # Table data cell
        'td': ParagraphStyle('td', fontName='Helvetica', fontSize=8,
                             leading=11, textColor=C_TEXT),
        # Small / caption
        'small': ParagraphStyle('small', fontName='Helvetica', fontSize=7.5,
                                leading=10, textColor=C_TEXT),
        'caption': ParagraphStyle('caption', fontName='Helvetica', fontSize=7,
                                  leading=9, textColor=C_MUTED),
        # Monospace (IDs, codes)
        'mono': ParagraphStyle('mono', fontName='Courier', fontSize=8,
                               leading=11, textColor=C_NAVY),
        # Cover banner subtitle label
        'cover_label': ParagraphStyle('cover_label', fontName='Helvetica',
                                      fontSize=7.5, leading=10,
                                      textColor=HexColor('#94A3B8')),
        'cover_value': ParagraphStyle('cover_value', fontName='Helvetica-Bold',
                                      fontSize=8.5, leading=11, textColor=C_WHITE),
        # Risk colours
        'risk_high':   ParagraphStyle('risk_high',   fontName='Helvetica-Bold',
                                      fontSize=8, textColor=C_RED),
        'risk_med':    ParagraphStyle('risk_med',    fontName='Helvetica-Bold',
                                      fontSize=8, textColor=C_ORANGE),
        'risk_low':    ParagraphStyle('risk_low',    fontName='Helvetica-Bold',
                                      fontSize=8, textColor=C_GREEN),
        # Centered
        'center': ParagraphStyle('center', fontName='Helvetica', fontSize=8,
                                 leading=11, textColor=C_TEXT, alignment=TA_CENTER),
        # Title for standalone pages
        'title': ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=16,
                                leading=20, textColor=C_NAVY),
        # Legacy aliases used in some call-sites
        'section':     ParagraphStyle('section',     fontName='Helvetica-Bold',
                                      fontSize=8.5, leading=11, textColor=C_NAVY),
        'heading2':    ParagraphStyle('heading2',    fontName='Helvetica-Bold',
                                      fontSize=9, leading=13, textColor=C_NAVY),
        'subtitle':    ParagraphStyle('subtitle',    fontName='Helvetica',
                                      fontSize=9, leading=12, textColor=C_GRAY),
        'badge_red':   ParagraphStyle('badge_red',   fontName='Helvetica-Bold',
                                      fontSize=8, textColor=C_RED),
        'badge_green': ParagraphStyle('badge_green', fontName='Helvetica-Bold',
                                      fontSize=8, textColor=C_GREEN),
        'badge_gold':  ParagraphStyle('badge_gold',  fontName='Helvetica-Bold',
                                      fontSize=8, textColor=C_GOLD),
        'badge_blue':  ParagraphStyle('badge_blue',  fontName='Helvetica-Bold',
                                      fontSize=8, textColor=C_BLUE),
        'badge_gray':  ParagraphStyle('badge_gray',  fontName='Helvetica-Bold',
                                      fontSize=8, textColor=C_GRAY),
        'watermark':   ParagraphStyle('watermark',   fontName='Helvetica-Bold',
                                      fontSize=42, textColor=HexColor('#e5e7eb'),
                                      alignment=TA_CENTER),
        'right':       ParagraphStyle('right',       fontName='Helvetica',
                                      fontSize=8, leading=11, textColor=C_TEXT,
                                      alignment=TA_RIGHT),
        'risk_intolerable': ParagraphStyle('risk_intolerable', fontName='Helvetica-Bold',
                                           fontSize=8, textColor=C_RED),
        'risk_tolerable':   ParagraphStyle('risk_tolerable',   fontName='Helvetica-Bold',
                                           fontSize=8, textColor=C_ORANGE),
        'risk_acceptable':  ParagraphStyle('risk_acceptable',  fontName='Helvetica-Bold',
                                           fontSize=8, textColor=C_GREEN),
    }


# =============================================================================
#  PAGE CANVAS  —  Header · Footer · Watermark
# =============================================================================
class _AviaHeader:
    """Canvas callback drawn on every page."""

    def __init__(self, doc_type, control_number, classification,
                 generated_by, report_status, total_pages=0, watermark=None):
        self.doc_type       = str(doc_type or 'Document')
        self.control_number = str(control_number or '—')
        self.classification = str(classification or 'INTERNAL').upper()
        self.generated_by   = str(generated_by or 'Safety Department')
        self.report_status  = str(report_status or '—')
        self.total_pages    = total_pages
        self.watermark      = watermark
        self.timestamp      = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

    def __call__(self, canvas, doc):
        canvas.saveState()
        w, h = A4
        pg   = doc.page
        pg_str = f'Page {pg} of {self.total_pages}' if self.total_pages else f'Page {pg}'

        # ── HEADER BAND (28 mm) ───────────────────────────────────────────────
        band_h = 28 * mm
        canvas.setFillColor(C_NAVY)
        canvas.rect(0, h - band_h, w, band_h, fill=1, stroke=0)

        # Gold accent line below header
        canvas.setFillColor(C_GOLD)
        canvas.rect(0, h - band_h - 1.2*mm, w, 1.2*mm, fill=1, stroke=0)

        # Left: AviaS wordmark
        canvas.setFillColor(C_WHITE)
        canvas.setFont('Helvetica-Bold', 13)
        canvas.drawString(MARGIN, h - 10*mm, 'AviaS')
        canvas.setFillColor(C_GOLD)
        canvas.setFont('Helvetica', 8)
        canvas.drawString(MARGIN, h - 16*mm, 'Safety Management System')
        canvas.setFillColor(HexColor('#64748B'))
        canvas.setFont('Helvetica', 6.5)
        canvas.drawString(MARGIN, h - 21.5*mm, 'ICAO Annex 19 Compliant')

        # Center: Document type
        canvas.setFillColor(C_WHITE)
        canvas.setFont('Helvetica-Bold', 11)
        canvas.drawCentredString(w/2, h - 10*mm, self.doc_type.upper())
        canvas.setFillColor(HexColor('#94A3B8'))
        canvas.setFont('Helvetica', 7)
        canvas.drawCentredString(w/2, h - 16*mm, 'CONTROLLED DOCUMENT')
        canvas.drawCentredString(w/2, h - 21.5*mm, self.report_status.upper())

        # Right: Control number + page
        canvas.setFillColor(C_WHITE)
        canvas.setFont('Helvetica-Bold', 8.5)
        canvas.drawRightString(w - MARGIN, h - 10*mm, self.control_number)
        canvas.setFillColor(HexColor('#94A3B8'))
        canvas.setFont('Helvetica', 7)
        canvas.drawRightString(w - MARGIN, h - 16*mm, pg_str)
        canvas.drawRightString(w - MARGIN, h - 21.5*mm, self.timestamp)

        # ── FOOTER BAND (13 mm) ───────────────────────────────────────────────
        canvas.setFillColor(C_NAVY)
        canvas.rect(0, 0, w, 13*mm, fill=1, stroke=0)
        canvas.setFillColor(C_GOLD)
        canvas.rect(0, 13*mm, w, 0.7*mm, fill=1, stroke=0)

        canvas.setFillColor(HexColor('#94A3B8'))
        canvas.setFont('Helvetica', 6.5)
        canvas.drawString(MARGIN, 8.5*mm,
                          f'Generated by: {self.generated_by}  ·  {self.timestamp}')
        canvas.drawString(MARGIN, 4.5*mm,
                          'AviaS Safety Management System  ·  Controlled Document  ·  '
                          'Unauthorised alteration is prohibited.')

        # Classification badge
        cls = self.classification
        cls_bg = (C_RED   if 'CONFIDENTIAL' in cls else
                  C_ORANGE if 'RESTRICTED'   in cls else
                  C_GREEN  if 'INTERNAL'     in cls else C_GRAY)
        bw = 52
        canvas.setFillColor(cls_bg)
        canvas.roundRect(w - MARGIN - bw, 4*mm, bw, 8*mm, 1.5, fill=1, stroke=0)
        canvas.setFillColor(C_WHITE)
        canvas.setFont('Helvetica-Bold', 6.5)
        canvas.drawCentredString(w - MARGIN - bw/2, 7.2*mm, cls)

        # ── WATERMARK ─────────────────────────────────────────────────────────
        if self.watermark:
            canvas.saveState()
            canvas.translate(w/2, h/2)
            canvas.rotate(45)
            canvas.setFillColor(HexColor('#E5E7EB'))
            canvas.setFont('Helvetica-Bold', 56)
            canvas.setFillAlpha(0.12)
            canvas.drawCentredString(0, 0, self.watermark.upper())
            canvas.restoreState()

        canvas.restoreState()


# =============================================================================
#  CORE PDF BUILDER  (2-pass for Page X of Y)
# =============================================================================
def _build_doc(flowables, doc_type, control_number, classification,
               generated_by, report_status, watermark=None):

    kw = dict(
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=32*mm, bottomMargin=19*mm,
        title=f'{doc_type} — {control_number}',
        author='AviaS Safety Management System',
        subject='ICAO Annex 19 Controlled Document',
        creator='AviaS SMS Corporate Edition v2.0',
    )

    # Pass 1 — count pages
    buf = BytesIO()
    hf  = _AviaHeader(doc_type, control_number, classification,
                      generated_by, report_status, total_pages=0, watermark=watermark)
    d   = SimpleDocTemplate(buf, **kw)
    d.build(flowables, onFirstPage=hf, onLaterPages=hf)
    total = d.page

    # Pass 2 — final render with correct page count
    buf = BytesIO()
    hf  = _AviaHeader(doc_type, control_number, classification,
                      generated_by, report_status, total_pages=total, watermark=watermark)
    d   = SimpleDocTemplate(buf, **kw)
    d.build(flowables, onFirstPage=hf, onLaterPages=hf)
    return buf.getvalue()


# =============================================================================
#  DESIGN HELPERS
# =============================================================================

def _hr(color=C_BORDER, thickness=0.5, spaceB=3, spaceA=3):
    return HRFlowable(width='100%', thickness=thickness, color=color,
                      spaceAfter=spaceA, spaceBefore=spaceB)


def _section_header(text, S, level=1):
    """Premium section header — gold left accent bar on light blue-gray background."""
    bg  = HexColor('#EEF1F8') if level == 1 else HexColor('#F4F6FB')
    fs  = 8.5 if level == 1 else 8
    lbl = Paragraph(text.upper(),
                    ParagraphStyle('_sh', fontName='Helvetica-Bold',
                                   fontSize=fs, leading=fs+3, textColor=C_NAVY))
    t = Table([[' ', lbl]], colWidths=[3.5*mm, CONTENT_W - 3.5*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (0, 0),   C_GOLD),
        ('BACKGROUND',    (1, 0), (1, 0),   bg),
        ('LEFTPADDING',   (0, 0), (0, 0),   0),
        ('RIGHTPADDING',  (0, 0), (0, 0),   0),
        ('LEFTPADDING',   (1, 0), (1, 0),   10),
        ('RIGHTPADDING',  (1, 0), (1, 0),   6),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return t


def _info_grid(pairs, S, cols=2):
    """Clean metadata grid — alternating rows, no heavy borders."""
    if not pairs:
        return Spacer(1, 2)
    col_w  = CONTENT_W / cols
    lbl_w  = col_w * 0.38
    val_w  = col_w * 0.62
    rows   = []
    step   = cols
    for i in range(0, len(pairs), step):
        row = []
        for j in range(step):
            if i + j < len(pairs):
                lbl, val = pairs[i + j]
                val_str  = str(val) if val is not None else '—'
                row += [Paragraph(str(lbl), S['field_label']),
                        Paragraph(val_str or '—', S['field_value'])]
            else:
                row += [Paragraph('', S['field_label']),
                        Paragraph('', S['field_value'])]
        rows.append(row)
    widths = [lbl_w, val_w] * cols
    t = Table(rows, colWidths=widths)
    t.setStyle(TableStyle([
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [C_GRAY_LITE, C_WHITE]),
        ('LEFTPADDING',    (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',   (0, 0), (-1, -1), 6),
        ('TOPPADDING',     (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 4),
        ('LINEBELOW',      (0, 0), (-1, -2), 0.25, C_BORDER),
        ('VALIGN',         (0, 0), (-1, -1), 'TOP'),
    ]))
    return t


def _text_block(label, text, S):
    """Labelled text block with gold left accent."""
    items = [Paragraph(label.upper(), S['field_label']), Spacer(1, 3)]
    if text and str(text).strip():
        items.append(Paragraph(str(text), S['body']))
    else:
        items.append(Paragraph('Not recorded.', S['caption']))
    data = [[items]]
    t = Table(data, colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), C_GRAY_LITE),
        ('LEFTPADDING',   (0, 0), (-1, -1), 10),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LINEBEFORE',    (0, 0), (0, -1),  2.5, C_GOLD),
    ]))
    return t


def _std_table(header_cells, data_rows, col_widths, S, stripe=True):
    """
    Premium standard table.
    header_cells: list of strings
    data_rows: list of lists of Paragraph (or strings auto-converted)
    col_widths: list of mm values, must sum to CONTENT_W
    """
    def _p(v, style):
        if isinstance(v, Paragraph):
            return v
        return Paragraph(str(v) if v is not None else '—', S[style])

    rows = [[_p(h, 'th') for h in header_cells]]
    for dr in data_rows:
        rows.append([_p(c, 'td') for c in dr])

    t = Table(rows, colWidths=col_widths, repeatRows=1)
    style = [
        # Header
        ('BACKGROUND',    (0, 0), (-1, 0),   C_NAVY),
        ('TEXTCOLOR',     (0, 0), (-1, 0),   C_WHITE),
        ('TOPPADDING',    (0, 0), (-1, 0),   5),
        ('BOTTOMPADDING', (0, 0), (-1, 0),   5),
        # Body
        ('TOPPADDING',    (0, 1), (-1, -1),  4),
        ('BOTTOMPADDING', (0, 1), (-1, -1),  4),
        ('LINEBELOW',     (0, 0), (-1, -1),  0.3, C_BORDER),
        ('VALIGN',        (0, 0), (-1, -1),  'TOP'),
        ('LEFTPADDING',   (0, 0), (-1, -1),  5),
        ('RIGHTPADDING',  (0, 0), (-1, -1),  5),
    ]
    if stripe:
        style.append(('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_WHITE, C_GRAY_LITE]))
    t.setStyle(TableStyle(style))
    return t


def _status_para(status, S):
    """Coloured status text paragraph."""
    s = (status or '').strip()
    up = s.upper()
    color = (C_GREEN  if up in ('CLOSED', 'APPROVED', 'COMPLETED', 'EFFECTIVE',
                                 'VERIFIED', 'IMPLEMENTED') else
             C_RED    if up in ('OVERDUE', 'REJECTED', 'FAILED', 'INTOLERABLE') else
             C_ORANGE if up in ('UNDER REVIEW', 'PENDING', 'DRAFT',
                                 'TOLERABLE', 'IN PROGRESS') else
             C_BLUE   if up in ('OPEN', 'ACTIVE', 'ASSIGNED') else C_GRAY)
    return Paragraph(s,
                     ParagraphStyle('_sp', fontName='Helvetica-Bold',
                                    fontSize=8, textColor=color))


def _signature_block(signatories, S):
    """
    Premium signature block.
    signatories: list of {'role': str, 'name': str, 'date': str}
    """
    n = len(signatories)
    if not n:
        return Spacer(1, 2)
    col_w = CONTENT_W / n
    cells = []
    for sig in signatories:
        cell = [
            Paragraph(sig.get('role', '').upper(), S['field_label']),
            Spacer(1, 14),
            Table([['']], colWidths=[col_w - 12*mm],
                  style=TableStyle([('LINEABOVE', (0,0), (-1,-1), 0.8, C_DIVIDER)])),
            Spacer(1, 3),
            Paragraph(sig.get('name', '') or '________________', S['field_value']),
            Paragraph(f"Date: {sig.get('date', '') or '____________'}", S['caption']),
        ]
        cells.append(cell)
    t = Table([cells], colWidths=[col_w] * n)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), C_GRAY_LITE),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('TOPPADDING',    (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LINEBEFORE',    (1, 0), (-1, -1), 0.5, C_BORDER),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
    ]))
    return t


def _timeline_table(events, S):
    """Premium activity timeline table."""
    if not events:
        return Paragraph('No activity recorded.', S['caption'])
    headers = ['DATE / TIME', 'EVENT', 'BY', 'NOTES']
    cw = [32*mm, 52*mm, 35*mm, CONTENT_W - 32*mm - 52*mm - 35*mm]
    rows = []
    for ev in events:
        rows.append([
            Paragraph(ev.get('date', '—'), S['mono']),
            Paragraph(ev.get('event', '—'), S['td']),
            Paragraph(ev.get('user', '—'), S['small']),
            Paragraph(ev.get('notes', '') or '—', S['small']),
        ])
    return _std_table(headers, rows, cw, S)


def _actions_table(action_dicts, S):
    """Standard corrective actions table."""
    if not action_dicts:
        return Paragraph('No corrective actions recorded.', S['caption'])
    headers = ['ACTION ID', 'DESCRIPTION', 'STATUS', 'ASSIGNED TO', 'DUE DATE']
    cw = [20*mm, 72*mm, 22*mm, 38*mm, CONTENT_W - 20*mm - 72*mm - 22*mm - 38*mm]
    rows = []
    for a in action_dicts:
        rows.append([
            Paragraph(str(a.get('id', '—')), S['mono']),
            Paragraph(a.get('description', '—') or '—', S['td']),
            _status_para(a.get('status', '—'), S),
            Paragraph(a.get('owner', '—') or '—', S['small']),
            Paragraph(a.get('due_date', '—') or '—', S['small']),
        ])
    return _std_table(headers, rows, cw, S)


def _cover_banner(title, ref, doc_type, status, dept, date_str,
                  classification, S):
    """
    Premium A4-width cover section — full navy card with gold accents.
    Used as the first flowable in every report.
    """
    # Status colour
    su = (status or '').upper()
    sc = (C_GREEN  if su in ('CLOSED', 'APPROVED', 'COMPLETED', 'IMPLEMENTED') else
          C_RED    if su in ('OVERDUE', 'REJECTED') else
          C_ORANGE if su in ('UNDER REVIEW', 'DRAFT', 'PENDING') else
          C_BLUE   if su in ('OPEN', 'ACTIVE') else C_GRAY)

    status_badge = Table(
        [[Paragraph(f'  {status or "—"}  ',
                    ParagraphStyle('_sb', fontName='Helvetica-Bold',
                                   fontSize=8, textColor=C_WHITE))]],
        colWidths=[28*mm])
    status_badge.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), sc),
        ('TOPPADDING',    (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING',   (0,0), (-1,-1), 4),
        ('RIGHTPADDING',  (0,0), (-1,-1), 4),
    ]))

    top_content = [
        Paragraph(doc_type.upper(),
                  ParagraphStyle('_dt', fontName='Helvetica', fontSize=8,
                                 textColor=C_GOLD, leading=11)),
        Spacer(1, 5),
        Paragraph(title or doc_type,
                  ParagraphStyle('_tt', fontName='Helvetica-Bold', fontSize=16,
                                 textColor=C_WHITE, leading=21)),
        Spacer(1, 8),
        _hr(C_GOLD, thickness=1, spaceB=0, spaceA=6),
        Table([[
            [Paragraph('REFERENCE', S['cover_label']),
             Paragraph(ref or '—', S['cover_value'])],
            [Paragraph('STATUS', S['cover_label']), status_badge],
            [Paragraph('DEPARTMENT', S['cover_label']),
             Paragraph(dept or '—', S['cover_value'])],
            [Paragraph('DATE', S['cover_label']),
             Paragraph(date_str or '—', S['cover_value'])],
            [Paragraph('CLASSIFICATION', S['cover_label']),
             Paragraph(classification, S['cover_value'])],
            [Paragraph('GENERATED', S['cover_label']),
             Paragraph(datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
                       S['cover_value'])],
        ]], colWidths=[CONTENT_W - 24*mm]),
    ]

    outer = Table([[top_content]], colWidths=[CONTENT_W])
    outer.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), C_NAVY),
        ('LEFTPADDING',   (0, 0), (-1, -1), 14),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 14),
        ('TOPPADDING',    (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
        ('LINEBELOW',     (0, 0), (-1, -1), 3.5, C_GOLD),
        ('LINEBEFORE',    (0, 0), (0,  -1), 4,   C_GOLD),
    ]))
    return outer


def _risk_matrix_cell(code, S):
    INTOLER = {'5A','5B','5C','4A','4B','3A'}
    TOLER   = {'4C','3B','3C','2A','2B','5D','4D'}
    if code in INTOLER:
        return Paragraph(code, S['risk_high'])
    if code in TOLER:
        return Paragraph(code, S['risk_med'])
    return Paragraph(code, S['risk_low'])


# =============================================================================
#  REPORT GENERATORS
# =============================================================================

# ── 1. HAZARD REPORT ─────────────────────────────────────────────────────────
def pdf_hazard_report(hr, hazard, actions, history, risks, investigation,
                      ra, generated_by='Safety Department'):
    S   = _styles()
    ref = hr.id if hr else '—'
    status = hr.status if hr else '—'
    title  = (hr.generic_hazard or hr.description or 'Hazard Report') if hr else 'Hazard Report'
    dept   = (hr.department.name if hr.department else '—') if hr else '—'
    E = []

    E.append(_cover_banner(title, ref, 'Hazard Report', status, dept,
                           hr.date if hr else '—',
                           'RESTRICTED — SAFETY SENSITIVE', S))
    E.append(Spacer(1, 10))

    E.append(_section_header('1. Report Information', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Report Reference',    ref),
        ('Report Type',         getattr(hr, 'report_type', 'Hazard Report') or 'Hazard Report'),
        ('Date of Occurrence',  hr.date if hr else '—'),
        ('Location',            getattr(hr, 'location', '—') or '—'),
        ('Classification',      getattr(hr, 'classification', '—') or '—'),
        ('Reporter',            getattr(hr, 'reporter', 'Anonymous') or 'Anonymous'),
        ('Reporter Severity',   getattr(hr, 'reporter_severity', '—') or '—'),
        ('Workflow Status',     status),
        ('Linked Hazard',       getattr(hr, 'hazard_id', '—') or '—'),
        ('Department',          dept),
    ], S, cols=2))
    E.append(Spacer(1, 8))

    E.append(_section_header('2. Hazard Description', S))
    E.append(Spacer(1, 4))
    for lbl, attr in [
        ('Generic Hazard / Event Title', 'generic_hazard'),
        ('Detailed Description',          'description'),
        ('Potential Consequences',         'consequences'),
        ('Immediate Action Taken',         'immediate_action'),
        ('Suggested Mitigation',           'suggested_mitigation'),
    ]:
        E.append(_text_block(lbl, getattr(hr, attr, '') if hr else '', S))
        E.append(Spacer(1, 4))
    E.append(Spacer(1, 4))

    if hazard:
        E.append(_section_header('3. Hazard Log Entry', S))
        E.append(Spacer(1, 4))
        E.append(_info_grid([
            ('Hazard ID',        hazard.id),
            ('Source',           hazard.source or '—'),
            ('Classification',   hazard.classification or '—'),
            ('Type of Activity', getattr(hazard, 'type_of_activity', '—') or '—'),
            ('Generic Hazard',   hazard.generic_hazard or '—'),
            ('Status',           hazard.status or '—'),
            ('Owner',            hazard.owner or '—'),
            ('Department',       hazard.department.name if hazard.department else '—'),
        ], S, cols=2))
        E.append(Spacer(1, 4))
        E.append(_text_block('Specific Components', getattr(hazard, 'specific_components', ''), S))
        E.append(Spacer(1, 8))

    if risks:
        E.append(_section_header('4. Risk Assessment', S))
        E.append(Spacer(1, 4))
        cw = [22*mm, CONTENT_W-22*mm-30*mm-30*mm-30*mm, 30*mm, 30*mm, 30*mm]
        rows = [[
            Paragraph(getattr(r, 'id', '—') or '—', S['mono']),
            Paragraph(getattr(r, 'description', '—') or '—', S['td']),
            Paragraph(str(getattr(r, 'initial_risk_index', '—') or '—'), S['td']),
            Paragraph(str(getattr(r, 'residual_risk_index', '—') or '—'), S['td']),
            Paragraph(getattr(r, 'residual_tolerance', '—') or '—', S['td']),
        ] for r in risks]
        E.append(_std_table(['RISK ID','DESCRIPTION','INIT RISK','RES RISK','TOLERANCE'],
                            rows, cw, S))
        E.append(Spacer(1, 8))

    if investigation:
        E.append(_section_header('5. Investigation Summary', S))
        E.append(Spacer(1, 4))
        E.append(_info_grid([
            ('Investigation ID',    investigation.id),
            ('Investigator',        getattr(investigation, 'investigator', '—') or '—'),
            ('Date of Occurrence',  getattr(investigation, 'date_of_occurrence', '—') or '—'),
            ('Status',              investigation.status or '—'),
        ], S, cols=2))
        E.append(Spacer(1, 4))
        E.append(_text_block('Description',   getattr(investigation, 'description', ''), S))
        E.append(Spacer(1, 4))
        E.append(_text_block('Root Cause',    getattr(investigation, 'root_cause', ''), S))
        E.append(Spacer(1, 8))

    E.append(_section_header('6. Corrective Actions', S))
    E.append(Spacer(1, 4))
    E.append(_actions_table([{
        'id': a.id, 'description': a.description,
        'owner': a.owner, 'due_date': a.due_date, 'status': a.status,
    } for a in (actions or [])], S))
    E.append(Spacer(1, 8))

    E.append(_section_header('7. Audit Trail', S))
    E.append(Spacer(1, 4))
    E.append(_timeline_table([{
        'date':  h.changed_at.strftime('%Y-%m-%d %H:%M') if h.changed_at else '—',
        'event': f'{h.from_status or "—"} → {h.to_status or "—"}',
        'user':  h.changed_by or '—', 'notes': h.notes or '',
    } for h in (history or [])], S))
    E.append(Spacer(1, 8))

    E.append(_section_header('8. Signatures & Authorisation', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Reporter',        'name': getattr(hr, 'reporter', '') if hr else '', 'date': hr.date if hr else ''},
        {'role': 'Safety Officer',  'name': '', 'date': ''},
        {'role': 'Safety Manager',  'name': '', 'date': ''},
        {'role': 'Accountable Mgr', 'name': '', 'date': ''},
    ], S))

    return _build_doc(E, 'Hazard Report', ref,
                      'RESTRICTED — SAFETY SENSITIVE', generated_by, status)


# ── 2. AIR SAFETY REPORT ─────────────────────────────────────────────────────
def pdf_asr_report(asr, hazard, hr, actions, generated_by='Safety Department'):
    S      = _styles()
    ref    = asr.id if asr else '—'
    status = 'Submitted'
    title  = (getattr(asr, 'occurrence_type', None) or 'Air Safety Report') if asr else 'Air Safety Report'
    E = []

    E.append(_cover_banner(title, ref, 'Air Safety Report (ASR)', status,
                           'Flight Operations', asr.date if asr else '—',
                           'RESTRICTED — SAFETY SENSITIVE', S))
    E.append(Spacer(1, 10))

    E.append(_section_header('1. Occurrence Information', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('ASR Reference',       ref),
        ('Occurrence Type',     getattr(asr, 'occurrence_type', '—') or '—'),
        ('Date',                getattr(asr, 'date', '—') or '—'),
        ('Time (UTC)',          getattr(asr, 'time_utc', '—') or '—'),
        ('Phase of Flight',     getattr(asr, 'phase_of_flight', '—') or '—'),
        ('Aircraft Reg.',       getattr(asr, 'aircraft_registration', '—') or '—'),
        ('Aircraft Type',       getattr(asr, 'aircraft_type', '—') or '—'),
        ('Route',               getattr(asr, 'route', '—') or '—'),
        ('Captain',             getattr(asr, 'captain_name', '—') or '—'),
        ('Reporter',            getattr(asr, 'reporter_name', '—') or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 8))

    E.append(_section_header('2. Description of Occurrence', S))
    E.append(Spacer(1, 4))
    for lbl, attr in [
        ('Description',              'description'),
        ('Hazard / Safety Issue',     'hazard_description'),
        ('Immediate Actions Taken',   'immediate_action'),
        ('Suggested Prevention',      'suggested_prevention'),
    ]:
        E.append(_text_block(lbl, getattr(asr, attr, '') if asr else '', S))
        E.append(Spacer(1, 4))
    E.append(Spacer(1, 4))

    if hazard:
        E.append(_section_header('3. Linked Hazard Record', S))
        E.append(Spacer(1, 4))
        E.append(_info_grid([
            ('Hazard ID',   hazard.id),
            ('Status',      hazard.status or '—'),
            ('Owner',       hazard.owner or '—'),
            ('Department',  hazard.department.name if hazard.department else '—'),
        ], S, cols=2))
        E.append(Spacer(1, 8))

    E.append(_section_header('4. Corrective Actions', S))
    E.append(Spacer(1, 4))
    E.append(_actions_table([{
        'id': a.id, 'description': a.description,
        'owner': a.owner, 'due_date': a.due_date, 'status': a.status,
    } for a in (actions or [])], S))
    E.append(Spacer(1, 8))

    E.append(_section_header('5. Signatures & Authorisation', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Reporting Crew',  'name': getattr(asr, 'reporter_name', '') if asr else '', 'date': getattr(asr, 'date', '') if asr else ''},
        {'role': 'Safety Officer',  'name': '', 'date': ''},
        {'role': 'Safety Manager',  'name': '', 'date': ''},
        {'role': 'Accountable Mgr', 'name': '', 'date': ''},
    ], S))

    return _build_doc(E, 'Air Safety Report', ref,
                      'RESTRICTED — SAFETY SENSITIVE', generated_by, status)


# ── 3. INVESTIGATION ─────────────────────────────────────────────────────────
def pdf_investigation(inv, hazard, actions, generated_by='Safety Department'):
    S      = _styles()
    ref    = inv.id if inv else '—'
    status = inv.status if inv else '—'
    title  = (inv.title or 'Safety Investigation') if inv else 'Safety Investigation'
    dept   = (inv.department.name if inv.department else '—') if inv else '—'
    E = []

    E.append(_cover_banner(title, ref, 'Safety Investigation Report', status, dept,
                           getattr(inv, 'date_of_occurrence', '—') if inv else '—',
                           'RESTRICTED — SAFETY SENSITIVE', S))
    E.append(Spacer(1, 10))

    E.append(_section_header('1. Investigation Overview', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Investigation Ref.',   ref),
        ('Classification',       getattr(inv, 'classification', '—') or '—'),
        ('Date of Occurrence',   getattr(inv, 'date_of_occurrence', '—') or '—'),
        ('Date Opened',          getattr(inv, 'date_opened', '—') or '—'),
        ('Date Closed',          getattr(inv, 'date_closed', '—') or '—'),
        ('Lead Investigator',    getattr(inv, 'investigator', '—') or '—'),
        ('Department',           dept),
        ('Status',               status),
        ('Linked Hazard',        getattr(inv, 'hazard_id', '—') or '—'),
        ('Linked Report',        getattr(inv, 'linked_report_id', '—') or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 8))

    E.append(_section_header('2. Investigation Narrative', S))
    E.append(Spacer(1, 4))
    for lbl, attr in [
        ('Description',          'description'),
        ('Contributing Factors', 'contributing_factors'),
        ('Root Cause Analysis',  'root_cause'),
        ('Recommendations',      'recommendations'),
    ]:
        E.append(_text_block(lbl, getattr(inv, attr, '') if inv else '', S))
        E.append(Spacer(1, 4))

    # 5-Whys
    whys = [(f'Why {i}', getattr(inv, f'why{i}', None))
            for i in range(1, 6) if getattr(inv, f'why{i}', None)]
    if whys:
        E.append(_section_header('3. Five-Whys Root Cause Analysis', S))
        E.append(Spacer(1, 4))
        for label, val in whys:
            E.append(_text_block(label, val, S))
            E.append(Spacer(1, 3))
        E.append(Spacer(1, 4))

    E.append(_section_header('4. Corrective & Preventive Actions', S))
    E.append(Spacer(1, 4))
    E.append(_actions_table([{
        'id': a.id, 'description': a.description,
        'owner': a.owner, 'due_date': a.due_date, 'status': a.status,
    } for a in (actions or [])], S))
    E.append(Spacer(1, 8))

    E.append(_section_header('5. Signatures & Authorisation', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Lead Investigator', 'name': getattr(inv, 'investigator', '') if inv else '', 'date': getattr(inv, 'date_closed', '') if inv else ''},
        {'role': 'Safety Manager',    'name': '', 'date': ''},
        {'role': 'Accountable Mgr',   'name': '', 'date': ''},
        {'role': 'Reviewed By',       'name': '', 'date': ''},
    ], S))

    return _build_doc(E, 'Safety Investigation', ref,
                      'RESTRICTED — SAFETY SENSITIVE', generated_by, status)


# ── 4. RISK ASSESSMENT ───────────────────────────────────────────────────────
def pdf_risk_assessment(ra, hazard, rows, mitigations, reviews,
                        generated_by='Safety Department'):
    S   = _styles()
    ref = ra.control_number or ra.id if ra else '—'
    status = ra.status if ra else '—'
    title  = ra.title or 'Risk Assessment' if ra else 'Risk Assessment'
    dept   = ra.department.name if ra and ra.department else '—'
    rev    = f'REV{ra.revision}' if ra and ra.revision else 'REV0'
    E = []

    E.append(_cover_banner(title, ref, f'Risk Assessment — {rev}', status, dept,
                           ra.assessment_date if ra else '—',
                           'RESTRICTED — SAFETY SENSITIVE', S))
    E.append(Spacer(1, 10))

    E.append(_section_header('1. Administration', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Control Number',      ref),
        ('Revision',            rev),
        ('Assessment Date',     ra.assessment_date or '—' if ra else '—'),
        ('Next Review Date',    ra.next_review_date or '—' if ra else '—'),
        ('Responsible',         ra.responsible_name or '—' if ra else '—'),
        ('Assessors',           ra.assessors_names or '—' if ra else '—'),
        ('Status',              status),
        ('Management Accept.',  ra.management_acceptance or 'Pending' if ra else '—'),
        ('Acceptance Date',     ra.acceptance_date or '—' if ra else '—'),
        ('Linked Hazard',       ra.hazard_id or '—' if ra else '—'),
    ], S, cols=2))
    E.append(Spacer(1, 8))

    E.append(_section_header('2. General Information', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Risk Level Before Controls', ra.risk_level_prior or '—' if ra else '—'),
        ('Risk Level After Controls',  ra.risk_level_after or '—' if ra else '—'),
    ], S, cols=2))
    E.append(Spacer(1, 4))
    E.append(_text_block('General Description',          ra.general_description if ra else '', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Reasons for Risk Assessment',  ra.reasons if ra else '', S))
    E.append(Spacer(1, 8))

    if rows:
        E.append(_section_header('3. Risk Table', S))
        E.append(Spacer(1, 4))
        cw = [8*mm, 26*mm, 26*mm, 34*mm, 14*mm, 34*mm, 14*mm,
              CONTENT_W - 8*mm - 26*mm - 26*mm - 34*mm - 14*mm - 34*mm - 14*mm]
        tbl_rows = []
        for row in rows:
            tbl_rows.append([
                Paragraph(str(row.seq_num or ''), S['mono']),
                Paragraph(row.type_of_activity or '—', S['td']),
                Paragraph(row.generic_hazard or '—', S['td']),
                Paragraph(row.consequences or '—', S['td']),
                _risk_matrix_cell(row.risk_index_initial or '—', S),
                Paragraph(row.current_defenses or '—', S['td']),
                _risk_matrix_cell(row.risk_index_residual or '—', S),
                Paragraph(row.risk_tolerance_residual or '—', S['td']),
            ])
        E.append(_std_table(
            ['#','ACTIVITY','HAZARD','CONSEQUENCE','INIT','CONTROLS','RES','TOL'],
            tbl_rows, cw, S))
        E.append(Spacer(1, 8))

    if mitigations:
        E.append(_section_header('4. Mitigation Responsibilities', S))
        E.append(Spacer(1, 4))
        cw = [12*mm, CONTENT_W-12*mm-45*mm-22*mm-25*mm, 45*mm, 22*mm, 25*mm]
        tbl_rows = [[
            Paragraph(str(m.hazard_seq or '—'), S['mono']),
            Paragraph(m.mitigation or '—', S['td']),
            Paragraph(m.responsible_manager or '—', S['td']),
            Paragraph(m.due_date or '—', S['td']),
            _status_para(m.status or '—', S),
        ] for m in mitigations]
        E.append(_std_table(['SEQ','MITIGATION','RESPONSIBLE MANAGER','DUE DATE','STATUS'],
                            tbl_rows, cw, S))
        E.append(Spacer(1, 8))

    if reviews:
        E.append(_section_header('5. Effectiveness Reviews', S))
        E.append(Spacer(1, 4))
        cw = [40*mm, CONTENT_W-40*mm-30*mm-22*mm-30*mm, 30*mm, 22*mm, 30*mm]
        tbl_rows = [[
            Paragraph(rv.risk_mitigation or '—', S['td']),
            Paragraph(rv.review_of_effectiveness or '—', S['td']),
            Paragraph(rv.effectiveness_rating or '—', S['td']),
            Paragraph(rv.date_completed or '—', S['td']),
            Paragraph(rv.actioner or '—', S['td']),
        ] for rv in reviews]
        E.append(_std_table(['MITIGATION','EFFECTIVENESS REVIEW','RATING','DATE','ACTIONER'],
                            tbl_rows, cw, S))
        E.append(Spacer(1, 8))

    E.append(_section_header('6. Signatures & Authorisation', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Prepared By',     'name': ra.prepared_by_name or '' if ra else '',  'date': ra.assessment_date or '' if ra else ''},
        {'role': 'Reviewed By',     'name': ra.reviewed_by_name or '' if ra else '',  'date': ''},
        {'role': 'Approved By',     'name': ra.approved_by_name or '' if ra else '',  'date': ''},
        {'role': 'Accountable Mgr', 'name': '', 'date': ''},
    ], S))

    return _build_doc(E, f'Risk Assessment {rev}', ref,
                      'RESTRICTED — SAFETY SENSITIVE', generated_by, status)


# ── 5. ACTION / CORRECTIVE ACTION ────────────────────────────────────────────
def pdf_action(action, history, generated_by='Safety Department'):
    S      = _styles()
    ref    = action.id if action else '—'
    status = action.status if action else '—'
    title  = (action.description or 'Action Record') if action else 'Action Record'
    E = []

    E.append(_cover_banner(title[:120], ref, 'Corrective / Preventive Action Record',
                           status, '—',
                           action.created_at.strftime('%Y-%m-%d') if action and action.created_at else '—',
                           'INTERNAL — SAFETY RECORD', S))
    E.append(Spacer(1, 10))

    E.append(_section_header('1. Action Details', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Action Reference',    ref),
        ('Action Type',         getattr(action, 'action_type', 'Corrective') or 'Corrective'),
        ('Source',              getattr(action, 'source', '—') or '—'),
        ('Linked Hazard',       getattr(action, 'hazard_id', '—') or '—'),
        ('Owner',               getattr(action, 'owner', '—') or '—'),
        ('Assigned By',         getattr(action, 'assigned_by', '—') or '—'),
        ('Priority',            getattr(action, 'priority', '—') or '—'),
        ('Status',              status),
        ('Due Date',            getattr(action, 'due_date', '—') or '—'),
        ('Closed Date',         getattr(action, 'closed_date', '—') or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 8))

    E.append(_section_header('2. Description & Root Cause', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Action Description',    getattr(action, 'description', '') if action else '', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Root Cause',            getattr(action, 'root_cause', '') if action else '', S))
    E.append(Spacer(1, 8))

    E.append(_section_header('3. Implementation', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Mitigation Description',   getattr(action, 'mitigation_description', '') if action else '', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Corrective Action Details', getattr(action, 'corrective_description', '') if action else '', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Evidence',                 getattr(action, 'evidence', '') if action else '', S))
    E.append(Spacer(1, 8))

    E.append(_section_header('4. Safety Review', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Reviewed By',          getattr(action, 'safety_reviewer', '—') or '—'),
        ('Review Date',          getattr(action, 'safety_review_date', '—') or '—'),
        ('Effectiveness',        getattr(action, 'effectiveness', '—') or '—'),
        ('Verified By',          getattr(action, 'verified_by', '—') or '—'),
        ('Verified Date',        getattr(action, 'verified_date', '—') or '—'),
        ('Implementation Date',  getattr(action, 'implementation_date', '—') or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 4))
    E.append(_text_block('Safety Notes',        getattr(action, 'safety_notes', '') if action else '', S))
    E.append(Spacer(1, 4))
    E.append(_text_block('Follow-Up Notes',     getattr(action, 'follow_up_notes', '') if action else '', S))
    E.append(Spacer(1, 8))

    E.append(_section_header('5. Audit Trail', S))
    E.append(Spacer(1, 4))
    E.append(_timeline_table([{
        'date':  h.changed_at.strftime('%Y-%m-%d %H:%M') if h.changed_at else '—',
        'event': f'{h.from_status or "—"} → {h.to_status or "—"}',
        'user':  h.changed_by or '—', 'notes': h.notes or '',
    } for h in (history or [])], S))
    E.append(Spacer(1, 8))

    E.append(_section_header('6. Signatures & Authorisation', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Action Owner',    'name': getattr(action, 'owner', '') if action else '',           'date': getattr(action, 'closed_date', '') if action else ''},
        {'role': 'Safety Reviewer', 'name': getattr(action, 'safety_reviewer', '') if action else '', 'date': getattr(action, 'safety_review_date', '') if action else ''},
        {'role': 'Verified By',     'name': getattr(action, 'verified_by', '') if action else '',     'date': getattr(action, 'verified_date', '') if action else ''},
        {'role': 'Accountable Mgr', 'name': '', 'date': ''},
    ], S))

    return _build_doc(E, 'Corrective / Preventive Action', ref,
                      'INTERNAL — SAFETY RECORD', generated_by, status)


# ── 6. MANAGEMENT OF CHANGE ──────────────────────────────────────────────────
def pdf_moc(moc, generated_by='Safety Department',
            milestones=None, stakeholders=None, updates=None,
            actions=None, linked_ra=None, investigations=None, avis=None):
    S      = _styles()
    mid    = moc.id if moc else '—'
    status = moc.status if moc else '—'
    title  = moc.title or 'Management of Change' if moc else 'Management of Change'
    dept   = moc.department.name if moc and moc.department else '—'
    E = []

    # Cover
    E.append(_cover_banner(title, mid, 'Management of Change', status, dept,
                           moc.date_raised if moc else '—',
                           'INTERNAL — CONTROLLED CHANGE', S))
    E.append(Spacer(1, 10))

    # ── 1. Change Identification ─────────────────────────────────────────────
    E.append(_section_header('1. Change Identification', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('MOC Reference',     mid),
        ('MOC Number',        mid),
        ('Change Category',   getattr(moc, 'change_category', '—') or '—'),
        ('Department',        dept),
        ('Initiator',         getattr(moc, 'initiator', '—') or '—'),
        ('Date Raised',       getattr(moc, 'date_raised', '—') or '—'),
        ('Target Completion', getattr(moc, 'target_completion_date', '—') or '—'),
        ('Lifecycle Status',  status),
        ('Approval Status',   getattr(moc, 'approval_status', '—') or '—'),
        ('Approved By',       getattr(moc, 'approved_by', '—') or '—'),
        ('Approved Date',     getattr(moc, 'approved_date', '—') or '—'),
        ('Implemented Date',  getattr(moc, 'implemented_date', '—') or '—'),
        ('Closed Date',       getattr(moc, 'closed_date', '—') or '—'),
        ('Linked Hazard',     getattr(moc, 'linked_hazard_id', '—') or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 8))

    # ── 2. Change Description ────────────────────────────────────────────────
    E.append(_section_header('2. Change Description', S))
    E.append(Spacer(1, 4))
    for lbl, attr in [
        ('Current Situation',           'current_situation'),
        ('Proposed Change / Description','description'),
        ('Reason for Change',           'reason_for_change'),
        ('Expected Benefits',           'expected_benefits'),
    ]:
        E.append(_text_block(lbl, getattr(moc, attr, '') if moc else '', S))
        E.append(Spacer(1, 4))
    E.append(Spacer(1, 4))

    # ── 3. Impact Assessment ─────────────────────────────────────────────────
    E.append(_section_header('3. Impact Assessment', S))
    E.append(Spacer(1, 4))
    yes_no = lambda a: 'YES' if getattr(moc, a, False) else 'No'
    E.append(_info_grid([
        ('Aircraft Operations',  yes_no('impact_aircraft_ops')),
        ('Flight Crew',          yes_no('impact_flight_crew')),
        ('Cabin Crew',           yes_no('impact_cabin_crew')),
        ('Ground Operations',    yes_no('impact_ground_ops')),
        ('Maintenance',          yes_no('impact_maintenance')),
        ('Operations Control',   yes_no('impact_ops_control')),
        ('Training',             yes_no('impact_training')),
        ('Safety Reporting',     yes_no('impact_safety_reporting')),
        ('Emergency Response',   yes_no('impact_emergency')),
        ('Security',             yes_no('impact_security')),
        ('Regulatory',           yes_no('impact_regulatory')),
        ('Contractors',          yes_no('impact_contractors')),
        ('Safety Impact Level',  getattr(moc, 'safety_impact_level', '—') or '—'),
        ('RA Required',          'Yes' if getattr(moc, 'ra_required', False) else 'No'),
        ('Training Required',    'Yes' if getattr(moc, 'training_required', False) else 'No'),
        ('Documentation Update', 'Yes' if getattr(moc, 'documentation_update', False) else 'No'),
        ('SOP Revision',         'Yes' if getattr(moc, 'sop_revision', False) else 'No'),
        ('ERP Update Required',  'Yes' if getattr(moc, 'erp_update', False) else 'No'),
    ], S, cols=2))
    E.append(Spacer(1, 8))

    # ── 4. Regulatory Compliance ─────────────────────────────────────────────
    E.append(_section_header('4. Regulatory Compliance', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('ICAO Impact',             'Yes' if getattr(moc, 'icao_impact', False) else 'No'),
        ('IOSA Impact',             'Yes' if getattr(moc, 'iosa_impact', False) else 'No'),
        ('EASA Impact',             'Yes' if getattr(moc, 'easa_impact', False) else 'No'),
        ('National Authority',      'Yes' if getattr(moc, 'national_authority_impact', False) else 'No'),
        ('Company Manual Impact',   'Yes' if getattr(moc, 'company_manual_impact', False) else 'No'),
        ('Regulatory Approval Req.','Yes' if getattr(moc, 'regulatory_approval_required', False) else 'No'),
        ('Reg. Approval Ref.',      getattr(moc, 'regulatory_approval_ref', 'N/A') or 'N/A'),
        ('Reg. Approval Date',      getattr(moc, 'regulatory_approval_date', '—') or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 8))

    # ── 5. Approval Chain ────────────────────────────────────────────────────
    E.append(_section_header('5. Approval Chain', S))
    E.append(Spacer(1, 4))
    chain_rows = []
    for step, (role, appr_attr, date_attr, notes_attr) in enumerate([
        ('1. Department Manager', 'dept_manager_approver', 'dept_manager_date', 'dept_manager_notes'),
        ('2. Safety Review',      'safety_reviewer',       'safety_review_date', 'safety_review_notes'),
        ('3. Safety Manager',     'safety_manager_approver','safety_manager_date','safety_manager_notes'),
        ('4. Accountable Executive','ae_approver',          'ae_date',            'ae_notes'),
    ], 1):
        approver  = getattr(moc, appr_attr, '—') or '—'
        decision  = 'Approved' if approver and approver != '—' else 'Pending'
        date_val  = getattr(moc, date_attr, '—') or '—'
        notes_val = getattr(moc, notes_attr, '—') or '—'
        chain_rows.append([
            Paragraph(role, S['td']),
            Paragraph(approver, S['td']),
            _status_para(decision, S),
            Paragraph(date_val, S['td']),
            Paragraph(notes_val, S['small']),
        ])
    cw = [40*mm, 38*mm, 22*mm, 24*mm, CONTENT_W-40*mm-38*mm-22*mm-24*mm]
    E.append(_std_table(['STEP','APPROVER','DECISION','DATE','COMMENTS'],
                        chain_rows, cw, S))
    E.append(Spacer(1, 8))

    # ── 6. Safety Risk Assessment ─────────────────────────────────────────────
    E.append(_section_header('6. Safety Risk Assessment', S))
    E.append(Spacer(1, 4))
    ra_req = getattr(moc, 'ra_required', False)
    if linked_ra:
        E.append(_info_grid([
            ('RA Required',       'Yes'),
            ('RA Status',         getattr(moc, 'linked_ra_status', linked_ra.status or '—')),
            ('Linked RA Ref',     linked_ra.id),
            ('RA Control Number', linked_ra.control_number or '—'),
            ('RA Title',          linked_ra.title or '—'),
            ('RA Status',         linked_ra.status or '—'),
            ('Responsible',       linked_ra.responsible_name or '—'),
            ('Assessment Date',   linked_ra.assessment_date or '—'),
            ('Next Review Date',  linked_ra.next_review_date or '—'),
        ], S, cols=2))
        E.append(Spacer(1, 6))
        # RA Rows table
        if hasattr(linked_ra, 'rows') and linked_ra.rows:
            E.append(Spacer(1, 4))
            cw = [10*mm, 36*mm, 36*mm, 16*mm, 16*mm,
                  CONTENT_W - 10*mm - 36*mm - 36*mm - 16*mm - 16*mm]
            tbl_rows = []
            for row in linked_ra.rows:
                tbl_rows.append([
                    Paragraph(str(row.seq_num or '—'), S['mono']),
                    Paragraph(row.generic_hazard or row.type_of_activity or '—', S['td']),
                    Paragraph(row.consequences or '—', S['td']),
                    _risk_matrix_cell(row.risk_index_initial or '—', S),
                    _risk_matrix_cell(row.risk_index_residual or '—', S),
                    Paragraph(row.further_mitigations or row.current_defenses or '—', S['td']),
                ])
            E.append(_std_table(
                ['SEQ','HAZARD / ACTIVITY','CONSEQUENCES','INITIAL RISK','RESIDUAL RISK','FURTHER MITIGATIONS'],
                tbl_rows, cw, S))
            E.append(Spacer(1, 6))
        # RA Mitigations
        if hasattr(linked_ra, 'mitigations') and linked_ra.mitigations:
            cw = [18*mm, CONTENT_W-18*mm-40*mm-22*mm-20*mm, 40*mm, 22*mm, 20*mm]
            tbl_rows = [[
                Paragraph(mit.hazard_seq or '—', S['mono']),
                Paragraph(mit.mitigation or '—', S['td']),
                Paragraph(mit.responsible_manager or '—', S['td']),
                Paragraph(mit.due_date or '—', S['td']),
                _status_para(mit.status or '—', S),
            ] for mit in linked_ra.mitigations]
            E.append(_std_table(['HAZARD REF','MITIGATION','RESPONSIBLE','DUE DATE','STATUS'],
                                tbl_rows, cw, S))
    else:
        E.append(_info_grid([
            ('RA Required', 'Yes' if ra_req else 'No'),
            ('RA Status',   getattr(moc, 'linked_ra_status', '—') or '—'),
        ], S, cols=2))
        E.append(Spacer(1, 4))
        if not ra_req:
            E.append(Paragraph('Risk Assessment not required for this change.', S['caption']))
        else:
            E.append(Paragraph('No linked Risk Assessment found.', S['caption']))
    E.append(Spacer(1, 8))

    # ── 7. Stakeholder Consultation ──────────────────────────────────────────
    E.append(_section_header('7. Stakeholder Consultation', S))
    E.append(Spacer(1, 4))
    if getattr(moc, 'stakeholder_summary', None):
        E.append(_text_block('Consultation Summary', moc.stakeholder_summary, S))
        E.append(Spacer(1, 4))
    if stakeholders:
        cw = [45*mm, 40*mm, 22*mm, CONTENT_W-45*mm-40*mm-22*mm]
        tbl_rows = [[
            Paragraph(getattr(sk, 'contact_name', None) or getattr(sk, 'name', '—') or '—', S['td']),
            Paragraph(getattr(sk, 'department_name', None) or getattr(sk, 'department', '—') or '—', S['td']),
            Paragraph(getattr(sk, 'consultation_date', None) or getattr(sk, 'consulted_date', '—') or '—', S['td']),
            Paragraph(getattr(sk, 'comments', None) or getattr(sk, 'feedback', '—') or '—', S['small']),
        ] for sk in stakeholders]
        E.append(_std_table(['CONTACT NAME','DEPARTMENT','DATE','COMMENTS'], tbl_rows, cw, S))
    else:
        E.append(Paragraph('No individual stakeholder records. See summary above.', S['caption']))
    E.append(Spacer(1, 8))

    # ── 8. Implementation Planning & Milestones ───────────────────────────────
    E.append(PageBreak())
    E.append(_section_header('8. Implementation Planning & Milestones', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Implementation Start',  getattr(moc, 'implementation_start_date', '—') or '—'),
        ('Target Completion',     getattr(moc, 'target_completion_date', '—') or '—'),
        ('Implementation Status', getattr(moc, 'implementation_status', '—') or '—'),
        ('Implemented Date',      getattr(moc, 'implemented_date', '—') or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 4))
    if milestones:
        cw = [50*mm, 30*mm, 20*mm, 18*mm, 20*mm,
              CONTENT_W-50*mm-30*mm-20*mm-18*mm-20*mm]
        tbl_rows = [[
            Paragraph(ms.description or '—', S['td']),
            Paragraph(ms.responsible_person or '—', S['td']),
            Paragraph(ms.target_date or '—', S['td']),
            _status_para(ms.status or '—', S),
            Paragraph(ms.completed_date or '—', S['td']),
            Paragraph(ms.notes or '—', S['small']),
        ] for ms in milestones]
        E.append(_std_table(['MILESTONE','RESPONSIBLE','TARGET','STATUS','COMPLETED','NOTES'],
                            tbl_rows, cw, S))
        done = sum(1 for m in milestones if m.status == 'Complete')
        E.append(Spacer(1, 4))
        E.append(Paragraph(f'Milestones: {done} of {len(milestones)} complete.',
                           S['caption']))
    else:
        E.append(Paragraph('No milestones recorded.', S['caption']))
    E.append(Spacer(1, 8))

    # ── 9. Actions Taken ─────────────────────────────────────────────────────
    E.append(_section_header('9. Actions Taken (Corrective & Preventive)', S))
    E.append(Spacer(1, 4))
    if actions:
        cw = [20*mm, 72*mm, 22*mm, 30*mm, 18*mm,
              CONTENT_W-20*mm-72*mm-22*mm-30*mm-18*mm]
        tbl_rows = [[
            Paragraph(str(a.id), S['mono']),
            Paragraph(a.description or '—', S['td']),
            _status_para(a.status or '—', S),
            Paragraph(getattr(a, 'sag_member', None) or a.owner or '—', S['td']),
            Paragraph(a.due_date or '—', S['td']),
            Paragraph(a.closed_date or '—', S['td']),
        ] for a in actions]
        E.append(_std_table(['ACTION ID','DESCRIPTION','STATUS','ASSIGNED TO','DUE','CLOSED'],
                            tbl_rows, cw, S))
        closed = sum(1 for a in actions if a.status == 'Closed')
        E.append(Spacer(1, 4))
        E.append(Paragraph(f'Actions: {closed} of {len(actions)} closed.',
                           S['caption']))
    else:
        E.append(Paragraph('No actions recorded for this MOC.', S['caption']))
    E.append(Spacer(1, 8))

    # ── 10. Linked Investigations ─────────────────────────────────────────────
    E.append(_section_header('10. Linked Investigations', S))
    E.append(Spacer(1, 4))
    if investigations:
        cw = [22*mm, 50*mm, 28*mm, 28*mm, CONTENT_W-22*mm-50*mm-28*mm-28*mm]
        tbl_rows = [[
            Paragraph(str(inv.id), S['mono']),
            Paragraph(inv.title or '—', S['td']),
            Paragraph(getattr(inv, 'classification', None) or
                      getattr(inv, 'investigation_type', '—') or '—', S['td']),
            Paragraph(getattr(inv, 'investigator', None) or
                      getattr(inv, 'lead_investigator', '—') or '—', S['td']),
            _status_para(inv.status or '—', S),
        ] for inv in investigations]
        E.append(_std_table(['REF','TITLE','TYPE','INVESTIGATOR','STATUS'],
                            tbl_rows, cw, S))
    else:
        E.append(Paragraph('No linked investigations.', S['caption']))
    E.append(Spacer(1, 8))

    # ── 11. Post-Implementation Review (PIR) ──────────────────────────────────
    E.append(_section_header('11. Post-Implementation Review (PIR)', S))
    E.append(Spacer(1, 4))
    pir_date   = getattr(moc, 'pir_date', '—') or '—'
    pir_rev    = getattr(moc, 'pir_reviewer', '—') or '—'
    pir_eff    = getattr(moc, 'pir_effectiveness', '—') or '—'
    pir_act    = getattr(moc, 'pir_additional_actions', '—') or '—'
    pir_out    = getattr(moc, 'pir_outcome', '') or ''
    E.append(_info_grid([
        ('PIR Date',           pir_date),
        ('Reviewer',           pir_rev),
        ('Effectiveness',      pir_eff),
        ('Additional Actions', pir_act),
    ], S, cols=2))
    if pir_out:
        E.append(Spacer(1, 4))
        E.append(_text_block('Actual Outcome', pir_out, S))
    E.append(Spacer(1, 8))

    # ── 12. Audit Verification Items (AVI) ────────────────────────────────────
    E.append(_section_header('12. Audit Verification Items (AVI)', S))
    E.append(Spacer(1, 4))
    if avis:
        cw = [16*mm, CONTENT_W-16*mm-22*mm-28*mm-28*mm, 22*mm, 28*mm, 28*mm]
        tbl_rows = [[
            Paragraph(str(avi.id), S['mono']),
            Paragraph(avi.verification_objective or '—', S['td']),
            _status_para(avi.status or '—', S),
            Paragraph(avi.verified_date or '—', S['td']),
            Paragraph(avi.verified_by or '—', S['td']),
        ] for avi in avis]
        E.append(_std_table(['AVI ID','OBJECTIVE','STATUS','VERIFIED DATE','VERIFIED BY'],
                            tbl_rows, cw, S))
    else:
        E.append(Paragraph('No audit verification items recorded.', S['caption']))
    E.append(Spacer(1, 8))

    # ── 13. Activity Log ──────────────────────────────────────────────────────
    E.append(_section_header('13. Activity Log', S))
    E.append(Spacer(1, 4))
    if updates:
        cw = [30*mm, 20*mm, 28*mm, CONTENT_W-30*mm-20*mm-28*mm]
        tbl_rows = [[
            Paragraph(u.created_at.strftime('%Y-%m-%d %H:%M') if u.created_at else '—', S['mono']),
            Paragraph(getattr(u, 'update_type', 'Progress') or 'Progress', S['td']),
            Paragraph(getattr(u, 'updated_by', '—') or '—', S['td']),
            Paragraph(getattr(u, 'notes', '') or getattr(u, 'content', '') or '—', S['td']),
        ] for u in updates]
        E.append(_std_table(['DATE','TYPE','BY','UPDATE'], tbl_rows, cw, S))
    else:
        E.append(Paragraph('No activity log entries.', S['caption']))
    E.append(Spacer(1, 8))

    # ── 14. Signatures & Authorisation ───────────────────────────────────────
    E.append(_section_header('14. Signatures & Authorisation', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Initiator',         'name': getattr(moc, 'initiator', '') if moc else '',       'date': getattr(moc, 'date_raised', '') if moc else ''},
        {'role': 'Department Manager','name': getattr(moc, 'dept_manager_approver', '') if moc else '', 'date': getattr(moc, 'dept_manager_date', '') if moc else ''},
        {'role': 'Safety Manager',    'name': getattr(moc, 'safety_manager_approver', '') if moc else '', 'date': getattr(moc, 'safety_manager_date', '') if moc else ''},
        {'role': 'Accountable MGR',   'name': getattr(moc, 'ae_approver', '') if moc else '',     'date': getattr(moc, 'ae_date', '') if moc else ''},
    ], S))

    return _build_doc(E, 'Management of Change', mid,
                      'INTERNAL — CONTROLLED CHANGE', generated_by, status)


# ── 7. AUDIT REPORT ──────────────────────────────────────────────────────────
def pdf_audit(audit, findings, generated_by='Safety Department'):
    S      = _styles()
    ref    = audit.id if audit else '—'
    status = audit.status if audit else '—'
    title  = audit.title or 'Audit Report' if audit else 'Audit Report'
    dept   = audit.department.name if audit and audit.department else '—'
    E = []

    E.append(_cover_banner(title, ref, 'Safety Audit Report', status, dept,
                           getattr(audit, 'planned_date', '—') if audit else '—',
                           'RESTRICTED — SAFETY SENSITIVE', S))
    E.append(Spacer(1, 10))

    E.append(_section_header('1. Audit Information', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Audit Reference',  ref),
        ('Audit Type',       getattr(audit, 'audit_type', '—') or '—'),
        ('Planned Date',     getattr(audit, 'planned_date', '—') or '—'),
        ('Actual Date',      getattr(audit, 'actual_date', '—') or '—'),
        ('Lead Auditor',     getattr(audit, 'lead_auditor', '—') or '—'),
        ('Department',       dept),
        ('Standard',         getattr(audit, 'standard', '—') or '—'),
        ('Status',           status),
        ('Closed Date',      getattr(audit, 'closed_date', '—') or '—'),
        ('Next Audit Date',  getattr(audit, 'next_audit_date', '—') or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 8))

    E.append(_section_header('2. Audit Scope & Objectives', S))
    E.append(Spacer(1, 4))
    for lbl, attr in [
        ('Scope',        'scope'),
        ('Objectives',   'objectives'),
        ('Criteria',     'criteria'),
        ('Methodology',  'methodology'),
    ]:
        E.append(_text_block(lbl, getattr(audit, attr, '') if audit else '', S))
        E.append(Spacer(1, 4))
    E.append(Spacer(1, 4))

    E.append(_section_header('3. Audit Findings', S))
    E.append(Spacer(1, 4))
    if findings:
        cw = [22*mm, 22*mm, 16*mm, CONTENT_W-22*mm-22*mm-16*mm-22*mm-30*mm, 22*mm, 30*mm]
        tbl_rows = [[
            Paragraph(str(f.id), S['mono']),
            Paragraph(getattr(f, 'reference', '—') or '—', S['td']),
            Paragraph(getattr(f, 'severity', '—') or '—', S['td']),
            Paragraph(getattr(f, 'description', '—') or '—', S['td']),
            _status_para(getattr(f, 'status', '—') or '—', S),
            Paragraph(getattr(f, 'due_date', '—') or '—', S['td']),
        ] for f in findings]
        E.append(_std_table(['ID','REF','SEVERITY','DESCRIPTION','STATUS','DUE DATE'],
                            tbl_rows, cw, S))
        sev = {'Major': 0, 'Minor': 0, 'Observation': 0}
        for f in findings:
            k = getattr(f, 'severity', 'Observation') or 'Observation'
            sev[k] = sev.get(k, 0) + 1
        E.append(Spacer(1, 4))
        E.append(Paragraph(
            f"Summary: {sev['Major']} Major · {sev['Minor']} Minor · {sev['Observation']} Observations",
            S['caption']))
    else:
        E.append(Paragraph('No findings recorded for this audit.', S['caption']))
    E.append(Spacer(1, 8))

    E.append(_section_header('4. Audit Conclusion', S))
    E.append(Spacer(1, 4))
    for lbl, attr in [
        ('Overall Conclusion',    'conclusion'),
        ('Summary of Findings',   'findings_summary'),
        ('Recommendations',       'recommendations'),
        ('Follow-Up Required',    'follow_up'),
    ]:
        E.append(_text_block(lbl, getattr(audit, attr, '') if audit else '', S))
        E.append(Spacer(1, 4))
    E.append(Spacer(1, 4))

    E.append(_section_header('5. Signatures & Authorisation', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Lead Auditor',    'name': getattr(audit, 'lead_auditor', '') if audit else '',   'date': getattr(audit, 'actual_date', '') if audit else ''},
        {'role': 'Auditee',         'name': getattr(audit, 'auditee', '') if audit else '',        'date': ''},
        {'role': 'Safety Manager',  'name': getattr(audit, 'safety_manager', '') if audit else '', 'date': ''},
        {'role': 'Accountable Mgr', 'name': '', 'date': ''},
    ], S))

    return _build_doc(E, 'Safety Audit Report', ref,
                      'RESTRICTED — SAFETY SENSITIVE', generated_by, status)


# ── 8. ERP / EMERGENCY REPORT ────────────────────────────────────────────────
def pdf_erp(report, generated_by='Safety Department'):
    S      = _styles()
    ref    = report.id if report else '—'
    status = getattr(report, 'status', 'Submitted') or 'Submitted'
    title  = getattr(report, 'title', 'Emergency Response Report') or 'Emergency Response Report'
    E = []

    E.append(_cover_banner(title, ref, 'Emergency Response Report', status, '—',
                           getattr(report, 'date', '—') if report else '—',
                           'RESTRICTED — SAFETY SENSITIVE', S))
    E.append(Spacer(1, 10))

    E.append(_section_header('1. Incident Information', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Report Reference',  ref),
        ('Incident Type',     getattr(report, 'incident_type', '—') or '—'),
        ('Date',              getattr(report, 'date', '—') or '—'),
        ('Time',              getattr(report, 'time', '—') or '—'),
        ('Location',          getattr(report, 'location', '—') or '—'),
        ('Reporter',          getattr(report, 'reporter', '—') or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 8))

    for lbl, attr in [
        ('Description', 'description'),
        ('Actions Taken', 'actions_taken'),
        ('Outcome', 'outcome'),
        ('Lessons Learned', 'lessons_learned'),
    ]:
        E.append(_section_header(lbl, S, level=2))
        E.append(Spacer(1, 4))
        E.append(_text_block(lbl, getattr(report, attr, '') if report else '', S))
        E.append(Spacer(1, 6))

    E.append(_section_header('5. Signatures', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Reporter',       'name': getattr(report, 'reporter', '') if report else '', 'date': getattr(report, 'date', '') if report else ''},
        {'role': 'Safety Manager', 'name': '', 'date': ''},
        {'role': 'Accountable Mgr','name': '', 'date': ''},
    ], S))

    return _build_doc(E, 'Emergency Response Report', ref,
                      'RESTRICTED — SAFETY SENSITIVE', generated_by, status)


# ── 9. VOLUNTARY REPORT ──────────────────────────────────────────────────────
def pdf_voluntary(report, generated_by='Safety Department'):
    S      = _styles()
    ref    = report.id if report else '—'
    status = getattr(report, 'status', 'Received') or 'Received'
    title  = getattr(report, 'subject', 'Voluntary Safety Report') or 'Voluntary Safety Report'
    E = []

    E.append(_cover_banner(title, ref, 'Voluntary Safety Report', status,
                           getattr(report, 'department', '—') if report else '—',
                           getattr(report, 'date', '—') if report else '—',
                           'CONFIDENTIAL — VOLUNTARY REPORT', S))
    E.append(Spacer(1, 10))

    E.append(_section_header('1. Report Details', S))
    E.append(Spacer(1, 4))
    anon = getattr(report, 'anonymous', True)
    E.append(_info_grid([
        ('Report Reference', ref),
        ('Date Submitted',   getattr(report, 'date', '—') or '—'),
        ('Category',         getattr(report, 'category', '—') or '—'),
        ('Reporter',         'Anonymous' if anon else (getattr(report, 'reporter_name', '—') or '—')),
        ('Department',       getattr(report, 'department', '—') or '—'),
        ('Status',           status),
    ], S, cols=2))
    E.append(Spacer(1, 8))

    for lbl, attr in [
        ('Description of Safety Concern', 'description'),
        ('Suggested Improvement',          'suggestion'),
        ('Safety Officer Notes',           'safety_notes'),
    ]:
        E.append(_text_block(lbl, getattr(report, attr, '') if report else '', S))
        E.append(Spacer(1, 6))

    E.append(Paragraph(
        'NOTE: This report was submitted voluntarily. Reporter identity is protected '
        'in accordance with the AviaS Just Culture Policy.',
        S['caption']))

    return _build_doc(E, 'Voluntary Safety Report', ref,
                      'CONFIDENTIAL — VOLUNTARY REPORT', generated_by, status,
                      watermark='CONFIDENTIAL')


# ── 10. CONFIDENTIAL REPORT ──────────────────────────────────────────────────
def pdf_confidential(report, generated_by='Safety Department'):
    S      = _styles()
    ref    = report.id if report else '—'
    status = getattr(report, 'status', 'Received') or 'Received'
    title  = getattr(report, 'subject', 'Confidential Safety Report') or 'Confidential Safety Report'
    E = []

    E.append(_cover_banner(title, ref, 'Confidential Safety Report', status, '—',
                           getattr(report, 'date', '—') if report else '—',
                           'STRICTLY CONFIDENTIAL', S))
    E.append(Spacer(1, 10))

    E.append(_section_header('1. Report Information', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Report Reference', ref),
        ('Date',             getattr(report, 'date', '—') or '—'),
        ('Category',         getattr(report, 'category', '—') or '—'),
        ('Status',           status),
    ], S, cols=2))
    E.append(Spacer(1, 8))

    for lbl, attr in [
        ('Safety Concern',    'description'),
        ('Suggested Action',  'suggestion'),
        ('Officer Response',  'safety_notes'),
    ]:
        E.append(_text_block(lbl, getattr(report, attr, '') if report else '', S))
        E.append(Spacer(1, 6))

    E.append(Paragraph(
        'STRICTLY CONFIDENTIAL. Access restricted to the Safety Manager and Accountable Executive only.',
        S['caption']))

    return _build_doc(E, 'Confidential Safety Report', ref,
                      'STRICTLY CONFIDENTIAL', generated_by, status,
                      watermark='CONFIDENTIAL')


# ── 11. TRAINING RECORD ──────────────────────────────────────────────────────
def pdf_training(employee, records, generated_by='Safety Department'):
    S    = _styles()
    ref  = employee.id if employee else '—'
    name = employee.full_name if employee else 'Employee'
    dept = employee.department.name if employee and employee.department else '—'
    E = []

    E.append(_cover_banner(f'Training Record — {name}', ref,
                           'Employee Training Record', 'Active', dept,
                           datetime.utcnow().strftime('%Y-%m-%d'),
                           'INTERNAL — HR RECORD', S))
    E.append(Spacer(1, 10))

    E.append(_section_header('1. Employee Profile', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Employee ID',    ref),
        ('Full Name',      name),
        ('Department',     dept),
        ('Role',           getattr(employee, 'role', '—') or '—'),
        ('Position',       getattr(employee, 'position', '—') or '—'),
        ('Email',          getattr(employee, 'email', '—') or '—'),
        ('Date of Join',   getattr(employee, 'date_of_join', '—') or '—'),
        ('Report Date',    datetime.utcnow().strftime('%Y-%m-%d')),
    ], S, cols=2))
    E.append(Spacer(1, 8))

    E.append(_section_header('2. Training Records', S))
    E.append(Spacer(1, 4))
    if records:
        cw = [28*mm, 40*mm, 24*mm, 20*mm, 22*mm, CONTENT_W-28*mm-40*mm-24*mm-20*mm-22*mm]
        tbl_rows = [[
            Paragraph(getattr(r, 'course_code', '—') or '—', S['mono']),
            Paragraph(getattr(r, 'course_name', '—') or '—', S['td']),
            Paragraph(getattr(r, 'training_date', '—') or '—', S['td']),
            Paragraph(getattr(r, 'expiry_date', '—') or '—', S['td']),
            _status_para(getattr(r, 'status', '—') or '—', S),
            Paragraph(getattr(r, 'provider', '—') or '—', S['td']),
        ] for r in records]
        E.append(_std_table(
            ['CODE','COURSE / TRAINING','DATE','EXPIRY','STATUS','PROVIDER'],
            tbl_rows, cw, S))
        expired = sum(1 for r in records if (getattr(r, 'status', '') or '').lower() in ('expired','overdue'))
        E.append(Spacer(1, 4))
        E.append(Paragraph(f'Total: {len(records)} records  ·  {expired} expired / overdue.',
                           S['caption']))
    else:
        E.append(Paragraph('No training records found for this employee.', S['caption']))
    E.append(Spacer(1, 8))

    E.append(_section_header('3. Authorisation', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Employee',          'name': name, 'date': ''},
        {'role': 'Training Manager',  'name': '', 'date': ''},
        {'role': 'Safety Manager',    'name': '', 'date': ''},
    ], S))

    return _build_doc(E, 'Employee Training Record', ref,
                      'INTERNAL — HR RECORD', generated_by, 'Active')


# ── 12. AUDIT FINDING ────────────────────────────────────────────────────────
def pdf_audit_finding(finding, audit, actions, generated_by='Safety Department'):
    S      = _styles()
    ref    = finding.id if finding else '—'
    status = getattr(finding, 'status', '—') or '—'
    title  = getattr(finding, 'description', 'Audit Finding') or 'Audit Finding'
    E = []

    E.append(_cover_banner(title[:120], ref, 'Audit Finding Report', status,
                           audit.department.name if audit and audit.department else '—',
                           getattr(audit, 'actual_date', getattr(audit, 'planned_date', '—')) if audit else '—',
                           'RESTRICTED — AUDIT RECORD', S))
    E.append(Spacer(1, 10))

    E.append(_section_header('1. Finding Details', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Finding Reference',  ref),
        ('Audit Reference',    audit.id if audit else '—'),
        ('Audit Type',         getattr(audit, 'audit_type', '—') or '—' if audit else '—'),
        ('Severity',           getattr(finding, 'severity', '—') or '—'),
        ('Standard / Clause',  getattr(finding, 'standard_clause', '—') or '—'),
        ('Audit Date',         getattr(audit, 'actual_date', '—') or '—' if audit else '—'),
        ('Lead Auditor',       getattr(audit, 'lead_auditor', '—') or '—' if audit else '—'),
        ('Status',             status),
        ('Due Date',           getattr(finding, 'due_date', '—') or '—'),
        ('Closed Date',        getattr(finding, 'closed_date', '—') or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 8))

    E.append(_section_header('2. Finding Narrative', S))
    E.append(Spacer(1, 4))
    for lbl, attr in [
        ('Description',              'description'),
        ('Evidence / Objective Evidence', 'evidence'),
        ('Required Corrective Action',    'required_action'),
        ('Root Cause',                    'root_cause'),
    ]:
        E.append(_text_block(lbl, getattr(finding, attr, '') if finding else '', S))
        E.append(Spacer(1, 4))
    E.append(Spacer(1, 4))

    E.append(_section_header('3. Corrective Actions', S))
    E.append(Spacer(1, 4))
    E.append(_actions_table([{
        'id': a.id, 'description': a.description,
        'owner': a.owner, 'due_date': a.due_date, 'status': a.status,
    } for a in (actions or [])], S))
    E.append(Spacer(1, 8))

    E.append(_section_header('4. Verification & Close-Out', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Verified By',    getattr(finding, 'verified_by', '—') or '—'),
        ('Verified Date',  getattr(finding, 'verified_date', '—') or '—'),
        ('Closure Method', getattr(finding, 'closure_method', '—') or '—'),
        ('Closure Notes',  getattr(finding, 'closure_notes', '—') or '—'),
    ], S, cols=2))
    E.append(Spacer(1, 8))

    E.append(_section_header('5. Signatures & Authorisation', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Lead Auditor',    'name': getattr(audit, 'lead_auditor', '') if audit else '', 'date': getattr(audit, 'actual_date', '') if audit else ''},
        {'role': 'Responsible Mgr', 'name': '', 'date': ''},
        {'role': 'Safety Manager',  'name': '', 'date': ''},
        {'role': 'Accountable Mgr', 'name': '', 'date': ''},
    ], S))

    return _build_doc(E, 'Audit Finding Report', ref,
                      'RESTRICTED — AUDIT RECORD', generated_by, status)


# ── 13. SPI SUMMARY ──────────────────────────────────────────────────────────
def pdf_spi_summary(indicators, period, generated_by='Safety Department'):
    S   = _styles()
    ref = f'SPI-{period}' if period else 'SPI-SUMMARY'
    E = []

    E.append(_cover_banner(f'Safety Performance Indicators — {period or "All Periods"}',
                           ref, 'Safety Performance Report', 'Active', 'Safety Department',
                           datetime.utcnow().strftime('%Y-%m-%d'),
                           'INTERNAL — SAFETY MANAGEMENT', S))
    E.append(Spacer(1, 10))

    E.append(_section_header('1. Report Information', S))
    E.append(Spacer(1, 4))
    E.append(_info_grid([
        ('Report Reference',   ref),
        ('Reporting Period',   period or 'All'),
        ('Generated By',       generated_by),
        ('Generated Date',     datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')),
        ('Total Indicators',   str(len(indicators or []))),
        ('ICAO Standard',      'Doc 9859 — Safety Management Manual'),
    ], S, cols=2))
    E.append(Spacer(1, 8))

    E.append(_section_header('2. Safety Performance Indicators', S))
    E.append(Spacer(1, 4))
    if indicators:
        cw = [22*mm, 50*mm, 20*mm, 20*mm, 20*mm, CONTENT_W-22*mm-50*mm-20*mm-20*mm-20*mm]
        tbl_rows = []
        for ind in indicators:
            tbl_rows.append([
                Paragraph(getattr(ind, 'code', str(ind.id)), S['mono']),
                Paragraph(getattr(ind, 'name', '—') or '—', S['td']),
                Paragraph(str(getattr(ind, 'target', '—') or '—'), S['td']),
                Paragraph(str(getattr(ind, 'actual', '—') or '—'), S['td']),
                _status_para(getattr(ind, 'performance_status', getattr(ind, 'status', '—')) or '—', S),
                Paragraph(getattr(ind, 'trend', '—') or '—', S['td']),
            ])
        E.append(_std_table(
            ['CODE','INDICATOR','TARGET','ACTUAL','STATUS','TREND'],
            tbl_rows, cw, S))
    else:
        E.append(Paragraph('No safety performance indicators found for this period.', S['caption']))
    E.append(Spacer(1, 8))

    E.append(_section_header('3. Authorisation', S))
    E.append(Spacer(1, 6))
    E.append(_signature_block([
        {'role': 'Safety Manager',    'name': generated_by, 'date': datetime.utcnow().strftime('%Y-%m-%d')},
        {'role': 'Accountable Mgr',   'name': '', 'date': ''},
        {'role': 'Reviewed By',       'name': '', 'date': ''},
    ], S))

    return _build_doc(E, 'Safety Performance Report', ref,
                      'INTERNAL — SAFETY MANAGEMENT', generated_by, 'Active')
