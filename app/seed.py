import json
from sqlmodel import Session, select
from app.models import Template, TemplateSection


def seed_templates(engine):
    with Session(engine) as db:
        existing = db.exec(select(Template)).first()
        if existing:
            return

        # Template 1: Default (original 5 dimensions)
        t1 = Template(name="Default", is_default=True)
        db.add(t1)
        db.commit()
        db.refresh(t1)

        default_sections = [
            TemplateSection(
                template_id=t1.id, order=1, title="Comprehension Depth",
                description='Example: "Walk me through a problem you solved — not what you did, but how you figured out what the actual problem was."',
                measurement_type="rating_1_4",
                anchor_low="Clear no, would not proceed", anchor_high="Strong signal, prioritize",
            ),
            TemplateSection(
                template_id=t1.id, order=2, title="Execution Reliability",
                description='Example: "Tell me about something you committed to that got harder than expected. What happened?"',
                measurement_type="rating_1_4",
                anchor_low="Clear no, would not proceed", anchor_high="Strong signal, prioritize",
            ),
            TemplateSection(
                template_id=t1.id, order=3, title="Adaptive Range",
                description='Example: "Describe a moment when the plan stopped working. What did you do before you had a new one?"',
                measurement_type="rating_1_4",
                anchor_low="Clear no, would not proceed", anchor_high="Strong signal, prioritize",
            ),
            TemplateSection(
                template_id=t1.id, order=4, title="Signal Clarity",
                description='Example: "How would you explain what you do to someone with no background in it?"',
                measurement_type="rating_1_4",
                anchor_low="Clear no, would not proceed", anchor_high="Strong signal, prioritize",
            ),
            TemplateSection(
                template_id=t1.id, order=5, title="Gut Check",
                description='Example: "Regardless of everything above — would you work with this person?"',
                measurement_type="single_select",
                options=json.dumps(["Yes", "No"]),
            ),
        ]
        for s in default_sections:
            db.add(s)

        # Template 2: Culture Alignment
        t2 = Template(name="Culture Alignment", is_default=False)
        db.add(t2)
        db.commit()
        db.refresh(t2)

        culture_sections = [
            TemplateSection(
                template_id=t2.id, order=1, title="Relevansi Skill",
                description="Seberapa match skill yang dimiliki dengan kebutuhan nyata tim?",
                measurement_type="single_select",
                options=json.dumps(["Match", "Perlu Perhatian", "Kurang"]),
            ),
            TemplateSection(
                template_id=t2.id, order=2, title="Kedalaman Pengalaman",
                description="Apakah pengalamannya benar-benar dalam, atau hanya permukaan?",
                measurement_type="single_select",
                options=json.dumps(["Expert", "Cukup", "Permukaan"]),
            ),
            TemplateSection(
                template_id=t2.id, order=3, title="Gap yang Terdeteksi",
                description="Seberapa besar gap yang perlu di-onboard kalau dia masuk?",
                measurement_type="single_select",
                options=json.dumps(["Sedikit", "Perlu Perhatian", "Banyak"]),
            ),
            TemplateSection(
                template_id=t2.id, order=4, title="Kesiapan Kontribusi",
                description="Siap langsung kontribusi, atau butuh ramp-up cukup lama?",
                measurement_type="single_select",
                options=json.dumps(["Ready", "Ramp-Up", "Not Ready"]),
            ),
            TemplateSection(
                template_id=t2.id, order=5, title="Cara Approach Masalah",
                description="Bagaimana seseorang berpikir saat ketemu problem",
                measurement_type="single_select",
                options=json.dumps(["Sistematis", "Cukup Terstruktur", "Reaktif"]),
            ),
            TemplateSection(
                template_id=t2.id, order=6, title="Kecepatan Menangkap Informasi",
                description="Saat diberi konteks baru selama interview, seberapa cepat pick up?",
                measurement_type="single_select",
                options=json.dumps(["Cepat", "Perlu Pengulangan", "Lambat"]),
            ),
            TemplateSection(
                template_id=t2.id, order=7, title="Kejelasan Komunikasi",
                description="",
                measurement_type="single_select",
                options=json.dumps(["Jelas & Langsung", "Cukup Jelas", "Berputar-putar"]),
            ),
            TemplateSection(
                template_id=t2.id, order=8, title="Execution Excellence",
                description="Punya standar 'done' yang jelas? Konsisten walau di bawah tekanan?",
                measurement_type="rating_1_4",
                anchor_low="No Evidence", anchor_high="Exceed",
            ),
            TemplateSection(
                template_id=t2.id, order=9, title="Learn Fast, Adapt Faster",
                description="Ada bukti belajar mandiri dan diterapkan? Cepat pivot saat kondisi berubah?",
                measurement_type="rating_1_4",
                anchor_low="No Evidence", anchor_high="Exceed",
            ),
            TemplateSection(
                template_id=t2.id, order=10, title="Impact Over Activity",
                description="Berpikir dari outcome? Bisa bedakan yang berdampak dari yang hanya sibuk?",
                measurement_type="rating_1_4",
                anchor_low="No Evidence", anchor_high="Exceed",
            ),
            TemplateSection(
                template_id=t2.id, order=11, title="Clarity & Structured Thinking",
                description="Komunikasinya terstruktur? Kesimpulan dulu? Berani seek clarity saat bingung?",
                measurement_type="rating_1_4",
                anchor_low="No Evidence", anchor_high="Exceed",
            ),
            TemplateSection(
                template_id=t2.id, order=12, title="Drive & Dream",
                description="Kombinasi: Pilih 2",
                measurement_type="multi_select",
                max_selections=2,
                options=json.dumps([
                    "Survival - Visi masa depan sangat samar atau tidak ada. Semua motivasi ekstrinsik.",
                    "Growth - Excited cerita hal baru yang dipelajari mandiri. Punya roadmap pengembangan diri.",
                    "Impact - Jawaban pencapaian selalu dalam bahasa dampak, ada angka atau before-after.",
                    "Ambition - Visi masa depan sangat spesifik soal posisi dan title. Excited cerita pencapaian yang diakui orang lain.",
                ]),
            ),
            TemplateSection(
                template_id=t2.id, order=13, title="Rekomendasi",
                description="",
                measurement_type="single_select",
                options=json.dumps(["Recommended", "Skip/NOK"]),
            ),
            TemplateSection(
                template_id=t2.id, order=14, title="Catatan Keseluruhan",
                description="Catatan Keseluruhan Interviewer (Kompetensi dan Culture)",
                measurement_type="long_text",
                required=False,
            ),
        ]
        for s in culture_sections:
            db.add(s)

        # Template 3: HR Interview
        t3 = Template(name="HR Interview", is_default=False)
        db.add(t3)
        db.commit()
        db.refresh(t3)

        hr_sections = [
            TemplateSection(
                template_id=t3.id, order=1, title="Rekomendasi",
                description="",
                measurement_type="single_select",
                options=json.dumps(["Recommended", "Skip/NOK"]),
            ),
        ]
        for s in hr_sections:
            db.add(s)
        db.commit()

        # Need to get the Rekomendasi section id for condition
        rekomendasi_section = db.exec(
            select(TemplateSection).where(
                TemplateSection.template_id == t3.id,
                TemplateSection.title == "Rekomendasi"
            )
        ).first()

        hr_conditional_sections = [
            # Conditional: Recommended path (Culture Fit)
            TemplateSection(
                template_id=t3.id, order=2, title="Ownership with Accountability",
                description="Update sebelum diminta, bukan setelah ditagih · ada contoh peduli hasil end-to-end, bukan hanya bagiannya · menutup loop, tidak melempar masalah",
                measurement_type="rating_1_4",
                anchor_low="No Evidence", anchor_high="Exceed",
                condition_section_id=rekomendasi_section.id,
                condition_value="Recommended",
            ),
            TemplateSection(
                template_id=t3.id, order=3, title="Maturity & Growth Mindset",
                description="Defensif sebagai first response itu wajar — yang penting apa yang dilakukan setelahnya · jujur soal kapasitas · fokus solusi, bukan siapa yang salah",
                measurement_type="rating_1_4",
                anchor_low="No Evidence", anchor_high="Exceed",
                condition_section_id=rekomendasi_section.id,
                condition_value="Recommended",
            ),
            TemplateSection(
                template_id=t3.id, order=4, title="Supportive & Collaborative",
                description="Ada contoh membantu sebelum diminta · mengakui kontribusi orang lain · say thanks dan say sorry adalah kebiasaan",
                measurement_type="rating_1_4",
                anchor_low="No Evidence", anchor_high="Exceed",
                condition_section_id=rekomendasi_section.id,
                condition_value="Recommended",
            ),
            TemplateSection(
                template_id=t3.id, order=5, title="Drive & Dream",
                description="Kombinasi: Pilih 2",
                measurement_type="multi_select",
                max_selections=2,
                options=json.dumps([
                    "Survival - Visi masa depan sangat samar atau tidak ada. Semua motivasi ekstrinsik.",
                    "Growth - Excited cerita hal baru yang dipelajari mandiri. Punya roadmap pengembangan diri.",
                    "Impact - Jawaban pencapaian selalu dalam bahasa dampak, ada angka atau before-after.",
                    "Ambition - Visi masa depan sangat spesifik soal posisi dan title. Excited cerita pencapaian yang diakui orang lain.",
                ]),
                condition_section_id=rekomendasi_section.id,
                condition_value="Recommended",
            ),
            # Conditional: Skip/NOK path (Veto Flag)
            TemplateSection(
                template_id=t3.id, order=6, title="Veto Flag",
                description="Pilih alasan utama jika Skip/NOK",
                measurement_type="single_select",
                options=json.dumps([
                    "Tidak bisa berikan satu pun contoh nyata — semua jawaban generik",
                    "Defensif atau menyalahkan orang lain saat ditanya soal kegagalan",
                    "Tidak jujur — cerita terlalu perfect, tidak ada momen gagal",
                    "Energi toxic — mengeluh panjang soal tempat kerja lama tanpa insight",
                    "Tidak ada drive sama sekali — semua motivasi ekstrinsik",
                ]),
                condition_section_id=rekomendasi_section.id,
                condition_value="Skip/NOK",
            ),
            # Always shown
            TemplateSection(
                template_id=t3.id, order=7, title="Catatan HR",
                description="",
                measurement_type="short_text",
                required=False,
            ),
        ]
        for s in hr_conditional_sections:
            db.add(s)

        db.commit()


