"""
Stability Tests for Evaluator.

Tests evaluator reliability through repeated runs.
"""
import numpy as np
from typing import List, Dict, Any, Callable
from dataclasses import dataclass

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.types import Task


@dataclass
class StabilityResult:
    """Result from stability testing."""
    n_runs: int
    task_id: int
    scores: List[float]
    mean: float
    std: float
    min: float
    max: float
    is_stable: bool  # std < threshold


@dataclass
class StabilityReport:
    """Full stability report."""
    per_task_results: List[StabilityResult]
    overall_stability: float  # Fraction of stable tasks
    avg_std: float
    max_std: float
    unstable_tasks: List[int]


class StabilityTester:
    """
    Tests evaluator stability through repeated evaluations.
    
    Identifies tasks where evaluation is inconsistent.
    """
    
    def __init__(
        self,
        n_runs: int = 5,
        stability_threshold: float = 0.05
    ):
        """
        Initialize stability tester.
        
        Args:
            n_runs: Number of repeated evaluations per task
            stability_threshold: Max std for a task to be considered stable
        """
        self.n_runs = n_runs
        self.stability_threshold = stability_threshold
    
    def test(
        self,
        tasks: List[Task],
        evaluate_fn: Callable[[Task], float]
    ) -> StabilityReport:
        """
        Run stability tests.
        
        Args:
            tasks: Tasks to test
            evaluate_fn: Function that evaluates a task and returns score
        
        Returns:
            StabilityReport with per-task and overall results
        """
        per_task = []
        
        for task in tasks:
            scores = []
            
            for _ in range(self.n_runs):
                score = evaluate_fn(task)
                scores.append(score)
            
            mean = np.mean(scores)
            std = np.std(scores)
            
            result = StabilityResult(
                n_runs=self.n_runs,
                task_id=task.task_id,
                scores=scores,
                mean=mean,
                std=std,
                min=np.min(scores),
                max=np.max(scores),
                is_stable=(std < self.stability_threshold)
            )
            per_task.append(result)
        
        # Aggregate
        stds = [r.std for r in per_task]
        stable_count = sum(1 for r in per_task if r.is_stable)
        unstable = [r.task_id for r in per_task if not r.is_stable]
        
        return StabilityReport(
            per_task_results=per_task,
            overall_stability=stable_count / len(per_task) if per_task else 0.0,
            avg_std=np.mean(stds) if stds else 0.0,
            max_std=np.max(stds) if stds else 0.0,
            unstable_tasks=unstable
        )
    
    def generate_report(self, report: StabilityReport) -> str:
        """Generate markdown stability report."""
        lines = [
            "# Stability Report",
            "",
            "## Summary",
            f"- Tasks tested: {len(report.per_task_results)}",
            f"- Runs per task: {self.n_runs}",
            f"- Overall stability: {report.overall_stability * 100:.1f}%",
            f"- Average std: {report.avg_std:.4f}",
            f"- Max std: {report.max_std:.4f}",
            "",
        ]
        
        if report.unstable_tasks:
            lines.extend([
                "## Unstable Tasks",
                "",
                "| Task ID | Mean Score | Std | Min | Max |",
                "|---------|------------|-----|-----|-----|",
            ])
            
            for result in report.per_task_results:
                if not result.is_stable:
                    lines.append(
                        f"| {result.task_id} | {result.mean:.3f} | {result.std:.3f} | {result.min:.3f} | {result.max:.3f} |"
                    )
            lines.append("")
        else:
            lines.append("All tasks are stable within threshold.")
            lines.append("")
        
        # Add stability by difficulty
        lines.extend([
            "## Stability by Difficulty",
            "",
        ])
        
        return "\n".join(lines)
