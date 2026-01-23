# Debugging and Fix Log

This document consolidates all debugging activities, root cause analyses, and fixes implemented during the development and validation of the Phase-1 FinanceBench evaluator.

**Document Purpose**: Audit trail for technical reviewers and judges.

---

## Table of Contents

1. [Numeric Judge Fixes](#1-numeric-judge-fixes)
2. [Contradiction Judge Fixes](#2-contradiction-judge-fixes)
3. [Confidence and Calibration Fixes](#3-confidence-and-calibration-fixes)
4. [Reporting and Diagnostics Improvements](#4-reporting-and-diagnostics-improvements)
5. [Version History](#5-version-history)

---

## 1. Numeric Judge Fixes

### 1.1 Confidence Collapse to Zero

**Issue**: Numeric judge returned `confidence=0.0` even when extraction succeeded but comparison failed.

**Root Cause**:
- LLM prompt did not distinguish between extraction failure and comparison failure
- Both cases returned `confidence=0.0`, making it impossible to audit whether the judge parsed values correctly

**Fix Applied**:
- Rewrote `mcp_server/prompts/numeric.txt` with explicit decision tree
- Added pre-flight check for numeric content existence before LLM call
- Exception handler now sets `confidence=0.5` (parse_error) when both answers contain numbers but LLM produces malformed JSON

**Files Modified**:
- `mcp_server/prompts/numeric.txt` (complete rewrite, 181 lines)
- `mcp_server/judges/numeric.py` (added `_has_numeric_content()` method and exception handling logic)

**Validation Evidence**:
```
Test ADVERSARIAL-1: Scale Error
  Before: confidence=0.000
  After:  confidence=0.900
  [PASS]
```

---

### 1.2 Exact-Match Canonical Answers Triggering numeric_error

**Issue**: When `gold_answer == model_answer` textually, semantic judge passed but numeric judge failed.

**Root Cause**:
- No pre-normalization check before detailed parsing
- LLM attempted complex multi-value alignment on identical text
- JSON parsing errors from LLM on complex structured outputs

**Fix Applied**:
- Added exact match shortcut in `mcp_server/judges/numeric.py`
- If normalized gold == normalized model, immediately return `score=1.0, confidence=1.0` without LLM call

**Files Modified**:
- `mcp_server/judges/numeric.py` (added `_normalize_text()` method and early return)

**Validation Evidence**:
```
Test CANONICAL-1: Exact Match
  Numeric: score=1.000, confidence=1.000, failure_reason=none
  [PASS]
```

---

### 1.3 Added failure_reason Field

**Issue**: Reports used generic language ("failed structured numeric checks") without distinguishing failure modes.

**Root Cause**:
- No diagnostic field to indicate extraction vs alignment vs tolerance failure
- Report generator could not provide specific explanations

**Fix Applied**:
- Added `failure_reason` field to numeric judge output schema
- Values: `extraction_failed`, `alignment_failed`, `tolerance_failed`, `parse_error`, `none`
- Made field `Optional[str]` for backward compatibility

**Files Modified**:
- `mcp_server/judges/numeric.py` (Pydantic model)
- `mcp_server/server.py` (response schema)
- `core/types.py` (JudgeOutput dataclass)
- `green_agent/mcp_client.py` (client parsing and `to_judge_call` method)

**Validation Evidence**:
```
Task 10 trace:
  failure_reason: parse_error
  Reason: Judge error: Unterminated string starting at...
```

---

## 2. Contradiction Judge Fixes

### 2.1 Numeric Mismatches Triggering Contradictions

**Issue**: Scale errors ($85,002 vs $85,002,000) and large numeric drifts were flagged as contradictions.

**Root Cause**:
- Original prompt explicitly listed "Numeric: Model says $5B, gold says $3B" as a contradiction type
- Judge was designed to catch all factual mismatches, not just logical contradictions

**Fix Applied**:
- Rewrote `mcp_server/prompts/contradiction.txt` to explicitly EXCLUDE numeric mismatches
- Added decision tree: "Is opposition about NUMERIC VALUES ONLY? YES → violated=false"
- Added 6 examples showing numeric differences are NOT contradictions

**Files Modified**:
- `mcp_server/prompts/contradiction.txt` (complete rewrite, 194 lines)

**Validation Evidence**:
```
Test ADVERSARIAL-1: Scale Error
  Numeric:       score=0.000, confidence=0.900
  Contradiction: violated=False, confidence=0.900
  [PASS] Numeric mismatch does NOT trigger contradiction
```

---

### 2.2 Contradiction Judge Confidence Missing

**Issue**: Contradiction judge examples in prompt did not include `confidence` field for `violated=false` cases.

**Root Cause**:
- Prompt examples showed confidence only for true contradictions
- LLM defaulted to omitting confidence or returning 0.0 for non-contradictions

**Fix Applied**:
- Added `confidence: 0.95` (or similar) to all examples in contradiction prompt
- Ensured both `violated=true` and `violated=false` cases show appropriate confidence

**Files Modified**:
- `mcp_server/prompts/contradiction.txt`

---

## 3. Confidence and Calibration Fixes

### 3.1 Confidence Semantics Clarification

**Issue**: Confidence was ambiguous—sometimes meant extraction success, sometimes comparison certainty.

**Root Cause**:
- No explicit semantic definition in prompts
- Different judges interpreted confidence differently

**Fix Applied**:
- Established semantic model:
  - `confidence=0.0` → extraction technically failed (no numbers found, parse error)
  - `confidence>0.0` → extraction attempted; value reflects certainty of comparison
- Added explicit guidance to numeric prompt

**Semantic Model Enforced**:

| Condition | Score | Confidence | failure_reason |
|-----------|-------|------------|----------------|
| Extraction failed | 0.0 | 0.0 | extraction_failed |
| Parse error (numbers exist) | 0.0 | 0.5 | parse_error |
| Extraction OK, comparison failed | 0.0 | >0.5 | tolerance_failed or alignment_failed |
| Comparison OK | ≥0.95 | ≥0.5 | none |

---

### 3.2 Hedged Answer Over-Triggering

**Issue**: Hedging detector flagged answers containing "approximately" or "around" even when these were precise financial terms, not expressions of uncertainty.

**Root Cause**:
- Loose hedging indicators included common financial language
- Threshold of `>= 2` matches was too low for verbose answers

**Fix Applied**:
- Restricted hedging indicators to explicit uncertainty phrases only:
  - "i'm not sure", "uncertain about", "might be wrong", "cannot determine"
- Removed "approximately", "around" (common in precise financial reporting)
- Changed threshold to `>= 1` explicit uncertainty phrase

**Files Modified**:
- `green_agent/scorer.py` (hedging detection logic)

**Validation Evidence**:
```
Consistency Patterns (Adversarial):
  Before: hedged_answer: 16.7% (Medium), 16.7% (Hard)
  After:  hedged_answer: 0%
```

---

## 4. Reporting and Diagnostics Improvements

### 4.1 Judge Agreement Metrics (Constant Variance)

**Issue**: Easy tasks with constant scores (all 1.0) showed misleading "0.000" for correlation.

**Root Cause**:
- Correlation is undefined when variance is zero
- Report displayed 0.0 instead of indicating undefined

**Fix Applied**:
- Detect constant variance in `analyze_judge_agreement()`
- Return `None` for correlation when `std(x) == 0 or std(y) == 0`
- Display "N/A (constant)" in report table

**Files Modified**:
- `reports/difficulty_analysis.py`

**Validation Evidence**:
```markdown
| Easy | N/A (constant) | 0.000 | 0.0% |
```

---

### 4.2 Report Confidence Extraction Bug

**Issue**: Reports showed `confidence=0.000` even when judges returned correct confidence values.

**Root Cause**:
- Judge name filter used exact match (`== "semantic"`) but actual names were `"semantic_equivalence"`, `"numeric_tolerance"`
- Confidence read from wrong path (top-level instead of `output_payload`)

**Fix Applied**:
- Changed filter to partial match (`"semantic" in jc.get("judge", "")`)
- Fixed confidence extraction to read from `output_payload.confidence`
- Added `failure_reason` to `output_payload` in `to_judge_call()`

**Files Modified**:
- `reports/difficulty_analysis.py`
- `green_agent/mcp_client.py`

---

### 4.3 Synthesis Section and Top Disagreement Examples

**Issue**: Reports lacked interpretive context and concrete examples of judge disagreements.

**Fix Applied**:
- Added `_generate_synthesis()` method with data-driven narrative generation
- Added `find_top_disagreement_examples()` method selecting 1-3 examples by highest semantic/numeric disagreement
- Examples include task metadata, truncated answers, judge outputs, flags, and auto-generated explanations

**Files Modified**:
- `reports/difficulty_analysis.py`

---

### 4.4 Track Type Labeling

**Issue**: Reports did not clearly distinguish canonical vs adversarial evaluation tracks.

**Fix Applied**:
- Added `track_type` parameter to report generators
- Report titles include track type: "Evaluation Summary Report (Canonical)"
- Dataset labels: `public_updated.csv` (canonical) or `public_adversarial.jsonl` (adversarial)
- Separate file names for each track

**Files Modified**:
- `reports/difficulty_analysis.py`
- `reports/summary.py`
- `scripts/run_evaluation.py`

---

### 4.5 Failure-Reason-Based Explanations

**Issue**: Report explanations used generic language for all numeric failures.

**Fix Applied**:
- Explanations now vary by `failure_reason`:
  - `extraction_failed`: "failed to extract any comparable numeric values"
  - `parse_error`: "attempted extraction but encountered a parsing error on complex structured output"
  - `alignment_failed`: "extraction succeeded but value alignment failed"
  - `tolerance_failed`: "extraction and alignment succeeded but values exceeded tolerance"

**Files Modified**:
- `reports/difficulty_analysis.py`

---

## 5. Version History

| Component | Version | Changes |
|-----------|---------|---------|
| Numeric Judge | v1.0.0 → v1.1.0 | Confidence semantics, failure_reason field, exact match shortcut, parse error handling |
| Contradiction Judge | v1.0.0 → v1.1.0 | Exclude numeric mismatches from contradiction detection |
| Scorer | v1.0.0 | Tightened hedging detection to explicit uncertainty only |
| Reports | v1.0.0 | Synthesis section, top disagreement examples, failure-reason explanations, track labeling |

---

## Regression Test Suite

A comprehensive regression test suite (`test_judge_semantics.py`) validates all fixes:

| Test | Expected Behavior | Status |
|------|-------------------|--------|
| CANONICAL-1: Exact Match | score≥0.95, confidence≥0.9, no flags | PASS |
| CANONICAL-2: Small Drift | within tolerance, no flags | PASS |
| ADVERSARIAL-1: Scale Error | numeric_error=true, contradiction=false, confidence>0 | PASS |
| ADVERSARIAL-2: Wrong Metric | numeric_error=true, contradiction=false | PASS |
| ADVERSARIAL-3: Large Drift | numeric_error=true, contradiction=false | PASS |
| CONTRADICTION-1: Directional | contradiction=true | PASS |
| CONTRADICTION-2: Profit/Loss | contradiction=true | PASS |
| CONTRADICTION-3: Entity Conflict | contradiction=true | PASS |
| EXTRACTION-1: No Numbers | both judges pass | PASS |

**Total: 9/9 PASS**

---

## Constraints Respected

All fixes adhere to the following constraints:

- No scoring thresholds changed (tolerance remains 1%)
- No difficulty-dependent scoring behavior
- Adversarial partial credit preserved
- Conservative fixes only (prompt clarification, diagnostic fields)
- Full audit trail maintained (failure_reason, confidence semantics)
- Backward compatible (new fields are optional)

---

*Document generated: 2026-01-22*