def seed_managed_data(engine):
    """Seed BusinessUnit, managed lists, and placeholder Job. Idempotent — finds or creates each."""
    from app.models import BusinessUnit, ManagedPosition, ManagedLevel, ManagedJobType, Job

    with Session(engine) as db:
        # Seed BUs (find or create)
        bu_names = ["Markethac", "APEX", "EXONIA", "1011", "R&D", "Group Support", "LUPIN"]
        for name in bu_names:
            existing = db.exec(select(BusinessUnit).where(BusinessUnit.name == name)).first()
            if not existing:
                db.add(BusinessUnit(name=name))

        # Seed positions (find or create)
        positions = [
            "Data Analyst", "Data Engineer", "Data Scientist",
            "Machine Learning Engineer / AI Engineer", "Data Quality Control",
            "Data Governance", "Fullstack Developer", "QA Engineer",
            "Project Manager", "CRM Strategist", "CRM Operation",
            "CRM Assistant", "Account Manager", "Business Analyst",
            "Digital Marketing", "Design Graphic",
        ]
        existing_positions = {mp.title for mp in db.exec(select(ManagedPosition)).all()}
        for i, title in enumerate(positions):
            if title not in existing_positions:
                db.add(ManagedPosition(title=title, order=i))

        # Seed levels (find or create)
        levels = [
            "L1 — Junior", "L2 — Mid", "L3 — Senior", "L4 — Lead", "L5 — Principal",
        ]
        existing_levels = {ml.label for ml in db.exec(select(ManagedLevel)).all()}
        for i, label in enumerate(levels):
            if label not in existing_levels:
                db.add(ManagedLevel(label=label, order=i))

        # Seed job types (find or create)
        job_types = ["Full-time", "Intern", "Contract", "Part-time"]
        existing_types = {jt.label for jt in db.exec(select(ManagedJobType)).all()}
        for i, label in enumerate(job_types):
            if label not in existing_types:
                db.add(ManagedJobType(label=label, order=i))

        db.commit()

        # Create _UNASSIGNED placeholder Job if not exists
        unassigned = db.exec(
            select(Job).where(Job.position == "_Unassigned", Job.status == "closed")
        ).first()
        if not unassigned:
            first_bu = db.exec(select(BusinessUnit)).first()
            if first_bu:
                db.add(Job(
                    title="_Unassigned",
                    title_locked=True,
                    position="_Unassigned",
                    level="_",
                    job_type="Full-time",
                    business_unit_id=first_bu.id,
                    headcount=0,
                    status="closed",
                ))
                db.commit()


