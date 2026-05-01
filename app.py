from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, Department, AuditPlan, AuditSchedule, ChecklistItem, AuditFinding, AuditAction, Hazard
from datetime import datetime, date
import os, uuid

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', f'sqlite:///{os.path.join(BASE_DIR, "audit.db")}')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'jav-audit-2024')
db.init_app(app)

# ─── Helpers ──────────────────────────────────────────────────────────────────
INTOLERABLE = {'5A','5B','5C','4A','4B','3A'}
TOLERABLE   = {'5D','5E','4C','4D','4E','3B','3C','3D','2A','2B','2C','1A'}

def get_tolerance(ri):
    if ri in INTOLERABLE: return 'INTOLERABLE'
    if ri in TOLERABLE:   return 'TOLERABLE'
    return 'ACCEPTABLE'

def new_id(prefix):
    year  = datetime.now().year
    short = str(uuid.uuid4())[:6].upper()
    return f'{prefix}-{year}-{short}'

def check_overdue():
    today = date.today().isoformat()
    for a in AuditAction.query.filter(AuditAction.status.in_(['Open','In Progress'])).all():
        if a.due_date and a.due_date < today:
            a.status = 'Overdue'
    db.session.commit()

def audit_can_close(audit):
    """Audit can close only when all findings have actions and all actions are closed/effective."""
    for f in audit.findings:
        if not f.actions:
            return False, f'Finding {f.id} has no corrective action.'
        for a in f.actions:
            if a.status not in ('Closed',):
                return False, f'Action {a.id} is not yet closed (status: {a.status}).'
            if not a.effectiveness_review:
                return False, f'Action {a.id} effectiveness not yet reviewed.'
            if a.effectiveness_review == 'Ineffective':
                return False, f'Action {a.id} is marked Ineffective — re-open required.'
    return True, 'All conditions met.'

