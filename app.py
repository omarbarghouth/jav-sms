from flask import Flask, render_template, request, redirect, url_for, flash, session
from models import db, Department, HazardReport, ASRReport, Hazard, Risk, Control, Action, Audit, Finding, Investigation, MOC, SPIIndicator, SPIData, SPIEscalation, ChecklistTemplate, ChecklistTemplateItem, DistributionList, EmailLog, SurveyResponse, User, VoluntaryReport, ConfidentialReport, SafetyNewsletter, SafetyCampaign, SafetySurvey, LessonLearned, SafetyBulletin, Training, AuditPlan, AuditSchedule, AuditChecklist, AuditFinding, AuditAction, SafetyPolicy, SafetyRole, SafetyPersonnel, ERPlan, SMSDocument, DocumentLink, RiskOccurrence, RiskAction, RAChecklistItem, RiskAssessment, RARow, RAMitigation, RAReview
from datetime import datetime, date
import os, uuid, io, hashlib, functools
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from flask import send_file, make_response

app = Flask(__name__)

@app.template_filter('fromjson')
def fromjson_filter(s):
    import json
    try: return json.loads(s or '{}')
    except: return {}

import smtplib, json as _json_mod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
SMTP_HOST=os.environ.get('SMTP_HOST','')
SMTP_PORT=int(os.environ.get('SMTP_PORT',587))
SMTP_USER=os.environ.get('SMTP_USER','')
SMTP_PASSWORD=os.environ.get('SMTP_PASSWORD','')
SMTP_FROM=os.environ.get('SMTP_FROM','safety@jordanaviation.com')
SMTP_FROM_NAME=os.environ.get('SMTP_FROM_NAME','Jordan Aviation Safety')

def send_email(to_list, subject, html_body):
    if not SMTP_HOST or not SMTP_USER: return len(to_list), None
    sent=0; errs=[]
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as srv:
            srv.starttls(); srv.login(SMTP_USER, SMTP_PASSWORD)
            for r in to_list:
                try:
                    msg=MIMEMultipart('alternative')
                    msg['Subject']=subject; msg['From']=SMTP_FROM_NAME+' <'+SMTP_FROM+'>'; msg['To']=r
                    msg.attach(MIMEText(html_body,'html'))
                    srv.sendmail(SMTP_FROM, r, msg.as_string()); sent+=1
                except Exception as ex: errs.append(str(ex)[:40])
    except Exception as ex: return 0, str(ex)
    return sent, '; '.join(errs) if errs else None

def get_recipients(dept_ids=None):
    q=DistributionList.query.filter_by(is_active=True)
    if dept_ids: q=q.filter(DistributionList.department_id.in_(dept_ids))
    return [r.email for r in q.all() if r.email]

def email_html(title, subtitle, body_html, ref='', dt=''):
    ref_line = ('<div style="color:#c9a84c;font-size:11px;margin-top:6px">Ref: '+ref+' · '+dt+'</div>') if ref else ''
    return ('<!DOCTYPE html><html><body style="background:#f0f2f8;font-family:Arial,sans-serif;padding:24px">'
            '<table width="580" style="background:#fff;border-radius:12px;overflow:hidden;margin:0 auto">'
            '<tr><td style="background:#0f1c3f;padding:18px 26px;border-bottom:3px solid #c9a84c">'
            '<span style="color:#fff;font-size:14px;font-weight:800">✈ Jordan Aviation</span></td></tr>'
            '<tr><td style="background:#0f1c3f;padding:16px 26px">'
            '<div style="color:rgba(255,255,255,.5);font-size:10px;text-transform:uppercase;letter-spacing:1px">'+subtitle+'</div>'
            '<div style="color:#fff;font-size:20px;font-weight:800;margin-top:4px">'+title+'</div>'
            +ref_line+'</td></tr>'
            '<tr><td style="padding:22px 26px;font-size:14px;color:#374151;line-height:1.7">'+body_html+'</td></tr>'
            '<tr><td style="background:#f8f9fc;padding:12px 26px;font-size:11px;color:#9ca3af">'
            'Jordan Aviation · Safety Management System · ICAO Annex 19</td></tr>'
            '</table></body></html>')

# Evidence file uploads
# Upload folder: use env var override for cloud (e.g. /tmp on Render free tier)
_default_upload = os.path.join(os.path.dirname(__file__), 'static', 'evidence')
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', _default_upload)
ALLOWED_EXT   = {'pdf','docx','xlsx','png','jpg','jpeg','gif','mp4','mov'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXT


def _save_upload(field_name, prefix=''):
    """Save an uploaded file, return filename or None."""
    if field_name not in request.files:
        return None
    f = request.files[field_name]
    if not f or not f.filename or not allowed_file(f.filename):
        return None
    from werkzeug.utils import secure_filename
    fname = f'{prefix}{secure_filename(f.filename)}'
    f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
    return fname

# ─── Config ───────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Render PostgreSQL uses postgres:// but SQLAlchemy needs postgresql://
_db_url = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(BASE_DIR, "sms.db")}')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'jav-sms-dev-only-change-in-prod')
# IMPORTANT: Set a strong SECRET_KEY env var in production (Render dashboard)

db.init_app(app)

# ─── Helpers ──────────────────────────────────────────────────────────────────
INTOLERABLE = {'5A','5B','5C','4A','4B','3A'}
TOLERABLE   = {'5D','5E','4C','4D','4E','3B','3C','3D','2A','2B','2C','1A'}

def get_tolerance(ri):
    if ri in INTOLERABLE: return 'INTOLERABLE'
    if ri in TOLERABLE:   return 'TOLERABLE'
    return 'ACCEPTABLE'

def new_id(prefix):
    """
    Generate standardised control number: MODULE/SMS/NN
    e.g.  HR/SMS/01  RA/SMS/03  AUD/SMS/02
    Falls back to UUID-suffix if module unknown.
    """
    MODULE_MAP = {
        'HR':   ('HR',  HazardReport),
        'ASR':  ('ASR', ASRReport),
        'HAZ':  ('HAZ', Hazard),
        'RSK':  ('RSK', Risk),
        'CTL':  ('CTL', Control),
        'ACT':  ('ACT', Action),
        'INV':  ('INV', Investigation),
        'MOC':  ('MOC', MOC),
        'AUD':  ('AUD', AuditSchedule),
        'PLAN': ('PLAN', AuditPlan),
        'FND':  ('FND', AuditFinding),
        'POL':  ('POL', SafetyPolicy),
        'ROLE': ('ROLE', SafetyRole),
        'PERS': ('PERS', SafetyPersonnel),
        'ERP':  ('ERP', ERPlan),
        'RA':   ('RA',  RiskAssessment),
        'RACT': ('RACT', RiskAction),
        'BUL':  ('BUL', SafetyBulletin),
        'DOC':  ('DOC', SMSDocument),
    }
    if prefix in MODULE_MAP:
        code, model = MODULE_MAP[prefix]
        seq = model.query.count() + 1
        return f'{code}-SMS-{seq:02d}'
    # fallback
    short = str(uuid.uuid4())[:6].upper()
    return f'{prefix}-SMS-{short}' 

def check_overdue_actions():
    """Auto-mark actions as Overdue when due_date passes (only Open/In Progress)."""
    today = date.today().isoformat()
    actions = Action.query.filter(Action.status.in_(['Open','In Progress'])).all()
    changed = False
    for a in actions:
        if a.due_date and a.due_date < today:
            a.status = 'Overdue'
            changed = True
    if changed:
        db.session.commit()

@app.context_processor
def inject_globals():
    depts = Department.query.all()
    now   = datetime.utcnow()
    # Count overdue actions for nav badge
    overdue = Action.query.filter_by(status='Overdue').count()
    return dict(all_departments=depts, now=now, get_tolerance=get_tolerance,
                nav_overdue=overdue, enumerate=enumerate)


# ── Auth helpers ──────────────────────────────────────────────────────────────

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def check_pw(pw, hashed):
    return hashlib.sha256(pw.encode()).hexdigest() == hashed

def is_logged_in():
    return session.get('admin_logged_in') is True

