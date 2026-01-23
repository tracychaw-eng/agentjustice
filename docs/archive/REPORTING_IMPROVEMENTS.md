# Reporting Improvements Summary

## Overview

This document summarizes the improvements made to AgentBeats Phase-1 reporting, diagnostics, and documentation. **No scoring logic or thresholds were changed.**

## Changes Implemented

### 1. Fixed Judge Agreement Metrics (Constant Variance Handling)

**File**: `reports/difficulty_analysis.py`

**Problem**: Easy tasks had constant scores (all 1.0), making correlation undefined, but reports showed misleading `0.000`.

**Fix**:
- Modified `analyze_judge_agreement()` to detect constant variance (std == 0)
- Returns `None` for correlation when either judge has constant scores
- Report displays "N/A (constant)" instead of numeric value
- Mean Diff and High Disagreement Rate still computed normally

**Code Changes**:
```python
# Detect constant variance
sem_std = np.std(semantic_scores)
num_std = np.std(numeric_scores)

if sem_std == 0.0 or num_std == 0.0:
    correlation = None  # Undefined - constant values
else:
    corr_val = np.corrcoef(semantic_scores, numeric_scores)[0, 1]
    correlation = float(corr_val) if not np.isnan(corr_val) else None
```

**Display**:
```markdown
| Easy | N/A (constant) | 0.000 | 0.0% |
```

---

### 2. Added Synthesis Section

**File**: `reports/difficulty_analysis.py`

**What**: Added a concise interpretive paragraph to the Difficulty-Stratified Analysis report.

**Content**:
- Explains difficulty is diagnostic only (no threshold adjustments)
- Describes score degradation from Easy → Medium → Hard
- Notes that Hard tasks show higher variance and disagreement (genuine ambiguity vs instability)
- Identifies flag patterns: `numeric_error` dominates Hard tasks, `wrong_metric` appears primarily in Hard

**Example**:
```markdown
## Synthesis

Scores degrade progressively from Easy to Medium to Hard, as expected for diagnostic
difficulty labels. Hard tasks show higher variance and increased judge disagreement,
suggesting genuine task ambiguity rather than evaluator instability. The `numeric_error`
flag dominates in harder tasks, while `wrong_metric` appears primarily in Hard buckets.
Difficulty is diagnostic only—no scoring thresholds are adjusted per difficulty level.
```

---

### 3. Added Top Disagreement Examples Section

**File**: `reports/difficulty_analysis.py`

**What**: New method `find_top_disagreement_examples()` and report section showing 1-3 concrete examples.

**Selection Criteria**:
- Highest judge disagreement (semantic vs numeric score difference)
- Boosted priority for tasks with `wrong_metric` or `numeric_error` flags

**Example Display** (per task):
- Task ID, Difficulty, Question Type, Expert Time
- Question (truncated to 200 chars)
- Gold Answer (truncated)
- Model Answer (truncated)
- Semantic judge: score + confidence
- Numeric judge: score + confidence + parsed values
- Consistency flags triggered
- Final hybrid score
- Judge disagreement magnitude
- Auto-generated explanation (derived from flags, not hallucinated)

**Example Output**:
```markdown
### Example 1

- **Task ID**: task_042
- **Difficulty**: Hard
- **Question Type**: Numeric
- **Expert Time**: 15 mins

**Question**: Calculate the compound interest on $1000...

**Gold Answer**: $1276.28

**Model Answer**: approximately $1280

**Judge Outputs**:
- Semantic: score=0.950, confidence=0.850
- Numeric: score=0.320, confidence=0.900
- Numeric parsed values: 1280

**Consistency Flags**: numeric_error
**Final Score**: 0.635
**Judge Disagreement**: 0.630

*Semantic judge passed but numeric judge found significant differences in numerical values.*
```

---

### 4. Track Type Labeling

**Files**: `reports/difficulty_analysis.py`, `reports/summary.py`, `scripts/run_evaluation.py`

**What**:
- Both report generators now accept `track_type` parameter ("Canonical" or "Adversarial")
- Reports clearly labeled with track type and dataset source
- Canonical and adversarial reports generated separately (never mixed)

**Changes**:
- `generate_report(track_type="Canonical")` added to both report classes
- Report titles: `# Evaluation Summary Report (Canonical)`
- Dataset labels: `**Dataset**: public_updated.csv` or `public_adversarial.jsonl`
- Separate file names:
  - `summary_report_<run_id>.md` (canonical)
  - `summary_report_adversarial_<run_id>.md` (adversarial)
  - `difficulty_analysis_<run_id>.md` (canonical)
  - `difficulty_analysis_adversarial_<run_id>.md` (adversarial)

