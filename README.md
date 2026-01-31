# AgentJustice FinanceBench Phase-1 Evaluator

Phase-1 Green Agent evaluation system designed to **improve and strengthen the existing Finance Agent Benchmark** introduced in *Finance Agent Benchmark* (2025) — https://arxiv.org/pdf/2508.00828

---

## Project Overview

This repository implements **AgentJustice**, a **Phase-1 Green Agent evaluation system** that **extends and improves the original Finance Agent Benchmark** proposed in *Finance Agent Benchmark* (arXiv:2508.00828).

The original benchmark demonstrated the feasibility of evaluating LLM-based financial agents, but left several open challenges unaddressed, including:
- Limited evaluation transparency
- Implicit or monolithic LLM-as-judge scoring
- Lack of fine-grained error attribution
- Insufficient adversarial robustness analysis
- Weak guarantees around reproducibility and auditability

**AgentJustice addresses these gaps** by introducing a modular, judge-based evaluation architecture that emphasizes **determinism, auditability, and diagnostic clarity**, while remaining fully compatible with the original FinanceBench task format and public dataset. Although our judges internally use LLMs, they are not LLM-as-judge in the traditional sense. The LLM is used strictly as a subroutine for extraction or semantic alignment, while all scoring logic, thresholds, and failure semantics are explicitly implemented and auditable.

---

**Key Characteristics**:
- 50-task canonical dataset with difficulty stratification (Easy/Medium/Hard)
- Three independent LLM-based judges (semantic, numeric, contradiction)
- Hybrid scoring with consistency checks
- MCP (Model Context Protocol) compatible judge server
- A2A (Agent-to-Agent) compatible orchestration
- Adversarial robustness testing (derived dataset)
- Complete audit trail with JSONL trace logging

---

## Phase-1 Compliance Checklist

This section maps the implementation to Phase-1 rubric requirements.

### Dataset Ingestion

| Requirement | Implementation | Location |
|-------------|----------------|----------|
| Load public_updated.csv dataset | CSV loading with pandas | `scripts/run_evaluation.py` |
| Parse task fields | task_id, question, gold_answer, rubric, question_type, difficulty_level, expert_time_mins | `core/types.py` |
| Validate dataset integrity | SHA-256 hash verification | `config/settings.py`, logged in manifest |

### Rubric-Driven Evaluation

| Requirement | Implementation | Location |
|-------------|----------------|----------|
| Pass rubric to judges | Rubric included in all judge calls | `green_agent/orchestrator.py` |
| Rubric-aware scoring | Judges consider rubric criteria in prompts | `mcp_server/prompts/*.txt` |

### Deterministic Scoring

| Requirement | Implementation | Location |
|-------------|----------------|----------|
| Fixed scoring thresholds | 1% relative tolerance for numeric comparisons | `config/settings.py` |
| No difficulty-based threshold adjustment | Thresholds constant across all difficulty levels | `green_agent/scorer.py` |
| Reproducible results | Seed-controlled, versioned prompts, hash-pinned | `config/settings.py` |

### Reproducibility

| Requirement | Implementation | Location |
|-------------|----------------|----------|
| Version-pinned judges | `JUDGE_VERSIONS` dictionary with semantic versioning | `config/settings.py` |
| Prompt hashing | SHA-256 hash of each prompt logged per call | `core/hashing.py` |
| Configuration manifest | Complete config JSON saved per run | `artifacts/config_summary_*.json` |
| Run ID tracking | UUID-based run identification | `scripts/run_evaluation.py` |

### Difficulty-Diagnostic Analysis

| Requirement | Implementation | Location |
|-------------|----------------|----------|
| Score stratification by difficulty | Per-difficulty mean, std, min, max | `reports/difficulty_analysis.py` |
| Diagnostic-only usage | Explicit note: "Scoring thresholds are NOT adjusted per difficulty" | Report output |
| Synthesis narrative | Data-driven interpretation paragraph | `reports/difficulty_analysis.py` |

### Judge Independence

| Requirement | Implementation | Location |
|-------------|----------------|----------|
| Semantic judge | Evaluates meaning equivalence | `mcp_server/judges/semantic.py` |
| Numeric judge | Compares extracted numeric values with tolerance | `mcp_server/judges/numeric.py` |
| Contradiction judge | Detects mutually exclusive claims | `mcp_server/judges/contradiction.py` |
| Independent scoring | Each judge returns separate score and confidence | `green_agent/mcp_client.py` |

### Auditability