def require_login(f):
    """Decorator — redirects to login if not authenticated."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not is_logged_in():
            return redirect(url_for('admin_login', next=request.path))
        return f(*args, **kwargs)
    return decorated

def seed_admin():
    """Create default admin account if no users exist."""
    if User.query.count() == 0:
        admin = User(
            username     = 'admin',
            password_hash= hash_pw('Jordan@SMS2026'),
            full_name    = 'Safety Manager',
            role         = 'admin',
            is_active    = True,
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Default admin created — user: admin / pass: Jordan@SMS2026")

# ─── SEED DATABASE ────────────────────────────────────────────────────────────
def seed():
    """Database initialisation — creates tables only. No demo data."""
    db.create_all()
    # Seed departments only if they do not exist yet
    if not Department.query.first():
        depts = [
            Department(id=1, code='FO', name='Flight Operations'),
            Department(id=2, code='ME', name='Maintenance & Engineering'),
            Department(id=3, code='GO', name='Ground Operations'),
            Department(id=4, code='CC', name='Cabin Crew'),
            Department(id=5, code='SD', name='Safety Department'),
        ]
        for d in depts:
            db.session.add(d)
        db.session.commit()
        print('✅ Departments seeded.')
    seed_admin()
    print('✅ Database ready — no demo data loaded.')


# ═══════════════════════════════════════════════════════════════════════════════
#  PUBLIC REPORTING PORTAL  — no login required
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    """Root: if logged in → admin dashboard, else → public reporting portal."""
    if is_logged_in():
        return redirect(url_for('dashboard'))
    return redirect(url_for('public_portal'))


@app.route('/portal')
def public_portal():
    """Public-facing reporting portal — employees, pilots, operational staff."""
    return render_template('portal/portal.html')


@app.route('/portal/voluntary', methods=['GET', 'POST'])
def portal_voluntary():
    """Voluntary Safety Report — open to all staff."""
    if request.method == 'POST':
        f = request.form
        from datetime import date as _date
        rnum = f'VR-{_date.today().strftime("%Y%m%d")}-{VoluntaryReport.query.count()+1:03d}'
        rpt = VoluntaryReport(
            ref_number    = rnum,
            reporter_name = f.get('reporter_name', '').strip() or 'Anonymous',
            position      = f.get('position', ''),
            department_id = int(f['department_id']) if f.get('department_id') else None,
            date          = f.get('date', _date.today().isoformat()),
            location      = f.get('location', ''),
            report_type   = f.get('report_type', 'Safety Concern'),
            description   = f.get('description', ''),
            consequences  = f.get('consequences', ''),
            suggestion    = f.get('suggestion', ''),
            status        = 'Submitted',
            is_confidential = False,
        )
        db.session.add(rpt)
        db.session.commit()
        return render_template('portal/portal_submitted.html',
                               ref=rnum, report_type='Voluntary Safety Report')
    return render_template('portal/portal_voluntary.html')


@app.route('/portal/confidential', methods=['GET', 'POST'])
def portal_confidential():
    """Confidential Safety Report — identity protected."""
    if request.method == 'POST':
        f = request.form
        from datetime import date as _date
        rnum = f'CR-{_date.today().strftime("%Y%m%d")}-{ConfidentialReport.query.count()+1:03d}'
        rpt = ConfidentialReport(
            ref_number    = rnum,
            position      = f.get('position', ''),
            department_id = int(f['department_id']) if f.get('department_id') else None,
            date          = f.get('date', _date.today().isoformat()),
            location      = f.get('location', ''),
            report_type   = f.get('report_type', 'Safety Concern'),
            description   = f.get('description', ''),
            consequences  = f.get('consequences', ''),
            suggestion    = f.get('suggestion', ''),
            status        = 'Submitted',
        )
        db.session.add(rpt)
        db.session.commit()
        return render_template('portal/portal_submitted.html',
                               ref=rnum, report_type='Confidential Safety Report')
    return render_template('portal/portal_confidential.html')


@app.route('/portal/hazard', methods=['GET', 'POST'])
def portal_hazard():
    """Public Hazard Report form — simplified for fast submission."""
    if request.method == 'POST':
        # Reuse existing hazard_report POST logic
        return hazard_report()
    return render_template('portal/portal_hazard.html')


@app.route('/portal/asr', methods=['GET', 'POST'])
def portal_asr():
    """Public ASR form — reuses existing ASR logic."""
    if request.method == 'POST':
        return asr_report()
    return render_template('portal/portal_asr.html')


# ═══════════════════════════════════════════════════════════════════════════════
#  ADMIN LOGIN / LOGOUT
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if is_logged_in():
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username, is_active=True).first()
        if user and check_pw(password, user.password_hash):
            session['admin_logged_in'] = True
            session['admin_user']      = user.username
            session['admin_role']      = user.role
            session['admin_name']      = user.full_name or user.username
            session.permanent          = True
            user.last_login            = datetime.utcnow()
            db.session.commit()
            next_url = request.args.get('next') or url_for('dashboard')
            return redirect(next_url)
        else:
            error = 'Invalid username or password.'
    return render_template('portal/login.html', error=error)


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('public_portal'))


@app.route('/admin/users')
@require_login
def admin_users():
    """User management — admin only."""
    if session.get('admin_role') != 'admin':
        flash('⚠ Admin access required.', 'error')
        return redirect(url_for('dashboard'))
    users = User.query.order_by(User.created_at).all()
    return render_template('portal/admin_users.html', users=users)


@app.route('/admin/users/new', methods=['POST'])
@require_login
def admin_user_new():
    if session.get('admin_role') != 'admin':
        return redirect(url_for('dashboard'))
    f = request.form
    if User.query.filter_by(username=f['username']).first():
        flash('⚠ Username already exists.', 'error')
        return redirect(url_for('admin_users'))
    u = User(username=f['username'], password_hash=hash_pw(f['password']),
             full_name=f.get('full_name',''), role=f.get('role','safety_officer'),
             is_active=True)
    db.session.add(u); db.session.commit()
    flash(f'✓ User {u.username} created.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:uid>/toggle', methods=['POST'])
@require_login
def admin_user_toggle(uid):
    if session.get('admin_role') != 'admin':
        return redirect(url_for('dashboard'))
    u = User.query.get_or_404(uid)
    u.is_active = not u.is_active
    db.session.commit()
    flash(f'✓ User {u.username} {"activated" if u.is_active else "deactivated"}.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/reports')
@require_login
def admin_reports_inbox():
    """Safety Admin inbox — all submitted public reports."""
    vol   = VoluntaryReport.query.order_by(VoluntaryReport.created_at.desc()).all()
    conf  = ConfidentialReport.query.order_by(ConfidentialReport.created_at.desc()).all()
    haz   = HazardReport.query.order_by(HazardReport.created_at.desc()).limit(20).all()
    asr   = ASRReport.query.order_by(ASRReport.created_at.desc()).limit(20).all()
    total_new = (VoluntaryReport.query.filter_by(status='Submitted').count() +
                 ConfidentialReport.query.filter_by(status='Submitted').count())
    return render_template('portal/admin_reports.html',
                           vol=vol, conf=conf, haz=haz, asr=asr,
                           total_new=total_new)


@app.route('/admin/reports/voluntary/<int:rid>/review', methods=['POST'])
@require_login
def vol_report_review(rid):
    r = VoluntaryReport.query.get_or_404(rid)
    r.status = 'Under Review'
    db.session.commit()
    flash('✓ Marked as Under Review.', 'success')
    return redirect(url_for('admin_reports_inbox'))


@app.route('/admin/reports/confidential/<int:rid>/review', methods=['POST'])
@require_login
def conf_report_review(rid):
    r = ConfidentialReport.query.get_or_404(rid)
    r.status = 'Under Review'
    db.session.commit()
    flash('✓ Marked as Under Review.', 'success')
    return redirect(url_for('admin_reports_inbox'))


# ═══════════════════════════════════════════════════════════════════════════════
#  INTERNAL ADMIN DASHBOARD  — login required
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/dashboard')
@require_login
def dashboard():
    check_overdue_actions()
    total_haz   = Hazard.query.count()
    open_haz    = Hazard.query.filter_by(status='Open').count()
    intol       = Risk.query.filter_by(initial_tolerance='INTOLERABLE').count()
    open_act    = Action.query.filter(Action.status.in_(['Open','In Progress','Overdue'])).count()
    overdue_act = Action.query.filter_by(status='Overdue').count()
    asr_cnt     = ASRReport.query.count()
    audit_cnt   = AuditSchedule.query.count()
    moc_cnt     = MOC.query.count()
    inv_cnt     = Investigation.query.count()
    doc_cnt     = SMSDocument.query.filter_by(status='Approved').count()
    spi_alerts  = 0
    for ind in SPIIndicator.query.all():
        recent = SPIData.query.filter_by(spi_id=ind.id).order_by(
                 SPIData.year.desc(), SPIData.month.desc()).first()
        if recent and ind.alert_l1 and recent.rate and recent.rate >= ind.alert_l1:
            spi_alerts += 1
    recent_haz = Hazard.query.order_by(Hazard.created_at.desc()).limit(6).all()
    recent_act = Action.query.filter(
                 Action.status != 'Closed').order_by(Action.created_at.desc()).limit(5).all()
    # Audit plan alerts for dashboard
    now_month = datetime.now().month
    now_year  = datetime.now().year
    plan_this_month = AuditPlan.query.filter_by(
        year=now_year, month=now_month).filter(
        AuditPlan.status != 'Completed').all()
    plan_overdue = AuditPlan.query.filter(
        AuditPlan.year == now_year,
        AuditPlan.month < now_month,
        AuditPlan.month != None,
        AuditPlan.status != 'Completed').all()
    return render_template('dashboard/dashboard.html',
        total_haz=total_haz, open_haz=open_haz, intol=intol,
        open_act=open_act, overdue_act=overdue_act,
        asr_cnt=asr_cnt, audit_cnt=audit_cnt, moc_cnt=moc_cnt,
        inv_cnt=inv_cnt, doc_cnt=doc_cnt, spi_alerts=spi_alerts,
        recent_haz=recent_haz, recent_act=recent_act,
        plan_this_month=plan_this_month, plan_overdue=plan_overdue)

# ─── Hazard Report ────────────────────────────────────────────────────────────
@app.route('/hazard-report', methods=['GET','POST'])
def hazard_report():
    if request.method == 'POST':
        f   = request.form
        rid = new_id('HR')
        hid = new_id('HAZ')
        dept_id = int(f['department_id'])

        # Resolve department name BEFORE any session operations
        dept = Department.query.get(dept_id)
        dept_name = dept.name if dept else ''

        # 1. Create and commit Hazard FIRST (HazardReport has FK to hazards.id)
        h = Hazard(
            id=hid,
            source='Hazard Report',
            linked_report_id=rid,
            department_id=dept_id,
            classification=f.get('classification','Operational'),
            type_of_activity=dept_name,
            generic_hazard=f.get('generic_hazard') or f.get('hazard_description','')[:100],
            specific_components=f.get('hazard_description',''),
            consequences=f.get('consequences','To Be Assessed'),
            status='Open',
            owner=None
        )
        db.session.add(h)
        db.session.commit()   # ← Hazard row exists in DB before report references it

        # 2. Now create HazardReport safely (hazard_id FK is satisfied)
        rep = HazardReport(
            id=rid,
            department_id=dept_id,
            location=f.get('location',''),
            date=f.get('date', date.today().isoformat()),
            description=f.get('hazard_description',''),
            classification=f.get('classification','Operational'),
            generic_hazard=f.get('generic_hazard',''),
            consequences=f.get('consequences',''),
            immediate_action=f.get('immediate_action',''),
            suggested_mitigation=f.get('suggested_mitigation',''),
            reporter_severity=f.get('reporter_severity',''),
            reporter=f.get('reporter','Anonymous') or 'Anonymous',
            report_type=f.get('report_type','Hazard Report'),
            status='Submitted',
            hazard_id=hid
        )
        db.session.add(rep)

        # 3. Update statuses and commit together
        h.status = 'Under Assessment'
        db.session.commit()

        # Auto-update matching SPI indicators (with deduplication)
        spi_auto_update(
            source_type   = 'hazard_report',
            department_id = dept_id,
            category      = f.get('classification',''),
            year          = datetime.now().year,
            month         = datetime.now().month,
            report_id     = rid
        )
        flash(f'✓ Hazard Report {rid} submitted successfully. Hazard {hid} created for assessment.', 'success')
        return redirect(url_for('hazard_report_detail', rid=rid))
    return render_template('reporting/hazard_report.html')

@app.route('/hazard-reports')
@require_login
def hazard_report_list():
    """Aviation Operational Reporting Center — all report types."""
    dept_f  = request.args.get('dept', '')
    cat_f   = request.args.get('category', '')
    stat_f  = request.args.get('status', '')
    type_f  = request.args.get('type', '')
    q_f     = request.args.get('q', '').strip()

    # Check if report_type column exists (safe for old DBs)
    has_type_col = True
    try:
        HazardReport.query.filter_by(report_type='test').first()
    except Exception:
        has_type_col = False
        db.session.rollback()

    q = HazardReport.query
    if dept_f:  q = q.filter_by(department_id=int(dept_f))
    if cat_f:   q = q.filter_by(classification=cat_f)
    if stat_f:  q = q.filter_by(status=stat_f)
    if type_f and has_type_col:
        q = q.filter_by(report_type=type_f)
    if q_f:
        q = q.filter(
            HazardReport.description.ilike(f'%{q_f}%') |
            HazardReport.location.ilike(f'%{q_f}%') |
            HazardReport.generic_hazard.ilike(f'%{q_f}%') |
            HazardReport.reporter.ilike(f'%{q_f}%')
        )

    reports = q.order_by(HazardReport.created_at.desc()).all()
    total            = HazardReport.query.count()
    submitted        = HazardReport.query.filter_by(status='Submitted').count()
    under_assessment = HazardReport.query.filter_by(status='Under Assessment').count()
    actioned         = HazardReport.query.filter_by(status='Actioned').count()
    closed           = HazardReport.query.filter_by(status='Closed').count()

    # By report type — safe fallback if column missing
    cnt_hazard = cnt_asr = cnt_vol = cnt_conf = cnt_tech = 0
    if has_type_col:
        try:
            cnt_hazard = HazardReport.query.filter_by(report_type='Hazard Report').count()
            cnt_asr    = HazardReport.query.filter_by(report_type='ASR').count()
            cnt_vol    = HazardReport.query.filter_by(report_type='Voluntary').count()
            cnt_conf   = HazardReport.query.filter_by(report_type='Confidential').count()
            cnt_tech   = HazardReport.query.filter_by(report_type='Technical Log').count()
        except Exception:
            db.session.rollback()

    return render_template('reporting/hazard_report_list.html',
        reports=reports, total=total,
        submitted=submitted, under_assessment=under_assessment,
        actioned=actioned, closed=closed,
        cnt_hazard=cnt_hazard, cnt_asr=cnt_asr, cnt_vol=cnt_vol,
        cnt_conf=cnt_conf, cnt_tech=cnt_tech,
        type_f=type_f,
        dept_f=dept_f, cat_f=cat_f, stat_f=stat_f, q_f=q_f)

@app.route('/hazard-reports/<rid>')
@require_login
def hazard_report_detail(rid):
    """Full detail view for a single hazard report."""
    rep    = HazardReport.query.get_or_404(rid)
    hazard = Hazard.query.get(rep.hazard_id) if rep.hazard_id else None
    ra     = RiskAssessment.query.filter_by(hazard_id=rep.hazard_id).first() if rep.hazard_id else None
    actions = Action.query.filter_by(hazard_id=rep.hazard_id).all() if rep.hazard_id else []
    return render_template('reporting/hazard_report_detail.html',
        rep=rep, hazard=hazard, ra=ra, actions=actions)

@app.route('/hazard-reports/<rid>/update-status', methods=['POST'])
def hazard_report_update_status(rid):
    rep = HazardReport.query.get_or_404(rid)
    rep.status = request.form.get('status', rep.status)
    db.session.commit()
    flash(f'✓ Report {rid} status updated to {rep.status}.', 'success')
    return redirect(url_for('hazard_report_detail', rid=rid))

# ─── ASR ─────────────────────────────────────────────────────────────────────
@app.route('/asr', methods=['GET','POST'])
def asr():
    if request.method == 'POST':
        f  = request.form
        li = int(f.get('likelihood', 3))
        se = f.get('severity','C')
        ri = f'{li}{se}'
        hid = new_id('HAZ')
        aid = new_id('ASR')
        h = Hazard(id=hid, source='ASR', linked_report_id=aid,
                   department_id=1, classification='Operational',
                   type_of_activity='Flight Operations',
                   generic_hazard=f.get('occurrence_type','Flight Occurrence'),
                   specific_components=f.get('event_description',''),
                   consequences='To Be Assessed by Safety Department',
                   status='Open', owner='Flight Operations Manager')
        db.session.add(h)
        db.session.flush()
        r = Risk(id=new_id('RSK'), hazard_id=hid,
                 description=f.get('event_description',''),
                 initial_likelihood=li, initial_severity=se,
                 initial_risk_index=ri, initial_tolerance=get_tolerance(ri))
        db.session.add(r)
        asr_rec = ASRReport(id=aid,
            report_type=f.get('report_type','Voluntary'),
            occurrence_type=f.get('occurrence_type',''),
            captain=f.get('captain',''), captain_staff_no=f.get('captain_staff_no',''),
            copilot=f.get('copilot',''), copilot_staff_no=f.get('copilot_staff_no',''),
            date=f.get('date',''), time_local=f.get('time_local',''),
            time_utc=f.get('time_utc',''), flight_no=f.get('flight_no',''),
            route_from=f.get('route_from',''), route_to=f.get('route_to',''),
            diverted_to=f.get('diverted_to',''), squawk=f.get('squawk',''),
            aircraft_type=f.get('aircraft_type',''), registration=f.get('registration',''),
            pax=int(f.get('pax') or 0), crew=int(f.get('crew') or 0),
            altitude_ft=int(f.get('altitude_ft') or 0),
            flight_phase=f.get('flight_phase',''),
            weather_wind=f.get('weather_wind',''), weather_vis_rvr=f.get('weather_vis_rvr',''),
            weather_clouds=f.get('weather_clouds',''),
            weather_temp_c=int(f.get('weather_temp_c') or 0),
            weather_qnh=int(f.get('weather_qnh') or 0),
            runway=f.get('runway',''), runway_state=f.get('runway_state',''),
            event_description=f.get('event_description',''),
            action_taken=f.get('action_taken',''),
            severity=se, likelihood=li, risk_index=ri, hazard_id=hid)
        db.session.add(asr_rec)
        db.session.commit()
        h.status = 'Under Assessment'
        db.session.commit()
        spi_auto_update(
            source_type   = 'asr',
            department_id = int(f.get('department_id', 1)),
            category      = 'ASR',
            year          = datetime.now().year,
            month         = datetime.now().month,
            report_id     = aid
        )
        flash(f'✓ ASR {aid} submitted. Complete the Risk Assessment for hazard {hid}.', 'success')
        return redirect(url_for('ra_wizard_start', hid=hid))
    return render_template('reporting/asr_report.html')

# ─── Hazard Log ───────────────────────────────────────────────────────────────
@app.route('/hazard-log')
@require_login
def hazard_log():
    dept_f = request.args.get('dept','')
    stat_f = request.args.get('status','')
    cls_f  = request.args.get('classification','')
    q = Hazard.query
    if dept_f: q = q.filter_by(department_id=int(dept_f))
    if stat_f: q = q.filter_by(status=stat_f)
    if cls_f:  q = q.filter_by(classification=cls_f)
    hazards = q.order_by(Hazard.created_at.desc()).all()
    return render_template('hazard/hazard_log.html', hazards=hazards,
        dept_f=dept_f, stat_f=stat_f, cls_f=cls_f)

@app.route('/hazard-log/<hid>')
def hazard_detail(hid):
    h = Hazard.query.get_or_404(hid)
    return render_template('hazard/hazard_detail.html', h=h)

@app.route('/hazard-log/<hid>/update', methods=['POST'])
def hazard_update(hid):
    h = Hazard.query.get_or_404(hid)
    f = request.form
    h.status = f.get('status', h.status)
    h.owner  = f.get('owner', h.owner)
    h.generic_hazard   = f.get('generic_hazard', h.generic_hazard)
    h.classification   = f.get('classification', h.classification)
    h.consequences     = f.get('consequences', h.consequences)
    db.session.commit()
    flash('✓ Hazard updated.', 'success')
    return redirect(url_for('hazard_detail', hid=hid))

# ─── Risk Register ────────────────────────────────────────────────────────────
@app.route('/hazard-log/<hid>/add-risk', methods=['POST'])
def add_risk(hid):
    f  = request.form
    li = int(f['likelihood'])
    se = f['severity']
    ri = f'{li}{se}'
    r = Risk(id=new_id('RSK'), hazard_id=hid,
             description=f['description'],
             initial_likelihood=li, initial_severity=se,
             initial_risk_index=ri, initial_tolerance=get_tolerance(ri),
             residual_likelihood=int(f['res_likelihood']) if f.get('res_likelihood') else None,
             residual_severity=f.get('res_severity') or None)
    if r.residual_likelihood and r.residual_severity:
        rri = f"{r.residual_likelihood}{r.residual_severity}"
        r.residual_risk_index   = rri
        r.residual_tolerance    = get_tolerance(rri)
    db.session.add(r)
    db.session.commit()
    flash('✓ Risk added.', 'success')
    return redirect(url_for('hazard_detail', hid=hid))

@app.route('/risk/<rid>/add-control', methods=['POST'])
def add_control(rid):
    risk = Risk.query.get_or_404(rid)
    f = request.form
    c = Control(id=new_id('CTL'), risk_id=rid,
                control_type=f['control_type'],
                description=f['description'],
                owner=f.get('owner',''),
                effectiveness=f.get('effectiveness',''),
                review_date=f.get('review_date',''))
    db.session.add(c)
    db.session.commit()
    flash('✓ Control measure added.', 'success')
    return redirect(url_for('hazard_detail', hid=risk.hazard_id))

# ─── Actions ──────────────────────────────────────────────────────────────────
@app.route('/actions')
@require_login
def actions():
    """
    Centralized Action Management Dashboard.
    Shows ALL actions from ALL SMS modules in one place.
    """
    check_overdue_actions()
    stat_f = request.args.get('status', '')
    pri_f  = request.args.get('priority', '')
    src_f  = request.args.get('source', '')
    dept_f = request.args.get('dept', '')
    q_f    = request.args.get('q', '').strip()

    q = Action.query
    if stat_f:  q = q.filter_by(status=stat_f)
    if pri_f:   q = q.filter_by(priority=pri_f)
    if src_f:   q = q.filter_by(source=src_f)
    if q_f:
        q = q.filter(
            Action.description.ilike(f'%{q_f}%') |
            Action.owner.ilike(f'%{q_f}%') |
            Action.id.ilike(f'%{q_f}%')
        )
    all_actions = q.order_by(Action.created_at.desc()).all()

    # Status counts
    counts = {
        'open':        Action.query.filter_by(status='Open').count(),
        'prog':        Action.query.filter_by(status='In Progress').count(),
        'closed':      Action.query.filter_by(status='Closed').count(),
        'overdue':     Action.query.filter_by(status='Overdue').count(),
        'total':       Action.query.count(),
        'pending_rev': Action.query.filter(
                           Action.effectiveness.is_(None),
                           Action.status=='Closed'
                       ).count(),
        'high':        Action.query.filter_by(priority='High',
                           status='Open').count(),
    }

    # Source breakdown
    from sqlalchemy import func
    sources = db.session.query(
        Action.source, func.count(Action.id)
    ).filter(Action.status != 'Closed').group_by(Action.source).all()
    source_counts = {s: n for s, n in sources if s}

    # All distinct sources for filter
    all_sources = [r[0] for r in
                   db.session.query(Action.source).distinct().all() if r[0]]

    # Department breakdown
    from sqlalchemy import func as sqlfunc
    dept_actions = db.session.query(Action.source, sqlfunc.count(Action.id))                   .filter(Action.status.in_(['Open','In Progress','Overdue']))                   .group_by(Action.source).all()

    # Pending effectiveness review
    pending_eff = Action.query.filter(
        Action.status=='Closed', Action.effectiveness.is_(None)
    ).all()

    return render_template('action/action_list.html',
        actions=all_actions, counts=counts,
        source_counts=source_counts, all_sources=sorted(all_sources),
        pending_eff=pending_eff,
        stat_f=stat_f, pri_f=pri_f, src_f=src_f, dept_f=dept_f, q_f=q_f)


@app.route('/actions/new', methods=['GET', 'POST'])
@require_login
def new_action():
    """Create a new action. Can be called from any page with pre-filled fields."""
    if request.method == 'POST':
        f = request.form
        # Handle evidence file upload
        evidence_filename = None
        if 'evidence_file' in request.files:
            ef = request.files['evidence_file']
            if ef and ef.filename and allowed_file(ef.filename):
                from werkzeug.utils import secure_filename
                evidence_filename = f"{new_id('EV')}_{secure_filename(ef.filename)}"
                ef.save(os.path.join(app.config['UPLOAD_FOLDER'], evidence_filename))

        alert_month = int(f['spi_alert_month']) if f.get('spi_alert_month') else datetime.now().month
        alert_year  = int(f['spi_alert_year'])  if f.get('spi_alert_year')  else datetime.now().year
        spi_id_val  = int(f['spi_id']) if f.get('spi_id') else None

        # Link to the persisted escalation record for accurate trigger data
        esc_id = None
        if spi_id_val and f.get('spi_trigger_rule'):
            esc = SPIEscalation.query.filter_by(
                spi_id=spi_id_val,
                trigger_month=alert_month,
                trigger_rule=f.get('spi_trigger_rule', '')
            ).first()
            if esc:
                esc_id = esc.id
                esc.status = 'Actioned'

        a = Action(
            id=new_id('ACT'),
            source=f.get('source', 'Manual'),
            hazard_id=f.get('hazard_id') or None,
            linked_ref_id=f.get('linked_ref_id', ''),
            description=f['description'],
            owner=f['owner'],
            due_date=f['due_date'],
            priority=f.get('priority', 'Medium'),
            status='Open',
            # SPI lifecycle fields
            spi_id               = spi_id_val,
            spi_alert_level      = f.get('spi_alert_level', ''),
            spi_trigger_rule     = f.get('spi_trigger_rule', ''),
            spi_alert_month      = alert_month,
            spi_alert_year       = alert_year,
            spi_escalation_id    = esc_id,
            mitigation_description = f.get('mitigation_description', ''),
            corrective_description = f.get('corrective_description', ''),
            safety_notes           = f.get('safety_notes', ''),
            assigned_by            = f.get('assigned_by', ''),
            evidence               = f.get('evidence', ''),
            evidence_filename      = evidence_filename,
            mitigation_status      = 'Pending'
        )
        db.session.add(a)
        db.session.commit()
        flash(f'✓ Action {a.id} created successfully.', 'success')
        # Return to wherever the user came from
        return_url = f.get('return_url', url_for('actions'))
        return redirect(return_url)

    # GET — show the form, pre-fill from URL params if provided
    hazards = Hazard.query.filter_by(status='Open').order_by(Hazard.created_at.desc()).all()
    pre = {
        'source':           request.args.get('source', ''),
        'hazard_id':        request.args.get('hazard_id', ''),
        'linked_ref_id':    request.args.get('linked_ref_id', ''),
        'return_url':       request.args.get('return_url', url_for('actions')),
        'spi_id':           request.args.get('spi_id', ''),
        'spi_alert_level':  request.args.get('spi_alert_level', ''),
        'spi_trigger_rule': request.args.get('spi_trigger_rule', ''),
        'description':      request.args.get('description', ''),
        'priority':         request.args.get('priority', 'Medium'),
    }
    return render_template('action/action_form.html', hazards=hazards, pre=pre)


@app.route('/actions/<aid>/update', methods=['POST'])
@require_login
def update_action(aid):
    """
    Update an action status.
    Simple rules:
    - Closing requires effectiveness to be selected.
    - If Ineffective → action is re-opened automatically.
    """
    a   = Action.query.get_or_404(aid)
    f   = request.form
    new_status    = f.get('status', a.status)
    # Map friendly status to canonical
    # Store the actual workflow status (not mapped) — allows richer lifecycle
    # Only map unknown values to avoid corruption
    VALID_STATUSES = {'Open','In Progress','Mitigation Implemented',
                      'Under Safety Review','Effectiveness Verification',
                      'Closed','Overdue'}
    if new_status not in VALID_STATUSES:
        new_status = 'In Progress'
    effectiveness = f.get('effectiveness', '')
    return_url    = f.get('return_url', url_for('actions'))

    # Only Safety Review step can close — require review fields
    if new_status == 'Closed' and not effectiveness:
        flash('⚠ Please select Effectiveness rating before closing the action.', 'error')
        return redirect(return_url)

    # If ineffective → re-open automatically
    if new_status == 'Closed' and effectiveness == 'Ineffective':
        a.status            = 'Open'
        a.effectiveness     = None
        a.effectiveness_review = f.get('effectiveness_review', '')
        flash('⚠ Action re-opened — effectiveness was Ineffective. Please update the approach.', 'error')
        db.session.commit()
        return redirect(return_url)

    # Normal update
    a.status                 = new_status
    a.evidence               = f.get('evidence', a.evidence)
    a.mitigation_description = f.get('mitigation_description', a.mitigation_description)
    a.corrective_description = f.get('corrective_description', a.corrective_description)
    a.safety_notes           = f.get('safety_notes', a.safety_notes)
    a.follow_up_notes        = f.get('follow_up_notes', a.follow_up_notes)
    a.mitigation_status      = f.get('mitigation_status', a.mitigation_status)
    a.assigned_by            = f.get('assigned_by', a.assigned_by)
    a.closure_by             = f.get('closure_by', a.closure_by)
    a.verified_by            = f.get('verified_by', a.verified_by)
    a.verified_date          = f.get('verified_date', a.verified_date)
    # Implementation date
    if f.get('implementation_date'):
        a.implementation_date = f.get('implementation_date')
    # Safety review fields
    if f.get('safety_review_notes'):
        a.safety_review_notes = f.get('safety_review_notes')
    if f.get('safety_reviewer'):
        a.safety_reviewer = f.get('safety_reviewer')
    if new_status == 'Under Safety Review' and not a.safety_review_date:
        a.safety_review_date = datetime.now().strftime('%Y-%m-%d')
    if new_status == 'Closed' and not a.closed_date:
        a.closed_date = datetime.now().strftime('%Y-%m-%d')
        if not a.closure_by:
            a.closure_by = f.get('closure_by', '')
    # Handle new evidence file upload on update
    if 'evidence_file' in request.files:
        ef = request.files['evidence_file']
        if ef and ef.filename and allowed_file(ef.filename):
            from werkzeug.utils import secure_filename
            fn = f"{a.id}_{secure_filename(ef.filename)}"
            ef.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
            a.evidence_filename = fn
    a.owner        = f.get('owner', a.owner)
    a.due_date     = f.get('due_date', a.due_date)
    a.priority     = f.get('priority', a.priority)
    a.description  = f.get('description', a.description)

    if new_status == 'Closed':
        a.effectiveness        = effectiveness
        a.effectiveness_review = f.get('effectiveness_review', '')
        a.closed_date          = date.today().isoformat()

    try:
        db.session.commit()
        flash('✓ Action updated.', 'success')
    except Exception as e:
        db.session.rollback()
        # Most likely cause: column doesn't exist in live DB yet
        err_str = str(e)
        if 'column' in err_str.lower() and 'does not exist' in err_str.lower():
            flash('⚠ Database schema update required. Please contact the system administrator to run migrations.', 'error')
        else:
            flash(f'⚠ Could not save: {err_str[:120]}', 'error')
    return redirect(return_url)


@app.route('/actions/<aid>/report')
@require_login
def action_report(aid):
    """Print-ready action report — full traceability."""
    a = Action.query.get_or_404(aid)
    # Resolve source reference details
    source_ref = None
    if a.linked_ref_id:
        from models import AuditFinding
        source_ref = AuditFinding.query.get(a.linked_ref_id)
    hazard_ref = None
    if a.hazard_id:
        from models import Hazard
        hazard_ref = Hazard.query.get(a.hazard_id)
    MONTHS = ['January','February','March','April','May','June',
              'July','August','September','October','November','December']
    return render_template('action/action_report.html',
                           a=a, source_ref=source_ref, hazard_ref=hazard_ref,
                           MONTHS=MONTHS, now=datetime.utcnow())


@app.route('/actions/dashboard')
@require_login
def action_dashboard():
    """Aviation Action Management Dashboard — centralized view of all action streams."""
    check_overdue_actions()
    from sqlalchemy import func as sqlfunc
    from datetime import date

    # Core stats
    total    = Action.query.count()
    open_c   = Action.query.filter_by(status='Open').count()
    prog_c   = Action.query.filter_by(status='In Progress').count()
    overdue_c= Action.query.filter_by(status='Overdue').count()
    closed_c = Action.query.filter_by(status='Closed').count()
    high_c   = Action.query.filter_by(status='Open', priority='High').count()
    pend_eff = Action.query.filter(Action.status=='Closed',
                                    Action.effectiveness.is_(None)).count()

    # Source breakdown (open only)
    src_rows = db.session.query(Action.source, sqlfunc.count(Action.id))               .filter(Action.status.in_(['Open','In Progress','Overdue']))               .group_by(Action.source).all()
    source_data = sorted(src_rows, key=lambda x: x[1], reverse=True)

    # Critical overdue actions
    overdue_list = Action.query.filter_by(status='Overdue')                   .order_by(Action.due_date).limit(10).all()

    # Recently closed (last 30 days)
    from datetime import timedelta
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    recently_closed = Action.query.filter(
        Action.status=='Closed', Action.closed_date >= cutoff
    ).order_by(Action.closed_date.desc()).limit(8).all()

    # High priority open
    high_priority = Action.query.filter_by(status='Open', priority='High')                    .order_by(Action.due_date).limit(8).all()

    # Pending effectiveness review
    pending_review = Action.query.filter(
        Action.status=='Closed', Action.effectiveness.is_(None)
    ).order_by(Action.closed_date.desc()).limit(8).all()

    return render_template('action/action_dashboard.html',
                           total=total, open_c=open_c, prog_c=prog_c,
                           overdue_c=overdue_c, closed_c=closed_c,
                           high_c=high_c, pend_eff=pend_eff,
                           source_data=source_data,
                           overdue_list=overdue_list,
                           recently_closed=recently_closed,
                           high_priority=high_priority,
                           pending_review=pending_review,
                           now=datetime.utcnow())


@app.route('/actions/<aid>')
@require_login
def action_detail(aid):
    """Single action detail page — shows everything linked to this action."""
    a      = Action.query.get_or_404(aid)
    hazard = Hazard.query.get(a.hazard_id) if a.hazard_id else None
    return render_template('action/action_detail.html', a=a, hazard=hazard)



# ─── Audits ───────────────────────────────────────────────────────────────────
# ─── Legacy /audits/* routes — redirected to new audit system ────────────────
@app.route('/audits')
def audits():
    return redirect(url_for('audit_schedule'))

@app.route('/audits/new')
def new_audit():
    return redirect(url_for('new_audit_schedule'))

@app.route('/audits/<aid>')
def audit_detail(aid):
    return redirect(url_for('audit_schedule'))

@app.route('/audits/<aid>/add-finding', methods=['GET','POST'])
def add_finding(aid):
    return redirect(url_for('audit_schedule'))

@app.route('/audits/<aid>/update', methods=['GET','POST'])
def update_audit(aid):
    return redirect(url_for('audit_schedule'))

# ─── Investigations ───────────────────────────────────────────────────────────
@app.route('/investigations')
@require_login
def investigations():
    all_inv = Investigation.query.order_by(Investigation.created_at.desc()).all()
    return render_template('investigation/investigation_list.html', investigations=all_inv)

@app.route('/investigations/new', methods=['GET','POST'])
@require_login
def new_investigation():
    if request.method == 'POST':
        f = request.form
        inv = Investigation(id=new_id('INV'),
            title=f['title'],
            linked_report_id=f.get('linked_report_id',''),
            hazard_id=f.get('hazard_id') or None,
            department_id=int(f['department_id']),
            date_of_occurrence=f['date_of_occurrence'],
            investigator=f['investigator'],
            description=f['description'],
            why1=f.get('why1',''), why2=f.get('why2',''),
            why3=f.get('why3',''), why4=f.get('why4',''),
            why5=f.get('why5',''),
            root_cause=f.get('root_cause',''),
            human_factors=f.get('human_factors',''),
            technical_factors=f.get('technical_factors',''),
            organizational_factors=f.get('organizational_factors',''),
            environmental_factors=f.get('environmental_factors',''),
            recommendations=f.get('recommendations',''),
            status='Open')
        db.session.add(inv)
        # Auto-create action from recommendations
        if f.get('recommendations'):
            act = Action(id=new_id('ACT'), source='Investigation',
                         hazard_id=f.get('hazard_id') or None,
                         linked_ref_id=inv.id,
                         description=f['recommendations'],
                         owner=f['investigator'],
                         due_date=f.get('due_date',''),
                         priority='High', status='Open')
            db.session.add(act)
        db.session.commit()
        flash(f'✓ Investigation {inv.id} created.', 'success')
        return redirect(url_for('investigations'))
    hazards = Hazard.query.order_by(Hazard.created_at.desc()).all()
    return render_template('investigation/investigation_form.html', hazards=hazards)

@app.route('/investigations/<iid>')
@require_login
def investigation_detail(iid):
    inv = Investigation.query.get_or_404(iid)
    return render_template('investigation/investigation_detail.html', inv=inv)

# ─── MOC ─────────────────────────────────────────────────────────────────────
@app.route('/moc')
@require_login
def moc_list():
    all_moc = MOC.query.order_by(MOC.created_at.desc()).all()
    return render_template('investigation/moc_list.html', mocs=all_moc)

@app.route('/moc/new', methods=['GET','POST'])
def new_moc():
    if request.method == 'POST':
        f = request.form
        m = MOC(id=new_id('MOC'),
                title=f['title'], description=f['description'],
                department_id=int(f['department_id']),
                change_type=f['change_type'],
                initiator=f['initiator'],
                planned_date=f['planned_date'],
                pre_change_risk=f.get('pre_change_risk',''),
                approval_status='Pending',
                implementation_status='Not Started')
        db.session.add(m)
        db.session.flush()
        # Auto-create hazard for pre-change risk
        hid = new_id('HAZ')
        h = Hazard(id=hid, source='MOC', linked_report_id=m.id,
                   department_id=int(f['department_id']),
                   classification='Organizational',
                   type_of_activity='Management of Change',
                   generic_hazard=f'MOC Risk: {f["title"]}',
                   specific_components=f.get('pre_change_risk',''),
                   consequences='To Be Assessed',
                   status='Open')
        db.session.add(h)
        m.hazard_id = hid
        # Auto-create Action in unified system — ICAO requirement
        moc_action = Action(
            id=new_id('ACT'),
            source='MOC',
            hazard_id=hid,
            linked_ref_id=m.id,
            description=f'Review and verify implementation of change: {f["title"]}',
            owner=f['initiator'],
            due_date=f.get('planned_date', ''),
            priority='High',
            status='Open'
        )
        db.session.add(moc_action)
        db.session.commit()
        flash(f'✓ MOC {m.id} created. Hazard {hid} and Action auto-generated.', 'success')
        return redirect(url_for('moc_list'))
    return render_template('investigation/moc_form.html')

@app.route('/moc/<mid>/update', methods=['POST'])
def update_moc(mid):
    m = MOC.query.get_or_404(mid)
    f = request.form
    m.approval_status       = f.get('approval_status', m.approval_status)
    m.approved_by           = f.get('approved_by', m.approved_by)
    m.implementation_status = f.get('implementation_status', m.implementation_status)
    m.post_change_review    = f.get('post_change_review', m.post_change_review)
    db.session.commit()
    flash('✓ MOC updated.', 'success')
    return redirect(url_for('moc_list'))

# ─── SPI ─────────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════
#  SPI — Safety Performance Indicators  (ICAO Annex 19 / Doc 9859)
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
#  SPI ENGINE — ICAO Annex 19 §6.3 / Doc 9859 Chapter 7
#  Statistical monitoring: Mean + Standard Deviation alert thresholds
#  Baseline collection mode → automatic transition to stat mode
#  Three ICAO calculation methods: COUNT / RATE / PERCENT
# ═══════════════════════════════════════════════════════════════════════════════

import math

def _spi_calc(ind, events, exposure, total_events):
    """
    ICAO three calculation methods:
      COUNT   : SPI = events
      RATE    : SPI = (events / exposure) × 1000
      PERCENT : SPI = (events / total_events) × 100
    """
    try:
        if ind.calc_type == 'COUNT':
            return float(events)
        elif ind.calc_type == 'PERCENT':
            return round(events / total_events * 100, 2) if total_events else 0.0
        else:  # RATE (default)
            return round(events / exposure * 1000, 4) if exposure else 0.0
    except Exception:
        return 0.0


def _spi_history(ind):
    """Return list of (year, month, value) sorted chronologically for all data."""
    rows = SPIData.query.filter_by(spi_id=ind.id).filter(
        SPIData.value.isnot(None)).order_by(
        SPIData.year, SPIData.month).all()
    return [(r.year, r.month, r.value) for r in rows]


def _spi_statistics(values):
    """Calculate mean and population standard deviation."""
    if not values:
        return 0.0, 0.0
    n    = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0
    variance = sum((v - mean) ** 2 for v in values) / n
    sd = math.sqrt(variance)
    return round(mean, 4), round(sd, 4)


def _spi_thresholds(ind, all_values=None):
    """
    ICAO Statistical Monitoring thresholds.
    Statistical mode (≥ baseline_months data points):
      L1 = Mean + 1 SD
      L2 = Mean + 2 SD
      L3 = Mean + 3 SD
    Baseline mode (insufficient data):
      Fall back to SPT +20% / +40% / +60%
    For PERCENT type: direction is reversed (lower = worse)
    """
    if all_values is None:
        history = _spi_history(ind)
        all_values = [v for _, _, v in history]

    baseline_needed = ind.baseline_months or 3
    is_pct = ind.calc_type == 'PERCENT'
    spt    = ind.spt_target or 0

    if len(all_values) >= baseline_needed:
        # Statistical mode — ICAO Mean ± SD
        mean, sd = _spi_statistics(all_values)
        if is_pct:
            l1 = max(0, round(mean - sd,     2))
            l2 = max(0, round(mean - 2 * sd, 2))
            l3 = max(0, round(mean - 3 * sd, 2))
        else:
            l1 = round(mean + sd,     2)
            l2 = round(mean + 2 * sd, 2)
            l3 = round(mean + 3 * sd, 2)
        return l1, l2, l3, mean, sd, True   # last two: mean, sd, is_stat_mode
    else:
        # Baseline mode — SPT-based fallback
        mean, sd = _spi_statistics(all_values) if all_values else (0.0, 0.0)
        if is_pct:
            l1 = round(spt * 0.90, 2)
            l2 = round(spt * 0.80, 2)
            l3 = round(spt * 0.70, 2)
        else:
            l1 = round(spt * 1.20, 2)
            l2 = round(spt * 1.40, 2)
            l3 = round(spt * 1.60, 2)
        return l1, l2, l3, mean, sd, False


def _spi_target(ind, all_values=None):
    """
    SPT = Safety Performance Target.
    ALWAYS returns ind.spt_target unchanged.
    SPT is fixed — defined by Safety Management, never auto-modified.
    
    improvement_target (shown separately on dashboard) =
      Avg × (1 − improvement_pct/100) for COUNT/RATE
      Avg × (1 + improvement_pct/100) for PERCENT
    """
    return ind.spt_target or 0.0


def _spi_improvement_target(ind, all_values=None):
    """
    ICAO improvement target — calculated from historical average.
    Shown as a separate line on the dashboard (not the SPT).
    Formula: Avg × (1 − improvement%) or Avg × (1 + improvement%) for %
    Falls back to SPT if insufficient data.
    """
    if all_values is None:
        history = _spi_history(ind)
        all_values = [v for _, _, v in history]

    improvement = (ind.improvement_pct or 5.0) / 100.0
    if len(all_values) >= 3:
        prev_avg = sum(all_values) / len(all_values)
        if ind.calc_type == 'PERCENT':
            return round(prev_avg * (1 + improvement), 2)
        else:
            return round(prev_avg * (1 - improvement), 2)
    return ind.spt_target or 0.0


def _spi_status(value, ind, all_values=None):
    """
    ICAO alert levels based on statistical thresholds.
    Returns (label, color, level 0-3)
    """
    l1, l2, l3, mean, sd, is_stat = _spi_thresholds(ind, all_values)
    spt    = ind.spt_target or 0
    is_pct = ind.calc_type == 'PERCENT'

    if is_pct:
        if value <= l3:   return ('🔴 CRITICAL',   '#dc2626', 3)
        elif value <= l2: return ('🟠 WARNING L2', '#ea580c', 2)
        elif value <= l1: return ('🟡 WATCH L1',   '#d97706', 1)
        elif value < spt: return ('🔵 BELOW SPT',  '#1d4ed8', 0)
        else:             return ('🟢 OK',          '#15803d', 0)
    else:
        if value >= l3:   return ('🔴 CRITICAL',   '#dc2626', 3)
        elif value >= l2: return ('🟠 WARNING L2', '#ea580c', 2)
        elif value >= l1: return ('🟡 WATCH L1',   '#d97706', 1)
        elif value > spt: return ('🔵 EXCEEDS SPT','#1d4ed8', 0)
        else:             return ('🟢 OK',          '#15803d', 0)


def _spi_trend(values_list):
    """
    3-point trend analysis.
    ↑ Increasing / ↓ Decreasing / → Stable
    """
    vals = [v for v in values_list if v is not None]
    if len(vals) < 2:
        return '— No trend'
    if vals[-1] > vals[-2] * 1.05:
        return '↑ Increasing'
    elif vals[-1] < vals[-2] * 0.95:
        return '↓ Decreasing'
    return '→ Stable'


def _spi_trigger_check(values_chronological, l1, l2, l3, is_pct=False):
    """
    ICAO alert trigger rules — detects abnormal safety trends.
    Returns triggered rule or None.
    (Thin wrapper — use _spi_trigger_detail for full month/value info.)
    """
    detail = _spi_trigger_detail(values_chronological, l1, l2, l3, is_pct)
    return detail['rule'] if detail else None


def _spi_trigger_detail(values_with_months, l1_current, l2_current, l3_current,
                        is_pct=False, spt=None):
    """
    ICAO alert trigger rules with EXACT MONTH identification.

    CORRECT ICAO LOGIC: For each month i, compute thresholds from
    months [0..i-1] (prior data only), then test month i against those
    prior thresholds. This prevents the spike itself from inflating the
    mean/SD and hiding the trigger.

    Requires a minimum of 2 prior points to compute meaningful statistics.
    Falls back to the passed-in l1/l2/l3 thresholds for the full dataset
    when insufficient prior data exists.

    values_with_months : list of (month_number, value) tuples, sorted asc.
    l1/l2/l3_current   : pre-calculated thresholds from full dataset
                         (used as fallback for the latest point).

    Returns dict or None:
      { 'rule', 'trigger_month', 'trigger_value', 'level', 'description' }
    Priority: A > B > C. Returns MOST RECENT trigger.
    """
    if not values_with_months:
        return None

    # Normalise
    if isinstance(values_with_months[0], (list, tuple)):
        pairs = [(int(x[0]), float(x[1]))
                 for x in values_with_months if x[1] is not None]
    else:
        pairs = [(i + 1, float(v))
                 for i, v in enumerate(values_with_months) if v is not None]

    if not pairs:
        return None

    months = [p[0] for p in pairs]
    vals   = [p[1] for p in pairs]
    n      = len(pairs)

    def above(v, thr):
        if thr is None:
            return False
        return (v <= thr) if is_pct else (v >= thr)

    def thresholds_for_prior(prior_vals, spt_fallback=None):
        """
        Compute L1/L2/L3 from prior values.
        - Needs >= 2 values with non-zero SD for statistical mode
        - If SD=0 or insufficient data, use SPT-based fallback:
            L1=SPT×1.2, L2=SPT×1.4, L3=SPT×1.6
        Returns (l1, l2, l3) — never None (always returns something usable)
        """
        if len(prior_vals) >= 2:
            m, s = _spi_statistics(prior_vals)
            if s > 0:
                if is_pct:
                    return (round(m - s, 4), round(m - 2*s, 4), round(m - 3*s, 4))
                return (round(m + s, 4), round(m + 2*s, 4), round(m + 3*s, 4))
        # Fall back to SPT-based thresholds
        if spt_fallback and spt_fallback > 0:
            if is_pct:
                return (spt_fallback*0.90, spt_fallback*0.80, spt_fallback*0.70)
            return (spt_fallback*1.20, spt_fallback*1.40, spt_fallback*1.60)
        # Last resort: use passed-in full-dataset thresholds
        return l1_current, l2_current, l3_current

    # For each month i, build its effective thresholds from prior data
    # Store per-month (l1, l2, l3)
    effective = []
    for i in range(n):
        prior = vals[:i]                    # everything BEFORE this month
        tl1, tl2, tl3 = thresholds_for_prior(prior, spt_fallback=spt)
        effective.append((tl1, tl2, tl3))

    # ── Rule A: any single point >= its own L3 ────────────────────────────
    rule_a_month = rule_a_val = None
    for i in range(n - 1, -1, -1):
        tl1, tl2, tl3 = effective[i]
        if tl3 is not None and above(vals[i], tl3):
            rule_a_month, rule_a_val = months[i], vals[i]
            break

    # ── Rule B: 2 consecutive >= their respective L2 ─────────────────────
    rule_b_month = rule_b_val = None
    for i in range(n - 1, 0, -1):
        _, tl2_i,  _ = effective[i]
        _, tl2_i1, _ = effective[i-1]
        if (tl2_i is not None and tl2_i1 is not None and
                above(vals[i], tl2_i) and above(vals[i-1], tl2_i1)):
            rule_b_month = months[i-1]
            rule_b_val   = vals[i-1]
            break

    # ── Rule C: 3 consecutive >= their respective L1 ─────────────────────
    rule_c_month = rule_c_val = None
    for i in range(n - 1, 1, -1):
        tl1_i,  _, _ = effective[i]
        tl1_i1, _, _ = effective[i-1]
        tl1_i2, _, _ = effective[i-2]
        if (tl1_i is not None and tl1_i1 is not None and tl1_i2 is not None and
                above(vals[i], tl1_i) and
                above(vals[i-1], tl1_i1) and
                above(vals[i-2], tl1_i2)):
            rule_c_month = months[i-2]
            rule_c_val   = vals[i-2]
            break

    # Return highest-priority result
    if rule_a_month is not None:
        _, _, tl3 = effective[months.index(rule_a_month)]
        return {
            'rule':          'A',
            'trigger_month': rule_a_month,
            'trigger_value': rule_a_val,
            'level':         'L3',
            'description':   (f'Rule A: One point ({rule_a_val:.3f}) exceeded '
                               f'L3 (Mean+3SD = {tl3:.3f})')
        }
    if rule_b_month is not None:
        idx = months.index(rule_b_month)
        _, tl2, _ = effective[idx]
        return {
            'rule':          'B',
            'trigger_month': rule_b_month,
            'trigger_value': rule_b_val,
            'level':         'L2',
            'description':   (f'Rule B: Two consecutive points exceeded '
                               f'L2 (Mean+2SD = {tl2:.3f})')
        }
    if rule_c_month is not None:
        idx = months.index(rule_c_month)
        tl1, _, _ = effective[idx]
        return {
            'rule':          'C',
            'trigger_month': rule_c_month,
            'trigger_value': rule_c_val,
            'level':         'L1',
            'description':   (f'Rule C: Three consecutive points exceeded '
                               f'L1 (Mean+1SD = {tl1:.3f})')
        }
    return None


def _spi_build_table(indicators, cur_year):
    """Build complete SPI table data for dashboard."""
    MONTHS = ['Jan','Feb','Mar','Apr','May','Jun',
              'Jul','Aug','Sep','Oct','Nov','Dec']
    table = []
    for ind in indicators:
        # Current year data
        month_vals = {}
        for d in SPIData.query.filter_by(spi_id=ind.id, year=cur_year).all():
            month_vals[d.month] = d.value if d.value is not None else (d.rate or 0.0)

        # All historical values (for statistics)
        all_history = _spi_history(ind)
        all_values  = [v for _, _, v in all_history]
        baseline_needed = ind.baseline_months or 3

        # Statistics
        l1, l2, l3, mean, sd, is_stat = _spi_thresholds(ind, all_values)
        target   = _spi_target(ind, all_values)

        # YTD + 3M avg
        sorted_months = sorted(month_vals)
        vals_yr  = [month_vals[m] for m in sorted_months]
        ytd      = round(sum(vals_yr) / len(vals_yr), 2) if vals_yr else 0.0
        recent   = vals_yr[-3:]
        avg3     = round(sum(recent) / len(recent), 2) if recent else 0.0
        trend    = _spi_trend(vals_yr[-3:])
        latest   = vals_yr[-1] if vals_yr else 0.0

        # SPT is FIXED — never auto-modified
        spt_fixed = ind.spt_target or 0.0
        # Improvement target — separate from SPT
        impr_target = _spi_improvement_target(ind, all_values)

        # Status
        status = _spi_status(latest, ind, all_values)

        # ICAO trigger check
        # Use all historical data (not just current year) to find real trigger month
        # Thresholds (l1,l2,l3) are already computed from all_values above
        all_history_pairs = [(m, v) for _, m, v in _spi_history(ind)]
        # Also include current-year data not in all_history (e.g. just logged)
        for sm in sorted_months:
            if not any(p[0] == sm for p in all_history_pairs):
                all_history_pairs.append((sm, month_vals[sm]))
        all_history_pairs.sort(key=lambda x: x[0])

        month_val_tuples = [(m, month_vals[m]) for m in sorted_months]
        trigger_detail = _spi_trigger_detail(
            month_val_tuples, l1, l2, l3, ind.calc_type == 'PERCENT',
            spt=ind.spt_target)
        trigger = trigger_detail['rule'] if trigger_detail else None

        # Extract exact escalation info AND persist a record
        if trigger_detail:
            escalation_month  = trigger_detail['trigger_month']
            escalation_year   = cur_year
            escalation_value  = trigger_detail['trigger_value']
            escalation_level  = trigger_detail['level']
            escalation_desc   = trigger_detail['description']
            # Compute threshold that was crossed
            esc_thr_map       = {'L3': l3, 'L2': l2, 'L1': l1}
            escalation_threshold = esc_thr_map.get(escalation_level, l1)
            escalation_diff   = (round(escalation_value - escalation_threshold, 4)
                                 if escalation_threshold else None)
            # Persist escalation record (idempotent)
            try:
                _spi_record_escalation(ind, trigger_detail, l1, l2, l3, mean, sd)
                db.session.commit()
            except Exception:
                db.session.rollback()
        else:
            escalation_month     = None
            escalation_year      = cur_year
            escalation_value     = None
            escalation_level     = None
            escalation_desc      = None
            escalation_threshold = None
            escalation_diff      = None

        # Baseline progress
        months_collected = len(all_values)
        baseline_pct     = min(100, int(months_collected / baseline_needed * 100))

        # Dept info
        dept_codes, dept_names = [], []
        for did in (ind.department_ids or '').split(','):
            try:
                d = Department.query.get(int(did.strip()))
                if d:
                    dept_codes.append(d.code)
                    dept_names.append(d.name)
            except Exception:
                pass

        last_month = max(month_vals.keys()) if month_vals else None

        # Linked actions for this SPI indicator
        spi_actions = Action.query.filter_by(spi_id=ind.id).order_by(
            Action.created_at.desc()).all()

        table.append(dict(
            spi_actions=spi_actions,
            ind=ind,
            month_vals=month_vals,
            ytd=ytd, avg3=avg3, trend=trend,
            status=status, trigger=trigger,
            trigger_detail=trigger_detail,
            # Exact escalation — the REAL month the threshold was crossed
            escalation_month=escalation_month,
            escalation_year=escalation_year,
            escalation_value=escalation_value,
            escalation_level=escalation_level,
            escalation_desc=escalation_desc,
            escalation_threshold=escalation_threshold,
            escalation_diff=escalation_diff,
            latest_val=latest,
            l1=l1, l2=l2, l3=l3,
            mean=mean, sd=round(sd, 4),
            spt=spt_fixed,
            impr_target=impr_target,
            target=spt_fixed,
            is_stat=is_stat,
            all_values=all_values,
            months_collected=months_collected,
            baseline_needed=baseline_needed,
            baseline_pct=baseline_pct,
            depts=', '.join(dept_codes),
            dept_names=', '.join(dept_names),
            last_month=last_month,
        ))
    return table, MONTHS


def _spi_record_escalation(ind, trigger_detail, l1, l2, l3, mean, sd):
    """
    Persist an SPIEscalation record when a trigger is detected.
    Idempotent — checks if this trigger month/rule/indicator already recorded.
    Returns the SPIEscalation instance (new or existing).
    """
    if not trigger_detail:
        return None

    rule  = trigger_detail['rule']
    month = trigger_detail['trigger_month']
    level = trigger_detail['level']
    value = trigger_detail['trigger_value']
    desc  = trigger_detail['description']

    # Which threshold was exceeded?
    thr_map = {'L3': l3, 'L2': l2, 'L1': l1}
    threshold = thr_map.get(level, l1)

    # Idempotency: don't duplicate for same indicator+month+rule
    existing = SPIEscalation.query.filter_by(
        spi_id=ind.id,
        trigger_month=month,
        trigger_rule=rule,
        alert_level=level
    ).first()
    if existing:
        return existing

    esc = SPIEscalation(
        spi_id          = ind.id,
        trigger_month   = month,
        trigger_year    = datetime.now().year,
        trigger_rule    = rule,
        alert_level     = level,
        spi_value       = round(value, 4),
        threshold_value = round(threshold, 4) if threshold else None,
        mean_value      = round(mean, 4),
        sd_value        = round(sd, 4),
        description     = desc,
        status          = 'Open',
    )
    db.session.add(esc)
    db.session.flush()   # get ID without committing
    return esc


def spi_auto_update(source_type, department_id, category, year, month,
                    report_id=None):
    """
    Auto-match a submitted report to SPIs and increment event count.
    
    DEDUPLICATION: Uses report_id to track which reports have already
    been counted. If report_id is provided and already in entry.notes
    (as a comma-separated log), the report is NOT counted again.
    
    source_type : 'hazard_report' | 'asr' | 'audit'
    report_id   : unique ID of the source record (e.g. 'HR-SMS-01')
    """
    matched = SPIIndicator.query.filter_by(
        auto_source=source_type, active=True).all()

    for ind in matched:
        # Category match (empty auto_category matches all)
        if ind.auto_category:
            if ind.auto_category.lower() not in (category or '').lower():
                continue
        # Department match
        dept_ids = [x.strip() for x in (ind.department_ids or '').split(',')]
        if str(department_id) not in dept_ids and '' not in dept_ids:
            continue

        entry = SPIData.query.filter_by(
            spi_id=ind.id, year=year, month=month).first()

        if entry:
            # DEDUPLICATION: check if this report was already counted
            already_counted = (
                report_id and
                entry.notes and
                report_id in entry.notes.split(',')
            )
            if already_counted:
                continue  # skip — already counted this report
            entry.events = (entry.events or 0) + 1
            # Log report_id to prevent future duplicate
            if report_id:
                existing = entry.notes or ''
                ids = [x for x in existing.split(',') if x]
                ids.append(report_id)
                entry.notes = ','.join(ids[-50:])  # keep last 50 IDs max
        else:
            entry = SPIData(
                spi_id=ind.id, year=year, month=month,
                events=1, exposure=1, total_events=1,
                source='auto',
                notes=report_id or ''
            )
            db.session.add(entry)

        # Recalculate SPI value
        entry.value = _spi_calc(
            ind, entry.events,
            entry.exposure or 1,
            entry.total_events or entry.events
        )
        entry.rate = entry.value  # legacy compat

        # Auto-transition to stat mode when baseline complete
        all_vals = [r.value for r in SPIData.query.filter_by(spi_id=ind.id).all()
                    if r.value is not None]
        if len(all_vals) >= (ind.baseline_months or 3) and not ind.stat_mode:
            ind.stat_mode = True

    db.session.commit()


@app.route('/spi', methods=['GET','POST'])
@require_login
def spi():
    """SPI Dashboard — ICAO Annex 19 §6.3 / Doc 9859 Chapter 7."""
    cur_year = datetime.now().year
    dept_f   = request.args.get('dept', '')

    if request.method == 'POST':
        f        = request.form
        ind      = SPIIndicator.query.get_or_404(int(f['spi_id']))
        year     = int(f.get('year', cur_year))
        month    = int(f['month'])
        events   = int(f.get('events', 0))
        exposure = float(f.get('exposure', 1) or 1)
        total_ev = int(f.get('total_events', events) or events)

        entry = SPIData.query.filter_by(
            spi_id=ind.id, year=year, month=month).first()
        if entry:
            entry.events      = events
            entry.exposure    = exposure
            entry.total_events = total_ev
        else:
            entry = SPIData(spi_id=ind.id, year=year, month=month,
                            events=events, exposure=exposure,
                            total_events=total_ev, source='manual')
            db.session.add(entry)

        entry.value   = _spi_calc(ind, events, exposure, total_ev)
        entry.rate    = entry.value
        entry.flights = int(exposure)
        db.session.flush()

        # Auto stat-mode transition
        all_vals = [r.value for r in SPIData.query.filter_by(spi_id=ind.id).all()
                    if r.value is not None]
        if len(all_vals) >= (ind.baseline_months or 3) and not ind.stat_mode:
            ind.stat_mode = True

        db.session.commit()
        flash(f'✓ {ind.code} logged: {month}/{year} = {entry.value:.3f}', 'success')
        return redirect(url_for('spi', dept=dept_f))

    indicators = SPIIndicator.query.filter_by(active=True).all()
    if dept_f:
        indicators = [i for i in indicators
                      if dept_f in (i.department_ids or '').split(',')]

    table, MONTHS = _spi_build_table(indicators, cur_year)

    critical = sum(1 for r in table if r['status'][2] >= 3)
    warning  = sum(1 for r in table if r['status'][2] == 2)
    watch    = sum(1 for r in table if r['status'][2] == 1)
    ok_count = sum(1 for r in table
                   if r['status'][2] == 0 and r['latest_val'] <= (r['ind'].spt_target or 999))

    # Any triggered ICAO rules?
    triggered = [r for r in table if r['trigger']]

    return render_template('spi/spi_dashboard.html',
        table=table, MONTHS=MONTHS,
        indicators=SPIIndicator.query.filter_by(active=True).all(),
        dept_f=dept_f, cur_year=cur_year,
        critical=critical, warning=warning, watch=watch, ok_count=ok_count,
        triggered=triggered,
        enumerate=enumerate)


@app.route('/spi/actions')
def spi_actions_list():
    """List of all SPI-linked actions with full escalation traceability."""
    status_f = request.args.get('status', '')
    dept_f   = request.args.get('dept', '')
    level_f  = request.args.get('level', '')

    q = Action.query.filter(Action.spi_id.isnot(None))
    if status_f: q = q.filter_by(status=status_f)
    if level_f:  q = q.filter_by(spi_alert_level=level_f)
    actions = q.order_by(Action.spi_alert_year.desc(),
                         Action.spi_alert_month.desc()).all()

    # For each action, load or recompute escalation data
    action_data = []
    for a in actions:
        esc = None
        if a.spi_escalation_id:
            esc = SPIEscalation.query.get(a.spi_escalation_id)
        if not esc and a.spi_id and a.spi_alert_month:
            esc = SPIEscalation.query.filter_by(
                spi_id=a.spi_id,
                trigger_month=a.spi_alert_month
            ).first()
        action_data.append({'action': a, 'esc': esc})

    return render_template('spi/spi_actions_list.html',
                           action_data=action_data,
                           actions=actions,
                           status_f=status_f,
                           dept_f=dept_f, level_f=level_f)

@app.route('/spi/escalation/<int:esc_id>')
def spi_escalation_detail(esc_id):
    """Escalation event detail — the source record for SPI actions."""
    esc = SPIEscalation.query.get_or_404(esc_id)
    ind = SPIIndicator.query.get(esc.spi_id) if esc.spi_id else None
    actions = Action.query.filter_by(spi_id=esc.spi_id,
                                     spi_alert_month=esc.trigger_month,
                                     spi_alert_year=esc.trigger_year).all()
    MONTHS = ['January','February','March','April','May','June',
              'July','August','September','October','November','December']
    return render_template('spi/spi_escalation_detail.html',
                           esc=esc, ind=ind, actions=actions,
                           MONTHS=MONTHS, now=datetime.utcnow())

@app.route('/spi/action-report/<action_id>')
def spi_action_report(action_id):
    """
    Print-ready SPI Alert Mitigation Report.

    Escalation data priority:
      1. Linked SPIEscalation record (most accurate — created when dashboard loaded)
      2. Recompute from SPI history using stored spi_alert_month (reliable fallback)
      3. Action's own spi_alert_* fields (last resort)

    This ensures the report ALWAYS shows the real trigger month,
    not the action creation date.
    """
    a   = Action.query.filter_by(id=action_id).first_or_404()
    ind = SPIIndicator.query.get(a.spi_id) if a.spi_id else None

    MONTHS = ['January','February','March','April','May','June',
              'July','August','September','October','November','December']

    # ── Step 1: try linked escalation record ─────────────────────────────
    esc = None
    if a.spi_escalation_id:
        esc = SPIEscalation.query.get(a.spi_escalation_id)

    # ── Step 2: search existing escalation records ────────────────────────
    if not esc and a.spi_id and a.spi_alert_month:
        esc = SPIEscalation.query.filter_by(
            spi_id       = a.spi_id,
            trigger_month= a.spi_alert_month,
            trigger_rule = a.spi_trigger_rule or ''
        ).first()
        if not esc:
            # also try without rule filter (broader match)
            esc = SPIEscalation.query.filter_by(
                spi_id        = a.spi_id,
                trigger_month = a.spi_alert_month
            ).first()

    # ── Step 3: recompute from live SPI data ──────────────────────────────
    # This is the guaranteed fallback — uses the stored trigger month and
    # recomputes what the SPI value and thresholds were at that point.
    esc_computed = None
    if not esc and ind and a.spi_alert_month:
        try:
            history = _spi_history(ind)
            all_vals = [v for _, _, v in history]
            l1, l2, l3, mean, sd, is_stat = _spi_thresholds(ind, all_vals)

            # Find the SPI value for the stored trigger month
            from models import SPIData
            dp = SPIData.query.filter_by(
                spi_id = ind.id,
                year   = a.spi_alert_year or datetime.now().year,
                month  = a.spi_alert_month
            ).first()
            spi_val_at_trigger = dp.value if dp and dp.value else None

            # Which threshold was triggered
            level = a.spi_alert_level or 'L1'
            thr_map  = {'L3': l3, 'L2': l2, 'L1': l1}
            thr_val  = thr_map.get(level)
            diff_val = round(spi_val_at_trigger - thr_val, 4)                        if spi_val_at_trigger and thr_val else None
            rule_desc = {
                'A': f'Rule A: One point exceeded L3 (Mean+3SD = {l3:.4f})',
                'B': f'Rule B: Two consecutive exceeded L2 (Mean+2SD = {l2:.4f})',
                'C': f'Rule C: Three consecutive exceeded L1 (Mean+1SD = {l1:.4f})',
            }.get(a.spi_trigger_rule or '', '')

            esc_computed = {
                'trigger_month'  : a.spi_alert_month,
                'trigger_year'   : a.spi_alert_year or datetime.now().year,
                'trigger_rule'   : a.spi_trigger_rule,
                'alert_level'    : level,
                'spi_value'      : spi_val_at_trigger,
                'threshold_value': round(thr_val, 4) if thr_val else None,
                'mean_value'     : round(mean, 4),
                'sd_value'       : round(sd, 4),
                'description'    : rule_desc,
                'diff_value'     : diff_val,
            }
        except Exception as ex:
            esc_computed = None

    return render_template('spi/spi_action_report.html',
                           a=a, ind=ind, esc=esc,
                           esc_computed=esc_computed,
                           now=datetime.utcnow(), MONTHS=MONTHS)

@app.route('/spi/indicators', methods=['GET','POST'])
@require_login
def spi_indicators():
    """Manage SPI indicator definitions."""
    if request.method == 'POST':
        f        = request.form
        dept_ids = ','.join(request.form.getlist('department_ids'))
        ind = SPIIndicator(
            code            = f['code'].upper().strip(),
            name            = f['name'],
            department_ids  = dept_ids,
            category        = f.get('category',''),
            description     = f.get('description',''),
            calc_type       = f.get('calc_type','RATE'),
            exposure_type   = f.get('exposure_type','Flights'),
            unit            = f.get('unit',''),
            frequency       = f.get('frequency','Monthly'),
            spt_target      = float(f['spt_target']) if f.get('spt_target') else None,
            improvement_pct = float(f['improvement_pct']) if f.get('improvement_pct') else 5.0,
            baseline_months = int(f['baseline_months']) if f.get('baseline_months') else 3,
            auto_source     = f.get('auto_source','manual'),
            auto_category   = f.get('auto_category',''),
            active          = True,
            stat_mode       = False
        )
        db.session.add(ind)
        db.session.commit()
        flash(f'✓ SPI Indicator {ind.code} created. Collecting baseline ({ind.baseline_months} months needed).', 'success')
        return redirect(url_for('spi_indicators'))

    indicators = SPIIndicator.query.order_by(SPIIndicator.code).all()
    return render_template('spi/spi_indicators.html', indicators=indicators)


@app.route('/spi/indicators/<int:iid>/delete', methods=['POST'])
def spi_delete_indicator(iid):
    ind = SPIIndicator.query.get_or_404(iid)
    db.session.delete(ind)
    db.session.commit()
    flash(f'✓ Indicator {ind.code} deleted.', 'success')
    return redirect(url_for('spi_indicators'))


@app.route('/spi/evidence/<filename>')
def spi_evidence_file(filename):
    """Serve uploaded evidence files."""
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/spi/indicators/<int:iid>/toggle', methods=['POST'])
def spi_toggle_indicator(iid):
    ind = SPIIndicator.query.get_or_404(iid)
    ind.active = not ind.active
    db.session.commit()
    flash(f'✓ {ind.code} {"activated" if ind.active else "deactivated"}.', 'success')
    return redirect(url_for('spi_indicators'))


# ─── Safety Promotion ─────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════
#  SAFETY PROMOTION MODULE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/safety-promotion')
@require_login
def safety_promotion():
    bulletins   = SafetyBulletin.query.filter_by(status='Active').order_by(SafetyBulletin.created_at.desc()).limit(5).all()
    newsletters = SafetyNewsletter.query.filter_by(status='Published').order_by(SafetyNewsletter.created_at.desc()).limit(4).all()
    trainings   = Training.query.order_by(Training.created_at.desc()).limit(8).all()
    campaigns   = SafetyCampaign.query.filter_by(status='Active').order_by(SafetyCampaign.created_at.desc()).limit(4).all()
    lessons     = LessonLearned.query.order_by(LessonLearned.created_at.desc()).limit(4).all()
    surveys     = SafetySurvey.query.filter_by(status='Active').all()
    overdue_training = Training.query.filter_by(status='Expired').count()
    due_soon    = Training.query.filter_by(status='Due Soon').count()
    emails_sent = EmailLog.query.count()
    dist_count  = DistributionList.query.filter_by(is_active=True).count()
    avg_response_rate = 0
    surveyed = SafetySurvey.query.filter(SafetySurvey.target_count > 0).all()
    if surveyed:
        avg_response_rate = round(sum(
            (s.response_count or 0) / s.target_count * 100 for s in surveyed
        ) / len(surveyed), 1)
    return render_template('spi/safety_promotion.html',
                           bulletins=bulletins, newsletters=newsletters,
                           trainings=trainings, campaigns=campaigns,
                           lessons=lessons, surveys=surveys,
                           overdue_training=overdue_training, due_soon=due_soon,
                           emails_sent=emails_sent, dist_count=dist_count,
                           avg_response_rate=avg_response_rate)

@app.route('/safety-promotion/bulletins')
@require_login
def sp_bulletins():
    status_f = request.args.get('status','')
    type_f   = request.args.get('type','')
    q = SafetyBulletin.query
    if status_f: q = q.filter_by(status=status_f)
    if type_f:   q = q.filter_by(bulletin_type=type_f)
    bulletins = q.order_by(SafetyBulletin.created_at.desc()).all()
    return render_template('spi/sp_bulletins.html', bulletins=bulletins, status_f=status_f, type_f=type_f)

@app.route('/safety-promotion/bulletin/new', methods=['GET','POST'])
def new_bulletin():
    if request.method == 'POST':
        f = request.form
        bid = new_id('SB')
        ef = None
        if 'attachment' in request.files:
            att = request.files['attachment']
            if att and att.filename and allowed_file(att.filename):
                from werkzeug.utils import secure_filename
                ef = f'{bid}_{secure_filename(att.filename)}'
                att.save(os.path.join(app.config['UPLOAD_FOLDER'], ef))
        b = SafetyBulletin(id=bid, ref_number=f.get('ref_number',bid), title=f['title'],
            bulletin_type=f.get('bulletin_type','Bulletin'), severity=f.get('severity','Information'),
            department_id=int(f['department_id']) if f.get('department_id') else None,
            issue_date=f.get('issue_date',datetime.now().strftime('%Y-%m-%d')),
            content=f['content'], recommendations=f.get('recommendations',''),
            issued_by=f.get('issued_by','Safety Department'), status='Active',
            attachment=ef, linked_hazard_id=f.get('linked_hazard_id') or None)
        db.session.add(b); db.session.commit()
        flash(f'✓ Bulletin {bid} published.', 'success')
        return redirect(url_for('sp_bulletins'))
    return render_template('spi/sp_bulletin_form.html',
                           now=datetime.utcnow())

@app.route('/safety-promotion/bulletin/<bid>')
def sp_bulletin_detail(bid):
    b = SafetyBulletin.query.get_or_404(bid)
    return render_template('spi/sp_bulletin_detail.html', b=b, now=datetime.utcnow())

@app.route('/safety-promotion/bulletin/<bid>/archive', methods=['POST'])
def sp_bulletin_archive(bid):
    b = SafetyBulletin.query.get_or_404(bid)
    b.status = 'Archived'; db.session.commit()
    flash('✓ Bulletin archived.', 'success')
    return redirect(url_for('sp_bulletins'))

@app.route('/safety-promotion/newsletters')
@require_login
def sp_newsletters():
    newsletters = SafetyNewsletter.query.order_by(SafetyNewsletter.created_at.desc()).all()
    return render_template('spi/sp_newsletters.html', newsletters=newsletters)

@app.route('/safety-promotion/newsletter/new', methods=['GET','POST'])
def sp_newsletter_new():
    if request.method == 'POST':
        f = request.form
        nid_str = new_id('NL')
        ef = None
        if 'attachment' in request.files:
            att = request.files['attachment']
            if att and att.filename and allowed_file(att.filename):
                from werkzeug.utils import secure_filename
                ef = f'{nid_str}_{secure_filename(att.filename)}'
                att.save(os.path.join(app.config['UPLOAD_FOLDER'], ef))
        n = SafetyNewsletter(ref_number=f.get('ref_number',nid_str), title=f['title'],
            issue_number=f.get('issue_number',''),
            department_id=int(f['department_id']) if f.get('department_id') else None,
            issue_date=f.get('issue_date',datetime.now().strftime('%Y-%m-%d')),
            author=f.get('author','Safety Department'), summary=f.get('summary',''),
            content=f.get('content',''), status=f.get('status','Draft'), attachment=ef)
        db.session.add(n); db.session.commit()
        flash(f'✓ Newsletter saved.', 'success')
        return redirect(url_for('sp_newsletters'))
    return render_template('spi/sp_newsletter_form.html',
                           now=datetime.utcnow())

@app.route('/safety-promotion/newsletter/<int:nid>')
def sp_newsletter_detail(nid):
    n = SafetyNewsletter.query.get_or_404(nid)
    return render_template('spi/sp_newsletter_detail.html', n=n, now=datetime.utcnow())

@app.route('/safety-promotion/newsletter/<int:nid>/publish', methods=['POST'])
def sp_newsletter_publish(nid):
    n = SafetyNewsletter.query.get_or_404(nid)
    n.status = 'Published'; db.session.commit()
    flash('✓ Newsletter published.', 'success')
    return redirect(url_for('sp_newsletters'))

@app.route('/safety-promotion/training')
@require_login
def sp_training():
    """Training records list with auto status refresh."""
    dept_f   = request.args.get('dept', '')
    status_f = request.args.get('status', '')
    type_f   = request.args.get('type', '')

    # Auto-refresh expired / due soon statuses
    from datetime import date as dt_date, timedelta
    today = dt_date.today()
    due_threshold = (today + timedelta(days=60)).isoformat()
    today_str = today.isoformat()
    for t in Training.query.filter(
            Training.status.in_(['Scheduled','In Progress','Completed','Current'])).all():
        if t.expiry_date and t.status not in ('Cancelled',):
            if t.expiry_date < today_str:
                t.status = 'Expired'
            elif t.expiry_date < due_threshold and t.status == 'Completed':
                t.status = 'Due Soon'
    db.session.commit()

    q = Training.query
    if dept_f:   q = q.filter_by(department_id=int(dept_f))
    if status_f: q = q.filter_by(status=status_f)
    if type_f:   q = q.filter_by(training_type=type_f)
    trainings = q.order_by(Training.created_at.desc()).all()

    stats = {
        'total':     Training.query.count(),
        'scheduled': Training.query.filter_by(status='Scheduled').count(),
        'in_progress':Training.query.filter_by(status='In Progress').count(),
        'completed': Training.query.filter_by(status='Completed').count(),
        'due_soon':  Training.query.filter(Training.status.in_(['Due Soon','Current'])).count(),
        'expired':   Training.query.filter_by(status='Expired').count(),
        'overdue':   Training.query.filter_by(status='Overdue').count(),
    }
    return render_template('spi/sp_training.html', trainings=trainings, stats=stats,
                           dept_f=dept_f, status_f=status_f, type_f=type_f)


@app.route('/safety-promotion/training/new', methods=['GET', 'POST'])
def new_training():
    if request.method == 'POST':
        f = request.form
        cert = _save_upload('certificate', f'CERT_')
        evid = _save_upload('evidence', f'EV_')
        t = Training(
            employee_name    = f.get('employee_name', ''),
            employee_id      = f.get('employee_id', ''),
            department_id    = int(f['department_id']) if f.get('department_id') else None,
            position         = f.get('position', ''),
            training_type    = f.get('training_type', 'SMS Training'),
            training_program = f.get('training_program', ''),
            course_code      = f.get('course_code', ''),
            instructor       = f.get('instructor', ''),
            location         = f.get('location', ''),
            scheduled_date   = f.get('scheduled_date', ''),
            training_date    = f.get('training_date', ''),
            completion_date  = f.get('completion_date', ''),
            expiry_date      = f.get('expiry_date', ''),
            duration_hours   = float(f['duration_hours']) if f.get('duration_hours') else None,
            status           = f.get('status', 'Scheduled'),
            certificate      = cert,
            evidence         = evid,
            is_recurrent     = 'is_recurrent' in f,
            recurrence_months= int(f['recurrence_months']) if f.get('recurrence_months') else None,
            notes            = f.get('notes', ''),
        )
        db.session.add(t)
        db.session.commit()
        flash(f'✓ Training record saved for {t.employee_name}.', 'success')
        return redirect(url_for('sp_training'))
    return render_template('spi/sp_training_form.html', now=datetime.utcnow(), editing=False)


@app.route('/safety-promotion/training/<int:tid>', methods=['GET', 'POST'])
def sp_training_detail(tid):
    """View and edit a single training record."""
    t = Training.query.get_or_404(tid)
    if request.method == 'POST':
        f = request.form
        action = f.get('action', 'update')

        if action == 'delete':
            db.session.delete(t)
            db.session.commit()
            flash('Training record deleted.', 'success')
            return redirect(url_for('sp_training'))

        # Handle file uploads
        new_cert = _save_upload('certificate', 'CERT_')
        new_evid = _save_upload('evidence', 'EV_')

        t.employee_name     = f.get('employee_name', t.employee_name)
        t.employee_id       = f.get('employee_id', t.employee_id)
        t.department_id     = int(f['department_id']) if f.get('department_id') else t.department_id
        t.position          = f.get('position', t.position)
        t.training_type     = f.get('training_type', t.training_type)
        t.training_program  = f.get('training_program', t.training_program)
        t.course_code       = f.get('course_code', t.course_code)
        t.instructor        = f.get('instructor', t.instructor)
        t.location          = f.get('location', t.location)
        t.scheduled_date    = f.get('scheduled_date', t.scheduled_date)
        t.training_date     = f.get('training_date', t.training_date)
        t.completion_date   = f.get('completion_date', t.completion_date)
        t.expiry_date       = f.get('expiry_date', t.expiry_date)
        t.duration_hours    = float(f['duration_hours']) if f.get('duration_hours') else t.duration_hours
        t.status            = f.get('status', t.status)
        t.is_recurrent      = 'is_recurrent' in f
        t.recurrence_months = int(f['recurrence_months']) if f.get('recurrence_months') else t.recurrence_months
        t.notes             = f.get('notes', t.notes)
        if new_cert: t.certificate = new_cert
        if new_evid: t.evidence    = new_evid
        t.updated_at = datetime.utcnow()
        db.session.commit()
        flash('✓ Training record updated.', 'success')
        return redirect(url_for('sp_training_detail', tid=tid))
    return render_template('spi/sp_training_detail.html', t=t, now=datetime.utcnow())


@app.route('/safety-promotion/training/export/xlsx')
def sp_training_export_xlsx():
    """Export training records to Excel with formatting."""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from flask import send_file

    dept_f   = request.args.get('dept', '')
    status_f = request.args.get('status', '')
    q = Training.query
    if dept_f:   q = q.filter_by(department_id=int(dept_f))
    if status_f: q = q.filter_by(status=status_f)
    records = q.order_by(Training.status, Training.expiry_date).all()

    wb = Workbook()
    ws = wb.active
    ws.title = 'Training Records'

    # Header styling
    navy   = PatternFill('solid', start_color='0F1C3F')
    gold   = PatternFill('solid', start_color='C9A84C')
    red_f  = PatternFill('solid', start_color='FEE2E2')
    amber_f= PatternFill('solid', start_color='FEF9C3')
    green_f= PatternFill('solid', start_color='DCFCE7')
    blue_f = PatternFill('solid', start_color='DBEAFE')
    white_f= Font(color='FFFFFF', bold=True, name='Arial')
    bold_f = Font(bold=True, name='Arial')
    std_f  = Font(name='Arial')
    center = Alignment(horizontal='center', vertical='center')
    left   = Alignment(horizontal='left', vertical='center', wrap_text=True)
    thin   = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'),  bottom=Side(style='thin')
    )

    # Title row
    ws.merge_cells('A1:L1')
    ws['A1'] = 'JORDAN AVIATION — SAFETY TRAINING RECORDS'
    ws['A1'].font = Font(name='Arial', bold=True, size=14, color='FFFFFF')
    ws['A1'].fill = navy
    ws['A1'].alignment = center

    # Subtitle
    ws.merge_cells('A2:L2')
    ws['A2'] = f'Generated: {datetime.utcnow().strftime("%d %b %Y")}   |   Total Records: {len(records)}'
    ws['A2'].font = Font(name='Arial', size=10, italic=True, color='C9A84C')
    ws['A2'].fill = PatternFill('solid', start_color='0F1C3F')
    ws['A2'].alignment = center

    # Column headers
    headers = [
        ('Employee Name', 22), ('Employee ID', 12), ('Department', 18),
        ('Position', 18), ('Training Type', 20), ('Program', 28),
        ('Instructor', 18), ('Scheduled', 12), ('Completion', 12),
        ('Expiry Date', 12), ('Status', 14), ('Certificate', 14)
    ]
    for col, (hdr, width) in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col, value=hdr)
        cell.font = white_f
        cell.fill = PatternFill('solid', start_color='1D4ED8')
        cell.alignment = center
        cell.border = thin
        ws.column_dimensions[get_column_letter(col)].width = width

    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 18
    ws.row_dimensions[3].height = 20
    ws.freeze_panes = 'A4'

    # Data rows
    STATUS_FILLS = {
        'Expired':    red_f,
        'Overdue':    red_f,
        'Due Soon':   amber_f,
        'Completed':  green_f,
        'Scheduled':  blue_f,
        'In Progress':blue_f,
        'Cancelled':  PatternFill('solid', start_color='F3F4F6'),
    }
    for row_n, t in enumerate(records, 4):
        fill = STATUS_FILLS.get(t.status, PatternFill())
        row_data = [
            t.employee_name or '',
            t.employee_id or '',
            t.department.name if t.department else '',
            t.position or '',
            t.training_type or '',
            t.training_program or '',
            t.instructor or '',
            t.scheduled_date or t.training_date or '',
            t.completion_date or '',
            t.expiry_date or '',
            t.status or '',
            '✓ Uploaded' if t.certificate else '✗ Missing',
        ]
        for col, val in enumerate(row_data, 1):
            cell = ws.cell(row=row_n, column=col, value=val)
            cell.font = std_f
            cell.border = thin
            cell.alignment = left
            if col in (11, 12):  # status + cert cols
                cell.fill = fill
                cell.alignment = center
        ws.row_dimensions[row_n].height = 16

    # Summary sheet
    ws2 = wb.create_sheet('Summary')
    ws2.merge_cells('A1:C1')
    ws2['A1'] = 'Training Status Summary'
    ws2['A1'].font = Font(name='Arial', bold=True, size=12, color='FFFFFF')
    ws2['A1'].fill = navy
    ws2['A1'].alignment = center
    ws2.column_dimensions['A'].width = 22
    ws2.column_dimensions['B'].width = 14
    ws2.column_dimensions['C'].width = 14

    statuses = ['Scheduled','In Progress','Completed','Due Soon','Expired','Overdue','Cancelled']
    ws2.cell(row=2, column=1, value='Status').font = bold_f
    ws2.cell(row=2, column=2, value='Count').font   = bold_f
    ws2.cell(row=2, column=3, value='% of Total').font = bold_f
    for i, st in enumerate(statuses, 3):
        cnt = sum(1 for r in records if r.status == st)
        ws2.cell(row=i, column=1, value=st)
        ws2.cell(row=i, column=2, value=cnt)
        ws2.cell(row=i, column=3, value=f'=B{i}/B{3+len(statuses)}' if cnt else 0)
        if st in STATUS_FILLS:
            for col in range(1, 4):
                ws2.cell(row=i, column=col).fill = STATUS_FILLS[st]
    total_row = 3 + len(statuses)
    ws2.cell(row=total_row, column=1, value='TOTAL').font = bold_f
    ws2.cell(row=total_row, column=2, value=f'=SUM(B3:B{total_row-1})').font = bold_f

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f'Training_Records_{datetime.now().strftime("%Y%m%d")}.xlsx'
    return send_file(buf, as_attachment=True, download_name=fname,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/safety-promotion/surveys')
@require_login
def sp_surveys():
    surveys = SafetySurvey.query.order_by(SafetySurvey.created_at.desc()).all()
    return render_template('spi/sp_surveys.html', surveys=surveys)

@app.route('/safety-promotion/survey/new', methods=['GET','POST'])
def sp_survey_new():
    if request.method == 'POST':
        f = request.form
        import json
        questions = request.form.getlist('question')
        s = SafetySurvey(title=f['title'], survey_type=f.get('survey_type','Safety Culture Survey'),
            department_id=int(f['department_id']) if f.get('department_id') else None,
            start_date=f.get('start_date',''), end_date=f.get('end_date',''),
            description=f.get('description',''), questions=json.dumps([q for q in questions if q.strip()]),
            status='Draft', target_count=int(f.get('target_count',0)))
        db.session.add(s); db.session.commit()
        flash('✓ Survey created.', 'success')
        return redirect('/safety-promotion/surveys')
    return render_template('spi/sp_survey_form.html',
                           now=datetime.utcnow())

@app.route('/safety-promotion/survey/<int:sid>/activate', methods=['POST'])
def sp_survey_activate(sid):
    s = SafetySurvey.query.get_or_404(sid)
    s.status = 'Active'; db.session.commit()
    flash('✓ Survey activated.', 'success')
    return redirect('/safety-promotion/surveys')

@app.route('/safety-promotion/survey/<int:sid>/close', methods=['POST'])
def sp_survey_close(sid):
    s = SafetySurvey.query.get_or_404(sid)
    s.status = 'Closed'; db.session.commit()
    flash('✓ Survey closed.', 'success')
    return redirect('/safety-promotion/surveys')

@app.route('/safety-promotion/survey/<int:sid>/respond', methods=['POST'])
def sp_survey_respond(sid):
    s = SafetySurvey.query.get_or_404(sid)
    s.response_count = (s.response_count or 0) + 1; db.session.commit()
    flash('✓ Response recorded.', 'success')
    return redirect('/safety-promotion/surveys')

@app.route('/safety-promotion/campaigns')
@require_login
def sp_campaigns():
    campaigns = SafetyCampaign.query.order_by(SafetyCampaign.created_at.desc()).all()
    return render_template('spi/sp_campaigns.html', campaigns=campaigns)

@app.route('/safety-promotion/campaign/new', methods=['GET','POST'])
def sp_campaign_new():
    if request.method == 'POST':
        f = request.form
        ef = None
        if 'attachment' in request.files:
            att = request.files['attachment']
            if att and att.filename and allowed_file(att.filename):
                from werkzeug.utils import secure_filename
                ef = f'CAM_{secure_filename(att.filename)}'
                att.save(os.path.join(app.config['UPLOAD_FOLDER'], ef))
        sc = SafetyCampaign(title=f['title'], campaign_type=f.get('campaign_type','Monthly'),
            department_id=int(f['department_id']) if f.get('department_id') else None,
            start_date=f.get('start_date',''), end_date=f.get('end_date',''),
            description=f.get('description',''), objectives=f.get('objectives',''),
            status='Active', attachment=ef)
        db.session.add(sc); db.session.commit()
        flash('✓ Campaign created.', 'success')
        return redirect(url_for('sp_campaigns'))
    return render_template('spi/sp_campaign_form.html',
                           now=datetime.utcnow())

@app.route('/safety-promotion/lessons')
@require_login
def sp_lessons():
    cat_f=request.args.get('category',''); q_f=request.args.get('q','').strip()
    q = LessonLearned.query
    if cat_f: q = q.filter_by(category=cat_f)
    if q_f:   q = q.filter(LessonLearned.title.ilike(f'%{q_f}%')|LessonLearned.description.ilike(f'%{q_f}%'))
    lessons = q.order_by(LessonLearned.created_at.desc()).all()
    return render_template('spi/sp_lessons.html', lessons=lessons, cat_f=cat_f, q_f=q_f)

@app.route('/safety-promotion/lesson/new', methods=['GET','POST'])
@require_login
def sp_lesson_new():
    if request.method == 'POST':
        f = request.form
        lid = new_id('LL')
        ef = None
        if 'attachment' in request.files:
            att = request.files['attachment']
            if att and att.filename and allowed_file(att.filename):
                from werkzeug.utils import secure_filename
                ef = f'{lid}_{secure_filename(att.filename)}'
                att.save(os.path.join(app.config['UPLOAD_FOLDER'], ef))
        ll = LessonLearned(ref_number=f.get('ref_number',lid), title=f['title'],
            category=f.get('category','Incident'),
            department_id=int(f['department_id']) if f.get('department_id') else None,
            date=f.get('date',datetime.now().strftime('%Y-%m-%d')),
            author=f.get('author','Safety Department'), description=f.get('description',''),
            lesson=f.get('lesson',''), recommendations=f.get('recommendations',''),
            status='Published', attachment=ef, linked_hazard_id=f.get('linked_hazard_id') or None)
        db.session.add(ll); db.session.commit()
        flash(f'✓ Lesson Learned {lid} published.', 'success')
        return redirect(url_for('sp_lessons'))
    return render_template('spi/sp_lesson_form.html', now=datetime.utcnow())

# ── Bulletin PDF print ────────────────────────────────────────────────────────


@app.route('/safety-promotion/distribution')
@require_login
def distribution_list():
    depts = Department.query.order_by(Department.name).all()
    dept_f = request.args.get('dept', '')
    q = DistributionList.query
    if dept_f:
        q = q.filter_by(department_id=int(dept_f))
    recipients = q.order_by(DistributionList.name).all()
    total = DistributionList.query.filter_by(is_active=True).count()
    return render_template('spi/sp_distribution.html',
                           recipients=recipients, total=total, dept_f=dept_f, depts=depts)

@app.route('/safety-promotion/distribution/add', methods=['POST'])
@require_login
def distribution_add():
    f = request.form
    email = f.get('email', '').strip()
    if not email:
        flash('Email required.', 'error')
        return redirect(url_for('distribution_list'))
    if DistributionList.query.filter_by(email=email).first():
        flash(email + ' already in list.', 'warning')
        return redirect(url_for('distribution_list'))
    db.session.add(DistributionList(
        name=f.get('name','').strip(), email=email,
        department_id=int(f['department_id']) if f.get('department_id') else None,
        position=f.get('position','').strip(), is_active=True))
    db.session.commit()
    flash('Added ' + email, 'success')
    return redirect(url_for('distribution_list'))

@app.route('/safety-promotion/distribution/<int:rid>/toggle', methods=['POST'])
@require_login
def distribution_toggle(rid):
    r = DistributionList.query.get_or_404(rid)
    r.is_active = not r.is_active
    db.session.commit()
    flash(r.email + ' updated.', 'success')
    return redirect(url_for('distribution_list'))

@app.route('/safety-promotion/distribution/<int:rid>/delete', methods=['POST'])
@require_login
def distribution_delete(rid):
    r = DistributionList.query.get_or_404(rid)
    db.session.delete(r)
    db.session.commit()
    flash('Removed.', 'success')
    return redirect(url_for('distribution_list'))

@app.route('/safety-promotion/distribution/import', methods=['POST'])
@require_login
def distribution_import():
    added = skipped = 0
    for line in request.form.get('csv_text','').strip().splitlines():
        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 2: continue
        name, email = parts[0], parts[1]
        if not email or DistributionList.query.filter_by(email=email).first():
            skipped += 1; continue
        dept_id = int(parts[2]) if len(parts)>2 and parts[2].isdigit() else None
        db.session.add(DistributionList(name=name, email=email, department_id=dept_id,
                                        position=parts[3] if len(parts)>3 else ''))
        added += 1
    db.session.commit()
    flash('Imported ' + str(added) + ' (' + str(skipped) + ' skipped).', 'success')
    return redirect(url_for('distribution_list'))

@app.route('/safety-promotion/email-log')
@require_login
def email_log_list():
    logs = EmailLog.query.order_by(EmailLog.sent_at.desc()).limit(100).all()
    total_sent = EmailLog.query.filter_by(status='Sent').count()
    total_recv = db.session.query(db.func.sum(EmailLog.recipient_count)).scalar() or 0
    return render_template('spi/sp_email_log.html', logs=logs,
                           total_sent=total_sent, total_recipients=int(total_recv))

@app.route('/safety-promotion/bulletin/<bid>/send-email', methods=['POST'])
@require_login
def bulletin_send_email(bid):
    b = SafetyBulletin.query.get_or_404(bid)
    dept_ids = [int(d) for d in request.form.getlist('dept_ids') if d.isdigit()] or None
    to = get_recipients(dept_ids)
    if not to:
        flash('No recipients. Add to Distribution List first.', 'warning')
        return redirect(url_for('sp_bulletin_detail', bid=bid))
    sev = {'Critical':'#dc2626','High':'#ea580c','Information':'#1d4ed8'}.get(b.severity,'#374151')
    body = ('<div style="background:'+sev+';color:#fff;padding:6px 14px;border-radius:5px;font-size:12px;font-weight:700;display:inline-block;margin-bottom:12px">'
            +b.severity.upper()+' — '+(b.bulletin_type or '')+'</div>'
            +'<p>'+(b.content or '').replace('\n','<br>')+'</p>'
            +('<p style="margin-top:12px"><strong>Recommendations:</strong><br>'+(b.recommendations or '').replace('\n','<br>')+'</p>' if b.recommendations else ''))
    subj = '[Safety Bulletin] '+(b.ref_number or b.id)+' — '+b.title
    sent, err = send_email(to, subj, email_html(b.title,'Safety Bulletin — '+(b.ref_number or b.id), body,
                           b.ref_number or b.id, b.issue_date or b.created_at.strftime('%d %b %Y')))
    dept_lbl = 'All' if not dept_ids else ','.join(d.name for d in Department.query.filter(Department.id.in_(dept_ids)).all())
    db.session.add(EmailLog(subject=subj,content_type='Bulletin',content_ref=str(bid),
        sent_by=session.get('admin_name','System'),recipient_count=sent,
        dept_filter=dept_lbl, status='Sent' if not err else 'Failed',error_message=err))
    db.session.commit()
    flash('Emailed to '+str(sent)+' recipient(s).', 'success')
    return redirect(url_for('sp_bulletin_detail', bid=bid))

@app.route('/safety-promotion/newsletter/<int:nid>/send-email', methods=['POST'])
@require_login
def newsletter_send_email(nid):
    n = SafetyNewsletter.query.get_or_404(nid)
    dept_ids = [int(d) for d in request.form.getlist('dept_ids') if d.isdigit()] or None
    to = get_recipients(dept_ids)
    if not to:
        flash('No recipients.', 'warning')
        return redirect('/safety-promotion/newsletter/'+str(nid))
    subj = '[Safety Newsletter] '+n.title
    body = '<p>'+(n.summary or '').replace('\n','<br>')+'</p>'+('<div>'+(n.content or '').replace('\n','<br>')+'</div>' if n.content else '')
    sent, err = send_email(to, subj, email_html(n.title,'Safety Newsletter',body))
    dept_lbl = 'All' if not dept_ids else ','.join(d.name for d in Department.query.filter(Department.id.in_(dept_ids)).all())
    db.session.add(EmailLog(subject=subj,content_type='Newsletter',content_ref=str(nid),
        sent_by=session.get('admin_name','System'),recipient_count=sent,
        dept_filter=dept_lbl,status='Sent' if not err else 'Failed',error_message=err))
    db.session.commit()
    flash('Emailed to '+str(sent)+' recipient(s).', 'success')
    return redirect('/safety-promotion/newsletter/'+str(nid))

@app.route('/safety-promotion/lesson/<int:lid>/send-email', methods=['POST'])
@require_login
def lesson_send_email(lid):
    ll = LessonLearned.query.get_or_404(lid)
    recip = _get_dist_list()
    if not recip:
        flash('No recipients in distribution list.', 'warning')
        return redirect(f'/safety-promotion/lesson/{lid}')
    emails = [r.email for r in recip]
    body = (
        '<p><b>Category:</b> ' + (ll.category or '') +
        ' &nbsp;&middot;&nbsp; <b>Date:</b> ' + (ll.date or '') +
        '<br/><b>Author:</b> ' + (ll.author or 'Safety') + '</p>'
        '<hr style="border:none;border-top:1px solid #e5e7eb;margin:14px 0"/>'
        '<p>' + (ll.description or '').replace('\n','<br/>') + '</p>'
        + ('<p><b>Lesson:</b><br/>' + (ll.lesson or '').replace('\n','<br/>') + '</p>'
           if ll.lesson else '')
        + ('<p><b>Recommendations:</b><br/>' + (ll.recommendations or '').replace('\n','<br/>') + '</p>'
           if ll.recommendations else '')
    )
    subject = '[Lessons Learned] ' + ll.title
    html = _email_html(ll.title, 'Lessons Learned', body, '#15803d')
    sent, err = _do_send(emails, subject, html)
    _write_log('Lesson', lid, subject, sent, 'All',
               'Sent' if not err else 'Failed', err)
    flash(f'Lesson shared with {sent} recipients.', 'success')
    return redirect(f'/safety-promotion/lesson/{lid}')
@app.route('/safety-promotion/bulletin/<bid>/print')
def sp_bulletin_print(bid):
    b = SafetyBulletin.query.get_or_404(bid)
    return render_template('spi/sp_bulletin_print.html', b=b, now=datetime.utcnow())


# ── Newsletter edit ────────────────────────────────────────────────────────────

@app.route('/safety-promotion/newsletter/<int:nid>/edit', methods=['GET','POST'])
def sp_newsletter_edit(nid):
    n = SafetyNewsletter.query.get_or_404(nid)
    if request.method == 'POST':
        f = request.form
        n.title        = f.get('title', n.title)
        n.issue_number = f.get('issue_number', n.issue_number)
        n.author       = f.get('author', n.author)
        n.issue_date   = f.get('issue_date', n.issue_date)
        n.summary      = f.get('summary', n.summary)
        n.content      = f.get('content', n.content)
        n.status       = f.get('status', n.status)
        if 'attachment' in request.files:
            att = request.files['attachment']
            if att and att.filename and allowed_file(att.filename):
                from werkzeug.utils import secure_filename
                fn = f'NL{n.id}_{secure_filename(att.filename)}'
                att.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                n.attachment = fn
        db.session.commit()
        flash('✓ Newsletter updated.', 'success')
        return redirect(url_for('sp_newsletter_detail', nid=nid))
    return render_template('spi/sp_newsletter_form.html', n=n, editing=True,
                           now=datetime.utcnow())


@app.route('/safety-promotion/newsletter/<int:nid>/archive', methods=['POST'])
def sp_newsletter_archive(nid):
    n = SafetyNewsletter.query.get_or_404(nid)
    n.status = 'Archived'
    db.session.commit()
    flash('✓ Newsletter archived.', 'success')
    return redirect(url_for('sp_newsletters'))


@app.route('/safety-promotion/newsletter/<int:nid>/print')
def sp_newsletter_print(nid):
    n = SafetyNewsletter.query.get_or_404(nid)
    return render_template('spi/sp_newsletter_print.html', n=n, now=datetime.utcnow())


# ── Survey results dashboard ──────────────────────────────────────────────────

@app.route('/safety-promotion/survey/<int:sid>')
def sp_survey_detail(sid):
    s = SafetySurvey.query.get_or_404(sid)
    import json
    questions = []
    try:
        questions = json.loads(s.questions or '[]')
    except Exception:
        pass
    pct = int((s.response_count or 0) / max(s.target_count or 1, 1) * 100)
    return render_template('spi/sp_survey_detail.html', s=s,
                           questions=questions, pct=pct, now=datetime.utcnow())


# ── Campaign detail & close ───────────────────────────────────────────────────

@app.route('/safety-promotion/campaign/<int:cid>')
def sp_campaign_detail(cid):
    c = SafetyCampaign.query.get_or_404(cid)
    return render_template('spi/sp_campaign_detail.html', c=c, now=datetime.utcnow())


@app.route('/safety-promotion/campaign/<int:cid>/complete', methods=['POST'])
def sp_campaign_complete(cid):
    c = SafetyCampaign.query.get_or_404(cid)
    c.status = 'Completed'
    db.session.commit()
    flash('✓ Campaign marked as Completed.', 'success')
    return redirect(url_for('sp_campaigns'))


# ── Training PDF report ───────────────────────────────────────────────────────

@app.route('/safety-promotion/training/<int:tid>/edit', methods=['GET', 'POST'])
def sp_training_edit(tid):
    """Full edit form — alias for detail page with editing mode."""
    t = Training.query.get_or_404(tid)
    if request.method == 'POST':
        return sp_training_detail(tid)
    return render_template('spi/sp_training_form.html', t=t, editing=True,
                           now=datetime.utcnow())


@app.route('/safety-promotion/training/report')
def sp_training_report():
    dept_f   = request.args.get('dept', '')
    status_f = request.args.get('status', '')
    q = Training.query
    if dept_f:   q = q.filter_by(department_id=int(dept_f))
    if status_f: q = q.filter_by(status=status_f)
    trainings = q.order_by(Training.expiry_date).all()
    stats = {
        'total':     Training.query.count(),
        'scheduled': Training.query.filter_by(status='Scheduled').count(),
        'completed': Training.query.filter_by(status='Completed').count(),
        'expired':   Training.query.filter_by(status='Expired').count(),
        'due_soon':  Training.query.filter(Training.status.in_(['Due Soon','Current'])).count(),
    }
    return render_template('spi/sp_training_report.html',
                           trainings=trainings, stats=stats, now=datetime.utcnow())


# ── Lessons Learned PDF ───────────────────────────────────────────────────────

@app.route('/safety-promotion/lesson/<int:lid>/print')
def sp_lesson_print(lid):
    ll = LessonLearned.query.get_or_404(lid)
    return render_template('spi/sp_lesson_print.html', ll=ll, now=datetime.utcnow())


@app.route('/safety-promotion/lesson/<int:lid>')

def sp_lesson_detail(lid):
    ll = LessonLearned.query.get_or_404(lid)
    return render_template('spi/sp_lesson_detail.html', ll=ll, now=datetime.utcnow())


# ═══════════════════════════════════════════════════════════════════════════════
#  TESTING-PHASE DELETE ROUTES — Safe cascade deletion for all major modules
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/delete/hazard-report/<rid>', methods=['POST'])
def delete_hazard_report(rid):
    """Safe delete: nullify FKs first, then cascade in correct dependency order."""
    rep = HazardReport.query.get_or_404(rid)
    hid = rep.hazard_id
    try:
        # Step 1: Nullify hazard_id on the report (removes the FK reference)
        rep.hazard_id = None
        db.session.flush()

        # Step 2: Delete the report row
        db.session.delete(rep)
        db.session.flush()

        # Step 3: If a linked Hazard exists, cascade-delete everything under it
        if hid:
            # Nullify hazard_id on ALL tables that reference hazards.id
            tables_to_nullify = [
                'asr_reports', 'actions', 'investigations',
                'audit_findings', 'audit_actions', 'risk_occurrences',
                'risk_actions', 'risk_assessments',
            ]
            for tbl in tables_to_nullify:
                db.session.execute(
                    db.text(f"UPDATE {tbl} SET hazard_id = NULL WHERE hazard_id = :hid"),
                    {'hid': hid}
                )
            db.session.flush()
            for r in Risk.query.filter_by(hazard_id=hid).all():
                db.session.execute(
                    db.text("UPDATE ra_rows SET risk_id = NULL WHERE risk_id = :rid"),
                    {'rid': r.id}
                )
                Control.query.filter_by(risk_id=r.id).delete(synchronize_session=False)
                db.session.delete(r)
            db.session.flush()
            haz = Hazard.query.get(hid)
            if haz:
                db.session.delete(haz)
        db.session.commit()
        flash(f'✓ Hazard Report {rid} deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'⚠ Could not delete {rid}: {str(e)[:120]}', 'error')
    return redirect(request.form.get('return_url', url_for('hazard_report_list')))


@app.route('/delete/hazard/<hid>', methods=['POST'])
def delete_hazard(hid):
    """Safe delete hazard: nullify ALL FK references across all 10 tables first."""
    h = Hazard.query.get_or_404(hid)
    try:
        # Nullify hazard_id on every table that references hazards.id
        tables_to_nullify = [
            'hazard_reports', 'asr_reports', 'actions', 'investigations',
            'audit_findings', 'audit_actions', 'risk_occurrences',
            'risk_actions', 'risk_assessments',
        ]
        for tbl in tables_to_nullify:
            db.session.execute(
                db.text(f"UPDATE {tbl} SET hazard_id = NULL WHERE hazard_id = :hid"),
                {'hid': hid}
            )
        db.session.flush()

        # Delete risks under this hazard (and their controls + ra_rows)
        for r in Risk.query.filter_by(hazard_id=hid).all():
            db.session.execute(
                db.text("UPDATE ra_rows SET risk_id = NULL WHERE risk_id = :rid"),
                {'rid': r.id}
            )
            Control.query.filter_by(risk_id=r.id).delete(synchronize_session=False)
            db.session.delete(r)
        db.session.flush()

        db.session.delete(h)
        db.session.commit()
        flash(f'✓ Hazard {hid} deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'⚠ Could not delete {hid}: {str(e)[:120]}', 'error')
    return redirect(url_for('hazard_log'))


@app.route('/delete/asr/<aid>', methods=['POST'])
def delete_asr(aid):
    rec = ASRReport.query.get_or_404(aid)
    db.session.delete(rec)
    db.session.commit()
    flash(f'✓ ASR Report {aid} deleted.', 'success')
    return redirect('/asr')


@app.route('/delete/action/<aid>', methods=['POST'])
def delete_action(aid):
    a = Action.query.get_or_404(aid)
    db.session.delete(a)
    db.session.commit()
    flash(f'✓ Action {aid} deleted.', 'success')
    return redirect(request.form.get('return_url', '/actions'))


@app.route('/delete/risk-assessment/<ra_id>', methods=['POST'])
def delete_risk_assessment(ra_id):
    """Safe delete RA: RARow/RAMitigation use assessment_id FK."""
    ra = RiskAssessment.query.get_or_404(ra_id)
    try:
        # RAMitigation and RARow use assessment_id (not ra_id)
        RAMitigation.query.filter_by(assessment_id=ra_id).delete(synchronize_session=False)
        RAReview.query.filter_by(assessment_id=ra_id).delete(synchronize_session=False)
        RAChecklistItem.query.filter_by(assessment_id=ra_id).delete(synchronize_session=False)
        # RARows: nullify risk_id FK first, then delete
        for row in RARow.query.filter_by(assessment_id=ra_id).all():
            row.risk_id = None
        db.session.flush()
        RARow.query.filter_by(assessment_id=ra_id).delete(synchronize_session=False)
        db.session.flush()
        db.session.delete(ra)
        db.session.commit()
        flash(f'✓ Risk Assessment {ra_id} deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'⚠ Could not delete {ra_id}: {str(e)[:120]}', 'error')
    return redirect(url_for('ra_list'))


@app.route('/delete/audit-schedule/<sid>', methods=['POST'])
def delete_audit_schedule(sid):
    """Safe delete audit: AuditAction.finding_id and
    AuditChecklist.linked_finding_id must be nullified before finding delete."""
    s = AuditSchedule.query.get_or_404(sid)
    try:
        findings = AuditFinding.query.filter_by(schedule_id=sid).all()
        fids = [f.id for f in findings]

        # Nullify linked_finding_id on checklists that reference these findings
        if fids:
            AuditChecklist.query.filter(
                AuditChecklist.linked_finding_id.in_(fids)
            ).update({'linked_finding_id': None}, synchronize_session=False)
            db.session.flush()
            # Delete audit actions linked to findings
            AuditAction.query.filter(
                AuditAction.finding_id.in_(fids)
            ).delete(synchronize_session=False)
            db.session.flush()

        # Delete checklist items for the schedule
        AuditChecklist.query.filter_by(schedule_id=sid).delete(synchronize_session=False)
        db.session.flush()

        # Now delete findings
        for f in findings:
            db.session.delete(f)
        db.session.flush()

        db.session.delete(s)
        db.session.commit()
        flash(f'✓ Audit Schedule {sid} deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'⚠ Could not delete {sid}: {str(e)[:120]}', 'error')
    return redirect(url_for('audit_schedule'))


@app.route('/delete/audit-finding/<int:fid>', methods=['POST'])
def delete_audit_finding(fid):
    """Safe delete finding: nullify linked_finding_id in checklists, delete actions first."""
    f = AuditFinding.query.get_or_404(fid)
    schedule_id = f.schedule_id
    try:
        # Nullify checklist linked_finding_id references
        AuditChecklist.query.filter_by(linked_finding_id=str(fid)).update(
            {'linked_finding_id': None}, synchronize_session=False)
        db.session.flush()
        AuditAction.query.filter_by(finding_id=str(fid)).delete(synchronize_session=False)
        db.session.flush()
        db.session.delete(f)
        db.session.commit()
        flash('✓ Audit Finding deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'⚠ Could not delete finding: {str(e)[:120]}', 'error')
    return redirect(url_for('audit_execution', sid=schedule_id))


@app.route('/delete/investigation/<iid>', methods=['POST'])
def delete_investigation(iid):
    inv = Investigation.query.get_or_404(iid)
    db.session.delete(inv)
    db.session.commit()
    flash('✓ Investigation deleted.', 'success')
    return redirect('/investigations')


@app.route('/delete/training/<int:tid>', methods=['POST'])
def delete_training(tid):
    t = Training.query.get_or_404(tid)
    db.session.delete(t)
    db.session.commit()
    flash('✓ Training record deleted.', 'success')
    return redirect(url_for('sp_training'))


@app.route('/delete/bulletin/<bid>', methods=['POST'])
def delete_bulletin(bid):
    b = SafetyBulletin.query.get_or_404(bid)
    db.session.delete(b)
    db.session.commit()
    flash('✓ Bulletin deleted.', 'success')
    return redirect(url_for('sp_bulletins'))


@app.route('/delete/newsletter/<int:nid>', methods=['POST'])
def delete_newsletter(nid):
    n = SafetyNewsletter.query.get_or_404(nid)
    db.session.delete(n)
    db.session.commit()
    flash('✓ Newsletter deleted.', 'success')
    return redirect(url_for('sp_newsletters'))


@app.route('/delete/survey/<int:sid>', methods=['POST'])
def delete_survey(sid):
    s = SafetySurvey.query.get_or_404(sid)
    db.session.delete(s)
    db.session.commit()
    flash('✓ Survey deleted.', 'success')
    return redirect('/safety-promotion/surveys')


@app.route('/delete/campaign/<int:cid>', methods=['POST'])
def delete_campaign(cid):
    sc = SafetyCampaign.query.get_or_404(cid)
    db.session.delete(sc)
    db.session.commit()
    flash('✓ Campaign deleted.', 'success')
    return redirect(url_for('sp_campaigns'))


@app.route('/delete/lesson/<int:lid>', methods=['POST'])
def delete_lesson(lid):
    ll = LessonLearned.query.get_or_404(lid)
    db.session.delete(ll)
    db.session.commit()
    flash('✓ Lesson Learned deleted.', 'success')
    return redirect(url_for('sp_lessons'))


@app.route('/delete/spi-data/<int:did>', methods=['POST'])
def delete_spi_data(did):
    d = SPIData.query.get_or_404(did)
    iid = d.spi_id
    db.session.delete(d)
    db.session.commit()
    flash('✓ SPI data point deleted.', 'success')
    return redirect(url_for('spi_indicator_detail', iid=iid))


@app.route('/delete/moc/<mid>', methods=['POST'])
def delete_moc(mid):
    m = MOC.query.get_or_404(mid)
    if m.hazard_id:
        Action.query.filter_by(hazard_id=m.hazard_id).update({'hazard_id': None})
        haz = Hazard.query.get(m.hazard_id)
        if haz: db.session.delete(haz)
    db.session.delete(m)
    db.session.commit()
    flash('✓ MOC record deleted.', 'success')
    return redirect(url_for('moc_list'))


# ── Admin cleanup dashboard ───────────────────────────────────────────────────

@app.route('/admin/cleanup')
@require_login
def admin_cleanup():
    counts = {
        'hazard_reports':   HazardReport.query.count(),
        'hazards':          Hazard.query.count(),
        'asr_reports':      ASRReport.query.count(),
        'actions':          Action.query.count(),
        'risk_assessments': RiskAssessment.query.count(),
        'audit_schedules':  AuditSchedule.query.count(),
        'investigations':   Investigation.query.count(),
        'training':         Training.query.count(),
        'bulletins':        SafetyBulletin.query.count(),
        'newsletters':      SafetyNewsletter.query.count(),
        'surveys':          SafetySurvey.query.count(),
        'campaigns':        SafetyCampaign.query.count(),
        'lessons':          LessonLearned.query.count(),
        'spi_data':         SPIData.query.count(),
    }
    return render_template('admin_cleanup.html', counts=counts, total=sum(counts.values()))


# ─── Risk Matrix Reference ────────────────────────────────────────────────────

# ═══════════════════════════════════════════════════════════════════════════════
#  SAFETY PROMOTION — EMAIL DISTRIBUTION & RESPONSE TRACKING
# ═══════════════════════════════════════════════════════════════════════════════

def _smtp_cfg():
    return {
        'host': os.environ.get('SMTP_HOST',''),
        'port': int(os.environ.get('SMTP_PORT','587')),
        'user': os.environ.get('SMTP_USER',''),
        'password': os.environ.get('SMTP_PASSWORD',''),
        'from_email': os.environ.get('SMTP_FROM','safety@aviation.jo'),
    }

def _get_dist_list(dept_id=None):
    q = DistributionList.query.filter_by(is_active=True)
    if dept_id:
        q = q.filter_by(department_id=int(dept_id))
    return q.all()

def _do_send(emails, subject, html):
    cfg = _smtp_cfg()
    if not cfg['host']:
        return len(emails), None  # SMTP not configured — log as simulated
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    try:
        srv = smtplib.SMTP(cfg['host'], cfg['port'])
        srv.starttls()
        srv.login(cfg['user'], cfg['password'])
        sent = 0
        for addr in emails:
            m = MIMEMultipart('alternative')
            m['Subject'] = subject
            m['From']    = cfg['from_email']
            m['To']      = addr
            m.attach(MIMEText(html, 'html'))
            try:
                srv.sendmail(cfg['from_email'], [addr], m.as_string())
                sent += 1
            except Exception:
                pass
        srv.quit()
        return sent, None
    except Exception as e:
        return 0, str(e)

def _write_log(ctype, cref, subject, count, dept_label, status='Sent', err=None):
    db.session.add(EmailLog(
        content_type=ctype, content_ref=str(cref), subject=subject,
        recipient_count=count, dept_filter=dept_label or 'All',
        sent_by=session.get('admin_name','System'),
        status=status, error_message=err
    ))
    db.session.commit()

def _email_html(title, subtitle, body, color='#0f1c3f'):
    return (
        '<!DOCTYPE html><html><head><meta charset="UTF-8"/><style>'
        'body{font-family:Arial,sans-serif;background:#f0f2f8;margin:0;padding:0}'
        '.w{max-width:620px;margin:20px auto;background:#fff;border-radius:10px;overflow:hidden}'
        '.h{background:' + color + ';padding:22px 28px;text-align:center}'
        '.hl{color:#c9a84c;font-size:22px;font-weight:800}'
        '.hs{color:rgba(255,255,255,.6);font-size:11px;margin-top:3px}'
        '.tb{background:' + color + '22;border-bottom:3px solid ' + color + ';padding:14px 28px}'
        '.tb h1{font-size:17px;font-weight:800;color:' + color + ';margin:0}'
        '.tb p{font-size:12px;color:#6b7280;margin:3px 0 0}'
        '.b{padding:22px 28px;font-size:14px;color:#374151;line-height:1.7}'
        '.f{background:#f8f9fc;padding:12px 28px;font-size:11px;color:#9ca3af;text-align:center;border-top:1px solid #e5e7eb}'
        '</style></head><body><div class="w">'
        '<div class="h"><div class="hl">&#x2708; Jordan Aviation</div>'
        '<div class="hs">Safety Management System</div></div>'
        '<div class="tb"><h1>' + title + '</h1><p>' + subtitle + '</p></div>'
        '<div class="b">' + body + '</div>'
        '<div class="f">Jordan Aviation SMS &middot; Official Safety Communication</div>'
        '</div></body></html>'
    )


# ── Distribution List ─────────────────────────────────────────────────────────

@app.route('/safety-promotion/distribution')
@require_login
def sp_distribution():
    recipients = DistributionList.query.order_by(DistributionList.department_id, DistributionList.name).all()
    total = DistributionList.query.filter_by(is_active=True).count()
    depts = Department.query.all()
    return render_template('spi/sp_distribution.html',
                           recipients=recipients, total=total, depts=depts)


@app.route('/safety-promotion/distribution/add', methods=['POST'])
@require_login
def sp_distribution_add():
    f = request.form
    if not f.get('email') or not f.get('name'):
        flash('Name and email required.', 'error')
        return redirect(url_for('sp_distribution'))
    if DistributionList.query.filter_by(email=f['email'].strip()).first():
        flash(f'{f["email"]} already in distribution list.', 'warning')
        return redirect(url_for('sp_distribution'))
    db.session.add(DistributionList(
        name=f['name'].strip(), email=f['email'].strip(),
        position=f.get('position',''),
        department_id=int(f['department_id']) if f.get('department_id') else None,
        is_active=True,
    ))
    db.session.commit()
    flash(f'+ {f["name"]} added to distribution list.', 'success')
    return redirect(url_for('sp_distribution'))


@app.route('/safety-promotion/distribution/<int:rid>/toggle', methods=['POST'])
@require_login
def sp_distribution_toggle(rid):
    r = DistributionList.query.get_or_404(rid)
    r.is_active = not r.is_active
    db.session.commit()
    flash(f'{"Activated" if r.is_active else "Deactivated"}: {r.name}', 'success')
    return redirect(url_for('sp_distribution'))


@app.route('/safety-promotion/distribution/<int:rid>/delete', methods=['POST'])
@require_login
def sp_distribution_delete(rid):
    r = DistributionList.query.get_or_404(rid)
    db.session.delete(r); db.session.commit()
    flash('Recipient removed.', 'success')
    return redirect(url_for('sp_distribution'))


# ── Email Log ─────────────────────────────────────────────────────────────────

@app.route('/safety-promotion/email-log')
@require_login
def sp_email_log():
    logs             = EmailLog.query.order_by(EmailLog.sent_at.desc()).all()
    total_sent       = sum(1 for l in logs if 'Sent' in (l.status or ''))
    total_failed     = sum(1 for l in logs if l.status == 'Failed')
    total_recipients = sum(l.recipient_count or 0 for l in logs)
    return render_template('spi/sp_email_log.html',
                           logs=logs, total_sent=total_sent,
                           total_failed=total_failed,
                           total_recipients=total_recipients)


# ── Send Bulletin ─────────────────────────────────────────────────────────────

@app.route('/safety-promotion/bulletin/<bid>/send-email', methods=['POST'])
@require_login
def sp_send_bulletin_email(bid):
    b    = SafetyBulletin.query.get_or_404(bid)
    dept_id = request.form.get('dept_id') or None
    recip   = _get_dist_list(dept_id)
    if not recip:
        flash('No active recipients. Add employees to Distribution List first.', 'warning')
        return redirect(url_for('sp_bulletin_detail', bid=bid))
    emails     = [r.email for r in recip]
    dept_label = Department.query.get(int(dept_id)).name if dept_id else 'All'
    clr        = {'Critical':'#dc2626','High':'#ea580c','Medium':'#d97706','Low':'#15803d'}.get(b.severity,'#0f1c3f')
    body       = ('<p><b>Ref:</b> ' + (b.ref_number or b.id) + ' &nbsp;&middot;&nbsp; '
                  '<b>Severity:</b> <span style="color:' + clr + '">' + (b.severity or '') + '</span><br/>'
                  '<b>Issued by:</b> ' + (b.issued_by or 'Safety') + ' &nbsp;&middot;&nbsp; '
                  '<b>Date:</b> ' + (b.issue_date or '') + '</p>'
                  '<hr style="border:none;border-top:1px solid #e5e7eb;margin:14px 0"/>'
                  '<p>' + (b.content or '').replace('\n','<br/>') + '</p>'
                  + ('<p><b>Recommendations:</b><br/>' + (b.recommendations or '').replace('\n','<br/>') + '</p>'
                     if b.recommendations else ''))
    subject    = '[Safety Bulletin] ' + b.title
    html       = _email_html(b.title, 'Safety Bulletin ' + (b.severity or ''), body, clr)
    sent, err  = _do_send(emails, subject, html)
    _write_log('Bulletin', bid, subject, sent, dept_label,
               'Sent' if not err else 'Failed', err)
    flash(f'Bulletin emailed to {sent} recipients ({dept_label}).', 'success')
    return redirect(url_for('sp_bulletin_detail', bid=bid))


# ── Send Newsletter ───────────────────────────────────────────────────────────

@app.route('/safety-promotion/newsletter/<int:nid>/send-email', methods=['POST'])
@require_login
def sp_send_newsletter_email(nid):
    n       = SafetyNewsletter.query.get_or_404(nid)
    dept_id = request.form.get('dept_id') or None
    recip   = _get_dist_list(dept_id)
    if not recip:
        flash('No active recipients in distribution list.', 'warning')
        return redirect(url_for('sp_newsletter_detail', nid=nid))
    emails     = [r.email for r in recip]
    dept_label = Department.query.get(int(dept_id)).name if dept_id else 'All'
    body       = ('<p><b>Issue:</b> ' + (n.issue_number or '') +
                  ' &nbsp;&middot;&nbsp; <b>Date:</b> ' + (n.issue_date or '') +
                  '<br/><b>Author:</b> ' + (n.author or 'Safety') + '</p>'
                  + ('<p><em>' + (n.summary or '') + '</em></p>' if n.summary else '')
                  + '<hr style="border:none;border-top:1px solid #e5e7eb;margin:14px 0"/>'
                  + '<p>' + (n.content or '').replace('\n','<br/>') + '</p>')
    subject    = '[Safety Newsletter] ' + n.title
    html       = _email_html(n.title, 'Safety Newsletter', body)
    sent, err  = _do_send(emails, subject, html)
    _write_log('Newsletter', nid, subject, sent, dept_label,
               'Sent' if not err else 'Failed', err)
    flash(f'Newsletter emailed to {sent} recipients.', 'success')
    return redirect(url_for('sp_newsletter_detail', nid=nid))


# ── Send Survey ───────────────────────────────────────────────────────────────

@app.route('/safety-promotion/survey/<int:sid>/send-email', methods=['POST'])
@require_login
def sp_send_survey_email(sid):
    s       = SafetySurvey.query.get_or_404(sid)
    dept_id = request.form.get('dept_id') or None
    recip   = _get_dist_list(dept_id)
    if not recip:
        flash('⚠ No active recipients found. Please add employees to the Distribution List first at /safety-promotion/distribution', 'warning')
        return redirect(url_for('sp_survey_detail', sid=sid))
    emails     = [r.email for r in recip]
    dept_label = Department.query.get(int(dept_id)).name if dept_id else 'All'
    pub_url    = request.host_url.rstrip('/') + '/safety-promotion/survey/' + str(sid) + '/respond-public'
    body       = ('<p>The Safety Department invites you to participate in this safety survey.</p>'
                  '<p><b>' + s.title + '</b><br/>'
                  + (s.description or '') + '</p>'
                  + '<p><b>Deadline:</b> ' + (s.end_date or 'Open ended') + '</p>'
                  '<p style="text-align:center;margin-top:18px">'
                  '<a href="' + pub_url + '" style="background:#7c3aed;color:#fff;padding:11px 24px;'
                  'border-radius:7px;font-weight:700;font-size:13px;text-decoration:none">'
                  'Complete Survey &rarr;</a></p>')
    subject    = '[Safety Survey] ' + s.title
    html       = _email_html(s.title, 'Safety Survey — Your Participation Required', body, '#7c3aed')
    sent, err  = _do_send(emails, subject, html)
    s.target_count = (s.target_count or 0) + sent
    _write_log('Survey', sid, subject, sent, dept_label,
               'Sent' if not err else 'Failed', err)
    flash(f'Survey invitation sent to {sent} recipients.', 'success')
    return redirect(url_for('sp_survey_detail', sid=sid))


# ── Send Campaign ─────────────────────────────────────────────────────────────

@app.route('/safety-promotion/campaign/<int:cid>/send-email', methods=['POST'])
@require_login
def sp_send_campaign_email(cid):
    camp    = SafetyCampaign.query.get_or_404(cid)
    dept_id = request.form.get('dept_id') or None
    recip   = _get_dist_list(dept_id)
    if not recip:
        flash('No active recipients in distribution list.', 'warning')
        return redirect(url_for('sp_campaign_detail', cid=cid))
    emails     = [r.email for r in recip]
    dept_label = Department.query.get(int(dept_id)).name if dept_id else 'All'
    body       = ('<p><b>Type:</b> ' + (camp.campaign_type or '') +
                  ' &nbsp;&middot;&nbsp; <b>Period:</b> ' + (camp.start_date or '') +
                  ' to ' + (camp.end_date or '') + '</p>'
                  '<p>' + (camp.description or '').replace('\n','<br/>') + '</p>'
                  + ('<p><b>Objectives:</b><br/>' + (camp.objectives or '').replace('\n','<br/>') + '</p>'
                     if camp.objectives else ''))
    subject    = '[Safety Campaign] ' + camp.title
    html       = _email_html(camp.title, 'Safety Campaign', body, '#d97706')
    sent, err  = _do_send(emails, subject, html)
    _write_log('Campaign', cid, subject, sent, dept_label,
               'Sent' if not err else 'Failed', err)
    flash(f'Campaign emailed to {sent} recipients.', 'success')
    return redirect(url_for('sp_campaign_detail', cid=cid))


# ── Send Lesson ───────────────────────────────────────────────────────────────

@app.route('/safety-promotion/lesson/<int:lid>/send-email', methods=['POST'])
@require_login
def sp_send_lesson_email(lid):
    ll   = LessonLearned.query.get_or_404(lid)
    recip = _get_dist_list()
    if not recip:
        flash('No active recipients in distribution list.', 'warning')
        return redirect(url_for('sp_lesson_detail', lid=lid))
    emails = [r.email for r in recip]
    body   = ('<p><b>Category:</b> ' + (ll.category or '') +
              ' &nbsp;&middot;&nbsp; <b>Date:</b> ' + (ll.date or '') +
              '<br/><b>Author:</b> ' + (ll.author or 'Safety') + '</p>'
              '<hr style="border:none;border-top:1px solid #e5e7eb;margin:14px 0"/>'
              '<p>' + (ll.description or '').replace('\n','<br/>') + '</p>'
              + ('<p><b>Lesson:</b><br/>' + (ll.lesson or '').replace('\n','<br/>') + '</p>'
                 if ll.lesson else '')
              + ('<p><b>Recommendations:</b><br/>' + (ll.recommendations or '').replace('\n','<br/>') + '</p>'
                 if ll.recommendations else ''))
    subject = '[Lessons Learned] ' + ll.title
    html    = _email_html(ll.title, 'Lessons Learned', body, '#15803d')
    sent, err = _do_send(emails, subject, html)
    _write_log('Lesson', lid, subject, sent, 'All',
               'Sent' if not err else 'Failed', err)
    flash(f'Lesson emailed to {sent} recipients.', 'success')
    return redirect(url_for('sp_lesson_detail', lid=lid))


# ── Public Survey Response ────────────────────────────────────────────────────

@app.route('/safety-promotion/survey/<int:sid>/respond-public', methods=['GET','POST'])
def sp_survey_respond_public(sid):
    s = SafetySurvey.query.get_or_404(sid)
    if s.status != 'Active':
        return render_template('spi/sp_survey_closed.html', survey=s)

    import json as _j
    questions = []
    try:
        raw = _j.loads(s.questions or '[]')
        # Normalize: strings → dicts so template can call q.get('text')
        for q in raw:
            if isinstance(q, str):
                questions.append({'text': q, 'type': 'text'})
            elif isinstance(q, dict):
                questions.append(q)
    except Exception:
        pass

    if request.method == 'POST':
        f       = request.form
        is_anon = bool(f.get('is_anonymous'))
        answers = {str(i): f.get('q_' + str(i), '') for i in range(len(questions))}
        db.session.add(SurveyResponse(
            survey_id=sid,
            respondent_name='' if is_anon else f.get('respondent_name',''),
            respondent_email='' if is_anon else f.get('respondent_email',''),
            department_id=int(f['department_id']) if f.get('department_id') else None,
            is_anonymous=is_anon,
            answers=_j.dumps(answers),
            ip_address=request.remote_addr,
        ))
        s.response_count = (s.response_count or 0) + 1
        db.session.commit()
        return render_template('spi/sp_survey_thanks.html', survey=s)

    return render_template('spi/sp_survey_public.html', survey=s, questions=questions)


# ── Survey Response Tracking ──────────────────────────────────────────────────

@app.route('/safety-promotion/survey/<int:sid>/responses')
@require_login
def sp_survey_responses(sid):
    s         = SafetySurvey.query.get_or_404(sid)
    responses = SurveyResponse.query.filter_by(survey_id=sid)\
                    .order_by(SurveyResponse.submitted_at.desc()).all()
    total_sent    = s.target_count or 0
    resp_count    = len(responses)
    response_rate = round((resp_count / total_sent * 100) if total_sent > 0 else 0, 1)

    import json as _j
    from collections import Counter, defaultdict

    # Parse questions
    questions = []
    try:
        raw = _j.loads(s.questions or '[]')
        for q in raw:
            if isinstance(q, str):
                questions.append({'text': q, 'type': 'text'})
            elif isinstance(q, dict):
                questions.append(q)
    except Exception:
        pass

    # Pre-parse answers for each response so template can display them
    parsed_responses = []
    for resp in responses:
        try:
            ans = _j.loads(resp.answers or '{}')
        except Exception:
            ans = {}
        parsed_responses.append({
            'obj':             resp,
            'answers':         ans,
            'answer_list':     [ans.get(str(i), '') for i in range(len(questions))],
        })

    # Department participation
    dept_counts = Counter(r.department_id for r in responses if r.department_id)
    all_depts   = Department.query.all()
    dept_names  = {d.id: d.name for d in all_depts}

    # Question analytics: for each question, tally all answers
    q_analytics = []
    for i, q in enumerate(questions):
        tally = Counter()
        for pr in parsed_responses:
            ans = pr['answer_list'][i]
            if ans:
                tally[ans] += 1
        q_analytics.append({'question': q, 'tally': dict(tally), 'total': len(tally)})

    # Timeline: responses by date
    from collections import OrderedDict
    timeline = Counter()
    for r in responses:
        if r.submitted_at:
            timeline[r.submitted_at.strftime('%d %b')] += 1
    timeline = dict(sorted(timeline.items()))

    anon_count    = sum(1 for r in responses if r.is_anonymous)
    tracked_count = len(responses) - anon_count

    return render_template('spi/sp_survey_responses.html',
                           survey=s,
                           responses=parsed_responses,
                           response_rate=response_rate,
                           questions=questions,
                           q_analytics=q_analytics,
                           dept_counts=dept_counts,
                           dept_names=dept_names,
                           all_depts=all_depts,
                           total_sent=total_sent,
                           anon_count=anon_count,
                           tracked_count=tracked_count,
                           timeline=timeline)



@app.route('/safety-promotion/survey/<int:sid>/response/<int:rid>')
@require_login
def sp_survey_response_detail(sid, rid):
    """Individual survey response detail view."""
    import json as _j
    s    = SafetySurvey.query.get_or_404(sid)
    resp = SurveyResponse.query.get_or_404(rid)
    questions = []
    try:
        raw = _j.loads(s.questions or '[]')
        for q in raw:
            questions.append({'text': q} if isinstance(q, str) else q)
    except Exception:
        pass
    try:
        answers = _j.loads(resp.answers or '{}')
    except Exception:
        answers = {}
    qa_pairs = [(questions[i], answers.get(str(i),'—'))
                for i in range(len(questions))]
    return render_template('spi/sp_survey_response_detail.html',
                           survey=s, resp=resp, qa_pairs=qa_pairs)


@app.route('/risk-matrix')
@require_login
def risk_matrix():
    return render_template('risk/risk_matrix.html')


# ═══════════════════════════════════════════════════════════════════════════════
#  AUDIT MANAGEMENT MODULE ROUTES
#  ICAO Annex 19 / IOSA ISM compliant
#  Added as extension — existing routes unchanged
# ═══════════════════════════════════════════════════════════════════════════════

# ── Checklist templates per department ───────────────────────────────────────
CHECKLIST_TEMPLATES = {
    'default': [
        ('SOP Compliance',      'ISM 1.1.1',  'Are Standard Operating Procedures current, approved and accessible to all relevant personnel?'),
        ('SOP Compliance',      'ISM 1.1.2',  'Have SOPs been reviewed within the required timeframe?'),
        ('Training Records',    'ISM 2.1.1',  'Are training records complete, current and properly filed for all personnel?'),
        ('Training Records',    'ISM 2.1.2',  'Do all personnel hold valid certifications required for their role?'),
        ('Safety Reporting',    'ISM 3.1.1',  'Is the safety reporting system accessible and promoted to all staff?'),
        ('Safety Reporting',    'ISM 3.1.2',  'Are safety reports reviewed and actioned within defined timeframes?'),
        ('Risk Management',     'ISM 4.1.1',  'Are hazard identification processes implemented and records maintained?'),
        ('Risk Management',     'ISM 4.1.2',  'Are risk assessments reviewed and updated when changes occur?'),
        ('Operational Procedures', 'ISM 5.1.1', 'Are operational procedures aligned with current regulatory requirements?'),
        ('Operational Procedures', 'ISM 5.1.2', 'Are emergency/contingency procedures known and practised by personnel?'),
    ],
    'FO': [
        ('SOP Compliance',      'FO-1.1',  'Are Operations Manual revisions current and controlled?'),
        ('SOP Compliance',      'FO-1.2',  'Are MEL/CDL procedures understood and correctly applied?'),
        ('Training Records',    'FO-2.1',  'Are all flight crew recency requirements met (line checks, simulator)?'),
        ('Training Records',    'FO-2.2',  'Are CRM and UPRT training records current for all pilots?'),
        ('Safety Reporting',    'FO-3.1',  'Are ASR reports submitted within 72 hours of occurrence?'),
        ('Safety Reporting',    'FO-3.2',  'Are TCAS RA events reported and entered into the safety system?'),
        ('Risk Management',     'FO-4.1',  'Are NOTAM and weather briefing procedures followed for all flights?'),
        ('Risk Management',     'FO-4.2',  'Are fuel policy and alternates planned per company policy?'),
        ('Operational Procedures', 'FO-5.1', 'Are sterile cockpit procedures enforced during critical phases of flight?'),
        ('Operational Procedures', 'FO-5.2', 'Are fatigue risk management procedures followed and documented?'),
    ],
    'ME': [
        ('SOP Compliance',      'ME-1.1',  'Are maintenance procedures documented and consistent with approved data?'),
        ('SOP Compliance',      'ME-1.2',  'Are tooling calibration records maintained and current?'),
        ('Training Records',    'ME-2.1',  'Do all certifying engineers hold valid licences and type ratings?'),
        ('Training Records',    'ME-2.2',  'Are Human Factors in Maintenance training records current?'),
        ('Safety Reporting',    'ME-3.1',  'Are occurrence reports filed for all significant maintenance events?'),
        ('Safety Reporting',    'ME-3.2',  'Are defect reporting and follow-up processes properly implemented?'),
        ('Risk Management',     'ME-4.1',  'Are safety risk assessments conducted before non-routine tasks?'),
        ('Risk Management',     'ME-4.2',  'Are foreign object damage (FOD) prevention procedures in place?'),
        ('Operational Procedures', 'ME-5.1', 'Are shift handover procedures formally documented and followed?'),
        ('Operational Procedures', 'ME-5.2', 'Are critical maintenance tasks subject to independent inspection?'),
    ],
    'GO': [
        ('SOP Compliance',      'GO-1.1',  'Are ramp operations procedures current and followed by all ground staff?'),
        ('SOP Compliance',      'GO-1.2',  'Are aircraft loading instructions and mass & balance procedures complied with?'),
        ('Training Records',    'GO-2.1',  'Are all ramp agents trained and current on vehicle airside driving?'),
        ('Training Records',    'GO-2.2',  'Are dangerous goods handling training records maintained for all staff?'),
        ('Safety Reporting',    'GO-3.1',  'Are ramp incidents and near-misses reported to the safety system?'),
        ('Risk Management',     'GO-4.1',  'Are FOD inspection procedures conducted before aircraft movement?'),
        ('Operational Procedures', 'GO-5.1', 'Are pushback procedures followed including communication protocols?'),
        ('Operational Procedures', 'GO-5.2', 'Are fuelling safety procedures and bonding requirements enforced?'),
    ],
    'CC': [
        ('SOP Compliance',      'CC-1.1',  'Are cabin crew procedures consistent with approved cabin safety manual?'),
        ('Training Records',    'CC-2.1',  'Are all cabin crew recurrent safety training records current?'),
        ('Training Records',    'CC-2.2',  'Are SEP (Safety & Emergency Procedures) drills completed on schedule?'),
        ('Safety Reporting',    'CC-3.1',  'Are cabin safety incidents reported through the SMS system?'),
        ('Risk Management',     'CC-4.1',  'Are pre-flight safety checks documented and completed for all flights?'),
        ('Operational Procedures', 'CC-5.1', 'Are passenger safety briefings conducted per approved procedure?'),
        ('Operational Procedures', 'CC-5.2', 'Are turbulence/emergency protocols reviewed and practised by crew?'),
    ],
    'SD': [
        ('SOP Compliance',      'SD-1.1',  'Is the SMS manual current, approved and distributed to all departments?'),
        ('Training Records',    'SD-2.1',  'Have all staff completed SMS awareness training within the required period?'),
        ('Safety Reporting',    'SD-3.1',  'Are all safety reports triaged, investigated and actioned within KPI timelines?'),
        ('Safety Reporting',    'SD-3.2',  'Are safety statistics reported to management at defined intervals?'),
        ('Risk Management',     'SD-4.1',  'Is the hazard register reviewed and updated quarterly?'),
        ('Risk Management',     'SD-4.2',  'Are SPI/SPT targets reviewed by the Safety Review Board?'),
        ('Operational Procedures', 'SD-5.1', 'Are Safety Review Board meetings held per schedule with full attendance?'),
        ('Operational Procedures', 'SD-5.2', 'Is the audit programme implemented as planned for the current year?'),
    ],
}

def get_checklist_template(dept_code):
    return CHECKLIST_TEMPLATES.get(dept_code, CHECKLIST_TEMPLATES['default'])


# ─── AUDIT PLAN ───────────────────────────────────────────────────────────────
# ─── CHECKLIST TEMPLATE MANAGEMENT ──────────────────────────────────────────

@app.route('/audit-checklists')
@require_login
def checklist_templates():
    """List all department checklist templates."""
    templates = ChecklistTemplate.query.filter_by(is_active=True).all()
    return render_template('audit/checklist_templates.html',
                           templates=templates)


@app.route('/audit-checklists/<int:dept_id>', methods=['GET','POST'])
def checklist_template_dept(dept_id):
    """
    Editable checklist template for a specific department.
    GET  = show current template with edit UI
    POST = save updated template as new version → becomes active
    """
    dept = Department.query.get_or_404(dept_id)
    audit_type = request.args.get('audit_type', 'Internal')

    if request.method == 'POST':
        action = request.form.get('action', 'save')

        if action == 'save':
            # Deactivate old templates for this dept+type
            ChecklistTemplate.query.filter_by(
                department_id=dept_id, audit_type=audit_type
            ).update({'is_active': False})

            # Get version number
            last = ChecklistTemplate.query.filter_by(
                department_id=dept_id, audit_type=audit_type
            ).order_by(ChecklistTemplate.version.desc()).first()
            ver = (last.version + 1) if last else 1

            tmpl = ChecklistTemplate(
                department_id=dept_id,
                audit_type=audit_type,
                name=f'{dept.name} — {audit_type} Audit Checklist v{ver}',
                version=ver,
                is_active=True,
            )
            db.session.add(tmpl)
            db.session.flush()

            # Save items from form
            refs     = request.form.getlist('item_ref')
            cats     = request.form.getlist('category')
            qs       = request.form.getlist('question')
            iosa_refs= request.form.getlist('iosa_ref')
            for i, (ref, cat, q, iosa) in enumerate(zip(refs, cats, qs, iosa_refs)):
                if q.strip():
                    db.session.add(ChecklistTemplateItem(
                        template_id=tmpl.id,
                        item_ref=ref.strip(),
                        category=cat.strip(),
                        question=q.strip(),
                        iosa_ref=iosa.strip(),
                        sequence=i,
                    ))

            db.session.commit()
            flash(f'✓ Checklist saved as version {ver}. Will be used for future {dept.name} audits.', 'success')

        elif action == 'add_item':
            # Quick add single item
            tmpl = ChecklistTemplate.query.filter_by(
                department_id=dept_id, audit_type=audit_type, is_active=True
            ).first()
            if tmpl:
                seq = len(tmpl.items)
                db.session.add(ChecklistTemplateItem(
                    template_id=tmpl.id,
                    item_ref=request.form.get('item_ref',''),
                    category=request.form.get('category','General'),
                    question=request.form.get('question',''),
                    iosa_ref=request.form.get('iosa_ref',''),
                    sequence=seq,
                ))
                db.session.commit()
                flash('✓ Item added.', 'success')

        return redirect(url_for('checklist_template_dept',
                                dept_id=dept_id, audit_type=audit_type))

    # GET — load active template
    tmpl = ChecklistTemplate.query.filter_by(
        department_id=dept_id, audit_type=audit_type, is_active=True
    ).first()
    all_versions = ChecklistTemplate.query.filter_by(
        department_id=dept_id, audit_type=audit_type
    ).order_by(ChecklistTemplate.version.desc()).all()
    # Group by category for display
    grouped = {}
    if tmpl:
        for item in tmpl.items:
            grouped.setdefault(item.category, []).append(item)

    audit_types = ['Internal', 'External', 'IOSA', 'Regulatory', 'Safety']
    return render_template('audit/checklist_template_edit.html',
                           dept=dept, tmpl=tmpl, grouped=grouped,
                           audit_type=audit_type, audit_types=audit_types,
                           all_versions=all_versions)


@app.route('/audit-findings-report')
@require_login
def audit_findings_report():
    """System-wide Audit Findings List Report with filters."""
    dept_f   = request.args.get('dept', '')
    sev_f    = request.args.get('severity', '')
    status_f = request.args.get('status', '')
    audit_f  = request.args.get('audit', '')
    q_f      = request.args.get('q', '').strip()

    query = AuditFinding.query
    if dept_f:
        # Filter via schedule → department
        query = query.join(AuditSchedule, AuditFinding.schedule_id == AuditSchedule.id)                     .filter(AuditSchedule.department_id == int(dept_f))
    if sev_f:
        query = query.filter(AuditFinding.severity == sev_f)
    if status_f:
        query = query.filter(AuditFinding.status == status_f)
    if audit_f:
        query = query.filter(AuditFinding.schedule_id == audit_f)
    if q_f:
        query = query.filter(
            AuditFinding.description.ilike(f'%{q_f}%') |
            AuditFinding.root_cause.ilike(f'%{q_f}%') |
            AuditFinding.finding_ref.ilike(f'%{q_f}%')
        )

    findings = query.order_by(AuditFinding.created_at.desc()).all()

    # Stats
    total    = AuditFinding.query.count()
    open_c   = AuditFinding.query.filter_by(status='Open').count()
    closed_c = AuditFinding.query.filter_by(status='Closed').count()
    overdue_c= AuditFinding.query.filter_by(status='Overdue').count()

    schedules = AuditSchedule.query.all()

    return render_template('audit/audit_findings_report.html',
                           findings=findings, total=total,
                           open_c=open_c, closed_c=closed_c, overdue_c=overdue_c,
                           dept_f=dept_f, sev_f=sev_f, status_f=status_f,
                           audit_f=audit_f, q_f=q_f, schedules=schedules)


@app.route('/audit-schedule-calendar')
@require_login
def audit_schedule_calendar():
    """Calendar view of all scheduled audits."""
    year  = int(request.args.get('year',  datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    dept_f= request.args.get('dept', '')

    # Get all schedules for the selected month/year
    from calendar import monthrange
    _, days_in_month = monthrange(year, month)

    q = AuditSchedule.query
    if dept_f:
        q = q.filter_by(department_id=int(dept_f))
    all_schedules = q.all()

    # Group by day for calendar display
    cal_data = {}  # day → list of schedules
    for s in all_schedules:
        if s.scheduled_date:
            try:
                from datetime import date as dt_date
                sd = dt_date.fromisoformat(s.scheduled_date)
                if sd.year == year and sd.month == month:
                    cal_data.setdefault(sd.day, []).append(s)
            except Exception:
                pass

    # Prev/next month
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    import calendar
    first_weekday = calendar.monthrange(year, month)[0]  # 0=Mon

    MONTH_NAMES = ['January','February','March','April','May','June',
                   'July','August','September','October','November','December']

    return render_template('audit/audit_schedule_calendar.html',
                           year=year, month=month,
                           month_name=MONTH_NAMES[month-1],
                           days_in_month=days_in_month,
                           first_weekday=first_weekday,
                           cal_data=cal_data,
                           prev_year=prev_year, prev_month=prev_month,
                           next_year=next_year, next_month=next_month,
                           dept_f=dept_f)


@app.route('/audit-plans')
@require_login
def audit_plans():
    year_f     = request.args.get('year', datetime.now().year, type=int)
    dept_f     = request.args.get('dept', '', type=str)
    month_f    = request.args.get('month', 0, type=int)
    all_plans  = AuditPlan.query.order_by(AuditPlan.year.desc(), AuditPlan.month).all()
    years      = list(range(datetime.now().year - 1, datetime.now().year + 3))
    this_month = datetime.now().month
    this_year  = datetime.now().year

    # Build monthly grid
    grid = {m: [] for m in range(1, 13)}
    year_plans = []
    for p in all_plans:
        if p.year == year_f:
            # Apply dept filter
            if dept_f and str(p.department_id) != dept_f:
                continue
            # Apply month filter
            if month_f and p.month != month_f:
                continue
            year_plans.append(p)
            if p.month:
                grid[p.month].append(p)

    total_p     = len(year_plans)
    completed_p = sum(1 for p in year_plans if p.status == 'Completed')
    active_p    = sum(1 for p in year_plans if p.status == 'Active')

    # Alert data — audits THIS month
    alerts_this_month = [
        p for p in all_plans
        if p.year == this_year and p.month == this_month and p.status != 'Completed'
    ]
    # Upcoming — next 2 months
    upcoming = [
        p for p in all_plans
        if p.year == this_year
        and p.month in [this_month + 1, this_month + 2]
        and p.status != 'Completed'
    ]
    # Overdue — past months this year, not completed
    overdue_plans = [
        p for p in all_plans
        if p.year == this_year
        and p.month is not None
        and p.month < this_month
        and p.status != 'Completed'
    ]

    return render_template('audit/audit_plan_list.html',
                           plans=year_plans, grid=grid,
                           year_f=year_f, years=years,
                           dept_f=dept_f, month_f=month_f,
                           total_p=total_p, completed_p=completed_p, active_p=active_p,
                           alerts_this_month=alerts_this_month,
                           upcoming=upcoming,
                           overdue_plans=overdue_plans,
                           this_month=this_month)

@app.route('/audit-plans/new', methods=['GET', 'POST'])
def new_audit_plan():
    if request.method == 'POST':
        f   = request.form
        pid = new_id('PLAN')
        p   = AuditPlan(
            id=pid,
            year=int(f['year']),
            month=int(f['month']) if f.get('month') else None,
            department_id=int(f['department_id']),
            audit_type=f['audit_type'],
            frequency=f.get('frequency', 'Annual'),
            responsible_manager=f.get('responsible_manager', ''),
            auditor_name=f.get('auditor_name', ''),
            planned_week=int(f['planned_week']) if f.get('planned_week') else None,
            scope=f.get('scope', ''),
            objectives=f.get('objectives', ''),
            iosa_reference=f.get('iosa_reference', ''),
            status='Planned'
        )
        db.session.add(p)
        db.session.commit()
        flash(f'✓ Audit Plan {pid} saved — {p.audit_type} for {f["year"]}.', 'success')
        return redirect(url_for('audit_plans') + f'?year={f["year"]}')
    years = list(range(datetime.now().year, datetime.now().year + 3))
    return render_template('audit/audit_plan_form.html', years=years)


@app.route('/audit-plans/<pid>/edit', methods=['GET','POST'])
def edit_audit_plan(pid):
    p = AuditPlan.query.get_or_404(pid)
    if request.method == 'POST':
        f = request.form
        p.year               = int(f['year'])
        p.month              = int(f['month']) if f.get('month') else None
        p.department_id      = int(f['department_id'])
        p.audit_type         = f['audit_type']
        p.frequency          = f.get('frequency', p.frequency)
        p.responsible_manager = f.get('responsible_manager', p.responsible_manager)
        p.auditor_name       = f.get('auditor_name', p.auditor_name)
        p.planned_week       = int(f['planned_week']) if f.get('planned_week') else None
        p.scope              = f.get('scope', p.scope)
        p.objectives         = f.get('objectives', p.objectives)
        p.iosa_reference     = f.get('iosa_reference', p.iosa_reference)
        p.status             = f.get('status', p.status)
        db.session.commit()
        flash(f'✓ Audit Plan {p.id} updated.', 'success')
        return redirect(url_for('audit_plans') + f'?year={p.year}')
    years = list(range(datetime.now().year, datetime.now().year + 3))
    return render_template('audit/audit_plan_form.html', years=years, edit=p)

@app.route('/audit-plans/<pid>/delete', methods=['POST'])
def delete_audit_plan(pid):
    p = AuditPlan.query.get_or_404(pid)
    year = p.year
    try:
        # Safely cascade: unlink schedules plan_id first, then delete schedules
        schedules = AuditSchedule.query.filter_by(plan_id=pid).all() if hasattr(AuditSchedule, 'plan_id') else (p.schedules if hasattr(p, 'schedules') else [])
        for s in schedules:
            # Each schedule: nullify checklist linked_finding_id, delete actions/findings/checklists
            findings = AuditFinding.query.filter_by(schedule_id=s.id).all()
            fids = [f.id for f in findings]
            if fids:
                AuditChecklist.query.filter(
                    AuditChecklist.linked_finding_id.in_(fids)
                ).update({'linked_finding_id': None}, synchronize_session=False)
                AuditAction.query.filter(
                    AuditAction.finding_id.in_(fids)
                ).delete(synchronize_session=False)
            AuditChecklist.query.filter_by(schedule_id=s.id).delete(synchronize_session=False)
            for f in findings:
                db.session.delete(f)
            db.session.flush()
            db.session.delete(s)
        db.session.flush()
        db.session.delete(p)
        db.session.commit()
        flash(f'✓ Audit Plan {pid} deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'⚠ Could not delete {pid}: {str(e)[:120]}', 'error')
    return redirect(url_for('audit_plans') + f'?year={year}')

@app.route('/audit-plans/<pid>/complete', methods=['POST'])
def complete_audit_plan(pid):
    """Mark an audit plan entry as Completed."""
    p = AuditPlan.query.get_or_404(pid)
    p.status = 'Completed'
    db.session.commit()
    flash(f'✓ Audit plan {p.id} marked as Completed.', 'success')
    return redirect(url_for('audit_plans'))

@app.route('/audit-plans/<pid>/schedule', methods=['POST'])
def schedule_from_plan(pid):
    """Convert an audit plan entry into a scheduled audit."""
    plan = AuditPlan.query.get_or_404(pid)
    f    = request.form
    sid  = new_id('AUD')
    s = AuditSchedule(
        id=sid,
        plan_id=pid,
        department_id=plan.department_id,
        audit_type=plan.audit_type,
        scheduled_date=f['scheduled_date'],
        lead_auditor=f['lead_auditor'],
        audit_team=f.get('audit_team', ''),
        scope=plan.scope,
        objectives=plan.objectives,
        status='Planned'
    )
    db.session.add(s)
    # Auto-populate checklist from template
    dept = Department.query.get(plan.department_id)
    template = get_checklist_template(dept.code if dept else 'default')
    for idx, (cat, ref, question) in enumerate(template):
        item = AuditChecklist(
            schedule_id=sid, category=cat,
            item_ref=ref, question=question, sequence=idx
        )
        db.session.add(item)
    db.session.commit()
    flash(f'✓ Audit {sid} scheduled. Checklist auto-populated ({len(template)} items).', 'success')
    return redirect(url_for('audit_schedule'))


# ─── AUDIT SCHEDULE ───────────────────────────────────────────────────────────
@app.route('/audit-schedule')
@require_login
def audit_schedule():
    dept_f   = request.args.get('dept', '')
    status_f = request.args.get('status', '')
    q = AuditSchedule.query
    if dept_f:   q = q.filter_by(department_id=int(dept_f))
    if status_f: q = q.filter_by(status=status_f)
    schedules = q.order_by(AuditSchedule.scheduled_date).all()

    # Check/update overdue audit actions
    today = date.today().isoformat()
    changed = False
    for s in AuditSchedule.query.all():
        for f2 in s.findings:
            for a in f2.actions:
                if a.status in ('Open', 'In Progress') and a.due_date and a.due_date < today:
                    a.status = 'Overdue'
                    changed = True
    if changed:
        db.session.commit()

    return render_template('audit/audit_schedule.html', schedules=schedules,
                           dept_f=dept_f, status_f=status_f)

@app.route('/audit-schedule/new', methods=['GET', 'POST'])
def new_audit_schedule():
    """Create a scheduled audit without an existing plan (ad-hoc)."""
    if request.method == 'POST':
        f   = request.form
        sid = new_id('AUD')
        dept = Department.query.get(int(f['department_id']))
        s = AuditSchedule(
            id=sid, plan_id=None,
            department_id=int(f['department_id']),
            audit_type=f['audit_type'],
            scheduled_date=f['scheduled_date'],
            lead_auditor=f['lead_auditor'],
            audit_team=f.get('audit_team', ''),
            scope=f.get('scope', ''),
            objectives=f.get('objectives', ''),
            status='Planned'
        )
        db.session.add(s)
        # Auto-populate checklist
        template = get_checklist_template(dept.code if dept else 'default')
        for idx, (cat, ref, question) in enumerate(template):
            item = AuditChecklist(
                schedule_id=sid, category=cat,
                item_ref=ref, question=question, sequence=idx
            )
            db.session.add(item)
        db.session.commit()
        flash(f'✓ Audit {sid} created. Checklist auto-populated.', 'success')
        return redirect(url_for('audit_schedule'))
    return render_template('audit/audit_schedule_form.html')


# ─── AUDIT EXECUTION ─────────────────────────────────────────────────────────
@app.route('/audit-schedule/<sid>')
@require_login
def audit_execution(sid):
    s = AuditSchedule.query.get_or_404(sid)
    # Group checklist by category
    checklist = {}
    for item in sorted(s.checklist_items, key=lambda x: x.sequence):
        checklist.setdefault(item.category, []).append(item)
    total = len(s.checklist_items)
    done  = sum(1 for i in s.checklist_items if i.response)
    nc    = sum(1 for i in s.checklist_items if i.response == 'No')

    # Checklist NO items without findings
    no_items_without_findings = [
        i for cat_items in checklist.values()
        for i in cat_items
        if i.response == 'No' and not i.linked_finding_id
    ]
    all_no_have_findings = len(no_items_without_findings) == 0

    # All findings closed (using the new lifecycle status OR old AuditAction check)
    all_findings_closed = all(
        f.status == 'Closed' for f in s.findings
    ) if s.findings else True

    # AuditAction-based checks (legacy — some findings have AuditActions)
    findings_with_audit_actions = [f for f in s.findings if f.actions]
    all_findings_actioned = True  # satisfied if all findings are Closed
    all_actions_closed    = True
    all_verified          = True

    if findings_with_audit_actions:
        all_actions_closed = all(
            all(a.status == 'Closed' for a in f.actions)
            for f in findings_with_audit_actions
        )
        # Effectiveness is optional — don't block closure on it
        all_verified = True

    # CAN CLOSE: checklist complete + all findings closed
    can_close = (
        all_no_have_findings and
        all_findings_closed and
        all_actions_closed
    )

    return render_template('audit/audit_execution.html',
        s=s, checklist=checklist, total=total, done=done, nc=nc,
        can_close=can_close,
        no_items_without_findings=no_items_without_findings,
        all_no_have_findings=all_no_have_findings,
        all_findings_closed=all_findings_closed,
        all_findings_actioned=all_findings_actioned,
        all_actions_closed=all_actions_closed,
        all_verified=all_verified)

@app.route('/audit-schedule/<sid>/start', methods=['POST'])
def start_audit(sid):
    s = AuditSchedule.query.get_or_404(sid)
    s.status       = 'In Progress'
    s.actual_date  = date.today().isoformat()
    s.opening_meeting = request.form.get('opening_meeting', date.today().isoformat())

    # Auto-load checklist from latest saved department template
    if s.department_id and not s.checklist_items:
        from models import AuditChecklist
        tmpl = ChecklistTemplate.query.filter_by(
            department_id=s.department_id,
            audit_type=s.audit_type or 'Internal',
            is_active=True
        ).first()
        if tmpl and tmpl.items:
            for ti in tmpl.items:
                db.session.add(AuditChecklist(
                    schedule_id=sid,
                    category=ti.category,
                    item_ref=ti.item_ref,
                    question=ti.question,
                    sequence=ti.sequence,
                ))
            db.session.flush()
            flash(f'✓ Audit started. Loaded {len(tmpl.items)} items from {tmpl.name}.', 'success')
        else:
            # Fall back to static template (existing get_checklist_template logic)
            from models import AuditChecklist as ACL
            dept = Department.query.get(s.department_id)
            static_tmpl = get_checklist_template(dept.code if dept else 'default')
            for cat, items in static_tmpl.items():
                for seq, (ref, q) in enumerate(items):
                    db.session.add(ACL(
                        schedule_id=sid,
                        category=cat,
                        item_ref=ref,
                        question=q,
                        sequence=seq,
                    ))
            flash('✓ Audit started. Checklist loaded from default template.', 'success')

    db.session.commit()
    return redirect(url_for('audit_execution', sid=sid))

@app.route('/audit-schedule/<sid>/checklist', methods=['POST'])
def save_checklist(sid):
    """
    Save checklist responses.
    For any item answered 'No' without a linked finding:
    Auto-create a Finding inheriting checklist metadata.
    """
    s = AuditSchedule.query.get_or_404(sid)
    new_findings = []

    for item in s.checklist_items:
        prev_resp = item.response
        item.response = request.form.get(f'resp_{item.id}', '')
        item.comment  = request.form.get(f'comment_{item.id}', '')
        item.evidence = request.form.get(f'evidence_{item.id}', '')

        # Handle evidence file upload per checklist item
        ef_key = f'evidence_file_{item.id}'
        if ef_key in request.files:
            ef = request.files[ef_key]
            if ef and ef.filename and allowed_file(ef.filename):
                from werkzeug.utils import secure_filename
                fn = f'CL{item.id}_{secure_filename(ef.filename)}'
                ef.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                item.evidence_filename = fn

        # Auto-create Finding when answer flips to 'No' and no finding yet
        if item.response == 'No' and not item.linked_finding_id:
            count       = AuditFinding.query.filter_by(schedule_id=sid).count() + len(new_findings) + 1
            finding_ref = f'F-{count:03d}'
            fid = new_id('FND')
            finding = AuditFinding(
                id          = fid,
                schedule_id = sid,
                finding_ref = finding_ref,
                # Inherit checklist metadata
                description  = item.question or '',
                category     = item.category or 'Operational',
                severity     = 'Minor',
                standard_ref = item.item_ref or '',
                requirement  = item.question or '',
                evidence     = item.comment or item.evidence or '',
                assigned_to  = s.lead_auditor or '',
                status       = 'Open',
            )
            db.session.add(finding)
            db.session.flush()
            item.linked_finding_id = fid
            new_findings.append(finding_ref)

        # If answer changed FROM 'No' to something else → unlink auto-finding if still Open
        elif item.response != 'No' and prev_resp == 'No' and item.linked_finding_id:
            linked = AuditFinding.query.get(item.linked_finding_id)
            if linked and linked.status == 'Open':
                db.session.delete(linked)
                item.linked_finding_id = None

    db.session.commit()

    if new_findings:
        flash(f'✓ Checklist saved. Auto-created findings: {", ".join(new_findings)} for NO items.', 'success')
    else:
        flash('✓ Checklist saved.', 'success')
    return redirect(url_for('audit_execution', sid=sid))

@app.route('/audit-schedule/<sid>/close', methods=['POST'])
@require_login
def close_audit(sid):
    s = AuditSchedule.query.get_or_404(sid)
    # Validate: all NO checklist items must have linked findings
    no_without = [i for i in s.checklist_items
                  if i.response == 'No' and not i.linked_finding_id]
    if no_without:
        refs = ', '.join(i.item_ref or f'item {i.id}' for i in no_without[:3])
        flash(f'✗ Cannot close: {len(no_without)} checklist NO item(s) still need findings ({refs}).', 'error')
        return redirect(url_for('audit_execution', sid=sid))
    # Validate: all findings must be Closed OR have closed AuditActions
    if s.findings:
        for finding in s.findings:
            if finding.status != 'Closed':
                # Allow if all AuditActions are closed (legacy workflow)
                if finding.actions:
                    open_actions = [a for a in finding.actions if a.status != 'Closed']
                    if open_actions:
                        flash(f'✗ Cannot close: Finding {finding.finding_ref} — '
                              f'{len(open_actions)} action(s) not yet closed.', 'error')
                        return redirect(url_for('audit_execution', sid=sid))
                else:
                    flash(f'✗ Cannot close: Finding {finding.finding_ref} is not yet Closed '
                          f'(current status: {finding.status}).', 'error')
                    return redirect(url_for('audit_execution', sid=sid))
    s.status        = 'Completed'
    s.closure_date  = date.today().isoformat()
    s.closed_by     = request.form.get('closed_by', 'Safety Manager')
    s.final_remarks = request.form.get('final_remarks', '')
    s.closing_meeting = request.form.get('closing_meeting', date.today().isoformat())
    db.session.commit()
    flash(f'✓ Audit {sid} closed and marked Completed.', 'success')
    return redirect(url_for('audit_execution', sid=sid))
    s.final_remarks = request.form.get('final_remarks', '')
    s.closing_meeting = request.form.get('closing_meeting', date.today().isoformat())
    db.session.commit()
    flash(f'✓ Audit {sid} closed successfully. All conditions met.', 'success')
    return redirect(url_for('audit_execution', sid=sid))


# ─── AUDIT FINDINGS ───────────────────────────────────────────────────────────
@app.route('/audit-schedule/<sid>/findings/new', methods=['POST'])
def new_finding(sid):
    s   = AuditSchedule.query.get_or_404(sid)
    f   = request.form
    fid = new_id('FND')

    # Count findings for this audit to generate ref
    count      = len(s.findings) + 1
    finding_ref = f'F-{count:03d}'

    finding = AuditFinding(
        id=fid, schedule_id=sid,
        finding_ref=finding_ref,
        description=f['description'],
        category=f['category'],
        severity=f['severity'],
        standard_ref=f.get('standard_ref', ''),
        root_cause=f.get('root_cause', ''),
        evidence=f.get('evidence', ''),
        requirement=f.get('requirement', ''),
        status='Open'
    )
    db.session.add(finding)
    db.session.flush()

    # Auto-create Hazard in main SMS Hazard Log
    auto_hazard = f.get('auto_hazard') == 'yes'
    hid = None
    if auto_hazard:
        hid  = new_id('HAZ')
        sev  = f.get('risk_severity', 'C')
        lik  = int(f.get('risk_likelihood', 3))
        ri   = f'{lik}{sev}'
        tol  = get_tolerance(ri)
        h = Hazard(
            id=hid, source='Audit',
            linked_report_id=fid,
            department_id=s.department_id,
            classification='Organizational',
            type_of_activity='Audit Finding',
            generic_hazard=f['description'][:120],
            specific_components=f.get('root_cause', ''),
            consequences='To be assessed by Safety Department',
            status='Open',
            owner=f.get('action_owner', 'Safety Manager')
        )
        db.session.add(h)
        db.session.flush()
        risk = Risk(
            id=new_id('RSK'), hazard_id=hid,
            description=f['description'],
            initial_likelihood=lik, initial_severity=sev,
            initial_risk_index=ri, initial_tolerance=tol
        )
        db.session.add(risk)
        finding.hazard_id = hid

    # Auto-create in BOTH tables: unified Action (visible everywhere) + AuditAction (for verification)
    act_desc = f.get('action_description', f['description'])
    act_owner = f.get('action_owner', '')
    act_due   = f.get('due_date', '')
    act_pri   = 'High' if f['severity'] == 'Major' else 'Medium'

    # 1. Unified Action table — appears in main Actions dashboard
    unified_id = new_id('ACT')
    unified_action = Action(
        id=unified_id, source='Audit',
        hazard_id=hid, linked_ref_id=fid,
        description=act_desc, owner=act_owner,
        due_date=act_due, priority=act_pri, status='Open'
    )
    db.session.add(unified_action)

    # 2. AuditAction table — for audit-specific effectiveness/verification tracking
    audit_action = AuditAction(
        id=new_id('ACT'), finding_id=fid,
        hazard_id=hid, description=act_desc,
        action_type='Corrective', owner=act_owner,
        due_date=act_due, priority=act_pri, status='Open'
    )
    db.session.add(audit_action)
    finding.status = 'Actioned'
    db.session.commit()

    msg = f'✓ Finding {finding_ref} recorded. Action {unified_action.id} created.'
    if hid: msg += f' Hazard {hid} created in SMS Hazard Log.'
    flash(msg, 'success')
    return redirect(url_for('audit_execution', sid=sid))


# ─── FINDING DETAIL ───────────────────────────────────────────────────────────
@app.route('/audit-findings/<fid>', methods=['GET','POST'])
def finding_detail(fid):
    """Finding detail with full lifecycle: auditee CAP submission + safety review."""
    finding = AuditFinding.query.get_or_404(fid)
    schedule = AuditSchedule.query.get(finding.schedule_id)

    if request.method == 'POST':
        action = request.form.get('form_action', '')
        f = request.form

        if action == 'assign':
            finding.assigned_to   = f.get('assigned_to', '')
            finding.assigned_dept = f.get('assigned_dept', '')
            finding.assigned_date = datetime.now().strftime('%Y-%m-%d')
            finding.status = 'Assigned'
            db.session.commit()
            flash(f'✓ Finding {fid} assigned to {finding.assigned_to}.', 'success')

        elif action == 'submit_root_cause':
            finding.root_cause           = f.get('root_cause', '')
            finding.investigation_notes  = f.get('investigation_notes', '')
            finding.contributing_factors = f.get('contributing_factors', '')
            finding.immediate_action     = f.get('immediate_action', '')
            finding.longterm_action      = f.get('longterm_action', '')
            finding.root_cause_submitted_at = datetime.utcnow()
            finding.status = 'Root Cause Submitted'
            db.session.commit()
            flash('✓ Root cause and corrective actions submitted.', 'success')

        elif action == 'submit_cap':
            finding.cap_responsible    = f.get('cap_responsible', '')
            finding.cap_due_date       = f.get('cap_due_date', '')
            finding.cap_completion_pct = int(f.get('cap_completion_pct', 0))
            finding.cap_status         = 'In Progress'
            finding.cap_submitted_at   = datetime.utcnow()
            # Handle evidence file uploads
            files = request.files.getlist('evidence_files')
            new_files = []
            for ef in files:
                if ef and ef.filename and allowed_file(ef.filename):
                    from werkzeug.utils import secure_filename
                    fname = f"{fid}_{secure_filename(ef.filename)}"
                    ef.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                    new_files.append(fname)
            if new_files:
                existing = [x for x in (finding.evidence_files or '').split(',') if x]
                finding.evidence_files = ','.join(existing + new_files)
            finding.status = 'CAP Submitted'
            # Auto-create Action in main Action module if not already done
            if not finding.linked_action_id and f.get('create_action') == 'yes':
                from models import Action
                aid = new_id('ACT')
                a = Action(
                    id=aid, source='Audit',
                    linked_ref_id=fid,
                    description=f'[{finding.finding_ref}] {(finding.immediate_action or finding.description or "")[:200]}',
                    owner=finding.cap_responsible or finding.assigned_to or '',
                    due_date=finding.cap_due_date or '',
                    priority='High' if finding.severity == 'Major' else 'Medium',
                    status='Open'
                )
                db.session.add(a)
                finding.linked_action_id = aid
            db.session.commit()
            flash('✓ CAP submitted and sent for Safety review.', 'success')

        elif action == 'submit_for_review':
            finding.status = 'Under Safety Review'
            db.session.commit()
            flash('✓ Finding submitted for Safety review.', 'success')

        elif action == 'safety_accept':
            finding.reviewed_by   = f.get('reviewed_by', '')
            finding.review_date   = datetime.now().strftime('%Y-%m-%d')
            finding.review_notes  = f.get('review_notes', '')
            finding.status = 'Accepted'
            db.session.commit()
            flash('✓ Finding accepted by Safety.', 'success')

        elif action == 'safety_return':
            finding.revision_reason = f.get('revision_reason', '')
            finding.reviewed_by     = f.get('reviewed_by', '')
            finding.status = 'Returned for Revision'
            db.session.commit()
            flash('⚠ Finding returned to auditee for revision.', 'warning')

        elif action == 'close_finding':
            finding.closure_verified_by = f.get('closure_verified_by', '')
            finding.closure_date        = datetime.now().strftime('%Y-%m-%d')
            finding.closure_notes       = f.get('closure_notes', '')
            finding.sig_dept_manager    = f.get('sig_dept_manager', '')
            finding.sig_auditor         = f.get('sig_auditor', '')
            finding.sig_safety_manager  = f.get('sig_safety_manager', '')
            finding.sig_date            = datetime.now().strftime('%Y-%m-%d')
            finding.cap_status          = 'Completed'
            finding.cap_completion_pct  = 100
            finding.status = 'Closed'
            # Update linked Action to Closed
            if finding.linked_action_id:
                from models import Action
                la = Action.query.get(finding.linked_action_id)
                if la:
                    la.status = 'Closed'
                    la.closed_date = finding.closure_date
            db.session.commit()
            flash(f'✓ Finding {fid} closed and verified.', 'success')

        elif action == 'reopen':
            finding.status = 'Assigned'
            finding.closure_date = None
            db.session.commit()
            flash('⚠ Finding reopened.', 'warning')

        elif action == 'update_cap_progress':
            finding.cap_completion_pct = int(f.get('cap_completion_pct', 0))
            finding.cap_status = f.get('cap_status', finding.cap_status)
            # Check overdue
            if finding.cap_due_date:
                from datetime import date
                try:
                    due = date.fromisoformat(finding.cap_due_date)
                    if date.today() > due and finding.cap_status != 'Completed':
                        finding.status = 'Overdue'
                        finding.cap_status = 'Overdue'
                except Exception:
                    pass
            db.session.commit()
            flash('✓ CAP progress updated.', 'success')

        return redirect(url_for('finding_detail', fid=fid))

    # Check overdue status on GET
    if finding.cap_due_date and finding.status not in ('Closed', 'Accepted'):
        from datetime import date
        try:
            due = date.fromisoformat(finding.cap_due_date)
            if date.today() > due and finding.status not in ('Closed', 'Accepted'):
                finding.status = 'Overdue'
                finding.cap_status = 'Overdue'
                db.session.commit()
        except Exception:
            pass

    # Evidence files list
    evidence_file_list = [x for x in (finding.evidence_files or '').split(',') if x]

    # Linked Action
    linked_action = None
    if finding.linked_action_id:
        from models import Action
        linked_action = Action.query.get(finding.linked_action_id)

    return render_template('audit/finding_detail.html',
                           finding=finding, schedule=schedule,
                           evidence_file_list=evidence_file_list,
                           linked_action=linked_action,
                           now=datetime.utcnow())


@app.route('/audit-findings/<fid>/report')
def finding_report(fid):
    """Print-ready finding closure report."""
    finding = AuditFinding.query.get_or_404(fid)
    schedule = AuditSchedule.query.get(finding.schedule_id)
    evidence_file_list = [x for x in (finding.evidence_files or '').split(',') if x]
    MONTHS = ['January','February','March','April','May','June',
              'July','August','September','October','November','December']
    return render_template('audit/finding_report.html',
                           finding=finding, schedule=schedule,
                           evidence_file_list=evidence_file_list,
                           now=datetime.utcnow(), MONTHS=MONTHS)


@app.route('/audit-schedule/<sid>/final-report')
def audit_final_report(sid):
    """Full Final Audit Report — all findings + closures."""
    schedule = AuditSchedule.query.get_or_404(sid)
    plan = AuditPlan.query.get(schedule.plan_id) if schedule.plan_id else None
    findings = AuditFinding.query.filter_by(schedule_id=sid).all()
    # Overdue check
    from datetime import date
    for f in findings:
        if f.cap_due_date and f.status not in ('Closed','Accepted'):
            try:
                if date.today() > date.fromisoformat(f.cap_due_date):
                    f.status = 'Overdue'; f.cap_status = 'Overdue'
            except Exception: pass
    db.session.commit()
    all_closed  = all(f.status == 'Closed' for f in findings) if findings else False
    return render_template('audit/audit_final_report.html',
                           schedule=schedule, plan=plan, findings=findings,
                           all_closed=all_closed, now=datetime.utcnow())


# ─── AUDIT ACTIONS ────────────────────────────────────────────────────────────
@app.route('/audit-actions')
def audit_actions():
    today    = date.today().isoformat()
    status_f = request.args.get('status', '')
    pri_f    = request.args.get('priority', '')
    q = AuditAction.query
    if status_f: q = q.filter_by(status=status_f)
    if pri_f:    q = q.filter_by(priority=pri_f)

    # Auto-mark overdue
    for a in AuditAction.query.filter(AuditAction.status.in_(['Open', 'In Progress'])).all():
        if a.due_date and a.due_date < today:
            a.status = 'Overdue'
    db.session.commit()

    actions  = q.order_by(AuditAction.created_at.desc()).all()
    open_c   = AuditAction.query.filter_by(status='Open').count()
    inprog   = AuditAction.query.filter_by(status='In Progress').count()
    overdue  = AuditAction.query.filter_by(status='Overdue').count()
    closed   = AuditAction.query.filter_by(status='Closed').count()
    return render_template('audit/audit_actions.html',
        actions=actions, open_c=open_c, inprog=inprog,
        overdue=overdue, closed=closed,
        status_f=status_f, pri_f=pri_f)

@app.route('/audit-actions/<aid>/update', methods=['POST'])
def update_audit_action(aid):
    a = AuditAction.query.get_or_404(aid)
    f = request.form
    a.status               = f.get('status', a.status)
    a.owner                = f.get('owner', a.owner)
    a.due_date             = f.get('due_date', a.due_date)
    a.priority             = f.get('priority', a.priority)
    a.implementation_notes = f.get('implementation_notes', a.implementation_notes)
    a.effectiveness        = f.get('effectiveness', a.effectiveness)
    a.effectiveness_notes  = f.get('effectiveness_notes', a.effectiveness_notes)
    a.verified_by          = f.get('verified_by', a.verified_by)
    a.verification_date    = f.get('verification_date', a.verification_date)
    if a.status == 'Closed':
        a.closed_date = date.today().isoformat()
        # Update parent finding status
        if a.finding and all(x.status == 'Closed' for x in a.finding.actions):
            a.finding.status = 'Closed'
    # Reopen if ineffective
    if a.effectiveness == 'Ineffective' and a.reopen_reason is None:
        a.status         = 'Open'
        a.reopen_reason  = f.get('reopen_reason', 'Re-opened: action was ineffective')
        a.effectiveness  = None
        if a.finding:
            a.finding.status = 'Open'
        flash('⚠ Action re-opened: effectiveness was Ineffective.', 'error')
    else:
        flash('✓ Action updated.', 'success')
    db.session.commit()
    return redirect(url_for('audit_actions'))


# ─── AUDIT DASHBOARD (summary view) ──────────────────────────────────────────
@app.route('/audit-dashboard')
@require_login
def audit_dashboard():
    total_plans     = AuditPlan.query.count()
    total_scheduled = AuditSchedule.query.count()
    in_progress     = AuditSchedule.query.filter_by(status='In Progress').count()
    completed       = AuditSchedule.query.filter_by(status='Completed').count()
    planned         = AuditSchedule.query.filter_by(status='Planned').count()
    total_findings  = AuditFinding.query.count()
    major           = AuditFinding.query.filter_by(severity='Major').count()
    minor           = AuditFinding.query.filter_by(severity='Minor').count()
    obs             = AuditFinding.query.filter_by(severity='Observation').count()
    open_actions    = AuditAction.query.filter_by(status='Open').count()
    overdue_actions = AuditAction.query.filter_by(status='Overdue').count()

    recent_audits   = AuditSchedule.query.order_by(
        AuditSchedule.scheduled_date.desc()).limit(5).all()
    recent_findings = AuditFinding.query.order_by(
        AuditFinding.created_at.desc()).limit(5).all()

    return render_template('audit/audit_dashboard.html',
        total_plans=total_plans, total_scheduled=total_scheduled,
        in_progress=in_progress, completed=completed, planned=planned,
        total_findings=total_findings, major=major, minor=minor, obs=obs,
        open_actions=open_actions, overdue_actions=overdue_actions,
        recent_audits=recent_audits, recent_findings=recent_findings)

# ─── Init ─────────────────────────────────────────────────────────────────────

# ═══════════════════════════════════════════════════════════════════════════════
#  SAFETY POLICY & OBJECTIVES — COMPONENT 1 OF SMS
#  ICAO Annex 19 §3 / Doc 9859 Ch.3 — Extension only, no existing code changed
# ═══════════════════════════════════════════════════════════════════════════════

# ── Document ID generator ────────────────────────────────────────────────────
def gen_doc_id(doc_type, dept_code, year, seq, rev=0):
    return f"{doc_type}-{dept_code}-{year}-{seq:03d}-REV{rev}"

def next_seq(doc_type, dept_id, year):
    existing = SMSDocument.query.filter_by(
        doc_type=doc_type, department_id=dept_id).filter(
        SMSDocument.id.like(f"%-{year}-%")).count()
    return existing + 1

# ─── SAFETY POLICY ───────────────────────────────────────────────────────────
@app.route('/safety-policy')
@require_login
def safety_policy():
    active  = SafetyPolicy.query.filter_by(status='Active').first()
    history = SafetyPolicy.query.filter_by(status='Archived').order_by(
              SafetyPolicy.version_num.desc()).all()
    drafts  = SafetyPolicy.query.filter_by(status='Draft').all()
    return render_template('safety_policy/policy.html',
                           active=active, history=history, drafts=drafts)

@app.route('/safety-policy/new', methods=['GET','POST'])
def new_safety_policy():
    if request.method == 'POST':
        f = request.form
        # Get current max version
        latest = SafetyPolicy.query.order_by(
                 SafetyPolicy.version_num.desc()).first()
        ver_num = (latest.version_num + 1) if latest else 0
        pid = new_id('POL')
        p = SafetyPolicy(
            id=pid, version=f'REV{ver_num}', version_num=ver_num,
            title=f['title'], content=f['content'],
            approved_by=f['approved_by'],
            approved_by_title=f.get('approved_by_title','Accountable Manager'),
            effective_date=f['effective_date'],
            review_date=f.get('review_date',''),
            status='Draft',
            change_summary=f.get('change_summary','Initial issue') if ver_num==0 else f.get('change_summary','')
        )
        db.session.add(p)
        db.session.commit()
        flash(f'✓ Safety Policy {pid} created as REV{ver_num} (Draft).', 'success')
        return redirect(url_for('safety_policy'))
    latest = SafetyPolicy.query.order_by(SafetyPolicy.version_num.desc()).first()
    next_ver = (latest.version_num + 1) if latest else 0
    return render_template('safety_policy/policy_form.html', next_ver=next_ver, latest=latest)

@app.route('/safety-policy/<pid>/activate', methods=['POST'])
def activate_policy(pid):
    # Archive current active
    current = SafetyPolicy.query.filter_by(status='Active').first()
    if current:
        current.status = 'Archived'
    policy = SafetyPolicy.query.get_or_404(pid)
    policy.status = 'Active'
    db.session.commit()
    flash(f'✓ Policy {policy.version} is now Active. Previous version archived.', 'success')
    return redirect(url_for('safety_policy'))

@app.route('/safety-policy/<pid>/edit', methods=['POST'])
def edit_policy(pid):
    p = SafetyPolicy.query.get_or_404(pid)
    f = request.form
    if p.status == 'Archived':
        flash('Cannot edit archived policy.', 'error')
        return redirect(url_for('safety_policy'))
    p.content          = f.get('content', p.content)
    p.approved_by      = f.get('approved_by', p.approved_by)
    p.effective_date   = f.get('effective_date', p.effective_date)
    p.review_date      = f.get('review_date', p.review_date)
    p.change_summary   = f.get('change_summary', p.change_summary)
    db.session.commit()
    flash('✓ Policy updated.', 'success')
    return redirect(url_for('safety_policy'))

# ─── SAFETY ACCOUNTABILITY (ROLES) ───────────────────────────────────────────
@app.route('/safety-roles')
@require_login
def safety_roles():
    roles = SafetyRole.query.filter_by(active=True).order_by(SafetyRole.role_type).all()
    return render_template('safety_policy/roles.html', roles=roles)

@app.route('/safety-roles/new', methods=['GET','POST'])
def new_safety_role():
    if request.method == 'POST':
        f = request.form
        r = SafetyRole(
            id=new_id('ROLE'),
            role_name=f['role_name'],
            role_type=f['role_type'],
            person_name=f['person_name'],
            department_id=int(f['department_id']) if f.get('department_id') else None,
            responsibilities=f.get('responsibilities',''),
            authority=f.get('authority',''),
            contact_email=f.get('contact_email',''),
            contact_phone=f.get('contact_phone',''),
            effective_from=f.get('effective_from',''),
            active=True
        )
        db.session.add(r)
        db.session.commit()
        flash(f'✓ Role {r.role_name} assigned to {r.person_name}.', 'success')
        return redirect(url_for('safety_roles'))
    return render_template('safety_policy/role_form.html')

@app.route('/safety-roles/<rid>/update', methods=['POST'])
def update_safety_role(rid):
    r = SafetyRole.query.get_or_404(rid)
    f = request.form
    r.person_name      = f.get('person_name', r.person_name)
    r.responsibilities = f.get('responsibilities', r.responsibilities)
    r.authority        = f.get('authority', r.authority)
    r.contact_email    = f.get('contact_email', r.contact_email)
    r.contact_phone    = f.get('contact_phone', r.contact_phone)
    r.active           = f.get('active','true') == 'true'
    db.session.commit()
    flash('✓ Role updated.', 'success')
    return redirect(url_for('safety_roles'))

# ─── KEY SAFETY PERSONNEL ─────────────────────────────────────────────────────
@app.route('/safety-personnel')
@require_login
def safety_personnel():
    personnel = SafetyPersonnel.query.filter_by(active=True).order_by(
                SafetyPersonnel.sms_role).all()
    return render_template('safety_policy/personnel.html', personnel=personnel)

@app.route('/safety-personnel/new', methods=['GET','POST'])
def new_safety_personnel():
    if request.method == 'POST':
        f = request.form
        p = SafetyPersonnel(
            id=new_id('PERS'),
            name=f['name'], position=f['position'],
            department_id=int(f['department_id']) if f.get('department_id') else None,
            sms_role=f.get('sms_role',''),
            qualifications=f.get('qualifications',''),
            contact_email=f.get('contact_email',''),
            contact_phone=f.get('contact_phone',''),
            sms_trained=f.get('sms_trained') == 'yes',
            training_date=f.get('training_date',''),
            active=True
        )
        db.session.add(p)
        db.session.commit()
        flash(f'✓ Personnel record created for {p.name}.', 'success')
        return redirect(url_for('safety_personnel'))
    return render_template('safety_policy/personnel_form.html')

@app.route('/safety-personnel/<pid>/update', methods=['POST'])
def update_personnel(pid):
    p = SafetyPersonnel.query.get_or_404(pid)
    f = request.form
    p.position       = f.get('position', p.position)
    p.sms_role       = f.get('sms_role', p.sms_role)
    p.qualifications = f.get('qualifications', p.qualifications)
    p.contact_email  = f.get('contact_email', p.contact_email)
    p.contact_phone  = f.get('contact_phone', p.contact_phone)
    p.sms_trained    = f.get('sms_trained') == 'yes'
    p.training_date  = f.get('training_date', p.training_date)
    p.active         = f.get('active','true') == 'true'
    db.session.commit()
    flash('✓ Personnel record updated.', 'success')
    return redirect(url_for('safety_personnel'))

# ─── EMERGENCY RESPONSE PLANNING ─────────────────────────────────────────────
@app.route('/erp')
def erp_list():
    plans = ERPlan.query.filter_by(status='Active').order_by(ERPlan.scenario_type).all()
    archived = ERPlan.query.filter_by(status='Archived').all()
    return render_template('safety_policy/erp.html', plans=plans, archived=archived)

@app.route('/erp/new', methods=['GET','POST'])
def new_erp():
    if request.method == 'POST':
        f   = request.form
        count = ERPlan.query.count() + 1
        e = ERPlan(
            id=new_id('ERP'),
            erp_ref=f'ERP-{count:03d}',
            scenario_type=f['scenario_type'],
            title=f['title'],
            description=f.get('description',''),
            activation_criteria=f.get('activation_criteria',''),
            response_procedures=f.get('response_procedures',''),
            responsible_roles=f.get('responsible_roles',''),
            emergency_contacts=f.get('emergency_contacts',''),
            resources_required=f.get('resources_required',''),
            notification_list=f.get('notification_list',''),
            review_date=f.get('review_date',''),
            version='REV0', status='Active'
        )
        db.session.add(e)
        db.session.commit()
        flash(f'✓ ERP {e.erp_ref} created: {e.title}', 'success')
        return redirect(url_for('erp_list'))
    return render_template('safety_policy/erp_form.html')

@app.route('/erp/<eid>')
def erp_detail(eid):
    e = ERPlan.query.get_or_404(eid)
    return render_template('safety_policy/erp_detail.html', e=e)

@app.route('/erp/<eid>/update', methods=['POST'])
def update_erp(eid):
    e = ERPlan.query.get_or_404(eid)
    f = request.form
    e.response_procedures = f.get('response_procedures', e.response_procedures)
    e.emergency_contacts  = f.get('emergency_contacts', e.emergency_contacts)
    e.responsible_roles   = f.get('responsible_roles', e.responsible_roles)
    e.notification_list   = f.get('notification_list', e.notification_list)
    e.resources_required  = f.get('resources_required', e.resources_required)
    e.review_date         = f.get('review_date', e.review_date)
    e.status              = f.get('status', e.status)
    db.session.commit()
    flash('✓ ERP updated.', 'success')
    return redirect(url_for('erp_detail', eid=eid))

# ─── DOCUMENT CONTROL ─────────────────────────────────────────────────────────
@app.route('/documents')
@require_login
def documents():
    type_f   = request.args.get('type','')
    dept_f   = request.args.get('dept','')
    status_f = request.args.get('status','')
    q = SMSDocument.query
    if type_f:   q = q.filter_by(doc_type=type_f)
    if dept_f:   q = q.filter_by(department_id=int(dept_f))
    if status_f: q = q.filter_by(status=status_f)
    docs = q.order_by(SMSDocument.created_at.desc()).all()
    doc_types = ['POL','MAN','SOP','RA','AUD','MOC','INV','TRN','NEWS']
    return render_template('document/document_list.html', docs=docs, doc_types=doc_types,
                           type_f=type_f, dept_f=dept_f, status_f=status_f)

@app.route('/documents/new', methods=['GET','POST'])
def new_document():
    if request.method == 'POST':
        f        = request.form
        doc_type = f['doc_type']
        dept_id  = int(f['department_id'])
        year     = datetime.now().year
        dept     = Department.query.get(dept_id)
        dept_code = dept.code if dept else 'XX'
        seq      = next_seq(doc_type, dept_id, year)
        doc_id   = gen_doc_id(doc_type, dept_code, year, seq, 0)
        d = SMSDocument(
            id=doc_id, doc_type=doc_type,
            department_id=dept_id,
            title=f['title'],
            description=f.get('description',''),
            content=f.get('content',''),
            version='REV0', version_num=0, seq_num=seq,
            status='Draft',
            created_by=f.get('created_by',''),
            effective_date=f.get('effective_date',''),
            review_due=f.get('review_due',''),
            change_summary='Initial issue'
        )
        db.session.add(d)
        db.session.commit()
        flash(f'✓ Document {doc_id} created as Draft.', 'success')
        return redirect(url_for('documents'))
    doc_types = ['POL','MAN','SOP','RA','AUD','MOC','INV','TRN','NEWS']
    return render_template('document/document_form.html', doc_types=doc_types)

@app.route('/documents/<did>')
def document_detail(did):
    doc = SMSDocument.query.get_or_404(did)
    # Get all versions (parent chain)
    versions = []
    current = doc
    while current:
        versions.append(current)
        if current.parent_doc_id:
            current = SMSDocument.query.get(current.parent_doc_id)
        else:
            break
    return render_template('document/document_detail.html', doc=doc, versions=versions)

@app.route('/documents/<did>/advance', methods=['POST'])
def advance_document(did):
    """Draft → Under Review → Approved → Archived"""
    doc = SMSDocument.query.get_or_404(did)
    f   = request.form
    transitions = {
        'Draft':        'Under Review',
        'Under Review': 'Approved',
        'Approved':     'Archived',
    }
    if doc.status in transitions:
        doc.status = transitions[doc.status]
        if doc.status == 'Approved':
            doc.approved_by    = f.get('approved_by', doc.approved_by)
            doc.effective_date = f.get('effective_date', doc.effective_date)
            doc.review_due     = f.get('review_due', doc.review_due)
            doc.reviewed_by    = f.get('reviewed_by', doc.reviewed_by)
        db.session.commit()
        flash(f'✓ Document status updated to {doc.status}.', 'success')
    return redirect(url_for('document_detail', did=did))

@app.route('/documents/<did>/revise', methods=['POST'])
def revise_document(did):
    """Create a new revision — old version becomes archived."""
    old = SMSDocument.query.get_or_404(did)
    if old.status != 'Approved':
        flash('Only Approved documents can be revised.', 'error')
        return redirect(url_for('document_detail', did=did))
    f       = request.form
    new_ver = old.version_num + 1
    dept    = Department.query.get(old.department_id)
    dept_code = dept.code if dept else 'XX'
    year    = datetime.now().year
    new_id_str = gen_doc_id(old.doc_type, dept_code, year, old.seq_num, new_ver)
    new_doc = SMSDocument(
        id=new_id_str, doc_type=old.doc_type,
        department_id=old.department_id,
        title=old.title,
        description=old.description,
        content=f.get('content', old.content),
        version=f'REV{new_ver}', version_num=new_ver,
        seq_num=old.seq_num,
        status='Draft',
        created_by=f.get('created_by', old.created_by),
        change_summary=f.get('change_summary',''),
        parent_doc_id=old.id
    )
    old.status = 'Archived'
    db.session.add(new_doc)
    db.session.commit()
    flash(f'✓ New revision {new_id_str} created. {old.id} archived.', 'success')
    return redirect(url_for('document_detail', did=new_id_str))


# ═══════════════════════════════════════════════════════════════════════════════
#  DOCUMENT TRACEABILITY BACKBONE — FULL INTEGRATION
#  Documents ↔ Hazards ↔ Risks ↔ Audits ↔ Actions ↔ MOC ↔ Training
#  Added as extension — all existing routes unchanged
# ═══════════════════════════════════════════════════════════════════════════════

# ── Entity resolver — fetch any entity by type + id ─────────────────────────
ENTITY_RESOLVERS = {
    'hazard':         lambda eid: Hazard.query.get(eid),
    'risk':           lambda eid: Risk.query.get(eid),
    'action':         lambda eid: Action.query.get(eid),
    'audit_schedule': lambda eid: AuditSchedule.query.get(eid),
    'audit_finding':  lambda eid: AuditFinding.query.get(eid),
    'audit_action':   lambda eid: AuditAction.query.get(eid),
    'moc':            lambda eid: MOC.query.get(eid),
    'investigation':  lambda eid: Investigation.query.get(eid),
    'training':       lambda eid: Training.query.get(eid),
    'erp':            lambda eid: ERPlan.query.get(eid),
}

ENTITY_LABELS = {
    'hazard':         ('Hazard',           '/hazard-log/{}'),
    'risk':           ('Risk',             '/hazard-log/{}'),   # risks shown via hazard
    'action':         ('Action',           '/actions'),
    'audit_schedule': ('Audit',            '/audit-schedule/{}'),
    'audit_finding':  ('Audit Finding',    '/audit-findings/{}'),
    'audit_action':   ('Audit Action',     '/audit-actions'),
    'moc':            ('MOC',              '/moc'),
    'investigation':  ('Investigation',    '/investigations/{}'),
    'training':       ('Training Record',  '/safety-promotion'),
    'erp':            ('ERP',              '/erp/{}'),
}

def resolve_entity_label(entity_type, entity_id):
    """Return display name and URL for a linked entity."""
    if entity_type not in ENTITY_LABELS:
        return entity_type, '#'
    label, url_tpl = ENTITY_LABELS[entity_type]
    try:
        url = url_tpl.format(entity_id)
    except Exception:
        url = url_tpl
    return label, url

def get_doc_links_for_entity(entity_type, entity_id):
    """Return all documents linked to a given entity."""
    links = DocumentLink.query.filter_by(
        entity_type=entity_type, entity_id=str(entity_id)).all()
    docs = []
    for lnk in links:
        doc = SMSDocument.query.get(lnk.document_id)
        if doc:
            docs.append({'doc': doc, 'link': lnk})
    return docs

def build_traceability(doc):
    """Build full traceability map for a document — all linked entities."""
    links = DocumentLink.query.filter_by(document_id=doc.id).all()
    result = []
    for lnk in links:
        label, url = resolve_entity_label(lnk.entity_type, lnk.entity_id)
        obj = None
        resolver = ENTITY_RESOLVERS.get(lnk.entity_type)
        if resolver:
            try:
                obj = resolver(lnk.entity_id)
            except Exception:
                pass
        result.append({
            'link': lnk,
            'label': label,
            'url': url,
            'entity_type': lnk.entity_type,
            'entity_id': lnk.entity_id,
            'obj': obj,
        })
    return result

# ─── DOCUMENT LINKING API ─────────────────────────────────────────────────────
@app.route('/documents/<did>/link', methods=['POST'])
def link_document(did):
    doc = SMSDocument.query.get_or_404(did)
    f   = request.form
    entity_type = f['entity_type']
    entity_id   = f['entity_id'].strip()
    reason      = f.get('link_reason', '')

    if not entity_type or not entity_id:
        flash('Entity type and ID are required.', 'error')
        return redirect(url_for('document_detail', did=did))

    # Validate entity exists
    resolver = ENTITY_RESOLVERS.get(entity_type)
    if resolver:
        obj = resolver(entity_id)
        if not obj:
            flash(f'No {entity_type} found with ID: {entity_id}', 'error')
            return redirect(url_for('document_detail', did=did))

    # Check duplicate
    existing = DocumentLink.query.filter_by(
        document_id=did, entity_type=entity_type, entity_id=entity_id).first()
    if existing:
        flash(f'Document already linked to this {entity_type}.', 'error')
        return redirect(url_for('document_detail', did=did))

    lnk = DocumentLink(
        document_id=did,
        entity_type=entity_type,
        entity_id=entity_id,
        link_reason=reason
    )
    db.session.add(lnk)
    db.session.commit()
    flash(f'✓ Document linked to {entity_type} {entity_id}.', 'success')
    return redirect(url_for('document_detail', did=did))

@app.route('/documents/<did>/unlink/<int:link_id>', methods=['POST'])
def unlink_document(did, link_id):
    lnk = DocumentLink.query.get_or_404(link_id)
    db.session.delete(lnk)
    db.session.commit()
    flash('✓ Link removed.', 'success')
    return redirect(url_for('document_detail', did=did))

# ─── DOCUMENT DETAIL (override — add traceability) ───────────────────────────
@app.route('/documents/<did>/trace')
def document_trace(did):
    doc   = SMSDocument.query.get_or_404(did)
    trace = build_traceability(doc)
    versions = []
    current = doc
    while current:
        versions.append(current)
        current = SMSDocument.query.get(current.parent_doc_id) if current.parent_doc_id else None
    return render_template('document/document_trace.html', doc=doc, trace=trace, versions=versions)

# ─── ENTITY TRACEABILITY VIEWS ────────────────────────────────────────────────
@app.route('/hazard-log/<hid>/documents')
def hazard_documents(hid):
    hazard = Hazard.query.get_or_404(hid)
    # Documents linked to hazard
    haz_docs  = get_doc_links_for_entity('hazard', hid)
    # Documents linked to any risk of this hazard
    risk_docs = []
    for risk in hazard.risks:
        for item in get_doc_links_for_entity('risk', risk.id):
            item['risk'] = risk
            risk_docs.append(item)
    # Actions
    action_docs = []
    for action in hazard.actions:
        for item in get_doc_links_for_entity('action', action.id):
            item['action'] = action
            action_docs.append(item)
    return render_template('hazard/hazard_documents.html',
        hazard=hazard, haz_docs=haz_docs,
        risk_docs=risk_docs, action_docs=action_docs)

@app.route('/audit-schedule/<sid>/documents')
def audit_documents(sid):
    schedule = AuditSchedule.query.get_or_404(sid)
    audit_docs   = get_doc_links_for_entity('audit_schedule', sid)
    finding_docs = []
    for finding in schedule.findings:
        for item in get_doc_links_for_entity('audit_finding', finding.id):
            item['finding'] = finding
            finding_docs.append(item)
    return render_template('audit/audit_documents.html',
        schedule=schedule, audit_docs=audit_docs, finding_docs=finding_docs)

# ─── TRACEABILITY DASHBOARD ───────────────────────────────────────────────────
@app.route('/traceability')
def traceability_dashboard():
    total_docs  = SMSDocument.query.count()
    total_links = DocumentLink.query.count()
    approved    = SMSDocument.query.filter_by(status='Approved').count()
    draft       = SMSDocument.query.filter_by(status='Draft').count()
    archived    = SMSDocument.query.filter_by(status='Archived').count()
    review      = SMSDocument.query.filter_by(status='Under Review').count()

    # Documents with no links (orphans)
    linked_ids = db.session.query(DocumentLink.document_id).distinct().all()
    linked_ids = [x[0] for x in linked_ids]
    orphan_docs = SMSDocument.query.filter(
        ~SMSDocument.id.in_(linked_ids)).all() if linked_ids else SMSDocument.query.all()

    # Hazards with no linked RA document
    all_hazards = Hazard.query.filter_by(status='Open').all()
    unlinked_hazards = []
    for h in all_hazards:
        ra_links = DocumentLink.query.filter_by(entity_type='hazard', entity_id=h.id).join(
            SMSDocument, DocumentLink.document_id == SMSDocument.id).filter(
            SMSDocument.doc_type == 'RA').first()
        if not ra_links:
            unlinked_hazards.append(h)

    # Recent links
    recent_links = DocumentLink.query.order_by(DocumentLink.created_at.desc()).limit(10).all()

    # Link stats by entity type
    link_stats = db.session.query(
        DocumentLink.entity_type,
        db.func.count(DocumentLink.id).label('cnt')
    ).group_by(DocumentLink.entity_type).all()

    return render_template('document/traceability.html',
        total_docs=total_docs, total_links=total_links,
        approved=approved, draft=draft, archived=archived, review=review,
        orphan_docs=orphan_docs, unlinked_hazards=unlinked_hazards,
        recent_links=recent_links, link_stats=link_stats,
        resolve_entity_label=resolve_entity_label)

# ─── QUICK LINK API (from any module page) ───────────────────────────────────
@app.route('/quick-link', methods=['POST'])
def quick_link():
    """Link a document to an entity from any page in the system."""
    f           = request.form
    doc_id      = f['document_id']
    entity_type = f['entity_type']
    entity_id   = f['entity_id']
    reason      = f.get('link_reason', '')
    return_url  = f.get('return_url', '/documents')

    doc = SMSDocument.query.get(doc_id)
    if not doc:
        flash(f'Document {doc_id} not found.', 'error')
        return redirect(return_url)

    existing = DocumentLink.query.filter_by(
        document_id=doc_id, entity_type=entity_type, entity_id=entity_id).first()
    if not existing:
        lnk = DocumentLink(
            document_id=doc_id, entity_type=entity_type,
            entity_id=entity_id, link_reason=reason)
        db.session.add(lnk)
        db.session.commit()
        flash(f'✓ {doc_id} linked to {entity_type} {entity_id}.', 'success')
    else:
        flash('Already linked.', 'error')
    return redirect(return_url)

# ─── AUTO-LINK HELPERS (called internally when creating objects) ──────────────
def auto_link_document(doc_id, entity_type, entity_id, reason='Auto-linked'):
    """Safe auto-link — skips if already exists or entity not found."""
    if not doc_id or not entity_id:
        return
    existing = DocumentLink.query.filter_by(
        document_id=doc_id, entity_type=entity_type,
        entity_id=str(entity_id)).first()
    if not existing:
        lnk = DocumentLink(
            document_id=doc_id, entity_type=entity_type,
            entity_id=str(entity_id), link_reason=reason)
        db.session.add(lnk)

# ─── SEED TRACEABILITY DATA (called from seed()) ─────────────────────────────
def seed_traceability():
    """Traceability seed — skipped in production (no demo data)."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