# ─── Default checklist templates per department ────────────────────────────────
CHECKLIST_TEMPLATES = {
    'Flight Operations': [
        ('SOP Compliance',      'IOSA FLT 1.1.1',  'Does the operator have documented standard operating procedures for all flight operations?'),
        ('SOP Compliance',      'IOSA FLT 1.1.2',  'Are SOPs reviewed and updated at least annually?'),
        ('SOP Compliance',      'IOSA FLT 1.2.1',  'Are crew members trained on current SOPs before operating?'),
        ('Training Records',    'IOSA TRG 1.1.1',  'Are training records maintained for all flight crew members?'),
        ('Training Records',    'IOSA TRG 1.1.2',  'Are recency requirements tracked and enforced?'),
        ('Training Records',    'IOSA TRG 2.1.1',  'Is CRM training conducted at prescribed intervals?'),
        ('Safety Reporting',    'ICAO Ann.19 3.1',  'Is a voluntary safety reporting system in place and actively used?'),
        ('Safety Reporting',    'IOSA ISM 1.3.1',  'Are safety reports processed within the required timeframe?'),
        ('Safety Reporting',    'IOSA ISM 1.3.2',  'Is reporter confidentiality maintained in all cases?'),
        ('Operational Procedures', 'IOSA FLT 2.1.1', 'Are pre-flight planning procedures followed for all flights?'),
        ('Operational Procedures', 'IOSA FLT 2.1.2', 'Are fuel policy requirements consistently applied?'),
        ('Operational Procedures', 'IOSA FLT 3.1.1', 'Are approach briefing standards compliant with IOSA requirements?'),
        ('Risk Management',     'ICAO Ann.19 5.1',  'Are hazard identification processes applied to flight operations?'),
        ('Risk Management',     'IOSA ISM 2.1.1',  'Are risk assessments documented for identified hazards?'),
        ('Risk Management',     'IOSA ISM 2.2.1',  'Are risk controls implemented and their effectiveness monitored?'),
    ],
    'Maintenance / Engineering': [
        ('SOP Compliance',      'IOSA MNT 1.1.1',  'Are maintenance procedures documented and approved by the authority?'),
        ('SOP Compliance',      'IOSA MNT 1.1.2',  'Are deferred defect procedures clearly documented and followed?'),
        ('Training Records',    'IOSA MNT 2.1.1',  'Are all certifying staff licensed and current?'),
        ('Training Records',    'IOSA MNT 2.1.2',  'Are human factors training records maintained for all maintenance staff?'),
        ('Safety Reporting',    'IOSA MNT 3.1.1',  'Are all defects and incidents reported in the technical log?'),
        ('Operational Procedures', 'IOSA MNT 4.1.1', 'Are tool control procedures in place and enforced?'),
        ('Operational Procedures', 'IOSA MNT 4.1.2', 'Are aircraft technical records complete and up to date?'),
        ('Risk Management',     'IOSA MNT 5.1.1',  'Are FOD prevention procedures in place and monitored?'),
        ('Risk Management',     'IOSA MNT 5.1.2',  'Is a fatigue risk management system applied to maintenance staff?'),
    ],
    'Ground Operations': [
        ('SOP Compliance',      'IOSA GRH 1.1.1',  'Are ground handling procedures documented for all aircraft types?'),
        ('SOP Compliance',      'IOSA GRH 1.1.2',  'Are ramp safety procedures reviewed at required intervals?'),
        ('Training Records',    'IOSA GRH 2.1.1',  'Are ground handling staff trained and competency-checked?'),
        ('Training Records',    'IOSA GRH 2.1.2',  'Are dangerous goods handling training records current?'),
        ('Safety Reporting',    'IOSA GRH 3.1.1',  'Are ramp incidents and near-misses reported and investigated?'),
        ('Operational Procedures', 'IOSA GRH 4.1.1', 'Are aircraft weight and balance procedures consistently applied?'),
        ('Operational Procedures', 'IOSA GRH 4.1.2', 'Are vehicle movement restrictions enforced on the ramp?'),
        ('Risk Management',     'IOSA GRH 5.1.1',  'Is a FOD walk conducted at prescribed intervals?'),
    ],
    'Cabin Crew': [
        ('SOP Compliance',      'IOSA CAB 1.1.1',  'Are cabin crew procedures documented and distributed to all crew?'),
        ('SOP Compliance',      'IOSA CAB 1.1.2',  'Are emergency procedures rehearsed at required intervals?'),
        ('Training Records',    'IOSA CAB 2.1.1',  'Are initial and recurrent training records current for all cabin crew?'),
        ('Training Records',    'IOSA CAB 2.1.2',  'Are security training records maintained and up to date?'),
        ('Safety Reporting',    'IOSA CAB 3.1.1',  'Are cabin safety incidents reported through the SMS?'),
        ('Operational Procedures', 'IOSA CAB 4.1.1', 'Are passenger safety briefings conducted for every flight?'),
        ('Operational Procedures', 'IOSA CAB 4.1.2', 'Is turbulence management policy consistently applied?'),
        ('Risk Management',     'IOSA CAB 5.1.1',  'Are hazards identified during cabin operations reported promptly?'),
    ],
    'Safety Department': [
        ('SOP Compliance',      'ICAO Ann.19 2.1',  'Is the SMS documented in the Safety Management System Manual?'),
        ('SOP Compliance',      'ICAO Ann.19 2.2',  'Is the safety policy signed by the Accountable Manager?'),
        ('Training Records',    'IOSA ISM 1.1.1',  'Are SMS awareness training records maintained for all staff?'),
        ('Safety Reporting',    'IOSA ISM 1.3.1',  'Is the safety reporting system accessible to all employees?'),
        ('Safety Reporting',    'IOSA ISM 1.3.2',  'Are safety reports acknowledged within 48 hours?'),
        ('Operational Procedures', 'IOSA ISM 2.1.1', 'Are safety performance indicators monitored monthly?'),
        ('Operational Procedures', 'IOSA ISM 3.1.1', 'Are safety bulletins issued when required?'),
        ('Risk Management',     'IOSA ISM 2.2.1',  'Is the hazard register reviewed at least quarterly?'),
        ('Risk Management',     'IOSA ISM 2.2.2',  'Are risk assessments completed for all identified hazards?'),
        ('Risk Management',     'ICAO Ann.19 5.2',  'Is the effectiveness of risk controls tracked and reviewed?'),
    ],
}

@app.context_processor
def inject_globals():
    depts   = Department.query.all()
    now     = datetime.utcnow()
    overdue = AuditAction.query.filter_by(status='Overdue').count()
    open_findings = AuditFinding.query.filter(AuditFinding.status != 'Closed').count()
    return dict(all_departments=depts, now=now, get_tolerance=get_tolerance,
                nav_overdue=overdue, nav_findings=open_findings)