| Requirement | Implementation | Location |
|-------------|----------------|----------|
| JSONL trace logging | Full trace per task (inputs, outputs, metadata) | `logs/run_*/canonical_traces.jsonl` |
| Judge call logging | Input/output payloads, latency, versions, hashes | `green_agent/logger.py` |
| Error taxonomy | Categorized error counts in summary | `reports/summary.py` |
| Replay capability | Traces support offline replay and analysis | `green_agent/logger.py` |

---

## Beyond Phase-1 Requirements

This implementation includes several capabilities beyond the minimum Phase-1 requirements.

### Hybrid Scoring Architecture

The system combines three judge outputs using a weighted hybrid scorer:
- Weighted average of semantic and numeric scores
- Consistency penalties for judge disagreement
- Contradiction penalty for mutually exclusive claims
- Hedging penalty for explicit uncertainty language

This provides more nuanced evaluation than single-judge scoring.

### Adversarial Robustness Testing

A separate adversarial track generates derived test cases:
- Scale errors (e.g., $85,002 vs $85,002,000)
- Wrong metric substitution (revenue vs profit)
- Multi-number conflicts
- Keyword stuffing
- Hedged/uncertain answers

Adversarial results are reported separately and do not affect canonical scoring.

### MCP-Based Judge Abstraction

Judges are exposed via MCP-compatible HTTP endpoints:
- Stateless, tool-invocation semantics
- Discoverable via `/mcp/tools` endpoint
- Version and prompt hash exposed via `/version`
- Health monitoring via `/health`

This enables integration with MCP-aware agent frameworks.

### Confidence and Failure Reason Reporting

Each judge returns:
- `score`: 0.0-1.0 evaluation result
- `confidence`: extraction/comparison certainty
- `failure_reason`: diagnostic field (`extraction_failed`, `alignment_failed`, `tolerance_failed`, `parse_error`, `none`)

This supports fine-grained debugging and audit.

### Cross-Validation Calibration

Optional 5-fold cross-validation for scorer parameter tuning:
- Grid search over penalty weights
- Variance analysis across folds
- Results logged but not applied to final scoring (maintains determinism)

### Top Disagreement Examples