#  SAFETY RISK MANAGEMENT (SRM) MODULE
#  ICAO Annex 19 §5 / Doc 9859 Ch.5
#  Hazard → Risk(s) → Control(s) → Residual Risk → Action(s) → Monitoring
#  Extension only — all existing routes unchanged
# ═══════════════════════════════════════════════════════════════════════════════

TREND_ICONS = {'Increasing': '↑', 'Stable': '→', 'Decreasing': '↓', 'New': '●'}
TREND_COLORS = {'Increasing': '#dc2626', 'Stable': '#d97706', 'Decreasing': '#15803d', 'New': '#1e40af'}

def calculate_trend(hazard_id):
    """Calculate trend based on occurrence count and recency."""
    occurrences = RiskOccurrence.query.filter_by(hazard_id=hazard_id).order_by(
        RiskOccurrence.created_at.desc()).all()
    count = len(occurrences)
    if count == 0:
        return 'New', 0
    if count == 1:
        return 'Stable', count
    # Compare recent 3 vs previous 3
    recent = len([o for o in occurrences[:3]])
    older  = len([o for o in occurrences[3:6]])
    if recent > older:
        return 'Increasing', count
    elif recent < older:
        return 'Decreasing', count
    return 'Stable', count

def get_srm_status(hazard):
    """Derive SRM status from risks and controls."""
    if not hazard.risks:
        return 'Open'
    all_controlled = all(
        r.residual_risk_index and r.residual_tolerance in ('ACCEPTABLE','TOLERABLE')
        for r in hazard.risks
    )
    any_intolerable = any(
        r.initial_tolerance == 'INTOLERABLE' for r in hazard.risks
    )
    has_controls = any(len(r.controls) > 0 for r in hazard.risks)
    if all_controlled:
        return 'Controlled'
    if has_controls:
        return 'Under Assessment'
    return 'Open'

