# Quick Start Guide

Get AgentBeats Phase-1 evaluation running in 5 minutes.

## Prerequisites

- Python 3.8+
- OpenAI API key

## Step 1: Install Dependencies

```powershell
# Install missing packages to user directory (avoids permission issues)
python -m pip install --user openai anthropic python-dotenv

# Verify installation
python -c "import openai, anthropic; print('Success! Packages installed.')"
```

## Step 2: Set OpenAI API Key

```powershell
# Option A: Set environment variable for current session
$env:OPENAI_API_KEY="sk-your-actual-key-here"

# Option B: Create .env file (persists across sessions)
# Create a file named .env in the project root with:
# OPENAI_API_KEY=sk-your-actual-key-here
```

## Step 3: Test Without MCP Server

First, verify the evaluation script runs (it will fail, but that's expected):

```powershell
python scripts/run_evaluation.py --preflight
```

**Expected output:**
```
[1/5] Checking health endpoint...
  [ERROR] Health check error: [WinError 10061] No connection could be made...

Overall Status: FAIL
```

This is normal - the MCP server isn't running yet.

## Step 4: Start MCP Server

Open a **NEW terminal window** and start the MCP judge server:

```powershell
# Terminal 1 (keep this running)
cd c:\Users\zou0010\.gemini\antigravity\scratch\agentbeats
python scripts/start_mcp_server.py
```

**Expected output:**
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

**Leave this terminal running!**

## Step 5: Run Preflight Check

In a **second terminal**, verify all endpoints work:

```powershell
# Terminal 2
python scripts/run_evaluation.py --preflight
```

**Expected output (SUCCESS):**
```
[1/5] Checking health endpoint...
  [PASS] Health check passed (status: 200)

[2/5] Checking version endpoint...
  [PASS] Version endpoint passed
    Server version: 1.0.0

[3/5] Testing semantic judge endpoint...
  [PASS] Semantic judge passed (score: 1.0)

[4/5] Testing numeric judge endpoint...
  [PASS] Numeric judge passed (score: 1.0)

[5/5] Testing contradiction judge endpoint...
  [PASS] Contradiction judge passed (score: 1.0)

======================================================================
  Overall Status: PASS
  Checks Passed: 5/5
======================================================================

[SUCCESS] All preflight checks passed. System is ready.
```

## Step 6: Run Smoke Test

Evaluate 3 tasks to verify end-to-end functionality:

```powershell
# Terminal 2 (with MCP server still running in Terminal 1)
python scripts/run_evaluation.py --smoke-test
```

**Expected output:**
```
======================================================================
  Phase 1: Canonical Dataset Evaluation
======================================================================

Dataset Statistics:
  Total tasks: 50
  By difficulty: {'Easy': 15, 'Medium': 20, 'Hard': 15}

  Limiting to first 3 tasks

Running evaluation...

Results:
  Completed: 3/3
  Failed: 0
  Average Score: 0.XXX

======================================================================
  Smoke Test Results
======================================================================

Tasks completed: 3
Average score: 0.XXX

[SUCCESS] Smoke test passed successfully

Logs saved to: logs/run_YYYYMMDD_HHMMSS_xxxxxxxx
```

## Step 7: View Results

Check the generated logs and reports:

```powershell
# View recent logs directory
ls logs | Sort-Object LastWriteTime -Descending | Select-Object -First 1

# View summary report
cat artifacts/summary_report_*.md | Select-Object -First 50
```

## Common Commands

```powershell
# Run preflight check
python scripts/run_evaluation.py --preflight

# Run smoke test (3 tasks)
python scripts/run_evaluation.py --smoke-test

# Run first 10 tasks
python scripts/run_evaluation.py --track canonical --num-tasks 10

# Run full canonical evaluation (50 tasks)
python scripts/run_evaluation.py --track canonical

# Manual server mode (start servers yourself)
python scripts/run_evaluation.py --no-servers --preflight
```

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'openai'"

**Solution:**
```powershell
python -m pip install --user openai anthropic python-dotenv
```

### Issue: Preflight shows all [ERROR] status

**Cause:** MCP server not running

**Solution:**
1. Start MCP server in separate terminal: `python scripts/start_mcp_server.py`
2. Run preflight again: `python scripts/run_evaluation.py --preflight`

### Issue: "OPENAI_API_KEY not set"

**Solution:**
```powershell
$env:OPENAI_API_KEY="sk-your-key-here"
```

Or create `.env` file:
```
OPENAI_API_KEY=sk-your-key-here
```

### Issue: All scores = 0, contradiction rate = 100%

**Cause:** Old code before fixes were applied

**Solution:** The fixes have already been applied. If you still see this:
1. Ensure MCP server is running
2. Run preflight check to verify connectivity
3. Check that openai package is installed

## Next Steps

Once smoke test passes:

1. **Full Canonical Evaluation** (50 tasks):
   ```powershell
   python scripts/run_evaluation.py --track canonical
   ```

2. **View Detailed Reports**:
   - Summary: `artifacts/summary_report_*.md`
   - Difficulty analysis: `artifacts/difficulty_analysis_*.md`
   - Config: `artifacts/config_summary_*.json`

3. **Review Audit Traces**:
   ```powershell
   # View first trace
   Get-Content logs/run_*/canonical_traces.jsonl | Select-Object -First 1 | ConvertFrom-Json | ConvertTo-Json -Depth 10
   ```

## Architecture Overview

```
Terminal 1: MCP Server (localhost:8001)
            Provides judge endpoints
            ↓
Terminal 2: Evaluation Script
            Calls MCP server
            Evaluates tasks
            Generates reports
```

## System Status Indicators

- `[PASS]` - Check succeeded
- `[FAIL]` - Check failed (non-critical)
- `[ERROR]` - Check failed (critical, usually connectivity)
- `[WARNING]` - Check passed with issues
- `[SUCCESS]` - Operation completed successfully

## Support

- See [README.md](README.md) for full documentation
- Check [troubleshooting section](README.md#troubleshooting) for detailed fixes
- Review logs in `logs/run_*/` for detailed traces

---

**Ready to evaluate!** 🚀
