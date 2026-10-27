# KB v2 audit

Bundle: data/knowledge/kb_v2_2_complete_doctor

## Decision

- Experimental doctor search: **YES**
- Patient RAG: **NO**
- Clinical automation: **NO**

The bundle may be used to develop and evaluate retrieval for doctors. Draft or unchecked knowledge must not be shown to patients or used for automatic treatment decisions.

## Summary

- Issue groups: 3
- Errors: 0
- Blocking records: 1
- Warnings: 29

## Record counts

- sources.jsonl: 28
- entities/chunks.jsonl: 247
- entities/conditions.jsonl: 81
- entities/eval_cases.jsonl: 20
- entities/medication_cards.jsonl: 25
- entities/medications.jsonl: 60
- entities/patient_model.jsonl: 28
- entities/safety_rules.jsonl: 72
- entities/scales.jsonl: 32

## Findings

- **BLOCKER / missing_patient_corpus** — No chunks are approved and scoped for patient retrieval (1).
- **WARNING / missing_raw_source** — Source registry points to raw files absent from the bundle (2). Samples: ru_cr_gad_adult_457_3, ru_cr_depression_adult_301_3.
- **WARNING / unknown_license** — Source reuse license is missing or unknown (27). Samples: ru_cr_gad_adult_457_3, ru_cr_depression_adult_301_3, ru_grls_agomelatine, ru_grls_alimemazine, ru_grls_bromdihydrochlorphenylbenzodiazepine.

## Gate for the next stage

The next implementation step may build a doctor-only retrieval endpoint with citations. Patient access remains disabled until chunks receive an explicit audience, clinical approval, and the evaluation and safety-rule gates pass.
