# KB v2 audit

Bundle: data/knowledge/kb_v2_1_doctor

## Decision

- Experimental doctor search: **YES**
- Patient RAG: **NO**
- Clinical automation: **NO**

The bundle may be used to develop and evaluate retrieval for doctors. Draft or unchecked knowledge must not be shown to patients or used for automatic treatment decisions.

## Summary

- Issue groups: 4
- Errors: 0
- Blocking records: 21
- Warnings: 29

## Record counts

- sources.jsonl: 27
- entities/chunks.jsonl: 88
- entities/conditions.jsonl: 33
- entities/eval_cases.jsonl: 20
- entities/medication_cards.jsonl: 15
- entities/medications.jsonl: 23
- entities/patient_model.jsonl: 28
- entities/safety_rules.jsonl: 16
- entities/scales.jsonl: 17

## Findings

- **BLOCKER / missing_patient_corpus** — No chunks are approved and scoped for patient retrieval (1).
- **WARNING / missing_raw_source** — Source registry points to raw files absent from the bundle (2). Samples: ru_cr_gad_adult_457_3, ru_cr_depression_adult_301_3.
- **WARNING / unknown_license** — Source reuse license is missing or unknown (27). Samples: ru_cr_gad_adult_457_3, ru_cr_depression_adult_301_3, ru_grls_agomelatine, ru_grls_alimemazine, ru_grls_bromdihydrochlorphenylbenzodiazepine.
- **BLOCKER / unchecked_records** — Unchecked evaluation cases (20). Samples: eval:gad__avi_001, eval:gad__avi_002, eval:gad__avi_003, eval:gad__avi_004, eval:gad__avi_005.

## Gate for the next stage

The next implementation step may build a doctor-only retrieval endpoint with citations. Patient access remains disabled until chunks receive an explicit audience, clinical approval, and the evaluation and safety-rule gates pass.
