# Doc-mate — Demo-Day Runbook

> A tight, confident script for judges. Read this once before you present.
> Everything below is driven by the seeded demo dataset (`scripts.seed_demo`).

---

## 1. The 60-second problem pitch

Government hospitals in India see enormous patient volume. A doctor gets about
**five minutes per patient** — and most of that is spent *reading paperwork*:
old prescriptions, lab reports, discharge summaries, scan films, handwritten
notes. The doctor is drowning in records before the consultation even begins.

Step one — "understand this patient" — eats the visit. Diagnosis gets whatever
minute is left.

**One-line solution:** Doc-mate ingests everything about a patient at reception
and hands the doctor a **structured, citation-backed snapshot they can read in
under a minute** — so the five minutes go to care, not paperwork.

Say this too, up front: *"Doc-mate summarises and surfaces. It never diagnoses.
Every line links back to a real source document."* That framing earns trust
immediately.

---

## 2. Before the judges arrive (setup / reset)

From `backend/`, with the database reachable:

```bash
alembic upgrade head
python -m scripts.seed_demo
```

This is also your **reset button** between runs — it is idempotent, so re-running
never duplicates data. It seeds:

- Demo logins: **`reception@demo`** and **`doctor@demo`**, password **`demo1234`**.
- **6 synthetic patients** (clearly fake data), each chosen to show one strength.
- Documents across every type, mixed statuses (mostly verified, some extracted,
  one *failed* on purpose), realistic filenames and confidence values.
- Clinical items linked to their source documents, and a **ready-made summary**
  per patient — so the doctor Snapshot looks great the instant you open it.

Runs **fully offline** — the AI layer falls back to deterministic stubs, no API
keys needed. Good for flaky venue wifi.

---

## 3. The cast (which patient shows what)

| Patient | Lang | The story it tells | The strength it proves |
|---|---|---|---|
| **Rukmini Devi Sharma**, 68 F | EN | Diabetic + hypertensive elder, years of records, labs, a discharge, an ECG, and one unreadable old film | **Summarisation power** — collapses a thick file into one screen |
| **Arjun Nair**, 24 M | EN | Acute 3-day fever, almost no history | **Fast intake** — useful even with thin records |
| **Meena Kumari**, 27 F | HI | Antenatal follow-up, Hindi UI | **India-scale i18n** — the summary in the patient's language |
| **Karthik Raman**, 45 M | TA | Documented **Penicillin allergy**, Tamil UI | **Safety** — allergy shown in red, prominent, cited |
| **Anasuya Pothineni**, 62 F | TE | On warfarin from a cardiology discharge, arrives with an outside clinic's prescription for diclofenac, Telugu UI | **Medication safety** — a drug–drug interaction across two facilities' paperwork, caught and cited |
| **Lakshmi Bai**, 55 F | HI | Referred with one faded photo + a broken upload | **Honest flags** — says what's missing, never bluffs |

---

## 4. The live demo (step-by-step, ~4 minutes)

### Act 1 — Reception: create, upload, verify (~90s)

1. Log in as **`reception@demo`**.
2. **Create a patient** (or open Arjun Nair to keep it quick). Show the form:
   name, age/sex, ABHA-style id, **preferred language**.
3. **Upload** a document (a prescription photo / lab PDF). Point out the status
   moving through the pipeline: *uploaded → processing → extracted*.
4. Open the extracted document. Show the **proposed structured fields** —
   medications, labs — each with a **confidence** value. Handwriting or low
   confidence is marked **⚠ needs verification**.
5. Click **Verify** on the good ones. Say: *"A human confirms extractions before
   the doctor ever sees them. OCR on medical handwriting is never trusted blindly."*

> Talking point: this is the **human-in-the-loop** step. The AI proposes; a person
> confirms. That's what makes it safe for a real clinic.

### Act 2 — Doctor: the Snapshot (the wow moment, ~2min)

6. Log in as **`doctor@demo`**. Open **Rukmini Devi Sharma** — the rich elder.
7. Let the snapshot land. Read the sections top to bottom:
   - **Reason for visit**, **Active problems** (T2DM, hypertension),
     **Medications** (Metformin, Amlodipine, Atorvastatin),
     **Recent labs & trends** (HbA1c 7.8% with a trend arrow vs the prior 8.4%),
     **Past encounters** (coronary angiography), and **Flags to verify**.
