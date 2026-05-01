from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, Department, HazardReport, ASRReport, Hazard, Risk, Control, Action, Audit, Finding, Investigation, MOC, SPIIndicator, SPIData, SafetyBulletin, Training
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
    open_act    = Action.query.filter(Action.status.in_(['Open','In Progress'])).count()
    overdue_act = Action.query.filter_by(status='Overdue').count()
    asr_cnt     = ASRReport.query.count()
    audit_cnt   = Audit.query.count()
    moc_cnt     = MOC.query.count()
    recent_haz  = Hazard.query.order_by(Hazard.created_at.desc()).limit(6).all()
    recent_act  = Action.query.filter(Action.status != 'Closed').order_by(Action.created_at.desc()).limit(5).all()
    return render_template('dashboard.html',
        total_haz=total_haz, open_haz=open_haz, intol=intol,
        open_act=open_act, overdue_act=overdue_act,
        asr_cnt=asr_cnt, audit_cnt=audit_cnt, moc_cnt=moc_cnt,
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
        flash(f'✓ Hazard Report submitted. ID: {rid} | Hazard: {hid} | Risk: {ri} — {get_tolerance(ri)}', 'success')
        return redirect(url_for('hazard_report'))
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
        flash(f'✓ ASR submitted. ID: {aid} | Hazard: {hid} | Risk: {ri} — {get_tolerance(ri)}', 'success')
        return redirect(url_for('asr'))
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
@app.route('/audits')
def audits():
    all_audits = Audit.query.order_by(Audit.planned_date.desc()).all()
    return render_template('audits.html', audits=all_audits)

@app.route('/audits/new', methods=['GET','POST'])
def new_audit():
    if request.method == 'POST':
        f = request.form
        a = Audit(id=new_id('AUD'),
                  title=f['title'], audit_type=f['audit_type'],
                  department_id=int(f['department_id']),
                  planned_date=f['planned_date'],
                  lead_auditor=f['lead_auditor'], status='Planned')
        db.session.add(a)
        db.session.commit()
        flash(f'✓ Audit {a.id} created.', 'success')
        return redirect(url_for('audits'))
    return render_template('audit_form.html')

@app.route('/audits/<aid>')
def audit_detail(aid):
    a = Audit.query.get_or_404(aid)
    return render_template('audit_detail.html', a=a)

@app.route('/audits/<aid>/add-finding', methods=['POST'])
def add_finding(aid):
    f   = request.form
    fid = new_id('FND')
    hid = None
    # Auto-create hazard from finding
    if f.get('create_hazard') == 'yes':
        hid = new_id('HAZ')
        h = Hazard(id=hid, source='Audit', linked_report_id=fid,
                   department_id=Audit.query.get(aid).department_id,
                   classification='Organizational',
                   type_of_activity='Audit Finding',
                   generic_hazard=f['description'][:100],
                   specific_components=f['description'],
                   consequences=f.get('root_cause',''),
                   status='Open')
        db.session.add(h)
        db.session.flush()
        act = Action(id=new_id('ACT'), source='Audit', hazard_id=hid,
                     linked_ref_id=fid,
                     description=f.get('corrective_action',''),
                     owner=f.get('owner','Safety Manager'),
                     due_date=f.get('due_date',''),
                     priority='High', status='Open')
        db.session.add(act)

    finding = Finding(id=fid, audit_id=aid,
                      description=f['description'],
                      severity=f['severity'],
                      root_cause=f.get('root_cause',''),
                      corrective_action=f.get('corrective_action',''),
                      status='Open', hazard_id=hid)
    db.session.add(finding)
    db.session.commit()
    flash('✓ Finding added.' + (' Hazard and Action created.' if hid else ''), 'success')
    return redirect(url_for('audit_detail', aid=aid))

@app.route('/audits/<aid>/update', methods=['POST'])
def update_audit(aid):
    a = Audit.query.get_or_404(aid)
    f = request.form
    a.status      = f.get('status', a.status)
    a.actual_date = f.get('actual_date', a.actual_date)
    a.summary     = f.get('summary', a.summary)
    db.session.commit()
    flash('✓ Audit updated.', 'success')
    return redirect(url_for('audit_detail', aid=aid))

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
        db.session.commit()
        flash(f'✓ MOC {m.id} created. Hazard {hid} auto-generated.', 'success')
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

# ─── Init ─────────────────────────────────────────────────────────────────────
with app.app_context():
    db.create_all()
    seed()

if __name__ == '__main__':
    app.run(debug=True)
