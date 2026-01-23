# Evaluation Summary Report (Canonical)

**Dataset**: public_updated.csv

## Overall Metrics

- **Total Tasks**: 15
- **Average Score**: 0.800 ± 0.190
- **Score Range**: [0.350, 1.000]
- **Contradiction Rate**: 0.0%
- **Disagreement Rate**: 13.3%

## By Difficulty Level

| Difficulty | N | Avg Score | Std | Contradiction | Disagreement |
|------------|---|-----------|-----|---------------|--------------|
| Easy | 5 | 1.000 | 0.000 | 0.0% | 0.0% |
| Medium | 5 | 0.830 | 0.024 | 0.0% | 0.0% |
| Hard | 5 | 0.570 | 0.117 | 0.0% | 40.0% |

## By Question Type

| Type | N | Avg Score | Std |
|------|---|-----------|-----|
| Factual | 5 | 1.000 | 0.000 |
| Numeric | 5 | 0.830 | 0.024 |
| Complex | 5 | 0.570 | 0.117 |

## Judge Performance

| Judge | Calls | Avg Latency (ms) | P95 Latency | Errors |
|-------|-------|------------------|-------------|--------|
| semantic | 15 | 340 | 450 | 0 |
| numeric | 15 | 283 | 390 | 0 |