# ═══════════════════════════════════════════════════════════════════════════════
#  SEED
# ═══════════════════════════════════════════════════════════════════════════════
def seed():
    if Department.query.first(): return

    depts = [
        Department(id=1, code='FO', name='Flight Operations',        color='#1e40af'),
        Department(id=2, code='ME', name='Maintenance / Engineering', color='#065f46'),
        Department(id=3, code='GO', name='Ground Operations',         color='#92400e'),
        Department(id=4, code='CC', name='Cabin Crew',                color='#6b21a8'),
        Department(id=5, code='SD', name='Safety Department',         color='#be123c'),
    ]
    db.session.add_all(depts)
    db.session.flush()

    # Audit Plan 2025
    plans = [
        AuditPlan(id='PLN-2025-FO', year=2025, department_id=1, audit_type='Internal Audit',
                  frequency='Semi-Annual', responsible_manager='Flight Operations Manager',
                  scope='Review of FO SOPs, training records, safety reporting compliance and risk management implementation.'),
        AuditPlan(id='PLN-2025-ME', year=2025, department_id=2, audit_type='Compliance Audit',
                  frequency='Annual', responsible_manager='Maintenance Manager',
                  scope='Review of maintenance procedures, licensing records, and technical documentation.'),
        AuditPlan(id='PLN-2025-GO', year=2025, department_id=3, audit_type='Internal Audit',
                  frequency='Annual', responsible_manager='Ground Operations Manager',
                  scope='Review of ramp procedures, training records, and incident reporting.'),
        AuditPlan(id='PLN-2025-SD', year=2025, department_id=5, audit_type='IOSA-style Audit',
                  frequency='Annual', responsible_manager='Safety Manager',
                  scope='Review of SMS documentation, SPI monitoring, and hazard register.'),
    ]
    db.session.add_all(plans)
    db.session.flush()

    # Audit Schedule — completed FO audit with findings
    aud1 = AuditSchedule(
        id='AUD-2025-FO01', plan_id='PLN-2025-FO', department_id=1,
        audit_type='Internal Audit',
        title='Flight Operations SMS Compliance Audit — Q1 2025',
        scheduled_date='2025-03-01', actual_date='2025-03-05',
        lead_auditor='Omar Al-Hassan', co_auditor='Hana Khalil',
        status='Completed',
        opening_meeting_date='2025-03-05',
        closing_meeting_date='2025-03-05',
    )
    db.session.add(aud1)
    db.session.flush()

    # Checklist items for aud1
    items_fo = [
        ChecklistItem(audit_id=aud1.id, category='SOP Compliance', reference='IOSA FLT 1.1.1',
            question='Does the operator have documented standard operating procedures for all flight operations?',
            response='Yes', comment='SOPs confirmed in FCOM Rev 14.'),
        ChecklistItem(audit_id=aud1.id, category='Training Records', reference='IOSA TRG 1.1.1',
            question='Are training records maintained for all flight crew members?',
            response='No', comment='3 crew members had no record of SEP recency training.',
            finding_generated=True),
        ChecklistItem(audit_id=aud1.id, category='Safety Reporting', reference='IOSA ISM 1.3.1',
            question='Are safety reports processed within the required timeframe?',
            response='No', comment='Average processing time was 14 days vs required 7 days.',
            finding_generated=True),
        ChecklistItem(audit_id=aud1.id, category='Operational Procedures', reference='IOSA FLT 2.1.2',
            question='Are fuel policy requirements consistently applied?',
            response='Yes', comment='Fuel policy records reviewed — all compliant.'),
        ChecklistItem(audit_id=aud1.id, category='Risk Management', reference='IOSA ISM 2.1.1',
            question='Are risk assessments documented for identified hazards?',
            response='N/A', comment='Not applicable to this audit scope.'),
    ]
    db.session.add_all(items_fo)
    db.session.flush()

    # Findings for aud1
    f1 = AuditFinding(
        id='FND-2025-001', audit_id=aud1.id,
        checklist_item_id=items_fo[1].id,
        description='3 flight crew members have no record of SEP (Safety & Emergency Procedures) recency training. Training was due in Q4 2024 and was not completed.',
        category='Organizational', severity='Major',
        root_cause='Training scheduling system did not send alerts for overdue recency training.',
        evidence='Training records reviewed on 05 Mar 2025. Staff IDs: FO-041, FO-078, FO-112.',
        requirement_ref='IOSA TRG 1.1.1', status='Closed'
    )
    f2 = AuditFinding(
        id='FND-2025-002', audit_id=aud1.id,
        checklist_item_id=items_fo[2].id,
        description='Average safety report processing time is 14 days, exceeding the 7-day requirement. 12 reports reviewed — none processed within required timeframe.',
        category='Organizational', severity='Minor',
        root_cause='No formal SLA or escalation process defined for safety report processing.',
        evidence='Safety report log reviewed — 12 reports from Jan-Feb 2025.',
        requirement_ref='IOSA ISM 1.3.1', status='Open'
    )
    db.session.add_all([f1, f2])
    db.session.flush()

    # Auto-create hazard from major finding
    h1 = Hazard(
        id='HAZ-2025-AUD01', source='Audit', linked_report_id=f1.id,
        department_id=1, classification='Organizational',
        generic_hazard='SEP Training Overdue — Flight Crew',
        specific_components='3 crew members operating without current SEP recency training',
        consequences='Non-compliance with IOSA TRG 1.1.1. Crew may not be fully prepared for emergency situations.',
        initial_likelihood=3, initial_severity='B',
        initial_risk_index='3B', initial_tolerance='INTOLERABLE',
        status='Open', owner='Flight Operations Manager'
    )
    db.session.add(h1)
    f1.hazard_id = h1.id
    db.session.flush()

    # Actions for findings
    a1 = AuditAction(
        id='ACT-2025-001', finding_id=f1.id, hazard_id=h1.id,
        description='Ground all 3 affected crew members immediately. Schedule SEP recurrency training within 14 days. Update training scheduler with auto-alerts for overdue items.',
        owner='Flight Operations Manager', due_date='2025-03-20',
        priority='High', status='Closed',
        completion_date='2025-03-18',
        completion_evidence='All 3 crew members completed SEP recurrency on 15 Mar 2025. Training records updated. Auto-alert system configured.',
        effectiveness_review='Effective',
        effectiveness_notes='Training completed on schedule. Auto-alert system now active for all recurrency items.',
        verified_by='Omar Al-Hassan', verification_date='2025-03-20'
    )
    a2 = AuditAction(
        id='ACT-2025-002', finding_id=f2.id,
        description='Define formal SLA for safety report processing (max 7 days). Implement escalation process for reports pending over 5 days. Assign Safety Officer as process owner.',
        owner='Safety Manager', due_date='2025-04-15',
        priority='Medium', status='In Progress',
        completion_evidence='',
        effectiveness_review=None
    )
    db.session.add_all([a1, a2])

    # Planned audit
    aud2 = AuditSchedule(
        id='AUD-2025-ME01', plan_id='PLN-2025-ME', department_id=2,
        audit_type='Compliance Audit',
        title='Maintenance & Engineering Annual Compliance Audit — 2025',
        scheduled_date='2025-06-10', lead_auditor='Rania Saad',
        status='Planned'
    )
    db.session.add(aud2)

    aud3 = AuditSchedule(
        id='AUD-2025-SD01', plan_id='PLN-2025-SD', department_id=5,
        audit_type='IOSA-style Audit',
        title='Safety Department IOSA-style SMS Audit — 2025',
        scheduled_date='2025-09-01', lead_auditor='External Auditor',
        status='Planned'
    )
    db.session.add(aud3)

    db.session.commit()
    print('✅ Audit database seeded.')

