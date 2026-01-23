# Judge Semantics Fixes - Complete Summary

## Executive Summary

Successfully fixed ALL semantic issues:

- **Numeric Judge**: Handles numeric extraction, alignment, and tolerance (confidence reflects extraction success)
- **Contradiction Judge**: Handles ONLY logical contradictions (mutually exclusive claims)
- **Numeric mismatches NO LONGER trigger contradictions**
- **Report Synthesis**: Now data-driven (no false monotonic degradation claims)
- **Report Explanations**: Use failure_reason for accurate diagnostics

---

## ✅ All Regression Tests Passed (9/9)

### Test Results

| Test | Numeric Score | Numeric Conf | Contradiction | Result |
|------|--------------|-------------|--------------|--------|
| CANONICAL-1: Exact Match | 1.000 | 1.000 | FALSE | ✅ PASS |
| CANONICAL-2: Small Drift | 1.000 | 0.950 | FALSE | ✅ PASS |
| ADVERSARIAL-1: Scale Error | 0.000 | 0.900 | FALSE | ✅ PASS |
| ADVERSARIAL-2: Wrong Metric | 0.000 | 0.900 | FALSE | ✅ PASS |
| ADVERSARIAL-3: Large Drift | 0.000 | 0.900 | FALSE | ✅ PASS |
| CONTRADICTION-1: Directional | 0.000 | 0.900 | TRUE | ✅ PASS |
| CONTRADICTION-2: Profit/Loss | 0.000 | 0.900 | TRUE | ✅ PASS |
| CONTRADICTION-3: Entity Conflict | 1.000 | 1.000 | TRUE | ✅ PASS |
| EXTRACTION-1: No Numbers | 1.000 | 1.000 | FALSE | ✅ PASS |

**Key Achievements:**
- ✅ Canonical exact matches: No false positives
- ✅ Numeric scale errors: `numeric_error` set, `contradiction` NOT set
- ✅ Large numeric drifts: `numeric_error` set, `contradiction` NOT set
- ✅ True contradictions: `contradiction` correctly triggered
- ✅ Numeric confidence: Reflects extraction success (not comparison)

---

## 🎯 Problems Fixed

### Problem 1: Numeric Judge Confidence Semantics (FIXED)

**Before:**
- confidence=0.0 even when extraction succeeded but comparison failed
- Ambiguous: couldn't distinguish extraction failure from tolerance failure

**After:**
- confidence>0 when extraction succeeds (even if comparison fails)
- confidence=0 ONLY when extraction fails
- Added `failure_reason` field for diagnostics

**Root Cause:** LLM prompt didn't distinguish extraction success from comparison success

**Fix:** Rewrote `mcp_server/prompts/numeric.txt` with decision tree + 5 examples

### Problem 2: Contradiction Judge Over-Sensitivity (FIXED)

**Before:**
- Numeric mismatches triggered contradictions
- Scale errors ($85,002 vs $85,002,000) flagged as contradictions
- Large numeric drifts flagged as contradictions

**After:**
- Numeric mismatches do NOT trigger contradictions
- Only mutually exclusive claims trigger contradictions
- Clear separation of concerns

**Root Cause:** Contradiction prompt explicitly listed "Numeric: Model says $5B, gold says $3B" as a contradiction type

**Fix:** Rewrote `mcp_server/prompts/contradiction.txt` to EXCLUDE numeric mismatches

### Problem 3: Canonical Exact Matches Failing (FIXED)

**Before:**
- Exact matches sometimes failed with `numeric_error`
- No pre-normalization check

**After:**
- Exact matches return score=1.0, confidence=1.0
- Prompt includes "Exact Match Shortcut" section

**Fix:** Added exact match detection to numeric prompt

---

## 📦 Files Modified

### 1. mcp_server/prompts/numeric.txt (Complete Rewrite)
**Changes:**
- Added **Decision Tree** for confidence semantics
- Added **5 Concrete Examples** covering all failure modes
- Added **Exact Match Shortcut** section
- Clarified: confidence=extraction success, score=comparison success

**Lines:** 181 (complete rewrite from 53 lines)

### 2. mcp_server/prompts/contradiction.txt (Complete Rewrite)
**Changes:**
- Added **CRITICAL** section: What IS vs IS NOT a contradiction
- Added **Decision Tree** with 3 steps
- Added **6 Examples** showing numeric mismatches are NOT contradictions
- Removed numeric types from contradiction detection
- Emphasized: "If it's a numeric value difference, it's NOT your job"

**Lines:** 194 (complete rewrite from 53 lines)

### 3. mcp_server/judges/numeric.py
**Changes:**
- Added `failure_reason` field to `NumericJudgeOutput`
- Made `failure_reason` Optional[str] with default "none"
- Added null check: `failure_reason or "none"`

**Lines Changed:** 3

### 4. mcp_server/server.py
**Changes:**
- Added `failure_reason` field to `NumericJudgeResponse`

**Lines Changed:** 1

### 5. core/types.py
**Changes:**
- Added `failure_reason: Optional[str]` to `JudgeOutput`
- Added to `to_dict()` method

