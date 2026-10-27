# KB v2 audit

Bundle: /mnt/d/datacon_2026/clinical-compass/data/knowledge/kb_v2.zip

## Decision

- Experimental doctor search: **YES**
- Patient RAG: **NO**
- Clinical automation: **NO**

The bundle may be used to develop and evaluate retrieval for doctors. Draft or unchecked knowledge must not be shown to patients or used for automatic treatment decisions.

## Summary

- Issue groups: 13
- Errors: 0
- Blocking records: 800
- Warnings: 371

## Record counts

- sources.jsonl: 27
- entities/chunks.jsonl: 320
- entities/conditions.jsonl: 81
- entities/eval_cases.jsonl: 20
- entities/medication_cards.jsonl: 25
- entities/medications.jsonl: 60
- entities/patient_model.jsonl: 28
- entities/safety_rules.jsonl: 72
- entities/scales.jsonl: 32

## Findings

- **WARNING / tiny_chunk** — Chunks shorter than 80 characters need merging or exclusion (239). Samples: ru_cr_depression_adult_301_3_D006__001, ru_grls_agomelatine_ЛП000528РГRU_adverse__001, ru_grls_agomelatine_ЛП000528РГRU_indications__001, ru_grls_agomelatine_ЛП000528РГRU_contraindications__001, ru_grls_agomelatine_ЛП000528РГRU_special__001.
- **BLOCKER / unapproved_chunks** — Chunks are not approved for clinical RAG output (320). Samples: ru_cr_gad_adult_457_3_A001__001, ru_cr_gad_adult_457_3_A002__001, ru_cr_gad_adult_457_3_A003__001, ru_cr_gad_adult_457_3_A004__001, ru_cr_gad_adult_457_3_A005__001.
- **BLOCKER / missing_audience** — Chunks have no doctor/patient access scope (320). Samples: ru_cr_gad_adult_457_3_A001__001, ru_cr_gad_adult_457_3_A002__001, ru_cr_gad_adult_457_3_A003__001, ru_cr_gad_adult_457_3_A004__001, ru_cr_gad_adult_457_3_A005__001.
- **WARNING / missing_raw_source** — Source registry points to raw files absent from the bundle (2). Samples: ru_cr_gad_adult_457_3, ru_cr_depression_adult_301_3.
- **WARNING / unknown_license** — Source reuse license is missing or unknown (27). Samples: ru_cr_gad_adult_457_3, ru_cr_depression_adult_301_3, ru_grls_agomelatine, ru_grls_alimemazine, ru_grls_bromdihydrochlorphenylbenzodiazepine.
- **WARNING / unchecked_records** — Unchecked condition facts (48). Samples: ru_cr_depression_adult_301_3__D001, ru_cr_depression_adult_301_3__D002, ru_cr_depression_adult_301_3__D003, ru_cr_depression_adult_301_3__D004, ru_cr_depression_adult_301_3__D005.
- **WARNING / unchecked_records** — Unchecked medication rows (30). Samples: ru_cr_depression_adult_301_3__M001, ru_cr_depression_adult_301_3__M002, ru_cr_depression_adult_301_3__M003, ru_cr_depression_adult_301_3__M004, ru_cr_depression_adult_301_3__M005.
- **WARNING / unchecked_records** — Unchecked medication cards (10). Samples: med:escitalopram, med:maritupirdine, med:vortioxetine, med:mirtazapine, med:amitriptyline.
- **BLOCKER / unchecked_records** — Unchecked safety rules (51). Samples: safety:S023, safety:S024, safety:S025, safety:S026, safety:S027.
- **WARNING / unchecked_records** — Unchecked scale rows (15). Samples: scale:hdrs17_ru__01, scale:hdrs17_ru__02, scale:hdrs17_ru__03, scale:hdrs17_ru__04, scale:hdrs17_ru__05.
- **BLOCKER / unchecked_records** — Unchecked evaluation cases (20). Samples: eval:gad__avi_001, eval:gad__avi_002, eval:gad__avi_003, eval:gad__avi_004, eval:gad__avi_005.
- **BLOCKER / untested_safety_rules** — Safety rules have neither positive nor negative tests (72). Samples: safety:S001, safety:S002, safety:S003, safety:S004, safety:S005.
- **BLOCKER / missing_medication_label** — Medication rows have no verified label card (17). Samples: med:alprazolam, med:amisulpride, med:brexpiprazole, med:buspirone, med:carbamazepine.

## Gate for the next stage

The next implementation step may build a doctor-only retrieval endpoint with citations. Patient access remains disabled until chunks receive an explicit audience, clinical approval, and the evaluation and safety-rule gates pass.
