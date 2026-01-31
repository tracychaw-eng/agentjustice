# Difficulty-Stratified Analysis (Adversarial)

**Dataset**: public_adversarial.jsonl

> **Note**: Difficulty is used for diagnostic analysis only.
> Scoring thresholds are NOT adjusted per difficulty.

## Score Distribution by Difficulty

| Difficulty | N | Mean | Std | Min | Max |
|------------|---|------|-----|-----|-----|
| Easy | 6 | 0.220 | 0.368 | 0.000 | 1.000 |
| Medium | 6 | 0.261 | 0.370 | 0.000 | 0.810 |
| Hard | 6 | 0.345 | 0.412 | 0.000 | 1.000 |

## Synthesis

Score patterns across difficulty levels reflect transformation-specific characteristics rather than strict monotonic degradation. This is expected for adversarial datasets where difficulty labels indicate transformation complexity, not necessarily model performance degradation. The `numeric_error` flag indicates extraction or tolerance failures, while `contradiction_violated` indicates mutually exclusive factual claims (not numeric mismatches). Small sample sizes per difficulty level limit statistical significance. Difficulty is diagnostic only—no scoring thresholds are adjusted per difficulty level.

## Consistency Patterns

### Easy

- contradiction_violated: 16.7%
- numeric_error: 16.7%

### Medium

- contradiction_violated: 16.7%
- numeric_error: 33.3%
- wrong_metric: 16.7%

### Hard

- numeric_error: 16.7%

## Judge Agreement

| Difficulty | Correlation | Mean Diff | High Disagreement Rate |
|------------|-------------|-----------|------------------------|
| Easy | 0.632 | 0.167 | 16.7% |
| Medium | -0.463 | 0.573 | 66.7% |
| Hard | 0.581 | 0.250 | 33.3% |

## Expert Time Correlation

Correlation between expert time (mins) and final score:

- Easy: 0.423
- Medium: -0.316
- Hard: 0.081

## Top Disagreement Examples

Examples with highest judge disagreement (semantic vs numeric):

### Example 1

- **Task ID**: 6
- **Difficulty**: Easy
- **Question Type**: Numerical Reasoning
- **Expert Time**: 5.0 mins

**Question**: What is the total value of MSCI's operating leases (in $'s, thousands) that are maturing in the next three years? What percentage?

**Gold Answer**: In thousands:

$85,002 which is 51.3% of leases

**Model Answer**: In thousands:

$85,002,000 which is 51.3% of leases

**Judge Outputs**:
- Semantic: score=1.000, confidence=0.900
- Numeric: score=0.000, confidence=0.900

**Consistency Flags**: numeric_error
**Final Score**: 0.320
**Judge Disagreement**: 1.000

*Numeric extraction succeeded but value alignment failed (e.g., unordered KPI lists, multi-field rows).*

### Example 2

- **Task ID**: 10
- **Difficulty**: Medium
- **Question Type**: Qualitative Retrieval
- **Expert Time**: 10.0 mins

**Question**: List the Operating KPIs Spirit Airlines (NYSE: SAVE) tracked in FY 2024. Provide the KPI and FY 2024 Total.

**Gold Answer**: Average aircraft: 209.9
Aircraft at end of period: 213
Average daily aircraft utilization (hours): 9.9
Departures: 288,180
Passenger flight segments (PFSs): 44,180,000
Revenue passenger miles (RPMs): ...

**Model Answer**: Average aircraft: 209.9
Aircraft at end of period: 213
Average daily aircraft utilization (hours): 9.9
Departures: 288,180
Passenger flight segments (PFSs): 44,180,000
Revenue passenger miles (RPMs): ...

**Judge Outputs**:
- Semantic: score=1.000, confidence=0.950
- Numeric: score=0.000, confidence=0.500

**Consistency Flags**: numeric_error
**Final Score**: 0.810
**Judge Disagreement**: 1.000

*Numeric judge attempted extraction but encountered a parsing error on complex structured output.*

### Example 3

- **Task ID**: 11
- **Difficulty**: Hard
- **Question Type**: Financial Modeling
- **Expert Time**: 60.0 mins

**Question**: Assuming normal March seasonality over last three years, will TSM beat or miss Q2 guidance and by how much?
Show work.

**Gold Answer**: Q1 2025 guidance (USD): $25.0B to $25.4B
Q1 2025 guidance (NT$ at 32.9): 833,120

February to March revenue growth rate 2022: 17.0%
February to March revenue growth rate 2023: 10.9%
February to March ...

**Model Answer**: Q1 2025 guidance (USD): $25.0B to $25.4B
Q1 2025 guidance (NT$ at 32.9): 833,120

February to March revenue growth rate 2022: 17.0%
February to March revenue growth rate 2023: 10.9%
February to March ...

**Judge Outputs**:
- Semantic: score=1.000, confidence=0.900
- Numeric: score=0.000, confidence=0.500

**Consistency Flags**: numeric_error
**Final Score**: 0.820
**Judge Disagreement**: 1.000

*Numeric judge attempted extraction but encountered a parsing error on complex structured output.*
