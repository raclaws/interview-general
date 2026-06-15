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
