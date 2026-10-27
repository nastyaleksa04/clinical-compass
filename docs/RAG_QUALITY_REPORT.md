# Doctor RAG quality report

- Index: kb_v2.2-complete-doctor
- Total cases: 30
- Physician-reviewed source cases: 20
- Adversarial cases: 10

## Retrieval

| Limit | Fully passed | Case pass rate | Source recall |
|---:|---:|---:|---:|
| Top-5 | 19/20 | 95.0% | 98.0% |
| Top-6 | 20/20 | 100.0% | 100.0% |
| Top-10 | 20/20 | 100.0% | 100.0% |

## Answer quality

**Quality gate: passed**

- Completed: 30 / 30
- Automated checks passed: 30 / 30
- Citation validity: 100.0%
- Safety/abstention behavior: 100.0%
- Cases with exact forbidden claims: 0

## Interpretation

Automated checks are a quality gate, not a clinical approval. Required-concept coverage is lexical and every live answer remains queued for physician review.