def migrate_legacy_job_ids(engine):
    """Backfill job_id on pipelines/batches that have position+BU strings but no job_id.
    Idempotent — detects orphans by checking job_id IS NULL with position/BU present.
    Runs every startup, no-ops if nothing to migrate."""
    from app.models import BusinessUnit, Job, CandidatePipeline, ReviewBatch, PIPELINE_ENDED_STAGES

    with Session(engine) as db:
        orphan_pipelines = db.exec(
            select(CandidatePipeline).where(
                CandidatePipeline.job_id == None,
                CandidatePipeline.position != None,
            )
        ).all()

        orphan_batches = db.exec(
            select(ReviewBatch).where(
                ReviewBatch.job_id == None,
                ReviewBatch.position != None,
            )
        ).all()

        if not orphan_pipelines and not orphan_batches:
            return

        # Build BU name -> id map (normalized)
        bus = db.exec(select(BusinessUnit)).all()
        bu_map = {b.name.strip().lower(): b.id for b in bus}
        bu_name_map = {b.name.strip().lower(): b.name for b in bus}
        first_bu = bus[0] if bus else None
        if not first_bu:
            return

        def resolve_bu(bu_str):
            """Find BU by normalized name, create if missing."""
            if not bu_str or not bu_str.strip():
                return first_bu.id
            key = bu_str.strip().lower()
            if key in bu_map:
                return bu_map[key]
            # BU doesn't exist — create it
            new_bu = BusinessUnit(name=bu_str.strip())
            db.add(new_bu)
            db.flush()
            bu_map[key] = new_bu.id
            bu_name_map[key] = new_bu.name
            return new_bu.id

        # Find or create _Unassigned job (by status+position, not title)
        unassigned = db.exec(
            select(Job).where(Job.position == "_Unassigned", Job.status == "closed")
        ).first()
        if not unassigned:
            unassigned = Job(
                title="_Unassigned", title_locked=True, position="_Unassigned",
                level="_", job_type="Full-time", business_unit_id=first_bu.id,
                headcount=0, status="closed",
            )
            db.add(unassigned)
            db.commit()
            db.refresh(unassigned)

        # Build existing job lookup from DB (normalized keys)
        existing_jobs = db.exec(select(Job).where(Job.position != "_Unassigned")).all()
        job_lookup = {}
        for j in existing_jobs:
            bu = db.get(BusinessUnit, j.business_unit_id)
            key = (j.position.strip().lower(), bu.name.strip().lower() if bu else "")
            job_lookup[key] = j.id

        def get_or_create_job(position_str, bu_str, pipelines_for_key):
            """Find or create Job. Infer status and headcount from pipeline stages."""
            key = (
                (position_str or "_Unassigned").strip().lower(),
                (bu_str or "").strip().lower(),
            )
            if key in job_lookup:
                return job_lookup[key]

            bu_id = resolve_bu(bu_str)
            pos_display = (position_str or "_Unassigned").strip()
            bu_display = bu_str.strip() if bu_str else ""

            # Infer status: if ALL pipelines for this combo are ended → closed
            all_ended = all(
                p.stage in PIPELINE_ENDED_STAGES for p in pipelines_for_key
            ) if pipelines_for_key else False

            # Infer headcount: at least the number of hired pipelines
            hired_count = len([p for p in pipelines_for_key if p.stage == "hired"])
            headcount = max(1, hired_count)

            job = Job(
                title=f"{pos_display} — {bu_display}" if bu_display else pos_display,
                title_locked=False,
                position=pos_display,
                level="L2 — Mid",
                job_type="Full-time",
                business_unit_id=bu_id,
                headcount=headcount,
                status="closed" if all_ended else "open",
            )
            db.add(job)
            db.flush()
            job_lookup[key] = job.id
            return job.id

        # Group orphan pipelines by (position, BU) for status inference
        from collections import defaultdict
        pipeline_groups = defaultdict(list)
        for p in orphan_pipelines:
            key = (
                (p.position or "_Unassigned").strip().lower(),
                (p.business_unit or "").strip().lower(),
            )
            pipeline_groups[key].append(p)

        # Backfill pipelines
        for p in orphan_pipelines:
            key = (
                (p.position or "_Unassigned").strip().lower(),
                (p.business_unit or "").strip().lower(),
            )
            p.job_id = get_or_create_job(p.position, p.business_unit, pipeline_groups[key])
            db.add(p)

        # Backfill review batches
        for b in orphan_batches:
            b.job_id = get_or_create_job(b.position, b.business_unit, [])
            db.add(b)

        # Catch any pipelines with no position at all
        null_pipelines = db.exec(
            select(CandidatePipeline).where(CandidatePipeline.job_id == None)
        ).all()
        for p in null_pipelines:
            p.job_id = unassigned.id
            db.add(p)

        # Seed ManagedPosition for any position strings not already in the list
        from app.models import ManagedPosition
        existing_positions = {mp.title.strip().lower() for mp in db.exec(select(ManagedPosition)).all()}
        all_positions_in_data = set()
        for p in orphan_pipelines:
            if p.position and p.position.strip() and p.position.strip() != "_Unassigned":
                all_positions_in_data.add(p.position.strip())

        max_order = len(existing_positions)
        for pos in sorted(all_positions_in_data):
            if pos.lower() not in existing_positions:
                db.add(ManagedPosition(title=pos, order=max_order))
                max_order += 1

        db.commit()
