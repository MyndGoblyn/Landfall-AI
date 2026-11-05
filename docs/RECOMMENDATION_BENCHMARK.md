# Recommendation Quality Benchmark

The recommendation benchmark is the regression gate for suggestion-engine
retrieval, filtering, ranking, and explanation changes.

Run it from the repository root:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_recommendation_benchmark.py --details
```

During Ranker V2 rollout, gate both ordering paths explicitly:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_recommendation_benchmark.py --ranker legacy
backend\.venv\Scripts\python.exe backend\scripts\run_recommendation_benchmark.py --ranker v2
```

The command exits with a nonzero status when any case fails its gates, making it
suitable for CI and release checks.

## Labels

- `core`: one of the best candidates for the represented job.
- `strong`: a high-quality alternative that belongs in the top results.
- `situational`: defensible only under narrower deck or user preferences.
- `weak`: legal and superficially related, but lower-value than the top options.
- `reject`: must not appear because it violates a constraint or matches the wrong
  mechanic, token type, counter context, or strategic job.

## Metrics

- Candidate recall verifies that labeled core and strong cards entered retrieval.
- Core recall at K verifies that the best card survived filters and ranking.
- Precision at K verifies that top output contains only core or strong choices.
- NDCG at K verifies that stronger labels rank ahead of weaker labels.
- Hard rejections are zero-tolerance top-K failures.
- Reason failures identify missing evidence tags, missing required explanation
  details, and banned circular or misleading language.

## Adding Cases

Add versioned cases to
`tests/fixtures/golden_recommendation_benchmark.json`. Each case must provide a
frozen candidate pool and a judgment for every candidate that can be returned.

Use compact candidate pools to isolate one decision boundary. Prefer a core
card, a strong alternative, and one or more tempting false positives. Every new
semantic detector or ranking feature should add:

1. A positive candidate that demonstrates the intended improvement.
2. A close negative candidate that demonstrates the false positive being
   prevented.
3. Evidence or reason requirements when the distinction affects user-facing
   explanation text.

The frozen pools primarily measure ranking quality. Local-catalog tests now
cover deterministic retrieval semantics and broad-pool expansion separately;
the next benchmark expansion will label end-to-end catalog retrieval pools so
candidate recall can be gated against real snapshot versions.

The current 14-case suite also gates deck-level marginal utility: dependable
draw, real acceleration rather than land access, flexible removal, and
protection that can save deck assets rather than only the candidate itself.