Difficulty analysis reports include 1-3 concrete examples of highest judge disagreement:
- Full task context (question, answers, judge outputs)
- Auto-generated explanations based on failure reason
- Supports manual audit and debugging

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Evaluation Pipeline                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     │
│  │ Purple Agent │───▶│ Green Agent  │────▶│   Reports    │     │
│  │ (Baseline)   │     │ (Orchestrator│     │   Generator  │     │
│  └──────────────┘     └──────┬───────┘     └──────────────┘     │
│                              │                                  │
│                              ▼                                  │
│                    ┌─────────────────┐                          │
│                    │  MCP Judge      │                          │
│                    │  Server         │                          │
│                    │  ┌───────────┐  │                          │
│                    │  │ Semantic  │  │                          │
│                    │  │ Numeric   │  │                          │
│                    │  │ Contradict│  │                          │
│                    │  └───────────┘  │                          │
│                    └─────────────────┘                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Components**:

| Component | Purpose | Location |
|-----------|---------|----------|
| Green Agent | Orchestrates evaluation, calls judges, computes hybrid score | `green_agent/` |
| Purple Agent | Baseline answer generator (gold mode returns gold answers) | `purple_agent/` |
| MCP Judge Server | Stateless HTTP server exposing judge tools | `mcp_server/` |
| Reports | Summary and difficulty-stratified analysis generators | `reports/` |
| Calibration | Cross-validation parameter tuning (optional) | `calibration/` |
| Adversarial | Derived adversarial dataset generation | `adversarial/` |

---

## Quick Start

### Prerequisites

- Python 3.8+
- OpenAI API key

### Installation

```bash
pip install -r requirements.txt
export OPENAI_API_KEY="your-api-key"
```

### Run Evaluation

```bash
# Preflight check (validate connectivity)
python scripts/run_evaluation.py --preflight

# Smoke test (3 tasks)
python scripts/run_evaluation.py --smoke-test

# Full canonical evaluation (50 tasks)
python scripts/run_evaluation.py --track canonical

# Both canonical and adversarial tracks
python scripts/run_evaluation.py
```

---

## Docker Quickstart

Run the evaluator in a container with no local Python setup required.

### Prerequisites

- Docker and Docker Compose installed
- `OPENAI_API_KEY` environment variable set

### Build

```bash
docker compose build
```

### Run Evaluation

**Set API key first:**

```bash
# macOS/Linux
export OPENAI_API_KEY="your-api-key"

# Windows PowerShell
$env:OPENAI_API_KEY="your-api-key"

# Windows CMD
set OPENAI_API_KEY=your-api-key
```

**Preflight check** (validate connectivity):
```bash
docker compose run --rm evaluator --preflight
```

**Smoke test** (3 tasks, quick validation):
```bash
docker compose run --rm evaluator --smoke-test
```

**Canonical track only** (50 tasks):
```bash
docker compose run --rm evaluator --track canonical
```

**Adversarial track only**:
```bash
docker compose run --rm evaluator --track adversarial
```

**Both tracks** (default full evaluation):
```bash
docker compose run --rm evaluator
```

### Makefile Shortcuts

```bash
make docker-build       # Build image
make docker-preflight   # Run preflight check
make docker-smoke       # Run smoke test
make docker-canonical   # Run canonical track
make docker-adversarial # Run adversarial track
make docker-all         # Run both tracks (default)
make docker-clean       # Clean up Docker resources
```

### Output Location

All outputs are written to host-mounted directories:
- `artifacts/` - Evaluation reports and config summaries
- `logs/` - JSONL trace files and run manifests
- `reports/` - Generated analysis reports

---

### Output

```
artifacts/
├── summary_report_<run_id>.md           # Canonical evaluation summary
├── difficulty_analysis_<run_id>.md      # Difficulty-stratified analysis
├── config_summary_<run_id>.json         # Complete configuration
└── ...

logs/
└── run_<timestamp>_<id>/
    ├── canonical_traces.jsonl           # Full audit traces
    └── manifest.json                    # Run metadata
```

---

## Repository Structure

```
agentjustice/
├── README.md                    # This file
├── DEBUGGING_AND_FIX_LOG.md     # Consolidated debugging history
├── requirements.txt             # Python dependencies
├── config/                      # Configuration and settings
├── core/                        # Core types and utilities
├── mcp_server/                  # MCP judge server
│   ├── judges/                  # Judge implementations
│   └── prompts/                 # Pinned judge prompts
├── green_agent/                 # Green agent (orchestrator)
├── purple_agent/                # Purple agent (baseline)
├── adversarial/                 # Adversarial dataset generation
├── calibration/                 # Parameter tuning
├── reports/                     # Report generators
├── scripts/                     # Executable scripts
├── tests/                       # Test suite
├── data/                        # Datasets
├── logs/                        # Evaluation logs
└── artifacts/                   # Generated reports
```

---

## Key Documentation

| Document | Purpose |
|----------|---------|
| [README.md](README.md) | Project overview and compliance checklist |
| [DEBUGGING_AND_FIX_LOG.md](DEBUGGING_AND_FIX_LOG.md) | Consolidated debugging history and fix record |

---

## Scoring Details

### Hybrid Score Computation

```
base_score = weighted_average(semantic_score, numeric_score)
final_score = base_score - consistency_penalty - contradiction_penalty - hedging_penalty
```

**Penalties**:
- `consistency_penalty`: Applied when semantic and numeric judges disagree significantly
- `contradiction_penalty`: Applied when contradiction judge detects mutually exclusive claims
- `hedging_penalty`: Applied when answer contains explicit uncertainty language

### Thresholds (Fixed)

| Parameter | Value | Description |
|-----------|-------|-------------|
| Numeric tolerance | 1% | Relative tolerance for numeric comparisons |
| High disagreement threshold | 0.3 | Absolute difference triggering consistency flag |
| Contradiction penalty | 0.5 | Score reduction for contradictions |

---

## Testing

### Smoke Test

```bash
python scripts/run_evaluation.py --smoke-test
```

Evaluates 3 tasks to verify end-to-end functionality.

---

## Known Limitations

1. **LLM Variability**: Judge outputs have some variability due to LLM temperature. Key invariants are enforced, but exact scores may differ between runs.

2. **Complex Structured Outputs**: Multi-value structured answers (e.g., 10+ KPIs) may trigger parse errors in the numeric judge. The system gracefully handles this with `failure_reason=parse_error` and `confidence=0.5`.

3. **Adversarial Track**: Adversarial results are diagnostic only and should not be compared directly to canonical results.

---

## License

Apache 2.0

---

## Version

- Phase-1 Evaluator: v1.0.0
- Numeric Judge: v1.1.0
- Contradiction Judge: v1.1.0
- Semantic Judge: v1.0.0