---

### 5. Error Taxonomy Clarification

**File**: `reports/summary.py`

**What**: Added explanatory note to Error Taxonomy section.

**Content**:
```markdown
## Error Taxonomy

> **Note**: Error counts represent unrecovered judge failures logged in traces.
> Retries are handled internally; only persistent errors are counted.

- semantic_judge_error: 0
- numeric_judge_error: 2
```

This clarifies that the system handles retries internally and only reports hard (unrecovered) errors.

---

## Files Modified

1. **reports/difficulty_analysis.py**
   - Updated `analyze_judge_agreement()` return type to `Dict[str, Dict[str, Any]]`
   - Added constant variance detection (correlation = None)
   - Added `find_top_disagreement_examples()` method
   - Updated `generate_report()` to accept `track_type` parameter
   - Added Synthesis section
   - Added Top Disagreement Examples section
   - Fixed correlation display ("N/A (constant)")

2. **reports/summary.py**
   - Updated `generate_report()` to accept `track_type` parameter
   - Added dataset label display
   - Added error taxonomy clarification note

3. **scripts/run_evaluation.py**
   - Updated `generate_reports()` to pass `track_type` to report generators
   - Generate separate reports for canonical and adversarial tracks
   - Never mix canonical and adversarial data in reports

4. **README.md**
   - Updated "Output Artifacts" section with separate canonical/adversarial report files
   - Added "Difficulty-Stratified Analysis" subsection documenting new features
   - Documented synthesis section, N/A correlation handling, and top examples
   - Clarified that difficulty is diagnostic only

5. **REPORTING_IMPROVEMENTS.md** (this file)
   - New documentation summarizing all changes

---

## Validation Checklist

- [x] No scoring thresholds changed
- [x] No judge prompts/models changed
- [x] No hybrid score computation logic changed (only reporting additions)
- [x] Constant variance handled correctly (N/A display)
- [x] Synthesis section added (3-5 sentences)
- [x] Top disagreement examples added (1-3 examples)
- [x] Track type labeling implemented
- [x] Canonical and adversarial reports separated
- [x] Error taxonomy clarified
- [x] README updated with new features
- [x] No secrets leaked in examples (truncated outputs)
- [x] Auto-generated explanations use only logged fields (no hallucination)

---

## Testing Recommendations

1. **Run smoke test** to verify reports generate correctly:
   ```bash
   python scripts/run_evaluation.py --smoke-test
   ```

2. **Check artifacts/** directory for new report format:
   - Verify synthesis section appears
   - Verify "N/A (constant)" shows for Easy difficulty correlation
   - Verify top disagreement examples section exists
   - Verify track type labels are correct

3. **Run full canonical evaluation** (50 tasks):
   ```bash
   python scripts/run_evaluation.py --track canonical
   ```

4. **Inspect difficulty_analysis_<run_id>.md**:
   - Confirm Easy correlation shows "N/A (constant)"
   - Confirm 1-3 examples with highest disagreement
   - Confirm auto-generated explanations match flags

5. **Run adversarial track** (if applicable):
   ```bash
   python scripts/run_evaluation.py --track adversarial
   ```
   - Verify separate adversarial reports generated
   - Verify no mixing of canonical/adversarial data

---

## Expected Report Improvements

### Before
```markdown
## Judge Agreement

| Difficulty | Correlation | Mean Diff | High Disagreement Rate |
|------------|-------------|-----------|------------------------|
| Easy       | 0.000       | 0.000     | 0.0%                   |
```

### After
```markdown
## Synthesis

Scores degrade progressively from Easy to Medium to Hard...

## Judge Agreement

| Difficulty | Correlation     | Mean Diff | High Disagreement Rate |
|------------|-----------------|-----------|------------------------|
| Easy       | N/A (constant)  | 0.000     | 0.0%                   |

## Top Disagreement Examples

### Example 1
- **Task ID**: task_042
...
```

---

## Impact Summary

- **Better interpretability**: Synthesis section provides judge-facing narrative
- **Better auditability**: Top examples show concrete instances of disagreement
- **Less confusion**: "N/A (constant)" instead of misleading "0.000"
- **Better organization**: Track types clearly labeled, never mixed
- **Better error understanding**: Clarified that errors are unrecovered failures only

All improvements focus on **reporting and diagnostics** without changing evaluation behavior.
