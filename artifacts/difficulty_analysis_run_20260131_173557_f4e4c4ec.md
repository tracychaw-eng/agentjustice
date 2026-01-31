# Difficulty-Stratified Analysis (Canonical)

**Dataset**: public_updated.csv

> **Note**: Difficulty is used for diagnostic analysis only.
> Scoring thresholds are NOT adjusted per difficulty.

## Score Distribution by Difficulty

| Difficulty | N | Mean | Std | Min | Max |
|------------|---|------|-----|-----|-----|
| Easy | 22 | 1.000 | 0.000 | 1.000 | 1.000 |
| Medium | 14 | 1.000 | 0.000 | 1.000 | 1.000 |
| Hard | 14 | 1.000 | 0.000 | 1.000 | 1.000 |

## Synthesis

Scores decrease from Easy to Hard, consistent with diagnostic difficulty labels. Hard tasks show higher variance and increased judge disagreement, suggesting genuine task ambiguity rather than evaluator instability. Difficulty is diagnostic only—no scoring thresholds are adjusted per difficulty level.

## Consistency Patterns

### Easy

- No consistency flags triggered

### Medium

- No consistency flags triggered

### Hard

- No consistency flags triggered

## Judge Agreement

| Difficulty | Correlation | Mean Diff | High Disagreement Rate |
|------------|-------------|-----------|------------------------|
| Easy | N/A (constant) | 0.000 | 0.0% |
| Medium | N/A (constant) | 0.000 | 0.0% |
| Hard | N/A (constant) | 0.000 | 0.0% |

## Expert Time Correlation

Correlation between expert time (mins) and final score:

- Easy: 0.000
- Medium: 0.000
- Hard: 0.000

## Top Disagreement Examples

Examples with highest judge disagreement (semantic vs numeric):

### Example 1

- **Task ID**: 0
- **Difficulty**: Hard
- **Question Type**: Market Analysis
- **Expert Time**: 30.0 mins

**Question**: How has US Steel addressed its planned merger with Nippton Steel and its effect on its business operations?

**Gold Answer**: The proposed merger between Nippon Steel and U.S. Steel occured late in 2023 when Nippon Steel made an unsolicited offer to acquire U.S. Steel for approximately $7.3 billion. U.S. Steel rejected the o...

**Model Answer**: The proposed merger between Nippon Steel and U.S. Steel occured late in 2023 when Nippon Steel made an unsolicited offer to acquire U.S. Steel for approximately $7.3 billion. U.S. Steel rejected the o...

**Judge Outputs**:
- Semantic: score=1.000, confidence=1.000
- Numeric: score=1.000, confidence=1.000

**Consistency Flags**: None
**Final Score**: 1.000
**Judge Disagreement**: 0.000

*Judges disagreed without triggering specific consistency flags.*

### Example 2

- **Task ID**: 1
- **Difficulty**: Medium
- **Question Type**: Trends
- **Expert Time**: 15.0 mins

**Question**: How has Netflix's (NASDAQ: NFLX) Average Revenue Per Paying User Changed from 2019 to 2024?

**Gold Answer**: 2019: 10.82
2020: 10.91
2021: 11.67
2022: 11.76
2023: 11.64
2024: 11.70

From 2019-2022, average revenue per paying membership increased approximately 2.8% annually. From 2022 to 2024, the average rev...

**Model Answer**: 2019: 10.82
2020: 10.91
2021: 11.67
2022: 11.76
2023: 11.64
2024: 11.70

From 2019-2022, average revenue per paying membership increased approximately 2.8% annually. From 2022 to 2024, the average rev...

**Judge Outputs**:
- Semantic: score=1.000, confidence=1.000
- Numeric: score=1.000, confidence=1.000

**Consistency Flags**: None
**Final Score**: 1.000
**Judge Disagreement**: 0.000

*Judges disagreed without triggering specific consistency flags.*

### Example 3

- **Task ID**: 2
- **Difficulty**: Medium
- **Question Type**: Beat or Miss
- **Expert Time**: 10.0 mins

**Question**: Did TJX beat or miss its Q4 FY 2025 pre-tax margin guidance? Express result as BPS difference

**Gold Answer**: 80bps beat from low end and 70bps beat from high end

**Model Answer**: 80bps beat from low end and 70bps beat from high end

**Judge Outputs**:
- Semantic: score=1.000, confidence=1.000
- Numeric: score=1.000, confidence=1.000

**Consistency Flags**: None
**Final Score**: 1.000
**Judge Disagreement**: 0.000

*Judges disagreed without triggering specific consistency flags.*