# ═══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Dashboard ────────────────────────────────────────────────────────────────
@app.route('/')
def dashboard():
    check_overdue()
    plans_cnt    = AuditPlan.query.count()
    audits_cnt   = AuditSchedule.query.count()
    planned_cnt  = AuditSchedule.query.filter_by(status='Planned').count()
    inprog_cnt   = AuditSchedule.query.filter_by(status='In Progress').count()
    complete_cnt = AuditSchedule.query.filter_by(status='Completed').count()
    findings_open = AuditFinding.query.filter(AuditFinding.status != 'Closed').count()
    findings_major = AuditFinding.query.filter_by(severity='Major').count()
    actions_open = AuditAction.query.filter(AuditAction.status.in_(['Open','In Progress'])).count()
    actions_overdue = AuditAction.query.filter_by(status='Overdue').count()
    recent_audits = AuditSchedule.query.order_by(AuditSchedule.created_at.desc()).limit(6).all()
    recent_findings = AuditFinding.query.filter(AuditFinding.status != 'Closed').order_by(AuditFinding.created_at.desc()).limit(5).all()
    return render_template('dashboard.html',
        plans_cnt=plans_cnt, audits_cnt=audits_cnt,
        planned_cnt=planned_cnt, inprog_cnt=inprog_cnt, complete_cnt=complete_cnt,
        findings_open=findings_open, findings_major=findings_major,
        actions_open=actions_open, actions_overdue=actions_overdue,
        recent_audits=recent_audits, recent_findings=recent_findings)