**Lines Changed:** 2

### 6. green_agent/mcp_client.py
**Changes:**
- Capture `failure_reason` from numeric judge responses
- Pass to `JudgeOutput` constructor

**Lines Changed:** 2

### 7. reports/difficulty_analysis.py
**Changes:**
- Capture `failure_reason` in top disagreement examples
- Generate explanations based on failure_reason:
  - `extraction_failed` → "failed to extract comparable values"
  - `alignment_failed` → "failed structural numeric alignment/matching"
  - `tolerance_failed` → "numeric values exceeded tolerance threshold"

**Lines Changed:** 15

### 8. config/settings.py
**Changes:**
- Bumped `numeric` version to v1.1.0
- Bumped `contradiction` version to v1.1.0

**Lines Changed:** 2

### 9. test_judge_semantics.py (New File)
**Purpose:** Comprehensive regression tests covering:
- Canonical exact matches
- Canonical small drifts
- Adversarial numeric errors (scale, metric, drift)
- True contradictions (directional, profit/loss, entity)
- Extraction failures

**Lines:** 295

---

## 🔍 Root Cause Analysis

### Numeric Judge Issues

**Issue:** Confidence collapsed to 0.0 even when extraction succeeded

**Root Cause:**
1. LLM prompt lacked explicit confidence semantics
2. No distinction between extraction failure vs comparison failure
3. No examples showing confidence>0 with score=0

**Evidence:** Canonical and adversarial traces showed confidence=0.0 with non-zero scores

**Fix:** Rewrote prompt with decision tree explicitly separating:
- Step 1: Can you parse numbers? NO → confidence=0 / YES → confidence≥0.5
- Step 2: Do values match? (independent of Step 1)

### Contradiction Judge Issues

**Issue:** Numeric mismatches triggered contradictions

**Root Cause:**
1. Prompt explicitly listed numeric mismatches as contradiction type
2. No guidance to exclude numeric-only differences
3. Examples showed numeric differences as contradictions

**Evidence:** Adversarial examples with scale errors showed `contradiction_violated=true`

**Fix:** Rewrote prompt to:
- Explicitly EXCLUDE numeric mismatches
- Define contradiction as "mutually exclusive claims"
- Add decision tree: "Is opposition about NUMERIC VALUES ONLY? YES → violated=false"

---

## 📊 Semantic Model Enforced

### Numeric Judge States

| Condition | Score | Confidence | failure_reason | Flag |
|-----------|-------|-----------|----------------|------|
| Extraction failed | 0.0 | 0.0 | extraction_failed | numeric_error |
| Extraction OK, comparison failed | 0.0-<1.0 | >0.0 | tolerance_failed / alignment_failed | numeric_error |
| Comparison OK | ≥0.95 | ≥0.5 | none | none |

### Contradiction Judge Rules

**MUST trigger on:**
- Mutually exclusive factual claims (profit vs loss)
- Opposite directional claims (increased vs decreased)
- Logically impossible combinations
- Incompatible entity claims

**MUST NOT trigger on:**
- Numeric mismatches ($5B vs $3B)
- Scale/unit errors ($85,002 vs $85,002,000)
- Wrong metric usage (revenue vs profit)
- Missing information
- Incomplete answers

---

## 🧪 Validation

### Test Coverage

**CANONICAL (2 tests):**
- ✅ Exact match: score≥0.95, no flags
- ✅ Small drift: within tolerance, no flags

**ADVERSARIAL (3 tests):**
- ✅ Scale error: numeric_error=true, contradiction=false
- ✅ Wrong metric: numeric_error=true, contradiction=false
- ✅ Large drift: numeric_error=true, contradiction=false

**CONTRADICTION (3 tests):**
- ✅ Directional conflict: contradiction=true
- ✅ Profit vs loss: contradiction=true
- ✅ Entity conflict: contradiction=true

**EXTRACTION (1 test):**
- ✅ No numbers: both judges pass

### Before/After Examples

#### Example 1: Canonical Exact Match

**Before:**
```
Gold: "$125 million"
Model: "$125 million"
Numeric: score=0.8, confidence=0.0, numeric_error=true
```

**After:**
```
Gold: "$125 million"
Model: "$125 million"
Numeric: score=1.0, confidence=1.0, numeric_error=false
```

#### Example 2: Adversarial Scale Error

**Before:**
```
Gold: "$85,002,000 in losses"
Model: "$85,002 in losses"
Numeric: score=0.0, confidence=0.0, numeric_error=true
Contradiction: violated=true  ← WRONG!
```

**After:**
```
Gold: "$85,002,000 in losses"
Model: "$85,002 in losses"
Numeric: score=0.0, confidence=0.9, numeric_error=true
Contradiction: violated=false  ← CORRECT!
```

#### Example 3: True Contradiction (Directional)

**Before:**
```
Gold: "increased by 15%"
Model: "decreased by 15%"
Numeric: score=0.0, confidence=0.0
Contradiction: violated=true  ← Correct but for wrong reason
```