# ─── RISK REGISTER (central view — risks, not hazards) ───────────────────────
@app.route('/risk-register')
@require_login
def risk_register():
    dept_f  = request.args.get('dept','')
    tol_f   = request.args.get('tolerance','')
    stat_f  = request.args.get('status','')
    src_f   = request.args.get('source','')

    q = Risk.query.join(Hazard, Risk.hazard_id == Hazard.id)
    if dept_f: q = q.filter(Hazard.department_id == int(dept_f))
    if tol_f:  q = q.filter(Risk.initial_tolerance == tol_f)

    risks = q.order_by(Risk.created_at.desc()).all()

    # Filter by hazard source
    if src_f:
        risks = [r for r in risks if r.hazard and r.hazard.source == src_f]

    # Stats
    total       = len(risks)
    intolerable = sum(1 for r in risks if r.initial_tolerance == 'INTOLERABLE')
    tolerable   = sum(1 for r in risks if r.initial_tolerance == 'TOLERABLE')
    acceptable  = sum(1 for r in risks if r.initial_tolerance == 'ACCEPTABLE')
    no_controls = sum(1 for r in risks if len(r.controls) == 0)
    no_residual = sum(1 for r in risks if not r.residual_risk_index)

    return render_template('risk/risk_register.html',
        risks=risks, dept_f=dept_f, tol_f=tol_f, stat_f=stat_f, src_f=src_f,
        total=total, intolerable=intolerable, tolerable=tolerable,
        acceptable=acceptable, no_controls=no_controls, no_residual=no_residual,
        get_srm_status=get_srm_status, calculate_trend=calculate_trend,
        TREND_ICONS=TREND_ICONS, TREND_COLORS=TREND_COLORS)