# ─── Audit Plans ──────────────────────────────────────────────────────────────
@app.route('/plans')
def plans():
    year = request.args.get('year', datetime.now().year, type=int)
    all_plans = AuditPlan.query.filter_by(year=year).order_by(AuditPlan.department_id).all()
    years = sorted(set(p.year for p in AuditPlan.query.all()), reverse=True) or [year]
    return render_template('plans.html', plans=all_plans, year=year, years=years)

@app.route('/plans/new', methods=['GET','POST'])
def new_plan():
    if request.method == 'POST':
        f = request.form
        d = Department.query.get(int(f['department_id']))
        pid = f'PLN-{f["year"]}-{d.code}'
        # Check if plan already exists for this dept/year
        existing = AuditPlan.query.get(pid)
        if existing:
            pid = new_id('PLN')
        p = AuditPlan(id=pid, year=int(f['year']),
                      department_id=int(f['department_id']),
                      audit_type=f['audit_type'],
                      frequency=f['frequency'],
                      responsible_manager=f['responsible_manager'],
                      scope=f.get('scope',''))
        db.session.add(p)
        db.session.commit()
        flash(f'✓ Audit Plan {pid} created for {d.name} — {f["year"]}.', 'success')
        return redirect(url_for('plans'))
    return render_template('plan_form.html', current_year=datetime.now().year)

# ─── Audit Schedule ───────────────────────────────────────────────────────────
@app.route('/schedule')
def schedule():
    check_overdue()
    status_f = request.args.get('status','')
    dept_f   = request.args.get('dept','')
    q = AuditSchedule.query
    if status_f: q = q.filter_by(status=status_f)
    if dept_f:   q = q.filter_by(department_id=int(dept_f))
    audits = q.order_by(AuditSchedule.scheduled_date).all()
    return render_template('schedule.html', audits=audits, status_f=status_f, dept_f=dept_f)

@app.route('/schedule/new', methods=['GET','POST'])
def new_audit():
    if request.method == 'POST':
        f = request.form
        aid = new_id('AUD')
        a = AuditSchedule(id=aid,
            plan_id=f.get('plan_id') or None,
            department_id=int(f['department_id']),
            audit_type=f['audit_type'],
            title=f['title'],
            scheduled_date=f['scheduled_date'],
            lead_auditor=f['lead_auditor'],
            co_auditor=f.get('co_auditor',''),
            status='Planned')
        db.session.add(a)
        db.session.commit()
        flash(f'✓ Audit {aid} scheduled.', 'success')
        return redirect(url_for('audit_detail', aid=aid))
    plans_list = AuditPlan.query.order_by(AuditPlan.year.desc()).all()
    return render_template('audit_form.html', plans=plans_list)

# ─── Audit Detail (Execution) ─────────────────────────────────────────────────
@app.route('/audit/<aid>')
def audit_detail(aid):
    a = AuditSchedule.query.get_or_404(aid)
    can_close, close_msg = audit_can_close(a)
    total_items  = len(a.checklist_items)
    yes_items    = sum(1 for i in a.checklist_items if i.response == 'Yes')
    no_items     = sum(1 for i in a.checklist_items if i.response == 'No')
    na_items     = sum(1 for i in a.checklist_items if i.response == 'N/A')
    compliance_pct = round(yes_items / (total_items - na_items) * 100, 1) if (total_items - na_items) > 0 else 0
    return render_template('audit_detail.html', a=a, can_close=can_close, close_msg=close_msg,
        total_items=total_items, yes_items=yes_items, no_items=no_items,
        na_items=na_items, compliance_pct=compliance_pct)