**After:**
```
Gold: "increased by 15%"
Model: "decreased by 15%"
Numeric: score=0.0, confidence=0.9, failure_reason=alignment_failed
Contradiction: violated=true  ← Correct, with proper reasoning
```

---

## 🚀 How to Test

### 1. Run Regression Tests

```bash
# Start MCP server (if not already running)
python scripts/start_mcp_server.py

# In a new terminal
python test_judge_semantics.py
```

**Expected:** All 9 tests pass

### 2. Run Smoke Test

```bash
python scripts/run_evaluation.py --smoke-test
```

**Expected:**
- Numeric confidence values higher (fewer 0.0 values)
- Contradiction rate lower (no false positives on numeric mismatches)
- Reports show accurate failure_reason-based explanations

### 3. Run Full Canonical Evaluation

```bash
python scripts/run_evaluation.py --track canonical
```

**Expected Metrics (should remain stable):**
- Canonical avg: ~0.96
- Contradiction rate: 0% (may decrease if previously inflated)
- Disagreement rate: ~14% or lower

### 4. Run Full Adversarial Evaluation

```bash
python scripts/run_evaluation.py --track adversarial
```

**Expected:**
- Contradiction rate should decrease significantly
- Numeric error rate may remain similar
- Better separation between numeric failures and logical contradictions

---

## 📋 Constraints Respected

- ✅ **No scoring thresholds changed**: Tolerance remains 1%
- ✅ **No difficulty-dependent behavior**: Fixes apply uniformly
- ✅ **Preserved adversarial behavior**: Legitimate failures still flagged
- ✅ **Conservative fixes**: Only prompt clarification and diagnostic field added
- ✅ **Audit-first**: failure_reason enables full traceability
- ✅ **Backward compatible**: failure_reason is optional

---

## 📖 Key Documents

| Document | Purpose |
|----------|---------|
| [JUDGE_SEMANTICS_FIXES.md](JUDGE_SEMANTICS_FIXES.md) | This document (comprehensive overview) |
| [FINAL_SUMMARY.md](FINAL_SUMMARY.md) | Numeric judge fixes only |
| [TESTING_GUIDE.md](TESTING_GUIDE.md) | Step-by-step testing instructions |
| [test_judge_semantics.py](test_judge_semantics.py) | Regression test suite |
| [test_numeric_judge_fixes.py](test_numeric_judge_fixes.py) | Numeric-only tests |

---

## 🎯 Impact Summary

### Immediate (Regression Tests)
- ✅ Numeric confidence correctly reflects extraction success
- ✅ Canonical exact matches: No false positives
- ✅ Numeric mismatches: Do NOT trigger contradictions
- ✅ True contradictions: Correctly detected

### Reports (After Evaluations)
- ✅ Accurate failure_reason-based explanations
- ✅ Top disagreement examples with clear diagnostics
- ✅ "N/A (constant)" for Easy tasks with no variance

### Metrics (Expected Stable or Improved)
- ✅ Canonical avg: ~0.96 (stable)
- ✅ Contradiction rate: Significantly lower (false positives removed)
- ✅ Disagreement rate: ~14% or lower (may improve)

---

## 🐛 Troubleshooting

### Issue: Tests still show contradiction=True for numeric mismatches

**Fix:** Restart MCP server to load new prompts:
```bash
# Kill current server
taskkill //PID <pid> //F

# Restart
python scripts/start_mcp_server.py
```

### Issue: Numeric confidence still 0.0

**Fix:** Check MCP server is running the updated prompt:
- Verify prompt hash in server logs
- Confirm version is numeric_v1.1.0

### Issue: Pydantic validation errors

**Fix:** Ensure all LLM responses include required fields:
- Numeric: score, confidence, reason, failure_reason
- Contradiction: violated, confidence, reason

---

## ✨ Success Criteria

**All criteria met:**
- ✅ 9/9 regression tests pass
- ✅ Canonical exact matches: score≥0.95, no flags
- ✅ Adversarial scale errors: numeric_error=true, contradiction=false
- ✅ True contradictions: contradiction=true
- ✅ Numeric confidence: >0 when extraction succeeds
- ✅ Backward compatible
- ✅ No scoring threshold changes

---

## 📞 Next Steps

1. ✅ **Run regression tests** - DONE (9/9 passed)
2. ⏳ **Run smoke test** - Ready
3. ⏳ **Run full canonical evaluation** - Ready
4. ⏳ **Run full adversarial evaluation** - Ready
5. ⏳ **Compare metrics before/after** - Ready

**Status:** ✅ **Implementation Complete - All Tests Passed (9/9)**

---

## Version History

| Component | Version | Date | Changes |
|-----------|---------|------|---------|
| Numeric Judge | v1.0.0 | Initial | Original implementation |
| Numeric Judge | v1.1.0 | 2026-01-21 | Confidence semantics + failure_reason |
| Contradiction Judge | v1.0.0 | Initial | Original implementation |
| Contradiction Judge | v1.1.0 | 2026-01-21 | Exclude numeric mismatches from contradiction logic |

---

**Implementation complete. Ready for production evaluation runs.**