# ─── RISK DETAIL ──────────────────────────────────────────────────────────────
@app.route('/risk/<rid>')
def risk_detail(rid):
    risk    = Risk.query.get_or_404(rid)
    hazard  = risk.hazard
    # Linked documents via DocumentLink
    doc_links = DocumentLink.query.filter_by(entity_type='risk', entity_id=rid).all()
    docs    = [SMSDocument.query.get(lnk.document_id) for lnk in doc_links if SMSDocument.query.get(lnk.document_id)]
    # Risk actions
    r_actions = RiskAction.query.filter_by(risk_id=rid).order_by(RiskAction.created_at.desc()).all()
    # Audit findings linked to same hazard
    audit_findings = AuditFinding.query.filter_by(hazard_id=hazard.id).all() if hazard else []
    return render_template('risk/risk_detail.html',
        risk=risk, hazard=hazard, docs=docs, r_actions=r_actions,
        audit_findings=audit_findings)

# ─── UPDATE RISK STATUS / RESIDUAL ────────────────────────────────────────────
@app.route('/risk/<rid>/update', methods=['POST'])
def update_risk(rid):
    risk = Risk.query.get_or_404(rid)
    f    = request.form
    risk.description = f.get('description', risk.description)
    rl = f.get('residual_likelihood','')
    rs = f.get('residual_severity','')
    if rl and rs:
        risk.residual_likelihood = int(rl)
        risk.residual_severity   = rs
        rri = f'{rl}{rs}'
        risk.residual_risk_index  = rri
        risk.residual_tolerance   = get_tolerance(rri)
    if f.get('consequence'):
        risk.description = f.get('consequence')
    db.session.commit()
    flash('✓ Risk updated.', 'success')
    return redirect(url_for('risk_detail', rid=rid))

