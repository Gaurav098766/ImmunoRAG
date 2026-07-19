# ImmunoRAG — Domain Glossary (Cancer Immunotherapy & Medical Concepts)

Plain-language explanations of the medical/biological concepts that have come up
while building this project — so the corpus, queries, and API data actually mean
something, not just "text that got retrieved."

---

## The Core Idea: Cancer Immunotherapy

**Cancer immunotherapy**
A category of cancer treatment that works by boosting or redirecting the patient's
own immune system to recognize and attack cancer cells — as opposed to
chemotherapy (poisons rapidly-dividing cells directly) or radiation (damages cells
directly). The core insight: cancer cells often find ways to "hide" from or
suppress the immune system, so many immunotherapies work by removing that
suppression or by directly engineering immune cells to hunt cancer.

**Tumor Microenvironment (TME)**
The "neighborhood" surrounding a tumor — not just cancer cells, but also immune
cells, blood vessels, connective tissue, and signaling molecules all interacting
together. The TME matters hugely in immunotherapy because a tumor can shape its
own microenvironment to suppress nearby immune cells, effectively creating a
local "shield." Much of cancer immunotherapy research is about how to break down
or work around this shield.

---

## Immune Cells That Show Up Repeatedly

**Macrophages**
A type of white blood cell that normally "eats" (phagocytoses) pathogens and
damaged cells. In the TME, macrophages can be reprogrammed by the tumor into a
tumor-supporting role instead of an attacking one.

**TAMs (Tumor-Associated Macrophages)**
Macrophages that have infiltrated the tumor microenvironment specifically. Often
categorized loosely as:
  - **M1-like** — pro-inflammatory, generally anti-tumor
  - **M2-like** — anti-inflammatory, generally pro-tumor (helps the tumor grow,
    suppresses nearby immune attack)
Many therapies aim to "repolarize" TAMs from M2-like back to M1-like behavior.

**Neutrophils**
Another type of white blood cell, usually the "first responders" to infection.
Like macrophages, tumors can co-opt neutrophils in the TME to support tumor growth
rather than fight it.

**MDSCs (Myeloid-Derived Suppressor Cells)**
Immature immune cells that actively suppress the immune system's ability to attack
the tumor. A major reason tumors can "hide" despite an intact immune system nearby.

**Tumor-Infiltrating Lymphocytes (TILs)**
Immune cells (mainly T cells) that have physically moved into the tumor tissue.
Their presence/absence and activity level is often used as a marker of how
"immunologically active" a tumor is, and how likely a patient is to respond to
immunotherapy.

**Trm cells (Tissue-Resident Memory T cells)**
A subtype of T cell that stays permanently in a specific tissue (rather than
circulating through blood) and provides long-term local immune surveillance —
relevant to how well the immune system can keep monitoring a tissue for cancer
recurrence.

---

## Checkpoint Inhibitors — the Biggest Immunotherapy Category in the Corpus

**Immune checkpoints**
Normal "brakes" the immune system uses to avoid attacking the body's own healthy
cells (prevents autoimmune damage). Cancer cells frequently exploit these same
brakes to avoid being attacked by the immune system — essentially hijacking a
safety mechanism for self-protection.

**PD-1 (Programmed Death receptor-1)**
A checkpoint protein on the surface of T cells. When activated, it tells the T
cell to "stand down" rather than attack.

**PD-L1 (Programmed Death-Ligand 1)**
The molecule (often found on tumor cells) that binds to PD-1 and triggers that
"stand down" signal. Many tumors overexpress PD-L1 specifically to suppress
nearby T cells — this is one of the most common resistance mechanisms discussed
in the corpus.

**Checkpoint inhibitors**
Drugs that block the PD-1/PD-L1 interaction (or similar checkpoint pairs), which
removes the "brake" and lets T cells attack the tumor again. Examples that appear
in the corpus/API queries: **pembrolizumab** (brand name Keytruda) and
**nivolumab** (brand name Opdivo) — both PD-1-blocking antibodies.

**CTLA-4**
Another checkpoint protein (different from PD-1), also targeted by some
checkpoint inhibitor drugs. Often mentioned alongside PD-1/PD-L1 as one of the
"traditional" checkpoint targets.

**VISTA, IDO1, CD276 (B7-H3)**
Additional, "next-generation" checkpoint targets beyond the well-established
PD-1/PD-L1/CTLA-4 — relevant because many patients don't respond to standard
checkpoint inhibitors, so research is expanding to find other checkpoints tumors
exploit.

