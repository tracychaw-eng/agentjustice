# Evaluation Summary Report (Adversarial)

**Dataset**: public_adversarial.jsonl

## Overall Metrics

- **Total Tasks**: 18
- **Average Score**: 0.258 ± 0.392
- **Score Range**: [0.000, 1.000]
- **Contradiction Rate**: 11.1%
- **Disagreement Rate**: 33.3%

## By Difficulty Level

| Difficulty | N | Avg Score | Std | Contradiction | Disagreement |
|------------|---|-----------|-----|---------------|--------------|
| Easy | 6 | 0.167 | 0.373 | 16.7% | 0.0% |
| Medium | 6 | 0.261 | 0.370 | 16.7% | 66.7% |
| Hard | 6 | 0.345 | 0.412 | 0.0% | 33.3% |

## By Question Type

| Type | N | Avg Score | Std |
|------|---|-----------|-----|
| Qualitative Retrieval | 4 | 0.642 | 0.381 |
| Quantitative Retrieval | 3 | 0.000 | 0.000 |
| Market Analysis | 3 | 0.083 | 0.118 |
| Numerical Reasoning | 2 | 0.000 | 0.000 |
| Adjustments | 2 | 0.000 | 0.000 |
| Financial Modeling | 2 | 0.910 | 0.090 |
| Beat or Miss | 1 | 0.000 | 0.000 |
| Complex Retrieval | 1 | 0.000 | 0.000 |

## Judge Performance

| Judge | Calls | Avg Latency (ms) | P95 Latency | Errors |
|-------|-------|------------------|-------------|--------|
| semantic_equivalence | 18 | 5132 | 9624 | 0 |
| numeric_tolerance | 18 | 4689 | 11117 | 0 |
| contradiction | 18 | 1684 | 3688 | 0 |

## Error Taxonomy

> **Note**: Error counts represent unrecovered judge failures logged in traces.
> Retries are handled internally; only persistent errors are counted.

- numeric_judge_error: 5