# ─── RISK → ACTION (direct risk-level action) ─────────────────────────────────
@app.route('/risk/<rid>/add-action', methods=['POST'])
def add_risk_action(rid):
    risk = Risk.query.get_or_404(rid)
    f    = request.form
    ra   = RiskAction(
        id=new_id('RACT'),
        risk_id=rid,
        hazard_id=risk.hazard_id,
        description=f['description'],
        owner=f['owner'],
        due_date=f['due_date'],
        priority=f.get('priority','Medium'),
        status='Open'
    )
    db.session.add(ra)
    # Also add to unified Action table
    unified = Action(
        id=new_id('ACT'),
        source='Risk Assessment',
        hazard_id=risk.hazard_id,
        linked_ref_id=rid,
        description=f['description'],
        owner=f['owner'],
        due_date=f['due_date'],
        priority=f.get('priority','Medium'),
        status='Open'
    )
    db.session.add(unified)
    db.session.commit()
    flash(f'✓ Action created for risk {rid}.', 'success')
    return redirect(url_for('risk_detail', rid=rid))

@app.route('/risk-action/<aid>/update', methods=['POST'])
def update_risk_action(aid):
    ra = RiskAction.query.get_or_404(aid)
    f  = request.form
    ra.status        = f.get('status', ra.status)
    ra.owner         = f.get('owner', ra.owner)
    ra.due_date      = f.get('due_date', ra.due_date)
    ra.effectiveness = f.get('effectiveness', ra.effectiveness)
    if ra.status == 'Closed':
        ra.closed_date = date.today().isoformat()
    db.session.commit()
    flash('✓ Action updated.', 'success')
    return redirect(url_for('risk_detail', rid=ra.risk_id))