@app.route('/audit/<aid>/start', methods=['POST'])
def start_audit(aid):
    a = AuditSchedule.query.get_or_404(aid)
    a.status = 'In Progress'
    a.actual_date = date.today().isoformat()
    a.opening_meeting_date = request.form.get('opening_meeting_date', date.today().isoformat())
    # Auto-load checklist template for this department
    dept_name = a.department.name if a.department else ''
    template  = CHECKLIST_TEMPLATES.get(dept_name, [])
    for cat, ref, question in template:
        item = ChecklistItem(audit_id=aid, category=cat, reference=ref, question=question)
        db.session.add(item)
    db.session.commit()
    flash(f'✓ Audit started. {len(template)} checklist items loaded.', 'success')
    return redirect(url_for('audit_detail', aid=aid))

@app.route('/audit/<aid>/update', methods=['POST'])
def update_audit(aid):
    a = AuditSchedule.query.get_or_404(aid)
    f = request.form
    a.closing_meeting_date = f.get('closing_meeting_date', a.closing_meeting_date)
    a.final_remarks        = f.get('final_remarks', a.final_remarks)
    db.session.commit()
    flash('✓ Audit updated.', 'success')
    return redirect(url_for('audit_detail', aid=aid))

@app.route('/audit/<aid>/close', methods=['POST'])
def close_audit(aid):
    a = AuditSchedule.query.get_or_404(aid)
    can_close, msg = audit_can_close(a)
    if not can_close:
        flash(f'✗ Cannot close audit: {msg}', 'error')
        return redirect(url_for('audit_detail', aid=aid))
    a.status       = 'Completed'
    a.closure_date = date.today().isoformat()
    a.closed_by    = request.form.get('closed_by','')
    a.final_remarks = request.form.get('final_remarks', a.final_remarks)
    db.session.commit()
    flash(f'✓ Audit {aid} closed successfully.', 'success')
    return redirect(url_for('audit_detail', aid=aid))

# ─── Checklist ────────────────────────────────────────────────────────────────
@app.route('/audit/<aid>/checklist', methods=['GET','POST'])
def checklist(aid):
    a = AuditSchedule.query.get_or_404(aid)
    if request.method == 'POST':
        f = request.form
        for item in a.checklist_items:
            item.response = f.get(f'resp_{item.id}', item.response or '')
            item.comment  = f.get(f'comment_{item.id}', item.comment or '')
        db.session.commit()
        flash('✓ Checklist saved.', 'success')
        return redirect(url_for('audit_detail', aid=aid))
    categories = sorted(set(i.category for i in a.checklist_items))
    return render_template('checklist.html', a=a, categories=categories)

@app.route('/audit/<aid>/checklist/add', methods=['POST'])
def add_checklist_item(aid):
    f = request.form
    item = ChecklistItem(audit_id=aid,
        category=f['category'], reference=f.get('reference',''),
        question=f['question'])
    db.session.add(item)
    db.session.commit()
    flash('✓ Checklist item added.', 'success')
    return redirect(url_for('checklist', aid=aid))

# ─── Findings ─────────────────────────────────────────────────────────────────
@app.route('/audit/<aid>/findings')
def findings(aid):
    a = AuditSchedule.query.get_or_404(aid)
    return render_template('findings.html', a=a)

@app.route('/audit/<aid>/finding/new', methods=['GET','POST'])
def new_finding(aid):
    a = AuditSchedule.query.get_or_404(aid)
    if request.method == 'POST':
        f   = request.form
        fid = new_id('FND')
        finding = AuditFinding(
            id=fid, audit_id=aid,
            description=f['description'],
            category=f['category'],
            severity=f['severity'],
            root_cause=f.get('root_cause',''),
            evidence=f.get('evidence',''),
            requirement_ref=f.get('requirement_ref',''),
            status='Open'
        )
        db.session.add(finding)
        db.session.flush()

        # Auto-create hazard for Major findings
        hid = None
        if f['severity'] == 'Major':
            hid = new_id('HAZ')
            h = Hazard(id=hid, source='Audit', linked_report_id=fid,
                       department_id=a.department_id,
                       classification=f['category'],
                       generic_hazard=f['description'][:100],
                       specific_components=f['description'],
                       consequences=f.get('root_cause',''),
                       initial_likelihood=3, initial_severity='B',
                       initial_risk_index='3B', initial_tolerance='INTOLERABLE',
                       status='Open', owner=a.lead_auditor)
            db.session.add(h)
            finding.hazard_id = hid

        # Auto-create corrective action
        act_id = new_id('ACT')
        action = AuditAction(
            id=act_id, finding_id=fid, hazard_id=hid,
            description=f.get('initial_action', f'Address finding: {f["description"][:100]}'),
            owner=f.get('action_owner', a.lead_auditor),
            due_date=f.get('due_date',''),
            priority='High' if f['severity']=='Major' else 'Medium' if f['severity']=='Minor' else 'Low',
            status='Open'
        )
        db.session.add(action)
        finding.status = 'Action Raised'
        db.session.commit()
        flash(f'✓ Finding {fid} created. Action {act_id} auto-generated.' +
              (f' Hazard {hid} created.' if hid else ''), 'success')
        return redirect(url_for('audit_detail', aid=aid))
    checklist_items = [i for i in a.checklist_items if i.response == 'No']
    return render_template('finding_form.html', a=a, checklist_items=checklist_items)