8. **Click a citation chip.** It jumps to the source document. Say: *"Every claim
   is one click from its source. Nothing here is invented."*
9. Open **Karthik Raman** — the **allergy** case. The **Penicillin allergy is red
   and at the top**, and the summary notes the antibiotic chosen was a
   non-penicillin alternative. *"This is the line that prevents a dangerous
   prescription."*
10. Open **Anasuya Pothineni** — the **interaction** case. Her discharge summary
    has her on **warfarin**; the prescription she brought from an outside clinic
    adds **diclofenac**. The two documents come from different facilities and
    nothing in the paper file connects them — the snapshot puts a cited
    interaction alert at the top. Say: *"Neither document is wrong on its own.
    The collision only shows up when you read the whole record at once, which is
    exactly the part a five-minute consult skips."*
11. Switch language / open **Meena Kumari** (Hindi), **Karthik Raman** (Tamil) or
    **Anasuya Pothineni** (Telugu) to show the **same structured snapshot
    rendered in the patient's language**. EN / HI / TE / TA are all first-class:
    the section titles and common clinical phrases are translated, and clinical
    values, doses and citations are carried across verbatim.
12. Open **Lakshmi Bai** — the **sparse** patient. The snapshot is mostly the
    **Flags** section: *"allergies and chronic conditions UNKNOWN — confirm at
    intake,"* and the **failed upload** is shown plainly, not hidden. Say: *"When
    data is missing or unreadable, Doc-mate says so. It never shows a confident
    summary built on data it silently dropped."*

Close on: *"Rich patient or empty file, the doctor gets the truth in under a
minute — and can verify any line in one click."*

---

## 5. Key talking points (drop these naturally)

- **RAG + citations.** We retrieve the patient's own records and generate a
  grounded summary. **No citation → the line does not appear.** Citations are
  load-bearing, not decoration.
- **Summarises, never diagnoses.** The AI organises and highlights; the doctor
  concludes. Scan films get a *neutral caption only* — never a pathology read.
- **Honest status.** Failed / unreadable uploads are surfaced, not buried.
  Low-confidence extractions are flagged for verification.
- **ABDM / FHIR-ready.** Patients carry ABHA-style ids; our internal model maps
  onto FHIR resources (Patient, Observation, MedicationRequest,
  AllergyIntolerance, Condition, Procedure, DocumentReference). Integration is
  plumbing, not a rewrite.
- **Stub vs. real AI.** One swappable LLM layer. Today it runs on cloud models;
  for this demo it runs on deterministic **offline stubs** with zero keys. Flip
  an env var and real vision/LLM extraction slots in.
- **Privacy / self-host story.** No PHI in logs, URLs, or query strings. The
  swappable layer means a government deployment can run **fully self-hosted**
  open models — patient data never leaves the hospital.

---

## 6. Likely judge questions (with answers)

**Q: Isn't this just an LLM that could hallucinate a wrong dose?**
A: Two guards. First, extractions are **human-verified at reception** before the
doctor sees them. Second, the summary is **citation-grounded** — a line with no
resolvable source is dropped, so the model can't invent a medication out of thin
air. Uncertain values are flagged, never asserted.

**Q: Does it diagnose or recommend treatment?**
A: No — by design. It summarises and surfaces; the doctor diagnoses. Scan films
get a neutral caption, never a pathology read. That boundary is non-negotiable.

**Q: What about patient privacy and data residency?**
A: No patient content in logs or URLs. The LLM layer is swappable, so a hospital
can run self-hosted open models — data never leaves the premises. ABDM's consent
model (HIP/HIU) is the integration target.

**Q: Is this ABDM-certified?**
A: Not for the hackathon — and we're honest about that. But we're **built to map
onto FHIR** and use ABHA-style ids, so certification and the ABDM sandbox are a
plumbing job on top, not a redesign.

**Q: Handwriting and regional-language documents are messy — how accurate is it?**
A: OCR on medical handwriting tops out around 82–95%, so we never trust it
blindly. That's exactly why low-confidence fields are marked **⚠ verify** and a
human confirms them before the doctor sees them.