---

## CAR-T Cell Therapy

**CAR-T (Chimeric Antigen Receptor T-cell) therapy**
A treatment where a patient's own T cells are extracted, genetically engineered
in a lab to recognize a specific marker on cancer cells (the "chimeric antigen
receptor"), multiplied, and infused back into the patient. Very different
mechanism from checkpoint inhibitors — instead of removing a "brake," this
actively re-targets immune cells to hunt the cancer directly.

**Ex vivo vs. In vivo (CAR-T manufacturing)**
- **Ex vivo** — the current standard: T cells are removed from the patient,
  engineered outside the body in a lab, then reinfused. Complex, expensive,
  time-consuming.
- **In vivo** — an emerging alternative: engineering the T cells directly inside
  the patient's body, skipping the external lab process. A major area of active
  research aiming to make CAR-T cheaper/faster/more accessible.

**CRS (Cytokine Release Syndrome)**
A common and potentially serious side effect of CAR-T therapy — the engineered
T cells activate so aggressively that they trigger a massive, body-wide immune/
inflammatory reaction. One of the main "toxicity" concerns that shows up
repeatedly in CAR-T literature.

**Neurotoxicity (in CAR-T context, sometimes called ICANS)**
Another significant CAR-T side effect — inflammation/immune activity affecting
the brain/nervous system, ranging from confusion to more severe neurological
symptoms.

**CAR-NKT cells**
A variation using NK (natural killer) T cells instead of standard T cells as the
engineered platform — appeared in the corpus as a potential safety improvement
over traditional CAR-T (different toxicity profile).

---

## Autophagy & Tumor Evasion Mechanisms

**Autophagy**
A cell's internal "recycling" process — breaking down and reusing its own damaged
components. In cancer, autophagy plays a complicated dual role: it can either help
kill stressed cancer cells, OR help cancer cells survive stress and evade the
immune system, depending on context. This dual nature is why it shows up in TME/
immune-evasion discussions.

**Immune Evasion**
The general term for any mechanism a tumor uses to avoid being detected or
attacked by the immune system (includes checkpoint overexpression, TAM
reprogramming, autophagy-related mechanisms, and others).

---

## Trial & Regulatory Concepts

**Clinical Trial Phases**
The staged process for testing a new treatment in humans, in increasing scale:
  - **Phase 1** — small group, primarily testing safety/dosage
  - **Phase 2** — larger group, testing effectiveness and further safety
  - **Phase 3** — large-scale, comparing against existing standard treatment;
    typically the last step before regulatory approval
  - (Phase 4 exists too — post-approval monitoring, not heavily used in our data)

**Trial Status** (as used in our `trials` table / ClinicalTrials.gov data)
Common values: RECRUITING (actively enrolling patients), COMPLETED, TERMINATED
(stopped early, often due to safety or efficacy issues), ACTIVE_NOT_RECRUITING,
etc.

**Sponsor**
The organization (pharma company, university, hospital) responsible for running/
funding a clinical trial.

**Enrollment (count)**
The number of patients participating in a given trial — relevant for judging how
statistically robust a trial's results are likely to be.

---

## FDA / Drug Safety Data (openFDA)

**Adverse Event Report**
A real-world report (from a doctor, patient, pharmacist, or manufacturer) that a
patient experienced some negative reaction after taking a drug. Important
caveat: these are voluntarily submitted and NOT verified/confirmed as actually
caused by the drug — high report counts can simply reflect a drug being widely
prescribed, not necessarily being more dangerous.

**Reaction types seen in our pembrolizumab query results:**
- **Cardiomyopathy** — disease/damage to the heart muscle, reducing its ability
  to pump blood effectively.
- **Hypothyroidism** — underactive thyroid gland; a known immune-related side
  effect of checkpoint inhibitors, since revving up the immune system can
  sometimes cause it to attack the patient's own thyroid.
- **Adrenal insufficiency** — the adrenal glands (which produce essential
  hormones like cortisol) stop functioning adequately — another example of
  checkpoint inhibitors sometimes triggering autoimmune-like side effects,
  since removing the immune system's "brakes" can occasionally cause it to
  attack healthy tissue too, not just the tumor.
- **Tumour lysis syndrome** — a dangerous condition where a large number of
  cancer cells die rapidly (often right after starting effective treatment),
  releasing their contents into the bloodstream faster than the body can
  process them — can cause serious metabolic/kidney complications.

**Drug Label / Package Insert**
The official FDA-approved document accompanying a drug, listing its approved
uses (indications), required dosing, and legally-mandated warnings. More
authoritative than adverse event reports for "what is this drug approved to
treat," since it reflects the FDA's formal determination rather than
unverified real-world reports.

---

*This file grows as new medical concepts come up during later levels (e.g. any new
mechanisms encountered while building L6's knowledge graph relationships, or new
drug classes queried via L5's live API).*

---

## Data Sources Used in ImmunoRAG — What Each Is and Why We Use It

**Europe PMC**
A free, open-access repository of biomedical and life-sciences literature —
essentially an alternative/mirror to PubMed Central, run by the European
Bioinformatics Institute. Provides full-text XML (JATS format) for open-access
papers, not just abstracts.
**Why we use it:** It's the source of our core 148-paper corpus — the actual
research literature ImmunoRAG searches over (checkpoint inhibitors, CAR-T, TME
biology, etc.). Chosen over plain PubMed because Europe PMC readily provides
full-text XML for open-access papers via a clean REST API, whereas PubMed
itself mostly indexes abstracts only — we need full papers, not just abstracts,
since a RAG system answering detailed questions needs the actual body text
(Methods, Results, Discussion), not just a 200-word summary.

**Europe PMC vs. plain PubMed — what's the actual difference?**
- **PubMed** — the most widely known biomedical literature search engine, run by
  the U.S. National Library of Medicine. Indexes almost all biomedical
  literature, but for most entries only provides the abstract (a short summary)
  plus a link to the publisher's site for full text — which is often paywalled.
- **Europe PMC** — run by the European Bioinformatics Institute, in
  collaboration with NIH/NLM (the same body behind PubMed) and other
  international partners. It indexes largely the same literature as PubMed, but
  additionally hosts full-text XML directly for open-access articles, and
  offers a more programmer-friendly REST API for searching and retrieving that
  full text.
- **Why this distinction mattered for ImmunoRAG specifically:** a RAG system
  needs full article text (Methods, Results, Discussion) to answer detailed
  questions — an abstract alone is too short and too vague for most real
  queries. Since PubMed itself doesn't reliably serve full text, and Europe PMC
  does (for open-access papers, via `fetch_papers.py`'s fulltextXML endpoint),
  Europe PMC was the natural choice as our literature source rather than
  PubMed directly.

**ClinicalTrials.gov (API v2)**
The U.S. National Library of Medicine's official registry of clinical trials
conducted worldwide — legally required (in most cases) for trial sponsors to
register here. Provides structured data: phase, recruitment status, sponsor,
enrollment size, conditions studied, interventions tested.
**Why we use it:** Published papers (from Europe PMC) tell you what's already
been studied and concluded — but trials data tells you what's currently being
tested, at what stage, and by whom. This is a fundamentally different, forward-
looking layer of information that a literature-only RAG system would completely
miss (e.g. "is there an active Phase 3 trial for X" isn't answerable from
published papers alone, since a trial's results might not be published yet).

**openFDA**
The FDA's public API surfacing several of its own internal datasets: drug
adverse event reports (FAERS), official drug labeling, and enforcement/recall
data.
**Why we use it:** Papers and trials tell you what researchers designed/
concluded in controlled study settings — openFDA's adverse event data tells you
what's actually been reported in the real world, across a much broader and less
controlled population than any single trial. It's a genuinely different kind of
evidence (uncontrolled, real-world signal vs. controlled research), and
official drug labels give the authoritative, legally-binding answer to "what is
this drug actually approved for" — something neither research papers nor trial
registrations definitively settle on their own (a paper might show promising
results; only the FDA label confirms actual approved use).

**Why three different sources instead of one bigger literature corpus:**
Each source answers a genuinely different question shape:
- "What does the research say about mechanism X?" → Europe PMC (papers)
- "What treatments are currently being tested, and how far along?" → ClinicalTrials.gov
- "What real-world side effects/official approved uses exist for drug Y?" → openFDA
A literature-only RAG system could only ever answer the first question type well —
adding trials + FDA data is what makes ImmunoRAG genuinely useful for a broader
range of real questions someone in this field would actually ask.

---