@app.route('/finding/<fid>')
def finding_detail(fid):
    f = AuditFinding.query.get_or_404(fid)
    return render_template('finding_detail.html', f=f)

@app.route('/finding/<fid>/update', methods=['POST'])
def update_finding(fid):
    finding = AuditFinding.query.get_or_404(fid)
    f = request.form
    finding.status    = f.get('status', finding.status)
    finding.root_cause = f.get('root_cause', finding.root_cause)
    finding.evidence  = f.get('evidence', finding.evidence)
    db.session.commit()
    flash('✓ Finding updated.', 'success')
    return redirect(url_for('finding_detail', fid=fid))

# ─── Actions ──────────────────────────────────────────────────────────────────
@app.route('/actions')
def actions():
    check_overdue()
    status_f   = request.args.get('status','')
    priority_f = request.args.get('priority','')
    q = AuditAction.query
    if status_f:   q = q.filter_by(status=status_f)
    if priority_f: q = q.filter_by(priority=priority_f)
    all_actions = q.order_by(AuditAction.created_at.desc()).all()
    open_c    = AuditAction.query.filter_by(status='Open').count()
    inprog    = AuditAction.query.filter_by(status='In Progress').count()
    overdue   = AuditAction.query.filter_by(status='Overdue').count()
    closed    = AuditAction.query.filter_by(status='Closed').count()
    return render_template('actions.html', actions=all_actions,
        open_c=open_c, inprog=inprog, overdue=overdue, closed=closed,
        status_f=status_f, priority_f=priority_f)

@app.route('/action/<acid>/update', methods=['POST'])
def update_action(acid):
    a = AuditAction.query.get_or_404(acid)
    f = request.form
    a.status               = f.get('status', a.status)
    a.owner                = f.get('owner', a.owner)
    a.due_date             = f.get('due_date', a.due_date)
    a.priority             = f.get('priority', a.priority)
    a.completion_evidence  = f.get('completion_evidence', a.completion_evidence)
    a.effectiveness_review = f.get('effectiveness_review') or a.effectiveness_review
    a.effectiveness_notes  = f.get('effectiveness_notes', a.effectiveness_notes)
    a.verified_by          = f.get('verified_by', a.verified_by)
    if a.status == 'Closed':
        a.completion_date   = date.today().isoformat()
        a.verification_date = date.today().isoformat()
        # Update finding status
        finding = AuditFinding.query.get(a.finding_id)
        if finding and a.effectiveness_review == 'Effective':
            finding.status = 'Verified'
        elif finding and a.effectiveness_review == 'Ineffective':
            a.reopened     = True
            a.reopen_reason = f.get('reopen_reason','Ineffective — action to be revised.')
            a.status       = 'Open'
            flash('⚠ Action marked Ineffective — re-opened for revision.', 'error')
    db.session.commit()
    flash('✓ Action updated.', 'success')
    return redirect(url_for('actions'))

# ─── Hazard Log (read-only view) ──────────────────────────────────────────────
@app.route('/hazards')
def hazards():
    all_h = Hazard.query.order_by(Hazard.created_at.desc()).all()
    return render_template('hazards.html', hazards=all_h)

# ─── Init ─────────────────────────────────────────────────────────────────────
with app.app_context():
    db.create_all()
    seed()

if __name__ == '__main__':
    app.run(debug=True)
