# Difficulty-Stratified Analysis (Canonical)

**Dataset**: public_updated.csv

> **Note**: Difficulty is used for diagnostic analysis only.
> Scoring thresholds are NOT adjusted per difficulty.

## Score Distribution by Difficulty

| Difficulty | N | Mean | Std | Min | Max |
|------------|---|------|-----|-----|-----|
| Easy | 5 | 1.000 | 0.000 | 1.000 | 1.000 |
| Medium | 5 | 0.830 | 0.024 | 0.800 | 0.850 |
| Hard | 5 | 0.570 | 0.117 | 0.350 | 0.700 |

## Synthesis

Scores degrade progressively from Easy to Medium to Hard, as expected for diagnostic difficulty labels. Hard tasks show higher variance and increased judge disagreement, suggesting genuine task ambiguity rather than evaluator instability. The `numeric_error` flag dominates in harder tasks, while `wrong_metric` appears primarily in Hard buckets. Difficulty is diagnostic only—no scoring thresholds are adjusted per difficulty level.

## Consistency Patterns

### Easy

- No consistency flags triggered

### Medium

- No consistency flags triggered

### Hard

- numeric_error: 40.0%
- wrong_metric: 20.0%

## Judge Agreement

| Difficulty | Correlation | Mean Diff | High Disagreement Rate |
|------------|-------------|-----------|------------------------|
| Easy | N/A (constant) | 0.000 | 0.0% |
| Medium | -1.000 | 0.140 | 0.0% |
| Hard | -0.502 | 0.340 | 40.0% |

## Expert Time Correlation

Correlation between expert time (mins) and final score:

- Easy: 0.000
- Medium: 0.000
- Hard: 0.000

## Top Disagreement Examples

Examples with highest judge disagreement (semantic vs numeric):

### Example 1

- **Task ID**: hard_0
- **Difficulty**: Hard
- **Question Type**: Complex
- **Expert Time**: 15 mins

**Question**: Analyze the complex multi-step problem 0 involving multiple constraints and edge cases that require careful consideration and numerical precision

**Gold Answer**: The answer involves multiple steps: step 1 gives 200, step 2 adjusts to 210, final result is 220

**Model Answer**: After analysis, the result is approximately 222, with some uncertainty in the final digits

**Judge Outputs**:
- Semantic: score=0.900, confidence=0.750
- Numeric: score=0.300, confidence=0.880
- Numeric parsed values: 222

**Consistency Flags**: numeric_error
**Final Score**: 0.600
**Judge Disagreement**: 0.600

*Semantic judge passed but numeric judge found significant differences in numerical values.*

### Example 2

- **Task ID**: hard_1
- **Difficulty**: Hard
- **Question Type**: Complex
- **Expert Time**: 15 mins

**Question**: Analyze the complex multi-step problem 1 involving multiple constraints and edge cases that require careful consideration and numerical precision

**Gold Answer**: The answer involves multiple steps: step 1 gives 201, step 2 adjusts to 211, final result is 221

**Model Answer**: After analysis, the result is approximately 223, with some uncertainty in the final digits

**Judge Outputs**:
- Semantic: score=0.300, confidence=0.750
- Numeric: score=0.900, confidence=0.880
- Numeric parsed values: 223

**Consistency Flags**: wrong_metric
**Final Score**: 0.600
**Judge Disagreement**: 0.600

*Numeric judge passed but semantic judge identified semantic mismatch, suggesting focus on wrong evaluation metric.*

### Example 3

- **Task ID**: hard_2
- **Difficulty**: Hard
- **Question Type**: Complex
- **Expert Time**: 15 mins

**Question**: Analyze the complex multi-step problem 2 involving multiple constraints and edge cases that require careful consideration and numerical precision

**Gold Answer**: The answer involves multiple steps: step 1 gives 202, step 2 adjusts to 212, final result is 222

**Model Answer**: After analysis, the result is approximately 224, with some uncertainty in the final digits

**Judge Outputs**:
- Semantic: score=0.700, confidence=0.750
- Numeric: score=0.500, confidence=0.880
- Numeric parsed values: 224

**Consistency Flags**: numeric_error
**Final Score**: 0.600
**Judge Disagreement**: 0.200

*Semantic judge passed but numeric judge found significant differences in numerical values.*
