from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, Department, HazardReport, ASRReport, Hazard, Risk, Control, Action, Audit, Finding, Investigation, MOC, SPIIndicator, SPIData, SafetyBulletin, Training, AuditPlan, AuditSchedule, AuditChecklist, AuditFinding, AuditAction, SafetyPolicy, SafetyRole, SafetyPersonnel, ERPlan, SMSDocument, DocumentLink, RiskOccurrence, RiskAction, RAChecklistItem, RiskAssessment, RARow, RAMitigation, RAReview
from datetime import datetime, date
import os, uuid

app = Flask(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', f'sqlite:///{os.path.join(BASE_DIR, "sms.db")}')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'jav-sms-2024')

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

def check_overdue_actions():
    today = date.today().isoformat()
    actions = Action.query.filter(Action.status.in_(['Open','In Progress'])).all()
    for a in actions:
        if a.due_date and a.due_date < today:
            a.status = 'Overdue'
    db.session.commit()

@app.context_processor
def inject_globals():
    depts = Department.query.all()
    now   = datetime.utcnow()
    # Count overdue actions for nav badge
    overdue = Action.query.filter_by(status='Overdue').count()
    return dict(all_departments=depts, now=now, get_tolerance=get_tolerance,
                nav_overdue=overdue)

# ─── SEED DATABASE ────────────────────────────────────────────────────────────
def seed():
    if Department.query.first(): return

    depts = [
        Department(id=1, code='FO', name='Flight Operations',       color='#1e40af'),
        Department(id=2, code='ME', name='Maintenance / Engineering',color='#065f46'),
        Department(id=3, code='GO', name='Ground Operations',        color='#92400e'),
        Department(id=4, code='CC', name='Cabin Crew',               color='#6b21a8'),
        Department(id=5, code='SD', name='Safety Department',        color='#be123c'),
    ]
    db.session.add_all(depts)

    spis = [
        SPIIndicator(code='UA',      name='Unstable Approach',           department_ids='1',   unit='/1000 flights', spt_target=9.40,  alert_l1=13.51, alert_l2=17.13),
        SPIIndicator(code='TCAS',    name='TCAS RA Encounter',           department_ids='1',   unit='/1000 flights', spt_target=3.02,  alert_l1=5.98,  alert_l2=8.78),
        SPIIndicator(code='GA',      name='Go-Around',                   department_ids='1',   unit='/1000 flights', spt_target=14.58, alert_l1=18.83, alert_l2=22.32),
        SPIIndicator(code='BS',      name='Bird Strike',                 department_ids='1,3', unit='/1000 flights', spt_target=2.15,  alert_l1=5.07,  alert_l2=7.87),
        SPIIndicator(code='RED',     name='Runway Excursion/Deviation',  department_ids='1,3', unit='/1000 flights', spt_target=1.38,  alert_l1=4.07,  alert_l2=6.70),
        SPIIndicator(code='RAMP',    name='Ramp Incidents',              department_ids='3',   unit='/1000 turns',   spt_target=5.00,  alert_l1=10.0,  alert_l2=15.0),
        SPIIndicator(code='CAB-INC', name='Cabin Safety Incidents',      department_ids='4',   unit='/1000 flights', spt_target=3.00,  alert_l1=6.0,   alert_l2=9.0),
        SPIIndicator(code='ME-INJ',  name='Maintenance Injury Rate',     department_ids='2',   unit='/100 staff',    spt_target=2.00,  alert_l1=4.0,   alert_l2=6.0),
    ]
    db.session.add_all(spis)

    # Sample hazard
    h1 = Hazard(id='HAZ-2024-DEMO1', source='ASR', linked_report_id='ASR-2024-DEMO1',
                department_id=1, classification='Environmental',
                type_of_activity='Flight Operations',
                generic_hazard='Weather / Low Visibility',
                specific_components='Bad visibility and LVP in progress during approach to AMM',
                consequences='Diversion, crew workload, potential runway excursion',
                status='Open', owner='Flight Operations Manager',
                created_at=datetime(2024,4,30))
    db.session.add(h1)
    db.session.flush()

    r1 = Risk(id='RSK-2024-DEMO1', hazard_id=h1.id,
              description='Aircraft unable to land due to below-minima visibility leading to diversion',
              initial_likelihood=4, initial_severity='B', initial_risk_index='4B', initial_tolerance='INTOLERABLE',
              residual_likelihood=2, residual_severity='C', residual_risk_index='2C', residual_tolerance='TOLERABLE')
    db.session.add(r1)
    db.session.flush()

    c1 = Control(id='CTL-2024-DEMO1', risk_id=r1.id, control_type='Preventive',
                 description='Low Visibility Procedure (LVP) — mandatory crew briefing before dispatch',
                 owner='Flight Operations Manager', effectiveness='Effective', review_date='2025-03-01')
    c2 = Control(id='CTL-2024-DEMO2', risk_id=r1.id, control_type='Detective',
                 description='Real-time ATIS monitoring and alternate aerodrome pre-planning',
                 owner='Flight Dispatch', effectiveness='Partially Effective', review_date='2025-03-01')
    db.session.add_all([c1, c2])

    a1 = Action(id='ACT-2024-DEMO1', source='ASR', hazard_id=h1.id,
                linked_ref_id='ASR-2024-DEMO1',
                description='Update LVP crew briefing checklist to include alternate fuel requirements',
                owner='Flight Operations Manager', due_date='2024-06-30',
                priority='High', status='Closed',
                effectiveness_review='Checklist updated and distributed. Effective.')
    db.session.add(a1)

    h2 = Hazard(id='HAZ-2024-DEMO2', source='Hazard Report', linked_report_id='HR-2024-DEMO2',
                department_id=3, classification='Operational',
                type_of_activity='Ground Operations',
                generic_hazard='FOD on Taxiway',
                specific_components='Debris found near Gate B3 after heavy rain',
                consequences='Engine ingestion, tyre damage, aircraft damage',
                status='Open', owner='Ground Operations Manager',
                created_at=datetime(2024,4,15))
    db.session.add(h2)
    db.session.flush()

    r2 = Risk(id='RSK-2024-DEMO2', hazard_id=h2.id,
              description='FOD ingested into engine during taxi causing engine damage',
              initial_likelihood=3, initial_severity='B', initial_risk_index='3B', initial_tolerance='INTOLERABLE',
              residual_likelihood=2, residual_severity='D', residual_risk_index='2D', residual_tolerance='ACCEPTABLE')
    db.session.add(r2)
    db.session.flush()

    c3 = Control(id='CTL-2024-DEMO3', risk_id=r2.id, control_type='Preventive',
                 description='Post-rain mandatory FOD walk before aircraft movement',
                 owner='Ramp Supervisor', effectiveness='Effective', review_date='2025-01-01')
    db.session.add(c3)

    a2 = Action(id='ACT-2024-DEMO2', source='Hazard Report', hazard_id=h2.id,
                linked_ref_id='HR-2024-DEMO2',
                description='Implement post-rain FOD inspection protocol with supervisor sign-off',
                owner='Ground Operations Manager', due_date='2024-05-15',
                priority='High', status='Closed',
                effectiveness_review='Protocol implemented. FOD incidents reduced.')
    db.session.add(a2)

    # Sample Audit
    aud = Audit(id='AUD-2024-DEMO1', title='Annual Flight Operations Safety Audit',
                audit_type='Internal', department_id=1,
                planned_date='2024-03-01', actual_date='2024-03-05',
                lead_auditor='Safety Manager', status='Closed',
                summary='Overall compliance satisfactory. Two minor findings identified.')
    db.session.add(aud)
    db.session.flush()

    f1 = Finding(id='FND-2024-DEMO1', audit_id=aud.id,
                 description='Crew briefing records for LVP operations not consistently filed',
                 severity='Minor', root_cause='No standardized filing procedure in place',
                 corrective_action='Implement digital briefing record system', status='Closed')
    db.session.add(f1)

    # Sample Investigation
    inv = Investigation(id='INV-2024-DEMO1', title='Diversion to ESB due to Low Visibility',
                        linked_report_id='ASR-2024-DEMO1', hazard_id=h1.id,
                        department_id=1, date_of_occurrence='2024-04-30',
                        investigator='Safety Officer',
                        description='B737-300 JY-JAX diverted to Esenboga due to visibility below minima at AMM',
                        why1='Aircraft could not land at destination',
                        why2='Visibility was below CAT I minima',
                        why3='Unexpected weather deterioration during approach',
                        why4='Weather forecast did not predict rapid deterioration',
                        why5='Insufficient meteorological data resolution for the area',
                        root_cause='Inadequate weather forecast resolution leading to unexpected visibility deterioration',
                        human_factors='Crew followed correct procedures. No human error identified.',
                        technical_factors='None identified.',
                        organizational_factors='Weather briefing process relies on third-party provider.',
                        environmental_factors='Rapid weather system movement across OJAI FIR.',
                        recommendations='Review weather data provider contract. Evaluate upgrade to higher-resolution forecast model.',
                        status='Closed')
    db.session.add(inv)

    # Sample MOC
    moc = MOC(id='MOC-2024-DEMO1', title='Implementation of Electronic Flight Bag (EFB)',
              description='Replace paper charts and manuals with EFB tablets for all flight crew',
              department_id=1, change_type='Equipment',
              initiator='Flight Operations Manager',
              planned_date='2024-07-01',
              pre_change_risk='Risk of crew unfamiliarity with new system. Training required.',
              approval_status='Approved', approved_by='Accountable Manager',
              implementation_status='Completed',
              post_change_review='EFB successfully implemented. No safety issues reported post-implementation.')
    db.session.add(moc)

    # Sample bulletin
    b1 = SafetyBulletin(id='BUL-2024-DEMO1', title='Low Visibility Operations — Crew Reminder',
                        bulletin_type='Alert', issued_by='Safety Department',
                        department_ids='1,4',
                        content='All crew are reminded of LVP requirements at OJAI. Ensure alternate fuel is loaded when forecast visibility is below 800m RVR.')
    db.session.add(b1)

    # Sample training
    t1 = Training(employee_name='Khaled Al Sabbagh', department_id=1,
                  training_type='CRM — Crew Resource Management',
                  training_date='2024-01-15', expiry_date='2026-01-15', status='Completed')
    t2 = Training(employee_name='Mohammad Rahall', department_id=1,
                  training_type='SMS Awareness Training',
                  training_date='2024-02-10', expiry_date='2026-02-10', status='Completed')
    db.session.add_all([t1, t2])

    # SPI data
    spi_entries = [
        SPIData(spi_id=1, year=2025, month=1, events=6,  flights=175, rate=11.43),
        SPIData(spi_id=1, year=2025, month=2, events=3,  flights=168, rate=5.95),
        SPIData(spi_id=1, year=2025, month=3, events=6,  flights=182, rate=10.99),
        SPIData(spi_id=1, year=2025, month=4, events=3,  flights=179, rate=5.59),
        SPIData(spi_id=2, year=2025, month=1, events=1,  flights=175, rate=5.71),
        SPIData(spi_id=2, year=2025, month=2, events=1,  flights=168, rate=5.95),
        SPIData(spi_id=2, year=2025, month=3, events=0,  flights=182, rate=0.0),
        SPIData(spi_id=2, year=2025, month=4, events=1,  flights=179, rate=5.59),
        SPIData(spi_id=4, year=2025, month=1, events=0,  flights=175, rate=0.0),
        SPIData(spi_id=4, year=2025, month=2, events=1,  flights=168, rate=5.95),
        SPIData(spi_id=4, year=2025, month=3, events=0,  flights=182, rate=0.0),
        SPIData(spi_id=4, year=2025, month=4, events=0,  flights=179, rate=0.0),
    ]
    db.session.add_all(spi_entries)
    db.session.commit()
    print('✅ Database seeded.')
    seed_traceability()

# ═══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Dashboard ────────────────────────────────────────────────────────────────
@app.route('/')
def dashboard():
    check_overdue_actions()
    total_haz   = Hazard.query.count()
    open_haz    = Hazard.query.filter_by(status='Open').count()
    intol       = Risk.query.filter_by(initial_tolerance='INTOLERABLE').count()
    # Unified action count — all sources
    open_act    = Action.query.filter(Action.status.in_(['Open','In Progress'])).count()
    overdue_act = Action.query.filter_by(status='Overdue').count()
    # Audit-specific actions
    audit_open  = AuditAction.query.filter(AuditAction.status.in_(['Open','In Progress'])).count()
    audit_over  = AuditAction.query.filter_by(status='Overdue').count()
    total_open_act = open_act + audit_open
    total_over_act = overdue_act + audit_over
    asr_cnt     = ASRReport.query.count()
    audit_cnt   = AuditSchedule.query.count()
    moc_cnt     = MOC.query.count()
    inv_cnt     = Investigation.query.count()
    doc_cnt     = SMSDocument.query.filter_by(status='Approved').count()
    spi_alerts  = 0
    for ind in SPIIndicator.query.all():
        recent = SPIData.query.filter_by(spi_id=ind.id).order_by(SPIData.year.desc(), SPIData.month.desc()).first()
        if recent and recent.rate >= ind.alert_l1:
            spi_alerts += 1
    recent_haz  = Hazard.query.order_by(Hazard.created_at.desc()).limit(6).all()
    recent_act  = Action.query.filter(Action.status != 'Closed').order_by(Action.created_at.desc()).limit(5).all()
    return render_template('dashboard.html',
        total_haz=total_haz, open_haz=open_haz, intol=intol,
        open_act=total_open_act, overdue_act=total_over_act,
        asr_cnt=asr_cnt, audit_cnt=audit_cnt, moc_cnt=moc_cnt,
        inv_cnt=inv_cnt, doc_cnt=doc_cnt, spi_alerts=spi_alerts,
        recent_haz=recent_haz, recent_act=recent_act)

# ─── Hazard Report ────────────────────────────────────────────────────────────
@app.route('/hazard-report', methods=['GET','POST'])
def hazard_report():
    if request.method == 'POST':
        f  = request.form
        li = int(f['likelihood'])
        se = f['severity']
        ri = f'{li}{se}'
        hid = new_id('HAZ')
        rid = new_id('HR')
        h = Hazard(id=hid, source='Hazard Report', linked_report_id=rid,
                   department_id=int(f['department_id']),
                   classification=f.get('classification','Operational'),
                   type_of_activity=Department.query.get(int(f['department_id'])).name,
                   generic_hazard=f.get('generic_hazard','To Be Classified'),
                   specific_components=f['hazard_description'],
                   consequences=f.get('consequences','To Be Assessed'),
                   status='Open', owner=None)
        db.session.add(h)
        db.session.flush()
        r = Risk(id=new_id('RSK'), hazard_id=hid, description=f['hazard_description'],
                 initial_likelihood=li, initial_severity=se,
                 initial_risk_index=ri, initial_tolerance=get_tolerance(ri))
        db.session.add(r)
        rep = HazardReport(id=rid, department_id=int(f['department_id']),
                           location=f['location'], date=f['date'],
                           description=f['hazard_description'],
                           immediate_action=f.get('immediate_action',''),
                           suggested_mitigation=f.get('suggested_mitigation',''),
                           severity=se, likelihood=li, risk_index=ri,
                           reporter=f.get('reporter','Anonymous') or 'Anonymous',
                           hazard_id=hid)
        db.session.add(rep)
        db.session.commit()
        # Set status to Under Assessment and redirect to guided RA wizard
        h.status = 'Under Assessment'
        db.session.commit()
        flash(f'✓ Hazard {hid} created (Risk: {ri}). Complete the Risk Assessment to continue.', 'success')
        return redirect(url_for('ra_wizard_start', hid=hid))
    return render_template('hazard_report.html')

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
        flash(f'✓ ASR {aid} submitted. Complete the Risk Assessment for hazard {hid}.', 'success')
        return redirect(url_for('ra_wizard_start', hid=hid))
    return render_template('asr.html')

# ─── Hazard Log ───────────────────────────────────────────────────────────────
@app.route('/hazard-log')
def hazard_log():
    dept_f = request.args.get('dept','')
    stat_f = request.args.get('status','')
    cls_f  = request.args.get('classification','')
    q = Hazard.query
    if dept_f: q = q.filter_by(department_id=int(dept_f))
    if stat_f: q = q.filter_by(status=stat_f)
    if cls_f:  q = q.filter_by(classification=cls_f)
    hazards = q.order_by(Hazard.created_at.desc()).all()
    return render_template('hazard_log.html', hazards=hazards,
        dept_f=dept_f, stat_f=stat_f, cls_f=cls_f)

@app.route('/hazard-log/<hid>')
def hazard_detail(hid):
    h = Hazard.query.get_or_404(hid)
    return render_template('hazard_detail.html', h=h)

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
def actions():
    check_overdue_actions()
    stat_f = request.args.get('status','')
    pri_f  = request.args.get('priority','')
    src_f  = request.args.get('source','')
    q = Action.query
    if stat_f: q = q.filter_by(status=stat_f)
    if pri_f:  q = q.filter_by(priority=pri_f)
    if src_f:  q = q.filter_by(source=src_f)
    all_actions = q.order_by(Action.created_at.desc()).all()
    overdue = Action.query.filter_by(status='Overdue').count()
    open_c  = Action.query.filter_by(status='Open').count()
    inprog  = Action.query.filter_by(status='In Progress').count()
    closed  = Action.query.filter_by(status='Closed').count()
    return render_template('actions.html', actions=all_actions,
        overdue=overdue, open_c=open_c, inprog=inprog, closed=closed,
        stat_f=stat_f, pri_f=pri_f, src_f=src_f)

@app.route('/actions/new', methods=['GET','POST'])
def new_action():
    if request.method == 'POST':
        f = request.form
        a = Action(id=new_id('ACT'),
                   source=f['source'],
                   hazard_id=f.get('hazard_id') or None,
                   linked_ref_id=f.get('linked_ref_id',''),
                   description=f['description'],
                   owner=f['owner'],
                   due_date=f['due_date'],
                   priority=f['priority'],
                   status='Open')
        db.session.add(a)
        db.session.commit()
        flash(f'✓ Action {a.id} created.', 'success')
        return redirect(url_for('actions'))
    hazards = Hazard.query.filter_by(status='Open').all()
    return render_template('action_form.html', hazards=hazards)

@app.route('/actions/<aid>/update', methods=['POST'])
def update_action(aid):
    a = Action.query.get_or_404(aid)
    f = request.form
    a.status = f.get('status', a.status)
    a.owner  = f.get('owner', a.owner)
    a.due_date = f.get('due_date', a.due_date)
    a.priority = f.get('priority', a.priority)
    a.effectiveness_review = f.get('effectiveness_review', a.effectiveness_review)
    if a.status == 'Closed': a.closed_date = date.today().isoformat()
    db.session.commit()
    flash('✓ Action updated.', 'success')
    return redirect(url_for('actions'))

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
def investigations():
    all_inv = Investigation.query.order_by(Investigation.created_at.desc()).all()
    return render_template('investigations.html', investigations=all_inv)

@app.route('/investigations/new', methods=['GET','POST'])
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
    return render_template('investigation_form.html', hazards=hazards)

@app.route('/investigations/<iid>')
def investigation_detail(iid):
    inv = Investigation.query.get_or_404(iid)
    return render_template('investigation_detail.html', inv=inv)

# ─── MOC ─────────────────────────────────────────────────────────────────────
@app.route('/moc')
def moc_list():
    all_moc = MOC.query.order_by(MOC.created_at.desc()).all()
    return render_template('moc.html', mocs=all_moc)

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
    return render_template('moc_form.html')

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
@app.route('/spi', methods=['GET','POST'])
def spi():
    if request.method == 'POST':
        f = request.form
        spi_id  = int(f['spi_id'])
        events  = int(f['events'])
        flights = int(f['flights'])
        rate    = round(events / flights * 1000, 4) if flights > 0 else 0
        entry   = SPIData(spi_id=spi_id, year=int(f['year']),
                          month=int(f['month']), events=events,
                          flights=flights, rate=rate)
        db.session.add(entry)
        db.session.commit()
        flash('✓ SPI data logged.', 'success')
        return redirect(url_for('spi'))

    dept_f     = request.args.get('dept','')
    cur_year   = datetime.now().year
    indicators = SPIIndicator.query.all()
    if dept_f:
        indicators = [i for i in indicators if dept_f in i.department_ids.split(',')]

    MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    table  = []
    for ind in indicators:
        month_rates = {}
        for d in SPIData.query.filter_by(spi_id=ind.id, year=cur_year).all():
            month_rates[d.month] = d.rate
        ytd = round(sum(month_rates.values()) / len(month_rates), 2) if month_rates else 0
        if   ytd >= ind.alert_l2:   status = ('🔴 CRITICAL', '#dc2626')
        elif ytd >= ind.alert_l1:   status = ('🟡 WARNING',  '#d97706')
        elif ytd > ind.spt_target:  status = ('🟠 WATCH',    '#ea580c')
        else:                       status = ('🟢 OK',       '#16a34a')
        dept_codes = []
        for did in ind.department_ids.split(','):
            d = Department.query.get(int(did))
            if d: dept_codes.append(d.code)
        table.append(dict(ind=ind, month_rates=month_rates, ytd=ytd,
                          status=status, depts=', '.join(dept_codes)))

    return render_template('spi.html', table=table, MONTHS=MONTHS,
        indicators=SPIIndicator.query.all(), dept_f=dept_f, cur_year=cur_year,
        enumerate=enumerate)

# ─── Safety Promotion ─────────────────────────────────────────────────────────
@app.route('/safety-promotion')
def safety_promotion():
    bulletins = SafetyBulletin.query.order_by(SafetyBulletin.created_at.desc()).all()
    trainings = Training.query.order_by(Training.training_date.desc()).all()
    completed = Training.query.filter_by(status='Completed').count()
    overdue_t = Training.query.filter_by(status='Overdue').count()
    return render_template('safety_promotion.html',
        bulletins=bulletins, trainings=trainings,
        completed=completed, overdue_t=overdue_t)

@app.route('/safety-promotion/bulletin/new', methods=['POST'])
def new_bulletin():
    f = request.form
    b = SafetyBulletin(id=new_id('BUL'),
        title=f['title'], bulletin_type=f['bulletin_type'],
        content=f['content'], issued_by=f['issued_by'],
        department_ids=f.get('department_ids','all'))
    db.session.add(b)
    db.session.commit()
    flash('✓ Bulletin published.', 'success')
    return redirect(url_for('safety_promotion'))

@app.route('/safety-promotion/training/new', methods=['POST'])
def new_training():
    f = request.form
    t = Training(employee_name=f['employee_name'],
                 department_id=int(f['department_id']),
                 training_type=f['training_type'],
                 training_date=f['training_date'],
                 expiry_date=f.get('expiry_date',''),
                 status=f.get('status','Completed'),
                 notes=f.get('notes',''))
    db.session.add(t)
    db.session.commit()
    flash('✓ Training record added.', 'success')
    return redirect(url_for('safety_promotion'))

# ─── Risk Matrix Reference ────────────────────────────────────────────────────
@app.route('/risk-matrix')
def risk_matrix():
    return render_template('risk_matrix.html')


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
@app.route('/audit-plans')
def audit_plans():
    year_f = request.args.get('year', str(datetime.now().year))
    plans  = AuditPlan.query.filter_by(year=int(year_f)).order_by(AuditPlan.created_at).all()
    years  = list(range(datetime.now().year - 1, datetime.now().year + 3))
    return render_template('audit_plan_list.html', plans=plans,
                           year_f=int(year_f), years=years)

@app.route('/audit-plans/new', methods=['GET', 'POST'])
def new_audit_plan():
    if request.method == 'POST':
        f   = request.form
        pid = new_id('PLAN')
        p   = AuditPlan(
            id=pid,
            year=int(f['year']),
            department_id=int(f['department_id']),
            audit_type=f['audit_type'],
            frequency=f['frequency'],
            responsible_manager=f['responsible_manager'],
            scope=f.get('scope', ''),
            objectives=f.get('objectives', ''),
            status='Active'
        )
        db.session.add(p)
        db.session.commit()
        flash(f'✓ Audit Plan {pid} created for {f["year"]}.', 'success')
        return redirect(url_for('audit_plans'))
    years = list(range(datetime.now().year, datetime.now().year + 3))
    return render_template('audit_plan_form.html', years=years)


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

    return render_template('audit_schedule.html', schedules=schedules,
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
    return render_template('audit_schedule_form.html')


# ─── AUDIT EXECUTION ─────────────────────────────────────────────────────────
@app.route('/audit-schedule/<sid>')
def audit_execution(sid):
    s = AuditSchedule.query.get_or_404(sid)
    # Group checklist by category
    checklist = {}
    for item in sorted(s.checklist_items, key=lambda x: x.sequence):
        checklist.setdefault(item.category, []).append(item)
    total   = len(s.checklist_items)
    done    = sum(1 for i in s.checklist_items if i.response)
    nc      = sum(1 for i in s.checklist_items if i.response == 'No')
    # Closure eligibility
    all_findings_actioned = all(len(f.actions) > 0 for f in s.findings) if s.findings else True
    all_actions_closed    = all(
        all(a.status == 'Closed' for a in f.actions) for f in s.findings
    ) if s.findings else True
    all_verified = all(
        all(a.effectiveness in ('Effective', 'Partially Effective') for a in f.actions)
        for f in s.findings
    ) if s.findings else True
    can_close = all_findings_actioned and all_actions_closed and all_verified
    return render_template('audit_execution.html',
        s=s, checklist=checklist, total=total, done=done, nc=nc,
        can_close=can_close,
        all_findings_actioned=all_findings_actioned,
        all_actions_closed=all_actions_closed,
        all_verified=all_verified)

@app.route('/audit-schedule/<sid>/start', methods=['POST'])
def start_audit(sid):
    s = AuditSchedule.query.get_or_404(sid)
    s.status       = 'In Progress'
    s.actual_date  = date.today().isoformat()
    s.opening_meeting = request.form.get('opening_meeting', date.today().isoformat())
    db.session.commit()
    flash('✓ Audit started. Checklist is now active.', 'success')
    return redirect(url_for('audit_execution', sid=sid))

@app.route('/audit-schedule/<sid>/checklist', methods=['POST'])
def save_checklist(sid):
    s = AuditSchedule.query.get_or_404(sid)
    for item in s.checklist_items:
        item.response = request.form.get(f'resp_{item.id}', '')
        item.comment  = request.form.get(f'comment_{item.id}', '')
        item.evidence = request.form.get(f'evidence_{item.id}', '')
    db.session.commit()
    flash('✓ Checklist saved.', 'success')
    return redirect(url_for('audit_execution', sid=sid))

@app.route('/audit-schedule/<sid>/close', methods=['POST'])
def close_audit(sid):
    s = AuditSchedule.query.get_or_404(sid)
    # Validate closure conditions
    if s.findings:
        for finding in s.findings:
            if not finding.actions:
                flash(f'✗ Cannot close: Finding {finding.id} has no corrective action.', 'error')
                return redirect(url_for('audit_execution', sid=sid))
            for a in finding.actions:
                if a.status != 'Closed':
                    flash(f'✗ Cannot close: Action {a.id} is not yet closed.', 'error')
                    return redirect(url_for('audit_execution', sid=sid))
                if not a.effectiveness:
                    flash(f'✗ Cannot close: Action {a.id} has no effectiveness review.', 'error')
                    return redirect(url_for('audit_execution', sid=sid))
    s.status        = 'Completed'
    s.closure_date  = date.today().isoformat()
    s.closed_by     = request.form.get('closed_by', 'Safety Manager')
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

    msg = f'✓ Finding {finding_ref} recorded. Action {aid} created.'
    if hid: msg += f' Hazard {hid} created in SMS Hazard Log.'
    flash(msg, 'success')
    return redirect(url_for('audit_execution', sid=sid))


# ─── FINDING DETAIL ───────────────────────────────────────────────────────────
@app.route('/audit-findings/<fid>')
def finding_detail(fid):
    finding = AuditFinding.query.get_or_404(fid)
    return render_template('finding_detail.html', finding=finding)


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
    return render_template('audit_actions.html',
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

    return render_template('audit_dashboard.html',
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
def safety_policy():
    active  = SafetyPolicy.query.filter_by(status='Active').first()
    history = SafetyPolicy.query.filter_by(status='Archived').order_by(
              SafetyPolicy.version_num.desc()).all()
    drafts  = SafetyPolicy.query.filter_by(status='Draft').all()
    return render_template('safety_policy.html',
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
    return render_template('safety_policy_form.html', next_ver=next_ver, latest=latest)

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
def safety_roles():
    roles = SafetyRole.query.filter_by(active=True).order_by(SafetyRole.role_type).all()
    return render_template('safety_roles.html', roles=roles)

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
    return render_template('safety_role_form.html')

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
def safety_personnel():
    personnel = SafetyPersonnel.query.filter_by(active=True).order_by(
                SafetyPersonnel.sms_role).all()
    return render_template('safety_personnel.html', personnel=personnel)

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
    return render_template('safety_personnel_form.html')

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
    return render_template('erp.html', plans=plans, archived=archived)

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
    return render_template('erp_form.html')

@app.route('/erp/<eid>')
def erp_detail(eid):
    e = ERPlan.query.get_or_404(eid)
    return render_template('erp_detail.html', e=e)

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
    return render_template('documents.html', docs=docs, doc_types=doc_types,
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
    return render_template('document_form.html', doc_types=doc_types)

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
    return render_template('document_detail.html', doc=doc, versions=versions)

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
    return render_template('document_trace.html', doc=doc, trace=trace, versions=versions)

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
    return render_template('hazard_documents.html',
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
    return render_template('audit_documents.html',
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

    return render_template('traceability.html',
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
    if DocumentLink.query.first():
        return
    # Only run if we have demo data
    demo_haz  = Hazard.query.get('HAZ-2024-DEMO1')
    demo_haz2 = Hazard.query.get('HAZ-2024-DEMO2')
    if not demo_haz:
        return

    dept_fo = Department.query.filter_by(code='FO').first()
    dept_go = Department.query.filter_by(code='GO').first()
    if not dept_fo:
        return

    year = 2024
    # Create demo RA document for HAZ-2024-DEMO1
    ra_id = f"RA-FO-{year}-001-REV0"
    if not SMSDocument.query.get(ra_id):
        ra = SMSDocument(
            id=ra_id, doc_type='RA',
            department_id=dept_fo.id if dept_fo else 1,
            title='Low Visibility Operations — Risk Assessment',
            description='Risk assessment for LVP operations at OJAI',
            content='Risk: Diversion due to visibility below minima.\nLikelihood: 4 (Occasional)\nSeverity: B (Hazardous)\nRisk Index: 4B — INTOLERABLE\nControls: LVP procedures, alternate planning, real-time ATIS monitoring.',
            version='REV0', version_num=0, seq_num=1,
            status='Approved',
            created_by='Safety Manager',
            approved_by='Accountable Manager',
            effective_date='2024-01-15',
            review_due='2025-01-15',
            change_summary='Initial issue'
        )
        db.session.add(ra)

    # Create demo SOP
    sop_id = f"SOP-FO-{year}-001-REV0"
    if not SMSDocument.query.get(sop_id):
        sop = SMSDocument(
            id=sop_id, doc_type='SOP',
            department_id=dept_fo.id if dept_fo else 1,
            title='Low Visibility Procedures (LVP) — Standard Operating Procedure',
            description='Crew procedures for operations in low visibility conditions',
            content='1. Pre-flight: Check LVP NOTAM and minima.\n2. Dispatch: Load alternate fuel per LVP policy.\n3. Approach: Brief crew on LVP requirements.\n4. Decision: Apply CAT I/II/III minima per approved OpSpecs.\n5. Go-around: Execute immediately if visual reference not established.',
            version='REV0', version_num=0, seq_num=1,
            status='Approved',
            created_by='Flight Operations Manager',
            approved_by='Accountable Manager',
            effective_date='2024-01-15',
            review_due='2025-01-15',
            change_summary='Initial issue'
        )
        db.session.add(sop)

    # Create FOD SOP for Ground Ops
    fod_id = f"SOP-GO-{year}-001-REV0"
    if not SMSDocument.query.get(fod_id) and dept_go:
        fod = SMSDocument(
            id=fod_id, doc_type='SOP',
            department_id=dept_go.id,
            title='Foreign Object Debris (FOD) Prevention and Control',
            description='Ramp FOD inspection and prevention procedures',
            content='1. Pre-movement: Conduct FOD walk of ramp area.\n2. Post-rain: Mandatory FOD inspection before resuming ops.\n3. Supervisor sign-off required before aircraft movement.\n4. All FOD found must be logged and reported.',
            version='REV0', version_num=0, seq_num=1,
            status='Approved',
            created_by='Ground Operations Manager',
            approved_by='Accountable Manager',
            effective_date='2024-03-01',
            review_due='2025-03-01',
            change_summary='Initial issue'
        )
        db.session.add(fod)

    db.session.flush()

    # Now create links — this is the traceability backbone
    links_to_create = [
        # RA linked to hazard and risk
        (ra_id,  'hazard',  'HAZ-2024-DEMO1', 'Risk assessment for this hazard'),
        (ra_id,  'risk',    'RSK-2024-DEMO1', 'RA covers this specific risk'),
        # SOP linked to hazard and risk
        (sop_id, 'hazard',  'HAZ-2024-DEMO1', 'SOP referenced as control measure'),
        (sop_id, 'risk',    'RSK-2024-DEMO1', 'SOP is the primary Preventive Control'),
        # FOD SOP linked to Ground Ops hazard
        (fod_id, 'hazard',  'HAZ-2024-DEMO2', 'FOD SOP addresses this hazard'),
    ]

    # Also link to audit finding if it exists
    demo_finding = AuditFinding.query.first()
    if demo_finding:
        links_to_create.append(
            (sop_id, 'audit_finding', demo_finding.id, 'SOP referenced in finding')
        )

    for doc_id, etype, eid, reason in links_to_create:
        existing = DocumentLink.query.filter_by(
            document_id=doc_id, entity_type=etype, entity_id=eid).first()
        if not existing:
            db.session.add(DocumentLink(
                document_id=doc_id, entity_type=etype,
                entity_id=eid, link_reason=reason))

    db.session.commit()
    print('✅ Traceability seed data created.')


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

    return render_template('risk_register.html',
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
    return render_template('risk_detail.html',
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

    return render_template('srm_dashboard.html',
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
    return f"JAV/RA/{dept_code}/{year}/{count:03d}"

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
    dept_f  = request.args.get('dept','')
    stat_f  = request.args.get('status','')
    q = RiskAssessment.query
    if dept_f: q = q.filter_by(department_id=int(dept_f))
    if stat_f: q = q.filter_by(status=stat_f)
    ras = q.order_by(RiskAssessment.created_at.desc()).all()
    return render_template('ra_list.html', ras=ras, dept_f=dept_f, stat_f=stat_f)

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
    return render_template('ra_form.html', hazard=hazard,
                           today=date.today().isoformat())

# ─── RA DETAIL (all 5 pages in one view) ────────────────────────────────────
@app.route('/risk-assessments/<ra_id>')
def ra_detail(ra_id):
    ra = RiskAssessment.query.get_or_404(ra_id)
    worst_i, worst_r = compute_ra_summary(ra)
    return render_template('ra_detail.html', ra=ra,
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
    ra.status                = f.get('status', ra.status)
    ra.management_acceptance = f.get('management_acceptance', ra.management_acceptance)
    ra.acceptance_date       = f.get('acceptance_date', ra.acceptance_date)
    ra.approved_by_name      = f.get('approved_by_name', ra.approved_by_name)
    ra.approved_by_position  = f.get('approved_by_position', ra.approved_by_position)
    ra.next_review_date      = f.get('next_review_date', ra.next_review_date)
    db.session.commit()
    flash('✓ Risk Assessment updated.', 'success')
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
            # Save admin header info
            ra.responsible_name  = f.get('responsible_name', ra.responsible_name)
            ra.assessors_names   = f.get('assessors_names', ra.assessors_names)
            ra.assessment_date   = f.get('assessment_date', ra.assessment_date)
            ra.next_review_date  = f.get('next_review_date', ra.next_review_date)
            ra.title             = f.get('title', ra.title)
            ra.reasons           = f.get('reasons', ra.reasons)
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

    return render_template('ra_wizard.html',
        hazard=hazard, ra=ra, step=step,
        steps=WIZARD_STEPS,
        completed_steps=completed_steps,
        checklist=CONTROL_CHECKLIST,
        checklist_items=checklist_items,
        get_tolerance=get_tolerance)

# ─── RESUME wizard from hazard log ───────────────────────────────────────────

with app.app_context():
    db.create_all()
    seed()

if __name__ == '__main__':
    app.run(debug=True)