# ─── CONTROL MANAGEMENT (enhanced) ───────────────────────────────────────────
@app.route('/control/<cid>/update', methods=['POST'])
def update_control(cid):
    ctrl = Control.query.get_or_404(cid)
    f    = request.form
    ctrl.control_type  = f.get('control_type', ctrl.control_type)
    ctrl.description   = f.get('description', ctrl.description)
    ctrl.owner         = f.get('owner', ctrl.owner)
    ctrl.effectiveness = f.get('effectiveness', ctrl.effectiveness)
    ctrl.review_date   = f.get('review_date', ctrl.review_date)
    db.session.commit()
    flash('✓ Control updated.', 'success')
    return redirect(url_for('risk_detail', rid=ctrl.risk_id))

@app.route('/delete/risk/<rid>', methods=['POST'])
def delete_risk_record(rid):
    """Safe delete a Risk row and its controls."""
    r = Risk.query.get_or_404(rid)
    try:
        # Nullify ra_rows referencing this risk
        db.session.execute(
            db.text("UPDATE ra_rows SET risk_id = NULL WHERE risk_id = :rid"),
            {'rid': rid}
        )
        db.session.flush()
        Control.query.filter_by(risk_id=rid).delete(synchronize_session=False)
        db.session.flush()
        db.session.delete(r)
        db.session.commit()
        flash(f'✓ Risk {rid} deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'⚠ Could not delete risk: {str(e)[:120]}', 'error')
    return redirect(request.form.get('return_url', '/risk-register'))


@app.route('/control/<cid>/delete', methods=['POST'])
def delete_control(cid):
    ctrl = Control.query.get_or_404(cid)
    rid  = ctrl.risk_id
    db.session.delete(ctrl)
    db.session.commit()
    flash('✓ Control removed.', 'success')
    return redirect(url_for('risk_detail', rid=rid))

# ─── OCCURRENCE TRACKING ──────────────────────────────────────────────────────
@app.route('/hazard-log/<hid>/occurrence', methods=['POST'])
def add_occurrence(hid):
    hazard = Hazard.query.get_or_404(hid)
    f      = request.form
    occ    = RiskOccurrence(
        hazard_id=hid,
        occurrence_date=f.get('occurrence_date', date.today().isoformat()),
        description=f.get('description',''),
        source=f.get('source','Report'),
        linked_report_id=f.get('linked_report_id','')
    )
    db.session.add(occ)
    db.session.commit()
    flash('✓ Occurrence logged. Trend updated.', 'success')
    return redirect(url_for('hazard_detail', hid=hid))

# ─── SRM DASHBOARD ────────────────────────────────────────────────────────────
@app.route('/srm-dashboard')
@require_login
def srm_dashboard():
    all_risks   = Risk.query.all()
    total_risks = len(all_risks)
    intol_risks = [r for r in all_risks if r.initial_tolerance == 'INTOLERABLE']
    no_ctrl     = [r for r in all_risks if len(r.controls) == 0]
    no_resid    = [r for r in all_risks if not r.residual_risk_index]
    reduced     = [r for r in all_risks if r.residual_risk_index and r.residual_tolerance != r.initial_tolerance]

    # Trend analysis per hazard
    all_hazards = Hazard.query.filter_by(status='Open').all()
    trend_data  = []
    for h in all_hazards:
        trend, count = calculate_trend(h.id)
        if count > 0 or h.risks:
            trend_data.append({
                'hazard': h,
                'trend': trend,
                'count': count,
                'risks': len(h.risks),
                'intol': sum(1 for r in h.risks if r.initial_tolerance == 'INTOLERABLE')
            })
    trend_data.sort(key=lambda x: (x['intol'], x['count']), reverse=True)

    # Source breakdown
    sources = {}
    for h in Hazard.query.all():
        sources[h.source] = sources.get(h.source, 0) + 1

    # Classification breakdown
    classifications = {}
    for h in Hazard.query.all():
        c = h.classification or 'Unclassified'
        classifications[c] = classifications.get(c, 0) + 1

    return render_template('risk/srm_dashboard.html',
        total_risks=total_risks, intol_risks=intol_risks,
        no_ctrl=no_ctrl, no_resid=no_resid, reduced=reduced,
        trend_data=trend_data[:10],
        sources=sources, classifications=classifications,
        TREND_ICONS=TREND_ICONS, TREND_COLORS=TREND_COLORS)


# ═══════════════════════════════════════════════════════════════════════════════
#  RISK ASSESSMENT MODULE — Jav/SMS/001 Rev 01
#  Converts the Jordan Aviation RA form into a full system module
#  Connected to: Hazard Log, Risk Register, Actions, Documents
# ═══════════════════════════════════════════════════════════════════════════════

def gen_control_number(dept_code):
    """Generate RA control number: JAV/RA/DEPT/YEAR/SEQ"""
    year = datetime.now().year
    count = RiskAssessment.query.count() + 1
    return f"JAV-RA-{dept_code}-{year}-{count:03d}"

def compute_ra_summary(ra):
    """Compute overall risk level before and after controls for page 2."""
    if not ra.rows:
        return None, None
    # Worst initial risk
    order = ['INTOLERABLE','TOLERABLE','ACCEPTABLE']
    initial_levels  = [r.risk_tolerance_initial  for r in ra.rows if r.risk_tolerance_initial]
    residual_levels = [r.risk_tolerance_residual for r in ra.rows if r.risk_tolerance_residual]
    worst_initial  = min(initial_levels,  key=lambda x: order.index(x) if x in order else 99) if initial_levels else None
    worst_residual = min(residual_levels, key=lambda x: order.index(x) if x in order else 99) if residual_levels else None
    return worst_initial, worst_residual

# ─── LIST ALL RISK ASSESSMENTS ───────────────────────────────────────────────
@app.route('/risk-assessments')
def ra_list():
    check_ra_review_dates()  # Auto-set Under Review when due date reached
    dept_f  = request.args.get('dept','')
    stat_f  = request.args.get('status','')
    q = RiskAssessment.query
    if dept_f: q = q.filter_by(department_id=int(dept_f))
    if stat_f: q = q.filter_by(status=stat_f)
    ras = q.order_by(RiskAssessment.created_at.desc()).all()
    return render_template('risk/ra_list.html', ras=ras, dept_f=dept_f, stat_f=stat_f)

# ─── CREATE NEW RA (linked to hazard or standalone) ──────────────────────────
@app.route('/risk-assessments/new', methods=['GET','POST'])
def new_ra():
    hid = request.args.get('hazard_id','')
    hazard = Hazard.query.get(hid) if hid else None

    if request.method == 'POST':
        f       = request.form
        dept_id = int(f['department_id'])
        dept    = Department.query.get(dept_id)
        ra_id   = new_id('RA')
        ctrl_no = gen_control_number(dept.code if dept else 'XX')

        ra = RiskAssessment(
            id=ra_id,
            control_number=f.get('control_number') or ctrl_no,
            responsible_name=f['responsible_name'],
            assessors_names=f.get('assessors_names',''),
            assessment_date=f['assessment_date'],
            next_review_date=f.get('next_review_date',''),
            title=f['title'],
            hazard_id=f.get('hazard_id') or None,
            department_id=dept_id,
            general_description=f.get('general_description',''),
            reasons=f.get('reasons',''),
            management_acceptance=f.get('management_acceptance',''),
            acceptance_date=f.get('acceptance_date',''),
            prepared_by_name=f.get('prepared_by_name',''),
            prepared_by_position=f.get('prepared_by_position',''),
            reviewed_by_name=f.get('reviewed_by_name',''),
            reviewed_by_position=f.get('reviewed_by_position',''),
            approved_by_name=f.get('approved_by_name',''),
            approved_by_position=f.get('approved_by_position',''),
            status='Draft'
        )
        db.session.add(ra)
        db.session.flush()

        # Page 3 — parse risk rows from the form
        seq = 1
        while f.get(f'activity_{seq}'):
            lik_i = int(f.get(f'lik_i_{seq}', 3))
            sev_i = f.get(f'sev_i_{seq}', 'C')
            ri_i  = f'{lik_i}{sev_i}'
            tol_i = get_tolerance(ri_i)

            lik_r = f.get(f'lik_r_{seq}','')
            sev_r = f.get(f'sev_r_{seq}','')
            ri_r  = f'{lik_r}{sev_r}' if lik_r and sev_r else None
            tol_r = get_tolerance(ri_r) if ri_r else None

            # Create/link a Risk record in the existing risks table
            risk_rec = Risk(
                id=new_id('RSK'),
                hazard_id=ra.hazard_id or '',
                description=f.get(f'consequences_{seq}',''),
                initial_likelihood=lik_i, initial_severity=sev_i,
                initial_risk_index=ri_i, initial_tolerance=tol_i,
                residual_likelihood=int(lik_r) if lik_r else None,
                residual_severity=sev_r or None,
                residual_risk_index=ri_r, residual_tolerance=tol_r
            )
            if ra.hazard_id:
                db.session.add(risk_rec)
                db.session.flush()

            row = RARow(
                assessment_id=ra_id, seq_num=seq,
                risk_id=risk_rec.id if ra.hazard_id else None,
                type_of_activity=f.get(f'activity_{seq}',''),
                generic_hazard=f.get(f'generic_hazard_{seq}',''),
                specific_components=f.get(f'specific_{seq}',''),
                consequences=f.get(f'consequences_{seq}',''),
                likelihood_initial=lik_i, severity_initial=sev_i,
                risk_index_initial=ri_i, risk_tolerance_initial=tol_i,
                current_defenses=f.get(f'defenses_{seq}',''),
                further_mitigations=f.get(f'mitigations_{seq}',''),
                likelihood_residual=int(lik_r) if lik_r else None,
                severity_residual=sev_r or None,
                risk_index_residual=ri_r, risk_tolerance_residual=tol_r
            )
            db.session.add(row)

            # Page 4 — auto-create mitigation + action if mitigation text exists
            mit_text = f.get(f'mitigations_{seq}','')
            resp_mgr = f.get(f'resp_manager_{seq}','')
            due_dt   = f.get(f'due_date_{seq}','')
            if mit_text:
                act_id = new_id('ACT')
                mit = RAMitigation(
                    assessment_id=ra_id,
                    hazard_seq=str(seq),
                    mitigation=mit_text,
                    responsible_manager=resp_mgr,
                    due_date=due_dt,
                    action_id=act_id,
                    status='Open'
                )
                db.session.add(mit)
                # Create unified Action
                action = Action(
                    id=act_id,
                    source='Risk Assessment',
                    hazard_id=ra.hazard_id,
                    linked_ref_id=ra_id,
                    description=f'[RA {ra.control_number}] Seq {seq}: {mit_text}',
                    owner=resp_mgr,
                    due_date=due_dt,
                    priority='High' if tol_i=='INTOLERABLE' else 'Medium',
                    status='Open'
                )
                db.session.add(action)
            seq += 1

        # Update page 2 summary levels
        worst_i, worst_r = compute_ra_summary(ra)
        ra.risk_level_prior = worst_i or ''
        ra.risk_level_after = worst_r or ''

        # Auto-link RA document to hazard in traceability
        if ra.hazard_id:
            auto_link_document(None, 'hazard', ra.hazard_id, f'Risk Assessment {ra.control_number}')

        db.session.commit()
        flash(f'✓ Risk Assessment {ra.control_number} created. {seq-1} risk row(s) added.', 'success')
        return redirect(url_for('ra_detail', ra_id=ra_id))

    # GET — pre-populate from hazard if provided
    return render_template('risk/ra_form.html', hazard=hazard,
                           today=date.today().isoformat())

# ─── RA DETAIL (all 5 pages in one view) ────────────────────────────────────
@app.route('/risk-assessments/<ra_id>')
@require_login
def ra_detail(ra_id):
    ra = RiskAssessment.query.get_or_404(ra_id)
    worst_i, worst_r = compute_ra_summary(ra)
    return render_template('risk/ra_detail.html', ra=ra,
                           worst_initial=worst_i, worst_residual=worst_r,
                           get_tolerance=get_tolerance)

# ─── ADD ROW to existing RA ──────────────────────────────────────────────────
@app.route('/risk-assessments/<ra_id>/add-row', methods=['POST'])
def ra_add_row(ra_id):
    ra = RiskAssessment.query.get_or_404(ra_id)
    f  = request.form
    seq = len(ra.rows) + 1

    lik_i = int(f.get('likelihood_initial', 3))
    sev_i = f.get('severity_initial','C')
    ri_i  = f'{lik_i}{sev_i}'
    tol_i = get_tolerance(ri_i)
    lik_r = f.get('likelihood_residual','')
    sev_r = f.get('severity_residual','')
    ri_r  = f'{lik_r}{sev_r}' if lik_r and sev_r else None
    tol_r = get_tolerance(ri_r) if ri_r else None

    # Create Risk record
    if ra.hazard_id:
        risk_rec = Risk(
            id=new_id('RSK'), hazard_id=ra.hazard_id,
            description=f.get('consequences',''),
            initial_likelihood=lik_i, initial_severity=sev_i,
            initial_risk_index=ri_i, initial_tolerance=tol_i,
            residual_likelihood=int(lik_r) if lik_r else None,
            residual_severity=sev_r or None,
            residual_risk_index=ri_r, residual_tolerance=tol_r
        )
        db.session.add(risk_rec)
        db.session.flush()
        risk_id = risk_rec.id
    else:
        risk_id = None

    row = RARow(
        assessment_id=ra_id, seq_num=seq, risk_id=risk_id,
        type_of_activity=f.get('type_of_activity',''),
        generic_hazard=f.get('generic_hazard',''),
        specific_components=f.get('specific_components',''),
        consequences=f.get('consequences',''),
        likelihood_initial=lik_i, severity_initial=sev_i,
        risk_index_initial=ri_i, risk_tolerance_initial=tol_i,
        current_defenses=f.get('current_defenses',''),
        further_mitigations=f.get('further_mitigations',''),
        likelihood_residual=int(lik_r) if lik_r else None,
        severity_residual=sev_r or None,
        risk_index_residual=ri_r, risk_tolerance_residual=tol_r
    )
    db.session.add(row)

    # Create mitigation + action if provided
    mit_text = f.get('further_mitigations','')
    resp_mgr = f.get('responsible_manager','')
    due_dt   = f.get('due_date','')
    if mit_text:
        act_id = new_id('ACT')
        mit = RAMitigation(
            assessment_id=ra_id, hazard_seq=str(seq),
            mitigation=mit_text, responsible_manager=resp_mgr,
            due_date=due_dt, action_id=act_id, status='Open'
        )
        db.session.add(mit)
        action = Action(
            id=act_id, source='Risk Assessment',
            hazard_id=ra.hazard_id, linked_ref_id=ra_id,
            description=f'[{ra.control_number}] Seq {seq}: {mit_text}',
            owner=resp_mgr, due_date=due_dt,
            priority='High' if tol_i=='INTOLERABLE' else 'Medium',
            status='Open'
        )
        db.session.add(action)

    # Refresh summary
    worst_i, worst_r = compute_ra_summary(ra)
    ra.risk_level_prior = worst_i or ra.risk_level_prior
    ra.risk_level_after = worst_r or ra.risk_level_after
    db.session.commit()
    flash(f'✓ Risk row {seq} added. Risk index: {ri_i} ({tol_i}).', 'success')
    return redirect(url_for('ra_detail', ra_id=ra_id))

# ─── ADD REVIEW (Page 5) ─────────────────────────────────────────────────────
@app.route('/risk-assessments/<ra_id>/add-review', methods=['POST'])
def ra_add_review(ra_id):
    ra = RiskAssessment.query.get_or_404(ra_id)
    f  = request.form
    rev = RAReview(
        assessment_id=ra_id,
        risk_mitigation=f.get('risk_mitigation',''),
        review_of_effectiveness=f.get('review_of_effectiveness',''),
        effectiveness_rating=f.get('effectiveness_rating',''),
        date_completed=f.get('date_completed',''),
        actioner=f.get('actioner','')
    )
    db.session.add(rev)
    # Update linked mitigation status if effectiveness is set
    if f.get('effectiveness_rating') == 'Effective':
        mit = RAMitigation.query.filter_by(
            assessment_id=ra_id,
            hazard_seq=f.get('hazard_seq','')).first()
        if mit:
            mit.status = 'Completed'
    db.session.commit()
    flash('✓ Mitigation review recorded.', 'success')
    return redirect(url_for('ra_detail', ra_id=ra_id))

# ─── UPDATE RA HEADER (approval / status) ────────────────────────────────────
@app.route('/risk-assessments/<ra_id>/update', methods=['POST'])
def ra_update(ra_id):
    ra = RiskAssessment.query.get_or_404(ra_id)
    f  = request.form
    # All General Information fields — now fully editable
    ra.status                = f.get('status', ra.status)
    ra.management_acceptance = f.get('management_acceptance', ra.management_acceptance)
    ra.acceptance_date       = f.get('acceptance_date', ra.acceptance_date)
    ra.next_review_date      = f.get('next_review_date', ra.next_review_date)
    ra.risk_level_prior      = f.get('risk_level_prior', ra.risk_level_prior)
    ra.risk_level_after      = f.get('risk_level_after', ra.risk_level_after)
    # General Info
    if f.get('responsible_name'):
        ra.responsible_name  = f.get('responsible_name')
    if f.get('assessors_names') is not None:
        ra.assessors_names   = f.get('assessors_names')
    if f.get('assessment_date'):
        ra.assessment_date   = f.get('assessment_date')
    if f.get('reasons') is not None:
        ra.reasons           = f.get('reasons')
    if f.get('general_description') is not None:
        ra.general_description = f.get('general_description')
    if f.get('department_id'):
        ra.department_id     = int(f.get('department_id'))
    # Signatories — all three rows
    if f.get('prepared_by_name') is not None:
        ra.prepared_by_name      = f.get('prepared_by_name')
    if f.get('prepared_by_position') is not None:
        ra.prepared_by_position  = f.get('prepared_by_position')
    if f.get('reviewed_by_name') is not None:
        ra.reviewed_by_name      = f.get('reviewed_by_name')
    if f.get('reviewed_by_position') is not None:
        ra.reviewed_by_position  = f.get('reviewed_by_position')
    if f.get('approved_by_name') is not None:
        ra.approved_by_name      = f.get('approved_by_name')
    if f.get('approved_by_position') is not None:
        ra.approved_by_position  = f.get('approved_by_position')
    db.session.commit()
    flash('✓ Risk Assessment updated successfully.', 'success')
    return redirect(url_for('ra_detail', ra_id=ra_id))

# ─── TRIGGER RA FROM HAZARD LOG ──────────────────────────────────────────────
@app.route('/hazard-log/<hid>/start-ra')
def start_ra_from_hazard(hid):
    """Redirect to new RA form pre-populated from hazard."""
    hazard = Hazard.query.get_or_404(hid)
    # Check if RA already exists
    existing = RiskAssessment.query.filter_by(hazard_id=hid).first()
    if existing:
        return redirect(url_for('ra_detail', ra_id=existing.id))
    return redirect(url_for('new_ra', hazard_id=hid))


# ═══════════════════════════════════════════════════════════════════════════════
#  GUIDED RISK ASSESSMENT WIZARD — 6-STEP WORKFLOW
#  Triggered automatically after Hazard Report / ASR submission
#  ICAO Annex 19 §5 / Doc 9859 Ch.5
# ═══════════════════════════════════════════════════════════════════════════════

WIZARD_STEPS = [
    (1, 'Hazard Review',        'Review the reported hazard'),
    (2, 'Risk Identification',  'Identify consequences and risk scenarios'),
    (3, 'Initial Risk Rating',  'Rate likelihood and severity'),
    (4, 'Current Controls',     'Check existing defences and controls'),
    (5, 'Further Mitigations',  'Define additional mitigation actions'),
    (6, 'Residual Risk',        'Recalculate risk after controls'),
]

CONTROL_CHECKLIST = [
    ('SOP',       'Standard Operating Procedure (SOP) available and current'),
    ('SOP',       'Crew / staff briefed on relevant SOP'),
    ('Training',  'Specific training programme exists for this hazard type'),
    ('Training',  'Personnel have completed required training and are current'),
    ('Monitoring','Regular monitoring / inspection process in place'),
    ('Monitoring','Safety data collected and reviewed for this hazard'),
    ('Equipment', 'Technical safeguards or equipment controls installed'),
    ('Equipment', 'Equipment is serviceable and within maintenance cycle'),
    ('Procedure', 'Emergency / contingency procedure defined'),
    ('Procedure', 'Supervisory checks / sign-off required before operation'),
    ('Reporting', 'Hazard reporting culture promoted in department'),
    ('Reporting', 'Occurrence data analysed and fed back to department'),
]

def get_or_create_ra(hid):
    """Get existing RA for hazard or create a new draft one."""
    hazard = Hazard.query.get_or_404(hid)
    ra = RiskAssessment.query.filter_by(hazard_id=hid).first()
    if not ra:
        dept = hazard.department
        ctrl_no = gen_control_number(dept.code if dept else 'XX')
        ra = RiskAssessment(
            id=new_id('RA'),
            control_number=ctrl_no,
            responsible_name='',
            assessment_date=date.today().isoformat(),
            title=hazard.generic_hazard or 'Risk Assessment',
            hazard_id=hid,
            department_id=hazard.department_id,
            general_description=hazard.specific_components or '',
            reasons=f'Hazard reported from {hazard.source}',
            status='Draft'
        )
        db.session.add(ra)
        db.session.commit()
    return ra

# ─── WIZARD ENTRY POINT ───────────────────────────────────────────────────────
@app.route('/ra-wizard/<hid>')
def ra_wizard_start(hid):
    hazard = Hazard.query.get_or_404(hid)
    ra     = get_or_create_ra(hid)
    return redirect(url_for('ra_wizard_step', hid=hid, step=1))

# ─── STEP ROUTER ─────────────────────────────────────────────────────────────
@app.route('/ra-wizard/<hid>/step/<int:step>', methods=['GET','POST'])
def ra_wizard_step(hid, step):
    hazard = Hazard.query.get_or_404(hid)
    ra     = get_or_create_ra(hid)
    if step < 1 or step > 6:
        return redirect(url_for('ra_wizard_step', hid=hid, step=1))

    # ── POST: save current step data ─────────────────────────────────────────
    if request.method == 'POST':
        f = request.form

        if step == 1:
            # Save ALL admin + general info + signatory fields
            ra.responsible_name      = f.get('responsible_name', ra.responsible_name)
            ra.assessors_names       = f.get('assessors_names', ra.assessors_names)
            ra.assessment_date       = f.get('assessment_date', ra.assessment_date)
            ra.next_review_date      = f.get('next_review_date', ra.next_review_date)
            ra.title                 = f.get('title', ra.title)
            ra.reasons               = f.get('reasons', ra.reasons)
            ra.general_description   = f.get('general_description', ra.general_description)
            # Signatories
            ra.prepared_by_name      = f.get('prepared_by_name', ra.prepared_by_name)
            ra.prepared_by_position  = f.get('prepared_by_position', ra.prepared_by_position)
            ra.reviewed_by_name      = f.get('reviewed_by_name', ra.reviewed_by_name)
            ra.reviewed_by_position  = f.get('reviewed_by_position', ra.reviewed_by_position)
            ra.approved_by_name      = f.get('approved_by_name', ra.approved_by_name)
            ra.approved_by_position  = f.get('approved_by_position', ra.approved_by_position)
            db.session.commit()

        elif step == 2:
            # Save risk rows (one or more risk scenarios)
            activities  = f.getlist('type_of_activity[]')
            hazards_g   = f.getlist('generic_hazard[]')
            components  = f.getlist('specific_components[]')
            consequences= f.getlist('consequences[]')
            # Remove existing rows first if re-doing step 2
            # Only add new rows that don't already exist (by seq)
            existing_seqs = {r.seq_num for r in ra.rows}
            for i, cons in enumerate(consequences):
                if not cons.strip():
                    continue
                seq = i + 1
                if seq not in existing_seqs:
                    row = RARow(
                        assessment_id=ra.id,
                        seq_num=seq,
                        type_of_activity=activities[i] if i < len(activities) else '',
                        generic_hazard=hazards_g[i] if i < len(hazards_g) else '',
                        specific_components=components[i] if i < len(components) else '',
                        consequences=cons,
                        likelihood_initial=3, severity_initial='C',
                        risk_index_initial='3C', risk_tolerance_initial='TOLERABLE'
                    )
                    # Also create Risk record
                    if ra.hazard_id:
                        rsk = Risk(
                            id=new_id('RSK'), hazard_id=ra.hazard_id,
                            description=cons,
                            initial_likelihood=3, initial_severity='C',
                            initial_risk_index='3C', initial_tolerance='TOLERABLE'
                        )
                        db.session.add(rsk)
                        db.session.flush()
                        row.risk_id = rsk.id
                    db.session.add(row)
            db.session.commit()

        elif step == 3:
            # Save initial risk rating per row
            for row in ra.rows:
                lik = f.get(f'lik_{row.seq_num}')
                sev = f.get(f'sev_{row.seq_num}')
                if lik and sev:
                    ri = f'{lik}{sev}'
                    row.likelihood_initial     = int(lik)
                    row.severity_initial       = sev
                    row.risk_index_initial     = ri
                    row.risk_tolerance_initial = get_tolerance(ri)
                    # Update linked Risk record
                    if row.risk_id:
                        rsk = Risk.query.get(row.risk_id)
                        if rsk:
                            rsk.initial_likelihood = int(lik)
                            rsk.initial_severity   = sev
                            rsk.initial_risk_index = ri
                            rsk.initial_tolerance  = get_tolerance(ri)
                row.current_defenses = f.get(f'def_{row.seq_num}', row.current_defenses)
            # Update RA summary
            worst_i, _ = compute_ra_summary(ra)
            if worst_i:
                ra.risk_level_prior = get_tolerance(worst_i)
            db.session.commit()

        elif step == 4:
            # Save checklist responses
            for row in ra.rows:
                # Delete existing checklist for this row
                RAChecklistItem.query.filter_by(
                    assessment_id=ra.id, row_seq=row.seq_num).delete()
                for idx, (cat, desc) in enumerate(CONTROL_CHECKLIST):
                    key     = f'ctrl_{row.seq_num}_{idx}'
                    notes_k = f'notes_{row.seq_num}_{idx}'
                    item = RAChecklistItem(
                        assessment_id=ra.id,
                        row_seq=row.seq_num,
                        category=cat,
                        description=desc,
                        checked=key in f,
                        notes=f.get(notes_k,'')
                    )
                    db.session.add(item)
            db.session.commit()

        elif step == 5:
            # Save further mitigations + auto-create actions
            for row in ra.rows:
                mit_text = f.get(f'mitigation_{row.seq_num}','')
                resp_mgr = f.get(f'manager_{row.seq_num}','')
                due_dt   = f.get(f'due_{row.seq_num}','')
                if mit_text:
                    row.further_mitigations = mit_text
                    # Check if mitigation already exists
                    existing = RAMitigation.query.filter_by(
                        assessment_id=ra.id, hazard_seq=str(row.seq_num)).first()
                    if not existing:
                        act_id = new_id('ACT')
                        mit = RAMitigation(
                            assessment_id=ra.id,
                            hazard_seq=str(row.seq_num),
                            mitigation=mit_text,
                            responsible_manager=resp_mgr,
                            due_date=due_dt,
                            action_id=act_id, status='Open'
                        )
                        db.session.add(mit)
                        action = Action(
                            id=act_id, source='Risk Assessment',
                            hazard_id=ra.hazard_id, linked_ref_id=ra.id,
                            description=f'[{ra.control_number}] Seq {row.seq_num}: {mit_text}',
                            owner=resp_mgr, due_date=due_dt,
                            priority='High' if row.risk_tolerance_initial=='INTOLERABLE' else 'Medium',
                            status='Open'
                        )
                        db.session.add(action)
            db.session.commit()

        elif step == 6:
            # Save residual risk per row — final step
            for row in ra.rows:
                lik_r = f.get(f'res_lik_{row.seq_num}')
                sev_r = f.get(f'res_sev_{row.seq_num}')
                if lik_r and sev_r:
                    ri_r = f'{lik_r}{sev_r}'
                    row.likelihood_residual    = int(lik_r)
                    row.severity_residual      = sev_r
                    row.risk_index_residual    = ri_r
                    row.risk_tolerance_residual = get_tolerance(ri_r)
                    if row.risk_id:
                        rsk = Risk.query.get(row.risk_id)
                        if rsk:
                            rsk.residual_likelihood = int(lik_r)
                            rsk.residual_severity   = sev_r
                            rsk.residual_risk_index = ri_r
                            rsk.residual_tolerance  = get_tolerance(ri_r)
            # Finalise assessment
            _, worst_r = compute_ra_summary(ra)
            if worst_r:
                ra.risk_level_after = get_tolerance(worst_r)
            ra.status = 'Under Review'
            # Update hazard status
            if ra.hazard_id:
                h = Hazard.query.get(ra.hazard_id)
                if h:
                    h.status = 'Under Assessment'
            ra.management_acceptance = f.get('acceptance','')
            ra.prepared_by_name      = f.get('prepared_by','')
            ra.prepared_by_position  = f.get('prepared_position','')
            db.session.commit()

            flash(f'✓ Risk Assessment {ra.control_number} completed. Review and approve below.', 'success')
            return redirect(url_for('ra_detail', ra_id=ra.id))

        # Advance to next step
        if step < 6:
            return redirect(url_for('ra_wizard_step', hid=hid, step=step+1))

    # ── GET: render current step ──────────────────────────────────────────────
    checklist_items = {}
    if step == 4:
        for row in ra.rows:
            items = RAChecklistItem.query.filter_by(
                assessment_id=ra.id, row_seq=row.seq_num).all()
            checklist_items[row.seq_num] = {
                item.description: item for item in items
            }

    # Compute progress
    completed_steps = 0
    if ra.responsible_name:                    completed_steps = max(completed_steps, 1)
    if ra.rows:                                completed_steps = max(completed_steps, 2)
    if ra.rows and ra.rows[0].risk_index_initial: completed_steps = max(completed_steps, 3)
    if RAChecklistItem.query.filter_by(assessment_id=ra.id).first(): completed_steps = max(completed_steps, 4)
    if ra.mitigations:                         completed_steps = max(completed_steps, 5)
    if ra.rows and ra.rows[0].risk_index_residual: completed_steps = max(completed_steps, 6)

    return render_template('risk/ra_wizard.html',
        hazard=hazard, ra=ra, step=step,
        steps=WIZARD_STEPS,
        completed_steps=completed_steps,
        checklist=CONTROL_CHECKLIST,
        checklist_items=checklist_items,
        get_tolerance=get_tolerance)

# ─── RESUME wizard from hazard log ───────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════════════════════
#  PRINT & EXPORT MODULE
#  1. Risk Assessment → Print-ready HTML (browser prints as PDF)
#  2. Hazard Log      → Excel (.xlsx) download
#  3. Hazard Report   → Print-ready HTML (browser prints as PDF)
# ═══════════════════════════════════════════════════════════════════════════════

# ─── HELPER: Excel styling ────────────────────────────────────────────────────
NAVY   = "0F1C3F"
GOLD   = "C9A84C"
WHITE  = "FFFFFF"
RED    = "DC2626"
YELLOW = "D97706"
GREEN  = "15803D"
GRAY   = "F4F6FB"
LGRAY  = "E5E7EB"

def hdr_font(bold=True, color=WHITE, size=11):
    return Font(bold=bold, color=color, size=size, name='Calibri')

def cell_font(bold=False, color="111827", size=10):
    return Font(bold=bold, color=color, size=size, name='Calibri')

def fill(hex_color):
    return PatternFill("solid", fgColor=hex_color)

def border():
    s = Side(style='thin', color=LGRAY)
    return Border(left=s, right=s, top=s, bottom=s)

def set_col_widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

def tol_color(tol):
    if tol == 'INTOLERABLE': return RED
    if tol == 'TOLERABLE':   return YELLOW
    return GREEN

# ─── 1. RISK ASSESSMENT PRINT ─────────────────────────────────────────────────
@app.route('/risk-assessments/<ra_id>/print')
def ra_print(ra_id):
    """Returns a print-ready HTML page that users print as PDF from the browser."""
    ra = RiskAssessment.query.get_or_404(ra_id)
    return render_template('risk/ra_print.html', ra=ra, get_tolerance=get_tolerance)

# ─── 2. HAZARD LOG → EXCEL ────────────────────────────────────────────────────
@app.route('/hazard-log/export-excel')
def hazard_log_excel():
    dept_f = request.args.get('dept','')
    stat_f = request.args.get('status','')
    cls_f  = request.args.get('classification','')

    q = Hazard.query
    if dept_f: q = q.filter_by(department_id=int(dept_f))
    if stat_f: q = q.filter_by(status=stat_f)
    if cls_f:  q = q.filter_by(classification=cls_f)
    hazards = q.order_by(Hazard.created_at.desc()).all()

    wb = Workbook()

    # ── Sheet 1: Hazard Log ───────────────────────────────────────────────────
    ws1 = wb.active
    ws1.title = "Hazard Log"

    # Title row
    ws1.merge_cells('A1:L1')
    ws1['A1'] = 'JORDAN AVIATION — HAZARD LOG'
    ws1['A1'].font = Font(bold=True, size=14, color=WHITE, name='Calibri')
    ws1['A1'].fill = fill(NAVY)
    ws1['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws1.row_dimensions[1].height = 28

    ws1.merge_cells('A2:L2')
    ws1['A2'] = f'Generated: {datetime.now().strftime("%d %b %Y %H:%M")} | Total Hazards: {len(hazards)} | Ref: Jav/SMS/001'
    ws1['A2'].font = Font(size=9, color="6B7280", name='Calibri')
    ws1['A2'].fill = fill(GRAY)
    ws1['A2'].alignment = Alignment(horizontal='center')

    # Headers
    headers = ['Hazard ID','Source','Department','Classification','Generic Hazard',
               'Specific Components','Consequences','Initial Risk','Tolerance',
               'Residual Risk','Res. Tolerance','Status']
    for col, h in enumerate(headers, 1):
        cell = ws1.cell(row=3, column=col, value=h)
        cell.font  = hdr_font()
        cell.fill  = fill(NAVY)
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = border()
    ws1.row_dimensions[3].height = 20

    # Data rows
    for row_num, haz in enumerate(hazards, 4):
        dept  = haz.department.name if haz.department else '—'
        risk  = haz.risks[0] if haz.risks else None
        ri_i  = risk.initial_risk_index  if risk else '—'
        tol_i = risk.initial_tolerance   if risk else '—'
        ri_r  = risk.residual_risk_index if risk else '—'
        tol_r = risk.residual_tolerance  if risk else '—'

        row_data = [
            haz.id, haz.source, dept, haz.classification or '—',
            haz.generic_hazard or '—', haz.specific_components or '—',
            haz.consequences or '—', ri_i, tol_i,
            ri_r or 'Pending', tol_r or 'Pending', haz.status
        ]
        bg = "FFFFFF" if row_num % 2 == 0 else GRAY
        for col, val in enumerate(row_data, 1):
            cell = ws1.cell(row=row_num, column=col, value=val)
            cell.font   = cell_font()
            cell.fill   = fill(bg)
            cell.border = border()
            cell.alignment = Alignment(wrap_text=True, vertical='top')
            # Color code tolerance columns
            if col == 9 and val in ('INTOLERABLE','TOLERABLE','ACCEPTABLE'):
                cell.font = Font(bold=True, color=tol_color(val), size=10, name='Calibri')
            if col == 11 and val in ('INTOLERABLE','TOLERABLE','ACCEPTABLE'):
                cell.font = Font(bold=True, color=tol_color(val), size=10, name='Calibri')
            if col == 12:  # Status
                if val == 'Open':   cell.font = Font(bold=True, color=YELLOW, size=10, name='Calibri')
                elif val == 'Closed': cell.font = Font(bold=True, color=GREEN, size=10, name='Calibri')
        ws1.row_dimensions[row_num].height = 32

    set_col_widths(ws1, [18, 14, 18, 16, 24, 32, 28, 10, 14, 10, 14, 10])

    # Auto-filter
    ws1.auto_filter.ref = f'A3:L{3 + len(hazards)}'
    ws1.freeze_panes    = 'A4'

    # ── Sheet 2: Risk Register ────────────────────────────────────────────────
    ws2 = wb.create_sheet("Risk Register")
    ws2.merge_cells('A1:K1')
    ws2['A1'] = 'JORDAN AVIATION — RISK REGISTER'
    ws2['A1'].font = Font(bold=True, size=14, color=WHITE, name='Calibri')
    ws2['A1'].fill = fill(NAVY)
    ws2['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws2.row_dimensions[1].height = 28

    ws2.merge_cells('A2:K2')
    ws2['A2'] = f'Generated: {datetime.now().strftime("%d %b %Y %H:%M")} | ICAO Annex 19 / Jav/SMS/001'
    ws2['A2'].font = Font(size=9, color="6B7280", name='Calibri')
    ws2['A2'].fill = fill(GRAY)
    ws2['A2'].alignment = Alignment(horizontal='center')

    rsk_headers = ['Risk ID','Hazard ID','Risk Description','Department',
                   'Initial L','Initial S','Initial Index','Initial Tolerance',
                   'Controls','Residual Index','Residual Tolerance']
    for col, h in enumerate(rsk_headers, 1):
        cell = ws2.cell(row=3, column=col, value=h)
        cell.font  = hdr_font()
        cell.fill  = fill(NAVY)
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = border()
    ws2.row_dimensions[3].height = 20

    all_risks = Risk.query.join(Hazard, Risk.hazard_id == Hazard.id)
    if dept_f: all_risks = all_risks.filter(Hazard.department_id == int(dept_f))
    all_risks = all_risks.order_by(Risk.created_at.desc()).all()

    for row_num, rsk in enumerate(all_risks, 4):
        haz   = rsk.hazard
        dept  = haz.department.name if haz and haz.department else '—'
        ctrl_summary = '; '.join([c.description[:40] for c in rsk.controls[:3]]) if rsk.controls else 'None'
        bg = "FFFFFF" if row_num % 2 == 0 else GRAY
        row_data = [
            rsk.id, rsk.hazard_id, rsk.description or '—', dept,
            rsk.initial_likelihood or '—', rsk.initial_severity or '—',
            rsk.initial_risk_index or '—', rsk.initial_tolerance or '—',
            ctrl_summary,
            rsk.residual_risk_index or 'Pending',
            rsk.residual_tolerance or 'Pending'
        ]
        for col, val in enumerate(row_data, 1):
            cell = ws2.cell(row=row_num, column=col, value=val)
            cell.font   = cell_font()
            cell.fill   = fill(bg)
            cell.border = border()
            cell.alignment = Alignment(wrap_text=True, vertical='top')
            if col == 8 and val in ('INTOLERABLE','TOLERABLE','ACCEPTABLE'):
                cell.font = Font(bold=True, color=tol_color(val), size=10, name='Calibri')
            if col == 11 and val in ('INTOLERABLE','TOLERABLE','ACCEPTABLE'):
                cell.font = Font(bold=True, color=tol_color(val), size=10, name='Calibri')
        ws2.row_dimensions[row_num].height = 30

    set_col_widths(ws2, [18, 18, 32, 18, 8, 8, 12, 16, 36, 12, 16])
    ws2.auto_filter.ref = f'A3:K{3 + len(all_risks)}'
    ws2.freeze_panes    = 'A4'

    # ── Sheet 3: Actions ──────────────────────────────────────────────────────
    ws3 = wb.create_sheet("Open Actions")
    ws3.merge_cells('A1:H1')
    ws3['A1'] = 'JORDAN AVIATION — OPEN ACTIONS'
    ws3['A1'].font = Font(bold=True, size=14, color=WHITE, name='Calibri')
    ws3['A1'].fill = fill(NAVY)
    ws3['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws3.row_dimensions[1].height = 28

    act_headers = ['Action ID','Source','Linked Hazard','Description','Owner','Due Date','Priority','Status']
    for col, h in enumerate(act_headers, 1):
        cell = ws3.cell(row=2, column=col, value=h)
        cell.font  = hdr_font()
        cell.fill  = fill(NAVY)
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border()

    open_actions = Action.query.filter(Action.status != 'Closed').order_by(Action.due_date).all()
    for row_num, act in enumerate(open_actions, 3):
        bg = "FFFFFF" if row_num % 2 == 0 else GRAY
        row_data = [
            act.id, act.source, act.hazard_id or '—',
            (act.description or '—')[:80], act.owner or '—',
            act.due_date or '—', act.priority or '—', act.status
        ]
        for col, val in enumerate(row_data, 1):
            cell = ws3.cell(row=row_num, column=col, value=val)
            cell.font   = cell_font()
            cell.fill   = fill(bg)
            cell.border = border()
            cell.alignment = Alignment(wrap_text=True, vertical='top')
            if col == 8:
                color_map = {'Overdue': RED, 'Open': YELLOW, 'In Progress': '1D4ED8'}
                c = color_map.get(val, "111827")
                cell.font = Font(bold=True, color=c, size=10, name='Calibri')
        ws3.row_dimensions[row_num].height = 24

    set_col_widths(ws3, [18, 16, 18, 40, 20, 12, 10, 12])
    ws3.freeze_panes = 'A3'

    # Save to buffer and send
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f'JAV_Hazard_Log_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
    return send_file(buf, as_attachment=True,
                     download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# ─── 3. HAZARD REPORT PRINT ───────────────────────────────────────────────────
@app.route('/hazard-reports/<rep_id>/print')
def hazard_report_print(rep_id):
    rep    = HazardReport.query.get_or_404(rep_id)
    hazard = Hazard.query.get(rep.hazard_id) if rep.hazard_id else None
    ra     = RiskAssessment.query.filter_by(hazard_id=rep.hazard_id).first() if rep.hazard_id else None
    return render_template('reporting/hazard_report_print.html', rep=rep, hazard=hazard, ra=ra,
                           get_tolerance=get_tolerance)

# ─── 4. ASR PRINT ─────────────────────────────────────────────────────────────
@app.route('/asr/<asr_id>/print')
def asr_print(asr_id):
    asr = ASRReport.query.get_or_404(asr_id)
    return render_template('reporting/asr_print.html', asr=asr)


# ═══════════════════════════════════════════════════════════════════════════════
#  RISK ASSESSMENT LIFECYCLE — STATUS ENGINE
#  Draft → Submitted → Active → Under Review → Closed
#  ICAO Annex 19 §5 / Doc 9859 Ch.5 — added without changing existing routes
# ═══════════════════════════════════════════════════════════════════════════════

def ra_can_edit(ra):
    """RA is editable in all states except Closed."""
    return ra.status != 'Closed'

def ra_closure_checks(ra):
    """
    Returns list of blocking reasons. Empty list = can close.
    Rules (ICAO): residual risk assessed + all linked actions closed + effectiveness verified.
    """
    blocks = []
    # 1. Every row must have residual risk assessed
    rows_no_residual = [r for r in ra.rows if not r.risk_index_residual]
    if rows_no_residual:
        blocks.append(f'{len(rows_no_residual)} risk row(s) still have no residual risk assessment.')

    # 2. Residual risk must not be INTOLERABLE
    rows_intol = [r for r in ra.rows if r.risk_tolerance_residual == 'INTOLERABLE']
    if rows_intol:
        blocks.append(f'{len(rows_intol)} risk row(s) have INTOLERABLE residual risk — must be reduced before closing.')

    # 3. All linked actions must be Closed
    if ra.hazard:
        open_actions = [a for a in ra.hazard.actions if a.status not in ('Closed',)]
        if open_actions:
            blocks.append(f'{len(open_actions)} linked action(s) are still open or in progress.')

    # 4. At least one review recorded with effectiveness
    if ra.reviews:
        unverified = [r for r in ra.reviews if not r.effectiveness_rating]
        if unverified:
            blocks.append(f'{len(unverified)} review(s) have no effectiveness rating.')

    return blocks

def check_ra_review_dates():
    """Auto-set status = Under Review when next_review_date is reached."""
    today = date.today().isoformat()
    due = RiskAssessment.query.filter(
        RiskAssessment.status == 'Active',
        RiskAssessment.next_review_date != None,
        RiskAssessment.next_review_date <= today
    ).all()
    for ra in due:
        ra.status = 'Under Review'
    if due:
        db.session.commit()

# ─── SUBMIT (Draft → Submitted → Active) ────────────────────────────────────
@app.route('/risk-assessments/<ra_id>/submit', methods=['POST'])
def ra_submit(ra_id):
    ra = RiskAssessment.query.get_or_404(ra_id)
    if ra.status != 'Draft':
        flash(f'Cannot submit — current status is {ra.status}.', 'error')
        return redirect(url_for('ra_detail', ra_id=ra_id))
    if not ra.rows:
        flash('Cannot submit — no risk rows added. Complete Steps 2–3 first.', 'error')
        return redirect(url_for('ra_detail', ra_id=ra_id))
    today = date.today().isoformat()
    ra.status          = 'Active'
    ra.submitted_date  = today
    ra.activated_date  = today
    # Update linked hazard status
    if ra.hazard:
        ra.hazard.status = 'Under Assessment'
    db.session.commit()
    flash(f'✓ Risk Assessment {ra.control_number} submitted and is now Active.', 'success')
    return redirect(url_for('ra_detail', ra_id=ra_id))

# ─── SEND FOR REVIEW (Active → Under Review) ─────────────────────────────────
@app.route('/risk-assessments/<ra_id>/send-review', methods=['POST'])
def ra_send_review(ra_id):
    ra = RiskAssessment.query.get_or_404(ra_id)
    if ra.status not in ('Active', 'Submitted'):
        flash(f'Cannot send for review — status is {ra.status}.', 'error')
        return redirect(url_for('ra_detail', ra_id=ra_id))
    ra.status = 'Under Review'
    db.session.commit()
    flash('✓ Risk Assessment sent for review.', 'success')
    return redirect(url_for('ra_detail', ra_id=ra_id))

# ─── REACTIVATE (Under Review → Active) ──────────────────────────────────────
@app.route('/risk-assessments/<ra_id>/reactivate', methods=['POST'])
def ra_reactivate(ra_id):
    ra = RiskAssessment.query.get_or_404(ra_id)
    if ra.status != 'Under Review':
        flash(f'Can only reactivate from Under Review status.', 'error')
        return redirect(url_for('ra_detail', ra_id=ra_id))
    ra.status = 'Active'
    db.session.commit()
    flash('✓ Risk Assessment reactivated to Active.', 'success')
    return redirect(url_for('ra_detail', ra_id=ra_id))

# ─── CLOSE (validated) ────────────────────────────────────────────────────────
@app.route('/risk-assessments/<ra_id>/close', methods=['POST'])
def ra_close(ra_id):
    ra = RiskAssessment.query.get_or_404(ra_id)
    if ra.status == 'Closed':
        flash('Already closed.', 'error')
        return redirect(url_for('ra_detail', ra_id=ra_id))
    blocks = ra_closure_checks(ra)
    if blocks:
        for b in blocks:
            flash(f'✗ {b}', 'error')
        return redirect(url_for('ra_detail', ra_id=ra_id))
    ra.status       = 'Closed'
    ra.closed_date  = date.today().isoformat()
    ra.management_acceptance = request.form.get('management_acceptance', ra.management_acceptance)
    ra.acceptance_date       = date.today().isoformat()
    # Update hazard status
    if ra.hazard:
        ra.hazard.status = 'Controlled'
    db.session.commit()
    flash(f'✓ Risk Assessment {ra.control_number} closed successfully.', 'success')
    return redirect(url_for('ra_detail', ra_id=ra_id))

# ─── CLOSURE CHECK (AJAX / page query) ───────────────────────────────────────
@app.route('/risk-assessments/<ra_id>/closure-check')
def ra_closure_check(ra_id):
    ra = RiskAssessment.query.get_or_404(ra_id)
    blocks = ra_closure_checks(ra)
    return render_template('risk/ra_closure_check.html', ra=ra, blocks=blocks)

# ─── REASSESS (create new revision) ──────────────────────────────────────────
@app.route('/risk-assessments/<ra_id>/reassess', methods=['POST'])
def ra_reassess(ra_id):
    old_ra = RiskAssessment.query.get_or_404(ra_id)
    if old_ra.status == 'Closed':
        flash('Cannot reassess a closed Risk Assessment — create a new one.', 'error')
        return redirect(url_for('ra_detail', ra_id=ra_id))

    # Archive the current one
    old_ra.status = 'Archived'
    new_rev = (old_ra.revision or 0) + 1
    new_ctrl = f"{old_ra.control_number}-REV{new_rev}" if old_ra.control_number else gen_control_number(
        old_ra.department.code if old_ra.department else 'XX')

    # Create new revision — copy header, fresh status
    new_ra = RiskAssessment(
        id=new_id('RA'),
        control_number=new_ctrl,
        responsible_name=old_ra.responsible_name,
        assessors_names=old_ra.assessors_names,
        assessment_date=date.today().isoformat(),
        next_review_date=old_ra.next_review_date,
        title=old_ra.title,
        hazard_id=old_ra.hazard_id,
        department_id=old_ra.department_id,
        general_description=old_ra.general_description,
        reasons=f'Reassessment of {old_ra.control_number}',
        risk_level_prior=old_ra.risk_level_prior,
        prepared_by_name=old_ra.prepared_by_name,
        prepared_by_position=old_ra.prepared_by_position,
        reviewed_by_name=old_ra.reviewed_by_name,
        reviewed_by_position=old_ra.reviewed_by_position,
        approved_by_name=old_ra.approved_by_name,
        approved_by_position=old_ra.approved_by_position,
        status='Draft',
        revision=new_rev,
        parent_ra_id=old_ra.id
    )
    db.session.add(new_ra)
    db.session.flush()

    # Copy rows from old RA into new RA (user will update them)
    for old_row in old_ra.rows:
        new_row = RARow(
            assessment_id=new_ra.id,
            seq_num=old_row.seq_num,
            type_of_activity=old_row.type_of_activity,
            generic_hazard=old_row.generic_hazard,
            specific_components=old_row.specific_components,
            consequences=old_row.consequences,
            likelihood_initial=old_row.likelihood_initial,
            severity_initial=old_row.severity_initial,
            risk_index_initial=old_row.risk_index_initial,
            risk_tolerance_initial=old_row.risk_tolerance_initial,
            current_defenses=old_row.current_defenses,
            further_mitigations=old_row.further_mitigations,
            # Residual cleared — user must re-evaluate
            likelihood_residual=None,
            severity_residual=None,
            risk_index_residual=None,
            risk_tolerance_residual=None,
        )
        db.session.add(new_row)

    # Move hazard_id from old RA to new RA (unique constraint requires clearing old first)
    haz_id = old_ra.hazard_id
    old_ra.hazard_id = None
    db.session.flush()
    new_ra.hazard_id = haz_id

    db.session.commit()
    flash(f'✓ New revision {new_ctrl} (REV{new_rev}) created. Please update controls and residual risk.', 'success')
    return redirect(url_for('ra_wizard_step', hid=haz_id, step=4))

with app.app_context():
    db.create_all()

    # ── Safe column migration (PostgreSQL + SQLite compatible) ─────────────────
    # Uses information_schema for PostgreSQL and PRAGMA for SQLite.
    # Safely adds any missing columns to existing live databases on Render.
    migrations = {
            'distribution_lists': [('name','VARCHAR(100)'),('email','VARCHAR(200)'),('department_id','INTEGER'),('position','VARCHAR(100)'),('is_active','BOOLEAN DEFAULT TRUE')],
            'email_logs': [('subject','VARCHAR(300)'),('content_type','VARCHAR(30)'),('content_ref','VARCHAR(50)'),('sent_by','VARCHAR(100)'),('recipient_count','INTEGER DEFAULT 0'),('dept_filter','VARCHAR(200)'),('status',"VARCHAR(20) DEFAULT 'Sent'"),('error_message','TEXT')],
            'survey_responses': [('survey_id','INTEGER'),('respondent_name','VARCHAR(100)'),('respondent_email','VARCHAR(200)'),('department_id','INTEGER'),('is_anonymous','BOOLEAN DEFAULT FALSE'),('answers','TEXT'),('ip_address','VARCHAR(50)')],
            'departments': [
                ('color',                  'VARCHAR(20) DEFAULT "#1e40af"'),
            ],
            'hazard_reports': [
                ('classification',         'VARCHAR(50) DEFAULT "Operational"'),
                ('report_type',            'VARCHAR(30) DEFAULT "Hazard Report"'),
                ('created_at',             'DATETIME'),
                ('status',                 'VARCHAR(30) DEFAULT "Submitted"'),
                ('generic_hazard',         'VARCHAR(200)'),
                ('consequences',           'TEXT'),
                ('immediate_action',       'TEXT'),
                ('suggested_mitigation',   'TEXT'),
                ('reporter_severity',      'VARCHAR(20)'),
                ('reporter',               'VARCHAR(100) DEFAULT "Anonymous"'),
                ('hazard_id',              'VARCHAR(30)'),
                ('severity',               'VARCHAR(2)'),
                ('likelihood',             'INTEGER'),
                ('risk_index',             'VARCHAR(5)'),
            ],
            'hazards': [
                ('classification',         'VARCHAR(50)'),
                ('type_of_activity',       'VARCHAR(100)'),
                ('generic_hazard',         'VARCHAR(200)'),
                ('specific_components',    'TEXT'),
                ('consequences',           'TEXT'),
                ('status',                 'VARCHAR(30) DEFAULT "Open"'),
                ('owner',                  'VARCHAR(100)'),
                ('linked_report_id',       'VARCHAR(30)'),
                ('department_id',          'INTEGER'),
                ('created_at',             'DATETIME'),
            ],
            'actions': [
                ('hazard_id',              'VARCHAR(30)'),
                ('spi_id',                 'INTEGER'),
                ('spi_alert_level',        'VARCHAR(5)'),
                ('spi_trigger_rule',       'VARCHAR(2)'),
                ('evidence',               'TEXT'),
                ('follow_up_notes',        'TEXT'),
                ('mitigation_status',      'VARCHAR(30) DEFAULT "Pending"'),
                ('verified_by',            'VARCHAR(100)'),
                ('verified_date',          'VARCHAR(20)'),
                ('spi_alert_month',        'INTEGER'),
                ('spi_alert_year',         'INTEGER'),
                ('spi_escalation_id',      'INTEGER'),
                ('safety_review_notes',    'TEXT'),
                ('safety_reviewer',        'VARCHAR(100)'),
                ('safety_review_date',     'VARCHAR(20)'),
                ('implementation_date',    'VARCHAR(20)'),
                ('evidence_filename',      'VARCHAR(200)'),
                ('mitigation_description', 'TEXT'),
                ('corrective_description', 'TEXT'),
                ('safety_notes',           'TEXT'),
                ('assigned_by',            'VARCHAR(100)'),
                ('closure_by',             'VARCHAR(100)'),
                ('linked_ref_id',          'VARCHAR(30)'),
                ('linked_risk_id',         'VARCHAR(30)'),
                ('linked_audit_id',        'VARCHAR(30)'),
                ('linked_ra_id',           'VARCHAR(30)'),
                ('department_id',          'INTEGER'),
                ('action_type',            'VARCHAR(20) DEFAULT "Corrective"'),
                ('owner',                  'VARCHAR(100)'),
                ('due_date',               'VARCHAR(20)'),
                ('priority',               'VARCHAR(20) DEFAULT "Medium"'),
                ('completed_date',         'VARCHAR(20)'),
                ('closed_date',            'VARCHAR(20)'),
                ('effectiveness',          'VARCHAR(30)'),
                ('effectiveness_review',   'TEXT'),
                ('verified_by',            'VARCHAR(100)'),
                ('verified_date',          'VARCHAR(20)'),
                ('spi_alert_month',        'INTEGER'),
                ('spi_alert_year',         'INTEGER'),
                ('spi_escalation_id',      'INTEGER'),
                ('safety_review_notes',    'TEXT'),
                ('safety_reviewer',        'VARCHAR(100)'),
                ('safety_review_date',     'VARCHAR(20)'),
                ('implementation_date',    'VARCHAR(20)'),
                ('evidence_filename',      'VARCHAR(200)'),
                ('mitigation_description', 'TEXT'),
                ('corrective_description', 'TEXT'),
                ('safety_notes',           'TEXT'),
                ('assigned_by',            'VARCHAR(100)'),
                ('closure_by',             'VARCHAR(100)'),
                ('reopen_count',           'INTEGER DEFAULT 0'),
                ('reopen_reason',          'TEXT'),
                ('created_at',             'DATETIME'),
            ],
            'audit_plans': [
                ('month',                  'INTEGER'),
                ('created_at',             'DATETIME'),
                ('objectives',             'TEXT'),
                ('iosa_reference',         'VARCHAR(100)'),
                ('auditor_name',           'VARCHAR(100)'),
                ('planned_week',           'INTEGER'),
                ('responsible_manager',    'VARCHAR(100)'),
                ('frequency',              'VARCHAR(30)'),
                ('scope',                  'TEXT'),
            ],
            'audit_schedules': [
                ('plan_id',                'VARCHAR(30)'),
                ('audit_team',             'VARCHAR(200)'),
                ('scope',                  'TEXT'),
                ('objectives',             'TEXT'),
                ('actual_date',            'VARCHAR(20)'),
                ('opening_meeting',        'TEXT'),
                ('closing_meeting',        'TEXT'),
                ('summary',                'TEXT'),
                ('final_remarks',          'TEXT'),
                ('closure_date',           'VARCHAR(20)'),
                ('closed_by',              'VARCHAR(100)'),
                ('created_at',             'DATETIME'),
            ],
            'audit_findings': [
                ('finding_ref',            'VARCHAR(30)'),
                ('assigned_to',            'VARCHAR(100)'),
                ('assigned_dept',          'VARCHAR(100)'),
                ('assigned_date',          'VARCHAR(20)'),
                ('investigation_notes',    'TEXT'),
                ('contributing_factors',   'TEXT'),
                ('root_cause_submitted_at','DATETIME'),
                ('immediate_action',       'TEXT'),
                ('longterm_action',        'TEXT'),
                ('cap_responsible',        'VARCHAR(100)'),
                ('cap_due_date',           'VARCHAR(20)'),
                ('cap_status',             'VARCHAR(30) DEFAULT "Pending"'),
                ('cap_completion_pct',     'INTEGER DEFAULT 0'),
                ('cap_submitted_at',       'DATETIME'),
                ('evidence_files',         'TEXT'),
                ('review_notes',           'TEXT'),
                ('reviewed_by',            'VARCHAR(100)'),
                ('review_date',            'VARCHAR(20)'),
                ('revision_reason',        'TEXT'),
                ('closure_verified_by',    'VARCHAR(100)'),
                ('closure_date',           'VARCHAR(20)'),
                ('closure_notes',          'TEXT'),
                ('sig_dept_manager',       'VARCHAR(100)'),
                ('sig_auditor',            'VARCHAR(100)'),
                ('sig_safety_manager',     'VARCHAR(100)'),
                ('sig_date',               'VARCHAR(20)'),
                ('linked_action_id',       'VARCHAR(30)'),
                ('created_at',             'DATETIME'),
                ('category',               'VARCHAR(50)'),
                ('severity',               'VARCHAR(20)'),
                ('requirement',            'TEXT'),
                ('root_cause',             'TEXT'),
                ('evidence',               'TEXT'),
                ('standard_ref',           'VARCHAR(100)'),
                ('status',                 'VARCHAR(20) DEFAULT "Open"'),
                ('hazard_id',              'VARCHAR(30)'),
            ],
            'risks': [
                ('description',            'TEXT'),
                ('initial_likelihood',      'INTEGER'),
                ('initial_severity',        'VARCHAR(2)'),
                ('initial_risk_index',      'VARCHAR(5)'),
                ('initial_tolerance',       'VARCHAR(20)'),
                ('residual_likelihood',     'INTEGER'),
                ('residual_severity',       'VARCHAR(2)'),
                ('residual_risk_index',     'VARCHAR(5)'),
                ('residual_tolerance',      'VARCHAR(20)'),
                ('created_at',             'DATETIME'),
            ],
            'controls': [
                ('hazard_id',              'VARCHAR(30)'),
                ('risk_id',               'VARCHAR(30)'),
                ('description',           'TEXT'),
                ('control_type',          'VARCHAR(50)'),
                ('effectiveness',         'VARCHAR(30)'),
                ('status',               'VARCHAR(20)'),
                ('created_at',           'DATETIME'),
            ],
            'spi_indicators': [
                ('category',        'VARCHAR(50)'),
                ('baseline_months', 'INTEGER DEFAULT 3'),
                ('improvement_pct', 'FLOAT DEFAULT 5.0'),
                ('stat_mode',       'BOOLEAN DEFAULT 0'),
                ('description',     'TEXT'),
                ('calc_type',       'VARCHAR(10) DEFAULT "RATE"'),
                ('exposure_type',   'VARCHAR(30) DEFAULT "Flights"'),
                ('frequency',       'VARCHAR(20) DEFAULT "Monthly"'),
                ('alert_l3',        'FLOAT'),
                ('auto_source',     'VARCHAR(50) DEFAULT "manual"'),
                ('auto_category',   'VARCHAR(50)'),
                ('active',          'BOOLEAN DEFAULT 1'),
                ('created_at',      'DATETIME'),
            ],
            'checklist_templates': [
                ('is_active',   'BOOLEAN DEFAULT 1'),
                ('updated_at',  'DATETIME'),
                ('version',     'INTEGER DEFAULT 1'),
            ],
            'checklist_template_items': [
                ('iosa_ref',    'VARCHAR(100)'),
            ],
            'audit_checklists': [
                ('evidence_filename',   'VARCHAR(200)'),
                ('linked_finding_id',   'VARCHAR(30)'),
            ],
            'spi_data': [
                ('exposure',        'FLOAT DEFAULT 1'),
                ('mean_at_time',    'FLOAT'),
                ('sd_at_time',      'FLOAT'),
                ('total_events',    'INTEGER DEFAULT 0'),
                ('value',           'FLOAT'),
                ('source',          'VARCHAR(20) DEFAULT "manual"'),
                ('notes',           'TEXT'),
            ],
            'risk_assessments': [
                ('control_number',         'VARCHAR(50)'),
                ('responsible_name',       'VARCHAR(100)'),
                ('assessors_names',        'VARCHAR(200)'),
                ('created_at',             'DATETIME'),
                ('title',                  'VARCHAR(200)'),
                ('general_description',    'TEXT'),
                ('reasons',                'TEXT'),
                ('risk_level_prior',       'VARCHAR(20)'),
                ('risk_level_after',       'VARCHAR(20)'),
                ('management_acceptance',  'VARCHAR(30)'),
                ('acceptance_date',        'VARCHAR(20)'),
                ('prepared_by_name',       'VARCHAR(100)'),
                ('prepared_by_position',   'VARCHAR(100)'),
                ('reviewed_by_name',       'VARCHAR(100)'),
                ('reviewed_by_position',   'VARCHAR(100)'),
                ('approved_by_name',       'VARCHAR(100)'),
                ('approved_by_position',   'VARCHAR(100)'),
                ('submitted_date',         'VARCHAR(20)'),
                ('activated_date',         'VARCHAR(20)'),
                ('closed_date',            'VARCHAR(20)'),
                ('revision',               'INTEGER DEFAULT 0'),
                ('parent_ra_id',           'VARCHAR(30)'),
                ('next_review_date',       'VARCHAR(20)'),
                ('assessment_date',        'VARCHAR(20)'),
            ],
            'voluntary_reports': [
                ('ref_number',      'VARCHAR(30)'),
                ('reporter_name',   'VARCHAR(100)'),
                ('position',        'VARCHAR(100)'),
                ('department_id',   'INTEGER'),
                ('date',            'VARCHAR(20)'),
                ('location',        'VARCHAR(200)'),
                ('report_type',     'VARCHAR(50)'),
                ('description',     'TEXT'),
                ('consequences',    'TEXT'),
                ('suggestion',      'TEXT'),
                ('status',          'VARCHAR(20) DEFAULT "Submitted"'),
                ('is_confidential', 'BOOLEAN DEFAULT 0'),
            ],
            'confidential_reports': [
                ('ref_number',      'VARCHAR(30)'),
                ('position',        'VARCHAR(100)'),
                ('department_id',   'INTEGER'),
                ('date',            'VARCHAR(20)'),
                ('location',        'VARCHAR(200)'),
                ('report_type',     'VARCHAR(50)'),
                ('description',     'TEXT'),
                ('consequences',    'TEXT'),
                ('suggestion',      'TEXT'),
                ('status',          'VARCHAR(20) DEFAULT "Submitted"'),
            ],
            'trainings': [
                ('employee_id',        'VARCHAR(50)'),
                ('position',           'VARCHAR(100)'),
                ('course_code',        'VARCHAR(50)'),
                ('location',           'VARCHAR(100)'),
                ('scheduled_date',     'VARCHAR(20)'),
                ('duration_hours',     'REAL'),
                ('evidence',           'VARCHAR(200)'),
                ('is_recurrent',       'BOOLEAN DEFAULT 0'),
                ('recurrence_months',  'INTEGER'),
                ('updated_at',         'DATETIME'),
            ],
    }

    # Detect database type
    db_url = str(db.engine.url)
    is_postgres = 'postgresql' in db_url or 'postgres' in db_url

    if is_postgres:
        # PostgreSQL: use information_schema
        from sqlalchemy import text as sa_text
        with db.engine.connect() as conn:
            # Widen status columns that were too narrow for longer values
            for tbl_col in [
                ('actions',        'status',           'VARCHAR(50)'),
                ('hazard_reports',  'status',           'VARCHAR(50)'),
                ('hazards',         'status',           'VARCHAR(50)'),
                ('audit_findings',  'status',           'VARCHAR(50)'),
            ]:
                try:
                    conn.execute(sa_text(
                        f'ALTER TABLE {tbl_col[0]} ALTER COLUMN {tbl_col[1]} TYPE {tbl_col[2]}'
                    ))
                    conn.commit()
                except Exception:
                    try: conn.rollback()
                    except: pass

            for table, columns in migrations.items():
                for col_name, col_def in columns:
                    try:
                        result = conn.execute(sa_text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name = :tbl AND column_name = :col"
                        ), {'tbl': table, 'col': col_name})
                        if result.fetchone() is None:
                            # Column doesn't exist — add it
                            pg_def = col_def.replace('DATETIME', 'TIMESTAMP').replace('BOOLEAN DEFAULT 0', 'BOOLEAN DEFAULT FALSE').replace('BOOLEAN DEFAULT 1', 'BOOLEAN DEFAULT TRUE')
                            conn.execute(sa_text(
                                f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_name} {pg_def}'
                            ))
                            conn.commit()
                            print(f'✅ Migration: added {table}.{col_name}')
                    except Exception as e:
                        # Column may already exist or table doesn't exist yet — safe to skip
                        try: conn.rollback()
                        except: pass
    else:
        # SQLite fallback
        import sqlite3
        db_path = os.path.join(os.path.dirname(__file__), 'sms.db')
        if os.path.exists(db_path):
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            for table, columns in migrations.items():
                try:
                    cur.execute(f'PRAGMA table_info({table})')
                    existing = {row[1] for row in cur.fetchall()}
                    for col_name, col_def in columns:
                        if col_name not in existing:
                            cur.execute(f'ALTER TABLE {table} ADD COLUMN {col_name} {col_def}')
                            print(f'✅ Migration: added {table}.{col_name}')
                except Exception as e:
                    print(f'Migration warning for {table}: {e}')
            con.commit()
            con.close()

    seed()

if __name__ == '__main__':
    app.run(debug=True)