**Q: What happens when a document can't be read?**
A: It becomes `failed` with a plain reason in the UI, and the snapshot's Flags
section says data is missing. We never show a confident summary over silently
dropped data — see Lakshmi Bai in the demo.

**Q: Does it work without internet / API keys?**
A: Yes — what you're seeing now runs on deterministic offline stubs. The real
providers drop in behind the same interface via one env var.

---

## 7. If something breaks mid-demo

- **Snapshot looks empty or stale:** re-run the reset —
  `python -m scripts.seed_demo` (idempotent, safe any time).
- **Fresh database:** `alembic upgrade head` then the seed command.
- **Can't log in:** users are `reception@demo` / `doctor@demo`, password
  `demo1234` (created by the seed).
- **Want a totally clean slate:** re-run migrations, then seed. No manual
  cleanup needed.

---

## 7b. Background cohort (surveillance + triage demo data)

The five showcase patients above are the *story*. Two features, though, are
**population** features and cannot be shown on a five-row database:

- **Public-health surveillance** applies k-anonymity at **K=5**. With five
  patients every bucket falls below the threshold, so the dashboard renders
  entirely suppressed and the outbreak trip-wire can never fire — it refuses,
  by design, to signal on a cell it would have to suppress.
- **The OPD triage queue.** A real government OPD sees 500–2000 patients a day.
  Five rows, all routine, does not look like one.

So there is a second, optional seeder that adds a realistic *background*
population. Run it from `backend/`, after migrations, **in addition to**
`scripts.seed_demo` (it does not replace it):

```bash
alembic upgrade head
python -m scripts.seed_demo      # the 5 showcase patients
python -m scripts.seed_cohort    # + ~100 background patients
python -m scripts.seed_cohort 250   # optional size override
```

What it adds (default size, verified numbers):

- **100 synthetic patients**, varied Indian regions (including Andhra /
  Telangana name pools), ages 2–86, language mix
  **en 48 / hi 27 / te 14 / ta 11**. Every language clears the K=5
  suppression threshold, so the surveillance language panel shows a real
  four-way mix rather than a suppressed cell.
- **134 documents** — mostly `verified`, some `extracted`, a few `failed` with a
  plain reason, so the data-quality panel reports honest numbers instead of a
  suspiciously perfect 100%.
- **313 clinical items**, every one linked to its source document.
- A condition spread that clears K=5 and maps to real bundled ICD-11 codes:
  hypertension ×24, type 2 diabetes ×22, dengue ×18, iron-deficiency anaemia
  ×14, gastroenteritis ×12, asthma ×11, tuberculosis ×7.
- Dates spread across roughly the **last six months**, with one deliberately
  engineered **dengue cluster in the current week** (baseline ≈0.14 cases/week
  → 15 this week) so `/surveillance/signals` fires a single **`alert`**. Every
  other condition is kept flat, so exactly the intended signal appears.
- A believable triage mix across all 106 seeded patients: **4 emergency,
  21 urgent, 81 routine**.

Deliberately **not** created: chunks/embeddings and summaries. These are
background population for the aggregate views, not snapshot showcases — skipping
them keeps the seed to a few seconds. Opening a cohort patient in the doctor UI
generates their snapshot on demand like any other patient.

**Deterministic and idempotent.** `random` is seeded with a fixed constant, so
every run produces the same cohort — the outbreak lands on the same counts each
time you rehearse. Patients are keyed by a cohort-only ABHA prefix (`90-…`),
disjoint from the showcase ids, so re-running skips what already exists, never
duplicates a row, and **never touches Rukmini, Arjun, Meena, Karthik, Anasuya
or Lakshmi**.

**Reset:** just re-run both seeders — they are both idempotent, so it is safe any
time. For a truly clean slate, drop and recreate the database, `alembic upgrade
head`, then run `scripts.seed_demo` followed by `scripts.seed_cohort`.

> Say this if a judge asks: *"The five patients are the demo. The hundred behind
> them are synthetic background population — that's what makes the anonymised
> surveillance view legal to show at all, because k-anonymity suppresses
> anything under five."*

---

## 8. One-line close

*"Five-minute consult. Under one minute to understand the patient. Every line
cited, nothing diagnosed, nothing invented — at India scale."*
