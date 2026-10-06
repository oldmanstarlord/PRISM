# Evidence-Bound Explanation Framework v1

## Scope

Step E1 supports only stock risk-component explanations. MST, sector, event, and
news explainers are intentionally outside this version.

## Deterministic flow

1. The registered explainer reads a completed point-in-time score run and its
   component, definition, and model-configuration rows.
2. Each fact becomes a typed evidence item with a stable ID, source table/ref,
   effective date, window, unit, and data age.
3. Versioned templates in draft `model_config` key `explain_templates:1.0.0` are
   filled only when all placeholders have stored values.
4. Guardrails omit unsupported sentences and reject configured advice, certainty,
   causal, or non-approved correlation wording.
5. The versioned payload includes supporting evidence, limitations, confidence
   reasons, age, subject, template version, and disclaimer.
6. Subject, evidence, date, and template inputs are fingerprinted. An identical
   request reuses the unique stored explanation row.

No language model generates explanation text. The initial wording and glossary
are draft under PD-29 and require owner approval.

## API and UI

- `GET /api/v1/explain/component/{symbol}/{component_key}`
- `GET /api/v1/glossary`
- `GET /api/v1/glossary/{term}`

The generic drawer renders arbitrary section keys and exposes each evidence item's
provenance. Component rows open it through their `Why?` action.
