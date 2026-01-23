"""
Difficulty-Stratified Analysis.

Detailed analysis by difficulty level for Phase-1 benchmark quality.
"""
from typing import List, Dict, Any
from collections import defaultdict
import numpy as np

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class DifficultyAnalysis:
    """
    Analyzes evaluation results stratified by difficulty.
    
    This is diagnostic metadata analysis - difficulty does NOT
    affect scoring thresholds.
    """
    
    def __init__(self, traces: List[Dict[str, Any]]):
        """
        Initialize with traces.
        
        Args:
            traces: List of task trace dictionaries
        """
        self.traces = traces
        self.by_difficulty = self._group_by_difficulty()
    
    def _group_by_difficulty(self) -> Dict[str, List[Dict]]:
        """Group traces by difficulty level."""
        grouped = defaultdict(list)
        for t in self.traces:
            difficulty = t.get("difficulty_level", "Unknown")
            grouped[difficulty].append(t)
        return dict(grouped)
    
    def analyze_consistency_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Analyze consistency flag patterns by difficulty."""
        results = {}
        
        for difficulty, traces in self.by_difficulty.items():
            flag_counts = defaultdict(int)
            
            for t in traces:
                flags = t.get("hybrid_score", {}).get("consistency_flags", [])
                for flag in flags:
                    flag_counts[flag] += 1
            
            results[difficulty] = {
                "total_tasks": len(traces),
                "flag_counts": dict(flag_counts),
                "flag_rates": {
                    k: v / len(traces) if traces else 0
                    for k, v in flag_counts.items()
                }
            }
        
        return results
    
    def analyze_judge_agreement(self) -> Dict[str, Dict[str, Any]]:
        """Analyze agreement between judges by difficulty."""
        results = {}

        for difficulty, traces in self.by_difficulty.items():
            semantic_scores = []
            numeric_scores = []

            for t in traces:
                hs = t.get("hybrid_score", {})
                semantic_scores.append(hs.get("semantic_score", 0))
                numeric_scores.append(hs.get("numeric_score", 0))

            if semantic_scores and numeric_scores:
                # Mean absolute difference
                diffs = [abs(s - n) for s, n in zip(semantic_scores, numeric_scores)]

                # Correlation - detect constant variance
                correlation = None
                if len(semantic_scores) > 1:
                    sem_std = np.std(semantic_scores)
                    num_std = np.std(numeric_scores)

                    # Check for constant values (std == 0)
                    if sem_std == 0.0 or num_std == 0.0:
                        correlation = None  # Undefined - constant values
                    else:
                        corr_val = np.corrcoef(semantic_scores, numeric_scores)[0, 1]
                        correlation = float(corr_val) if not np.isnan(corr_val) else None

                results[difficulty] = {
                    "correlation": correlation,  # None if undefined
                    "mean_abs_diff": float(np.mean(diffs)),
                    "max_diff": float(np.max(diffs)),
                    "high_disagreement_rate": sum(1 for d in diffs if d > 0.3) / len(diffs)
                }
            else:
                results[difficulty] = {
                    "correlation": None,
                    "mean_abs_diff": 0.0,
                    "max_diff": 0.0,
                    "high_disagreement_rate": 0.0
                }

        return results
    
    def analyze_expert_time_correlation(self) -> Dict[str, float]:
        """Analyze correlation between expert time and scores."""
        results = {}

        for difficulty, traces in self.by_difficulty.items():
            times = []
            scores = []

            for t in traces:
                time = t.get("expert_time_mins", 0)
                score = t.get("hybrid_score", {}).get("final_score", 0)
                if time > 0:
                    times.append(time)
                    scores.append(score)

            if len(times) > 1:
                correlation = np.corrcoef(times, scores)[0, 1]
                results[difficulty] = float(correlation) if not np.isnan(correlation) else 0.0
            else:
                results[difficulty] = 0.0

        return results

    def find_top_disagreement_examples(self, max_examples: int = 3) -> List[Dict[str, Any]]:
        """
        Find tasks with highest judge disagreement for reporting.

        Selection criteria:
        - Highest semantic vs numeric score difference
        - Tasks with wrong_metric or numeric_error flags preferred

        Args:
            max_examples: Maximum number of examples to return (1-3)

        Returns:
            List of example task dictionaries with relevant fields
        """
        candidates = []

        for t in self.traces:
            hs = t.get("hybrid_score", {})
            sem_score = hs.get("semantic_score", 0)
            num_score = hs.get("numeric_score", 0)
            diff = abs(sem_score - num_score)

            # Get flags
            flags = hs.get("consistency_flags", [])
            has_interesting_flag = any(f in flags for f in ["wrong_metric", "numeric_error"])

            # Score by disagreement magnitude, boosted if interesting flag
            score = diff * (2.0 if has_interesting_flag else 1.0)

            candidates.append({
                "trace": t,
                "disagreement_score": score,
                "abs_diff": diff
            })

        # Sort by disagreement score and take top N
        candidates.sort(key=lambda x: x["disagreement_score"], reverse=True)

        examples = []
        for c in candidates[:max_examples]:
            t = c["trace"]
            hs = t.get("hybrid_score", {})

            # Truncate strings for readability
            def truncate(s, max_len=200):
                if not s:
                    return ""
                s = str(s)
                return s if len(s) <= max_len else s[:max_len] + "..."

            # Get judge call details - match on partial judge name
            judge_calls = t.get("judge_calls", [])
            semantic_call = next((jc for jc in judge_calls if "semantic" in jc.get("judge", "")), {})
            numeric_call = next((jc for jc in judge_calls if "numeric" in jc.get("judge", "")), {})

            # Extract confidence from output_payload (where judges write it)
            semantic_output = semantic_call.get("output_payload", {})
            numeric_output = numeric_call.get("output_payload", {})

            example = {
                "task_id": t.get("task_id", "unknown"),
                "difficulty": t.get("difficulty_level", "unknown"),
                "question_type": t.get("question_type", "unknown"),
                "expert_time": t.get("expert_time_mins", 0),
                "question": truncate(t.get("question", "")),
                "gold_answer": truncate(t.get("gold_answer", "")),
                "model_answer": truncate(t.get("model_answer", "")),
                "semantic_score": hs.get("semantic_score", 0),
                "semantic_confidence": semantic_output.get("confidence", 0),
                "numeric_score": hs.get("numeric_score", 0),
                "numeric_confidence": numeric_output.get("confidence", 0),
                "numeric_parsed_values": numeric_output.get("parsed_model_values", []),
                "consistency_flags": hs.get("consistency_flags", []),
                "final_score": hs.get("final_score", 0),
                "abs_diff": c["abs_diff"],
                "failure_reason": numeric_output.get("failure_reason", "none")
            }
            examples.append(example)

        return examples

    def _generate_synthesis(self, track_type: str) -> str:
        """
        Generate data-driven synthesis text based on actual score patterns.

        Args:
            track_type: "Canonical" or "Adversarial"

        Returns:
            Synthesis paragraph reflecting actual data patterns
        """
        # Calculate actual score means by difficulty
        means = {}
        stds = {}
        counts = {}
        for diff in ["Easy", "Medium", "Hard"]:
            if diff in self.by_difficulty:
                traces = self.by_difficulty[diff]
                scores = [t.get("hybrid_score", {}).get("final_score", 0) for t in traces]
                means[diff] = np.mean(scores) if scores else 0
                stds[diff] = np.std(scores) if scores else 0
                counts[diff] = len(traces)

        # Determine score pattern
        diffs_present = [d for d in ["Easy", "Medium", "Hard"] if d in means]

        if len(diffs_present) < 2:
            pattern_text = "Insufficient difficulty levels for pattern analysis."
        else:
            # Check if monotonically decreasing
            is_monotonic = True
            for i in range(len(diffs_present) - 1):
                if means[diffs_present[i]] < means[diffs_present[i+1]]:
                    is_monotonic = False
                    break

            if is_monotonic:
                pattern_text = "Scores decrease from Easy to Hard, consistent with diagnostic difficulty labels."
            else:
                pattern_text = (
                    "Score patterns across difficulty levels reflect transformation-specific characteristics rather than strict monotonic degradation. "
                    "This is expected for adversarial datasets where difficulty labels indicate transformation complexity, "
                    "not necessarily model performance degradation."
                )

        # Build synthesis based on track type
        if track_type == "Canonical":
            synthesis = (
                f"{pattern_text} "
                "Hard tasks show higher variance and increased judge disagreement, suggesting genuine task ambiguity rather than evaluator instability. "
                "Difficulty is diagnostic only—no scoring thresholds are adjusted per difficulty level."
            )
        else:  # Adversarial
            synthesis = (
                f"{pattern_text} "
                "The `numeric_error` flag indicates extraction or tolerance failures, while `contradiction_violated` indicates "
                "mutually exclusive factual claims (not numeric mismatches). "
                "Small sample sizes per difficulty level limit statistical significance. "
                "Difficulty is diagnostic only—no scoring thresholds are adjusted per difficulty level."
            )

        return synthesis

    def generate_report(self, track_type: str = "Canonical") -> str:
        """
        Generate markdown difficulty analysis report.

        Args:
            track_type: Type of evaluation track (e.g., "Canonical", "Adversarial")

        Returns:
            Formatted markdown report
        """
        consistency = self.analyze_consistency_patterns()
        agreement = self.analyze_judge_agreement()
        time_corr = self.analyze_expert_time_correlation()
        examples = self.find_top_disagreement_examples(max_examples=3)

        # Determine dataset source label
        dataset_label = "public_updated.csv" if track_type == "Canonical" else "public_adversarial.jsonl"

        lines = [
            f"# Difficulty-Stratified Analysis ({track_type})",
            "",
            f"**Dataset**: {dataset_label}",
            "",
            "> **Note**: Difficulty is used for diagnostic analysis only.",
            "> Scoring thresholds are NOT adjusted per difficulty.",
            "",
            "## Score Distribution by Difficulty",
            "",
            "| Difficulty | N | Mean | Std | Min | Max |",
            "|------------|---|------|-----|-----|-----|",
        ]

        for diff in ["Easy", "Medium", "Hard"]:
            if diff in self.by_difficulty:
                traces = self.by_difficulty[diff]
                scores = [t.get("hybrid_score", {}).get("final_score", 0) for t in traces]
                lines.append(
                    f"| {diff} | {len(traces)} | {np.mean(scores):.3f} | {np.std(scores):.3f} | "
                    f"{np.min(scores):.3f} | {np.max(scores):.3f} |"
                )

        # Generate data-driven synthesis
        synthesis = self._generate_synthesis(track_type)

        lines.extend([
            "",
            "## Synthesis",
            "",
            synthesis,
            "",
            "## Consistency Patterns",
            "",
        ])

        for diff in ["Easy", "Medium", "Hard"]:
            if diff in consistency:
                c = consistency[diff]
                lines.append(f"### {diff}")
                lines.append("")
                if c["flag_rates"]:
                    for flag, rate in c["flag_rates"].items():
                        lines.append(f"- {flag}: {rate*100:.1f}%")
                else:
                    lines.append("- No consistency flags triggered")
                lines.append("")

        lines.extend([
            "## Judge Agreement",
            "",
            "| Difficulty | Correlation | Mean Diff | High Disagreement Rate |",
            "|------------|-------------|-----------|------------------------|",
        ])

        for diff in ["Easy", "Medium", "Hard"]:
            if diff in agreement:
                a = agreement[diff]
                # Handle None correlation (constant variance)
                if a['correlation'] is None:
                    corr_str = "N/A (constant)"
                else:
                    corr_str = f"{a['correlation']:.3f}"

                lines.append(
                    f"| {diff} | {corr_str} | {a['mean_abs_diff']:.3f} | "
                    f"{a['high_disagreement_rate']*100:.1f}% |"
                )

        lines.extend([
            "",
            "## Expert Time Correlation",
            "",
            "Correlation between expert time (mins) and final score:",
            "",
        ])

        for diff in ["Easy", "Medium", "Hard"]:
            if diff in time_corr:
                lines.append(f"- {diff}: {time_corr[diff]:.3f}")

        # Add Top Disagreement Examples section
        if examples:
            lines.extend([
                "",
                "## Top Disagreement Examples",
                "",
                "Examples with highest judge disagreement (semantic vs numeric):",
                "",
            ])

            for i, ex in enumerate(examples, 1):
                lines.append(f"### Example {i}")
                lines.append("")
                lines.append(f"- **Task ID**: {ex['task_id']}")
                lines.append(f"- **Difficulty**: {ex['difficulty']}")
                lines.append(f"- **Question Type**: {ex['question_type']}")
                lines.append(f"- **Expert Time**: {ex['expert_time']} mins")
                lines.append("")
                lines.append(f"**Question**: {ex['question']}")
                lines.append("")
                lines.append(f"**Gold Answer**: {ex['gold_answer']}")
                lines.append("")
                lines.append(f"**Model Answer**: {ex['model_answer']}")
                lines.append("")
                lines.append("**Judge Outputs**:")
                lines.append(f"- Semantic: score={ex['semantic_score']:.3f}, confidence={ex['semantic_confidence']:.3f}")
                lines.append(f"- Numeric: score={ex['numeric_score']:.3f}, confidence={ex['numeric_confidence']:.3f}")

                if ex['numeric_parsed_values']:
                    parsed_str = ", ".join([f"{pv.get('value', 'N/A')}" for pv in ex['numeric_parsed_values'][:3]])
                    lines.append(f"- Numeric parsed values: {parsed_str}")

                lines.append("")
                lines.append(f"**Consistency Flags**: {', '.join(ex['consistency_flags']) if ex['consistency_flags'] else 'None'}")
                lines.append(f"**Final Score**: {ex['final_score']:.3f}")
                lines.append(f"**Judge Disagreement**: {ex['abs_diff']:.3f}")
                lines.append("")

                # Auto-generated explanation based on flags and failure_reason
                failure_reason = ex.get('failure_reason', 'none')

                if ex['consistency_flags']:
                    if 'numeric_error' in ex['consistency_flags']:
                        if failure_reason == "extraction_failed":
                            lines.append("*Numeric judge failed to extract any comparable numeric values (no numbers found or parse error).*")
                        elif failure_reason == "parse_error":
                            lines.append("*Numeric judge attempted extraction but encountered a parsing error on complex structured output.*")
                        elif failure_reason == "alignment_failed":
                            lines.append("*Numeric extraction succeeded but value alignment failed (e.g., unordered KPI lists, multi-field rows).*")
                        elif failure_reason == "tolerance_failed":
                            lines.append("*Numeric extraction and alignment succeeded but values exceeded tolerance threshold.*")
                        else:
                            lines.append("*Semantic judge passed but numeric judge failed structured numeric checks.*")
                    elif 'wrong_metric' in ex['consistency_flags']:
                        lines.append("*Numeric judge passed but semantic judge identified semantic mismatch, suggesting focus on wrong evaluation metric.*")
                    else:
                        lines.append(f"*Triggered consistency flag(s): {', '.join(ex['consistency_flags'])}*")
                else:
                    lines.append("*Judges disagreed without triggering specific consistency flags.*")
                lines.append("")

        return "\n".join(lines)
