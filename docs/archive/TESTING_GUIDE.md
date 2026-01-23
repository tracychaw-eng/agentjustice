# Testing Guide: Numeric Judge Fixes

## Current Status

✅ **Code Changes Complete**:
- Prompt rewritten with decision tree + examples
- `failure_reason` field added (made optional for backward compatibility)
- Report wording updated to use failure_reason
- Regression test suite created

⚠️ **MCP Server Must Be Restarted** to pick up new prompt

---

## Step-by-Step Testing Instructions

### Step 1: Stop Current MCP Server

If the MCP server is running in a terminal, stop it:

```bash
# In the terminal running the MCP server
Press Ctrl+C
```

**Expected output**:
```
Shutting down...
```

### Step 2: Restart MCP Server with New Prompt

```bash
cd c:\Users\zou0010\.gemini\antigravity\scratch\agentbeats
python scripts/start_mcp_server.py
```

**Expected output**:
```
============================================================
AgentBeats MCP Judge Server
============================================================
Host: localhost
Port: 8001

Available endpoints:
  POST /judge/semantic_equivalence
  POST /judge/numeric_tolerance
  POST /judge/contradiction
  GET  /health
  GET  /version
  GET  /mcp/tools
============================================================
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://localhost:8001 (Press CTRL+C to quit)
```

**Keep this terminal open!** The server must stay running for tests.

### Step 3: Run Regression Tests (in a NEW terminal)

Open a **new terminal window** and run:

```bash
cd c:\Users\zou0010\.gemini\antigravity\scratch\agentbeats
python test_numeric_judge_fixes.py
```

**Expected output**:
```
======================================================================
  Numeric Judge Confidence Semantics Regression Tests
======================================================================

Checking MCP server health...
[PASS] MCP server is healthy

Test 1: Case 1: Extraction Failed (no numbers)
----------------------------------------------------------------------
  Result:
    score: 1.000
    confidence: 1.000
    failure_reason: none
  [PASS]

Test 2: Case 2: Extraction Success, Comparison Failed (tolerance)
----------------------------------------------------------------------
  Result:
    score: 0.000
    confidence: 0.850
    failure_reason: tolerance_failed
  [PASS]

... (tests 3-6) ...

======================================================================
  Test Summary
======================================================================

Total: 6
Passed: 6
Failed: 0

[SUCCESS] All tests passed!
```

---

## What Each Test Validates

| Test | Scenario | Expected Behavior |
|------|----------|------------------|
| 1 | No numbers in answers | score=1.0, confidence=1.0, failure_reason="none" |
| 2 | Values don't match | score=0.0, confidence>0.5, failure_reason="tolerance_failed" |
| 3 | Values match within tolerance | score≥0.95, confidence>0.5, failure_reason="none" |
| 4 | Exact text match | score=1.0, confidence=1.0, failure_reason="none" |
| 5 | Multi-value alignment issue | score≈0.5, confidence>0.5, failure_reason="alignment_failed" |
| 6 | Canonical exact match | score≥0.95, confidence>0.9, failure_reason="none" |

---

## If Tests Still Fail

### Symptom: 422 Unprocessable Entity errors

**Cause**: MCP server still running old code

**Fix**:
1. Stop MCP server (Ctrl+C)
2. Wait 2-3 seconds
3. Restart: `python scripts/start_mcp_server.py`
4. Run tests again

### Symptom: All tests return confidence=0.0

**Cause**: LLM not following new prompt

**Fix**: Check MCP server terminal for errors during judge calls. The new prompt should be loaded (look for the updated prompt hash in logs).

### Symptom: Tests pass but values unexpected

**Fix**: This is fine - the LLM has some variability. Key checks:
- When no numbers exist, confidence should NOT be 0.0
- When extraction succeeds, confidence should be > 0
- failure_reason should match extraction vs comparison outcome

---

## After Tests Pass

### Step 4: Run Smoke Test

```bash
python scripts/run_evaluation.py --smoke-test
```

**Expected**:
- 3 tasks evaluated
- Non-zero average score
- No systematic judge errors
- Reports generated in `artifacts/`

**What to Check**:
- Numeric judge confidence values should be higher (fewer 0.0 values)
- `failure_reason` field appears in judge calls
- Report explanations use failure_reason-based language

### Step 5: Inspect Generated Reports

```bash
# List recent artifacts
ls artifacts | Sort-Object LastWriteTime -Descending | Select-Object -First 5

# View difficulty analysis report
notepad artifacts/difficulty_analysis_<run_id>.md
```

**Look For**:
1. **Judge Agreement section**: "N/A (constant)" for Easy tasks
2. **Top Disagreement Examples section**: Present with 1-3 examples
3. **Failure-reason explanations**: Should say things like:
   - "failed structural numeric alignment/matching" (alignment_failed)
   - "numeric values exceeded tolerance threshold" (tolerance_failed)
   - "failed to extract comparable values" (extraction_failed)

### Step 6: Run Full Canonical Evaluation (Optional)

```bash
python scripts/run_evaluation.py --track canonical
```

**Expected Metrics** (should remain stable):
- Canonical avg: ~0.96
- Contradiction rate: 0%
- Disagreement rate: ~14% (may decrease slightly with fewer false positives)

**Time**: ~5-10 minutes for 50 tasks

---

## Troubleshooting

### Issue: "No module named 'openai'"

**Fix**:
```bash
python -m pip install --user openai anthropic python-dotenv
```

### Issue: "OPENAI_API_KEY not set"

**Fix**:
```powershell
$env:OPENAI_API_KEY="sk-your-key-here"
```

Or create `.env` file:
```
OPENAI_API_KEY=sk-your-key-here
```

### Issue: MCP server won't start

**Check**:
1. Port 8001 not already in use: `netstat -ano | findstr :8001`
2. Python packages installed: `python -c "import fastapi, uvicorn; print('OK')"`

---

## Success Criteria

✅ **All regression tests pass** (6/6)

✅ **Smoke test shows**:
- Numeric confidence > 0 when extraction succeeds
- failure_reason correctly set
- No systematic errors

✅ **Reports contain**:
- "N/A (constant)" for Easy correlation
- Top Disagreement Examples section
- Failure-reason-based explanations

✅ **Metrics stable**:
- Canonical avg ≈ 0.96
- No performance regression

---

## Quick Reference

```bash
# Terminal 1: Start MCP server
cd c:\Users\zou0010\.gemini\antigravity\scratch\agentbeats
python scripts/start_mcp_server.py

# Terminal 2: Run tests
cd c:\Users\zou0010\.gemini\antigravity\scratch\agentbeats
python test_numeric_judge_fixes.py
python scripts/run_evaluation.py --smoke-test
python scripts/run_evaluation.py --track canonical

# View reports
ls artifacts | Sort-Object LastWriteTime -Descending | Select-Object -First 5
```

---

## Contact

If tests fail after following all steps, check:
1. [NUMERIC_JUDGE_FIXES.md](NUMERIC_JUDGE_FIXES.md) - Detailed fix documentation
2. [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) - Implementation checklist
3. MCP server logs for error messages during judge calls
