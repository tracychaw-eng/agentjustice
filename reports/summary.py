"""
Summary Metrics Computation.

Computes overall and stratified metrics from evaluation results.
"""
import json
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class SummaryMetrics:
    """
    Computes summary metrics from evaluation traces.
    """
    
    def __init__(self, traces: List[Dict[str, Any]]):
        """
        Initialize with traces.
        
        Args:
            traces: List of task trace dictionaries
        """
        self.traces = traces
    
    def compute_overall(self) -> Dict[str, Any]:
        """Compute overall metrics."""
        if not self.traces:
            return {"error": "No traces available"}
        
        scores = [t.get("hybrid_score", {}).get("final_score", 0) for t in self.traces]
        semantic_scores = [t.get("hybrid_score", {}).get("semantic_score", 0) for t in self.traces]
        numeric_scores = [t.get("hybrid_score", {}).get("numeric_score", 0) for t in self.traces]
        
        # Contradiction rate
        contradictions = sum(
            1 for t in self.traces
            if t.get("hybrid_score", {}).get("contradiction_violated", False)
        )
        
        # Disagreement rate (semantic vs numeric differ significantly)
        disagreements = sum(
            1 for t in self.traces
            if abs(t.get("hybrid_score", {}).get("semantic_score", 0) -
                   t.get("hybrid_score", {}).get("numeric_score", 0)) > 0.3
        )
        
        # Error rates
        all_errors = []
        for t in self.traces:
            all_errors.extend(t.get("error_taxonomy", []))
        
        error_counts = defaultdict(int)
        for e in all_errors:
            error_counts[e] += 1
        
        return {
            "total_tasks": len(self.traces),
            "avg_final_score": float(np.mean(scores)),
            "std_final_score": float(np.std(scores)),
            "min_score": float(np.min(scores)),
            "max_score": float(np.max(scores)),
            "avg_semantic_score": float(np.mean(semantic_scores)),
            "avg_numeric_score": float(np.mean(numeric_scores)),
            "contradiction_rate": contradictions / len(self.traces),
            "disagreement_rate": disagreements / len(self.traces),
            "error_counts": dict(error_counts),
            "total_errors": len(all_errors),
        }
    
    def compute_by_difficulty(self) -> Dict[str, Dict[str, Any]]:
        """Compute metrics stratified by difficulty."""
        by_difficulty = defaultdict(list)
        
        for t in self.traces:
            difficulty = t.get("difficulty_level", "Unknown")
            by_difficulty[difficulty].append(t)
        
        results = {}
        for difficulty, traces in by_difficulty.items():
            scores = [t.get("hybrid_score", {}).get("final_score", 0) for t in traces]
            
            contradictions = sum(
                1 for t in traces
                if t.get("hybrid_score", {}).get("contradiction_violated", False)
            )
            
            disagreements = sum(
                1 for t in traces
                if abs(t.get("hybrid_score", {}).get("semantic_score", 0) -
                       t.get("hybrid_score", {}).get("numeric_score", 0)) > 0.3
            )
            
            errors = sum(len(t.get("error_taxonomy", [])) for t in traces)
            
            results[difficulty] = {
                "count": len(traces),
                "avg_score": float(np.mean(scores)) if scores else 0.0,
                "std_score": float(np.std(scores)) if scores else 0.0,
                "contradiction_rate": contradictions / len(traces) if traces else 0.0,
                "disagreement_rate": disagreements / len(traces) if traces else 0.0,
                "error_count": errors,
            }
        
        return results
    
    def compute_by_question_type(self) -> Dict[str, Dict[str, Any]]:
        """Compute metrics stratified by question type."""
        by_type = defaultdict(list)
        
        for t in self.traces:
            qtype = t.get("question_type", "Unknown")
            by_type[qtype].append(t)
        
        results = {}
        for qtype, traces in by_type.items():
            scores = [t.get("hybrid_score", {}).get("final_score", 0) for t in traces]
            
            results[qtype] = {
                "count": len(traces),
                "avg_score": float(np.mean(scores)) if scores else 0.0,
                "std_score": float(np.std(scores)) if scores else 0.0,
            }
        
        return results
    
    def compute_judge_stats(self) -> Dict[str, Dict[str, Any]]:
        """Compute statistics about judge calls."""
        judge_stats = defaultdict(lambda: {"latencies": [], "errors": 0})
        
        for t in self.traces:
            for call in t.get("judge_calls", []):
                judge_name = call.get("judge", "unknown")
                latency = call.get("latency_ms", 0)
                judge_stats[judge_name]["latencies"].append(latency)
                
                if call.get("error"):
                    judge_stats[judge_name]["errors"] += 1
        
        results = {}
        for judge_name, stats in judge_stats.items():
            latencies = stats["latencies"]
            results[judge_name] = {
                "calls": len(latencies),
                "avg_latency_ms": float(np.mean(latencies)) if latencies else 0.0,
                "p95_latency_ms": float(np.percentile(latencies, 95)) if latencies else 0.0,
                "errors": stats["errors"],
                "error_rate": stats["errors"] / len(latencies) if latencies else 0.0,
            }
        
        return results
    
    def generate_report(self, track_type: str = "Canonical") -> str:
        """
        Generate markdown summary report.

        Args:
            track_type: Type of evaluation track (e.g., "Canonical", "Adversarial")

        Returns:
            Formatted markdown report
        """
        overall = self.compute_overall()
        by_difficulty = self.compute_by_difficulty()
        by_type = self.compute_by_question_type()
        judge_stats = self.compute_judge_stats()

        # Determine dataset source label
        dataset_label = "public_updated.csv" if track_type == "Canonical" else "public_adversarial.jsonl"

        lines = [
            f"# Evaluation Summary Report ({track_type})",
            "",
            f"**Dataset**: {dataset_label}",
            "",
            "## Overall Metrics",
            "",
            f"- **Total Tasks**: {overall['total_tasks']}",
            f"- **Average Score**: {overall['avg_final_score']:.3f} ± {overall['std_final_score']:.3f}",
            f"- **Score Range**: [{overall['min_score']:.3f}, {overall['max_score']:.3f}]",
            f"- **Contradiction Rate**: {overall['contradiction_rate']*100:.1f}%",
            f"- **Disagreement Rate**: {overall['disagreement_rate']*100:.1f}%",
            "",
            "## By Difficulty Level",
            "",
            "| Difficulty | N | Avg Score | Std | Contradiction | Disagreement |",
            "|------------|---|-----------|-----|---------------|--------------|",
        ]
        
        for diff in ["Easy", "Medium", "Hard"]:
            if diff in by_difficulty:
                d = by_difficulty[diff]
                lines.append(
                    f"| {diff} | {d['count']} | {d['avg_score']:.3f} | {d['std_score']:.3f} | "
                    f"{d['contradiction_rate']*100:.1f}% | {d['disagreement_rate']*100:.1f}% |"
                )
        
        lines.extend([
            "",
            "## By Question Type",
            "",
            "| Type | N | Avg Score | Std |",
            "|------|---|-----------|-----|",
        ])
        
        for qtype, stats in sorted(by_type.items(), key=lambda x: -x[1]['count']):
            lines.append(f"| {qtype} | {stats['count']} | {stats['avg_score']:.3f} | {stats['std_score']:.3f} |")
        
        lines.extend([
            "",
            "## Judge Performance",
            "",
            "| Judge | Calls | Avg Latency (ms) | P95 Latency | Errors |",
            "|-------|-------|------------------|-------------|--------|",
        ])
        
        for judge, stats in judge_stats.items():
            lines.append(
                f"| {judge} | {stats['calls']} | {stats['avg_latency_ms']:.0f} | "
                f"{stats['p95_latency_ms']:.0f} | {stats['errors']} |"
            )
        
        if overall.get("error_counts"):
            lines.extend([
                "",
                "## Error Taxonomy",
                "",
                "> **Note**: Error counts represent unrecovered judge failures logged in traces.",
                "> Retries are handled internally; only persistent errors are counted.",
                "",
            ])
            for error, count in overall["error_counts"].items():
                lines.append(f"- {error}: {count}")

        return "\n".join(lines)


def compute_summary(traces: List[Dict[str, Any]]) -> SummaryMetrics:
    """Create summary metrics from traces."""
    return SummaryMetrics(traces)
