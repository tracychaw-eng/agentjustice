"""
Cross-Validation Framework for Calibration.

Implements 5-fold × 5-repeat CV with lexicographic objective.
"""
import numpy as np
from typing import List, Dict, Any, Tuple, Callable
from dataclasses import dataclass
from itertools import product
import random

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import calibration_config, ScorerConfig
from core.types import Task


@dataclass
class CVResult:
    """Result from one CV fold."""
    fold_idx: int
    repeat_idx: int
    train_indices: List[int]
    test_indices: List[int]
    params: Dict[str, float]
    metrics: Dict[str, float]


@dataclass
class CalibrationResult:
    """Result from full calibration run."""
    best_params: Dict[str, float]
    cv_stats: Dict[str, Any]
    all_results: List[CVResult]
    sensitivity_analysis: Dict[str, Any]


class KFoldCV:
    """
    K-Fold Cross-Validation with repeated runs.
    
    Designed for small datasets (~50 samples) with low-DoF parameter tuning.
    """
    
    def __init__(
        self,
        n_folds: int = 5,
        n_repeats: int = 5,
        random_seed: int = 42
    ):
        """
        Initialize CV framework.
        
        Args:
            n_folds: Number of folds
            n_repeats: Number of times to repeat CV with different seeds
            random_seed: Base random seed
        """
        self.n_folds = n_folds
        self.n_repeats = n_repeats
        self.random_seed = random_seed
    
    def generate_splits(
        self,
        n_samples: int
    ) -> List[Tuple[int, int, List[int], List[int]]]:
        """
        Generate all train/test splits.
        
        Args:
            n_samples: Total number of samples
        
        Returns:
            List of (repeat_idx, fold_idx, train_indices, test_indices)
        """
        all_splits = []
        
        for repeat_idx in range(self.n_repeats):
            # Set seed for this repeat
            seed = self.random_seed + repeat_idx
            rng = random.Random(seed)
            
            # Shuffle indices
            indices = list(range(n_samples))
            rng.shuffle(indices)
            
            # Create folds
            fold_size = n_samples // self.n_folds
            for fold_idx in range(self.n_folds):
                start = fold_idx * fold_size
                end = start + fold_size if fold_idx < self.n_folds - 1 else n_samples
                
                test_indices = indices[start:end]
                train_indices = indices[:start] + indices[end:]
                
                all_splits.append((repeat_idx, fold_idx, train_indices, test_indices))
        
        return all_splits
    
    def run(
        self,
        tasks: List[Task],
        param_grid: Dict[str, List[float]],
        evaluate_fn: Callable[[List[Task], List[Task], Dict[str, float]], Dict[str, float]]
    ) -> CalibrationResult:
        """
        Run cross-validation over parameter grid.
        
        Args:
            tasks: All tasks to evaluate on
            param_grid: Grid of parameters to search
            evaluate_fn: Function that evaluates on train/test split
                         Returns dict of metrics
        
        Returns:
            CalibrationResult with best params and statistics
        """
        n_samples = len(tasks)
        splits = self.generate_splits(n_samples)
        
        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        param_combos = list(product(*param_values))
        
        all_results = []
        
        # Evaluate each parameter combination
        for params_tuple in param_combos:
            params = dict(zip(param_names, params_tuple))
            
            # Run on all splits
            for repeat_idx, fold_idx, train_indices, test_indices in splits:
                train_tasks = [tasks[i] for i in train_indices]
                test_tasks = [tasks[i] for i in test_indices]
                
                metrics = evaluate_fn(train_tasks, test_tasks, params)
                
                result = CVResult(
                    fold_idx=fold_idx,
                    repeat_idx=repeat_idx,
                    train_indices=train_indices,
                    test_indices=test_indices,
                    params=params,
                    metrics=metrics
                )
                all_results.append(result)
        
        # Aggregate and find best
        best_params, cv_stats = self._aggregate_results(all_results, param_combos, param_names)
        
        # Sensitivity analysis
        sensitivity = self._sensitivity_analysis(all_results, param_names, best_params)
        
        return CalibrationResult(
            best_params=best_params,
            cv_stats=cv_stats,
            all_results=all_results,
            sensitivity_analysis=sensitivity
        )
    
    def _aggregate_results(
        self,
        all_results: List[CVResult],
        param_combos: List[Tuple],
        param_names: List[str]
    ) -> Tuple[Dict[str, float], Dict[str, Any]]:
        """Aggregate CV results and find best parameters."""
        # Group by parameter combination
        combo_results: Dict[Tuple, List[CVResult]] = {}
        for result in all_results:
            key = tuple(result.params[n] for n in param_names)
            if key not in combo_results:
                combo_results[key] = []
            combo_results[key].append(result)
        
        # Compute statistics for each combo
        combo_stats = {}
        for combo, results in combo_results.items():
            params = dict(zip(param_names, combo))
            
            # Extract primary metric (score)
            scores = [r.metrics.get("score", 0) for r in results]
            false_passes = [r.metrics.get("false_passes", 0) for r in results]
            false_fails = [r.metrics.get("false_fails", 0) for r in results]
            
            combo_stats[combo] = {
                "params": params,
                "mean_score": np.mean(scores),
                "std_score": np.std(scores),
                "worst_score": np.min(scores),
                "mean_false_passes": np.mean(false_passes),
                "mean_false_fails": np.mean(false_fails),
            }
        
        # Lexicographic selection:
        # 1. Minimize catastrophic false passes
        # 2. Minimize false positives on wrong probes
        # 3. Maximize score
        best_combo = min(
            combo_stats.keys(),
            key=lambda c: (
                combo_stats[c]["mean_false_passes"],
                combo_stats[c]["mean_false_fails"],
                -combo_stats[c]["mean_score"]  # Negate to maximize
            )
        )
        
        best_params = dict(zip(param_names, best_combo))
        
        cv_stats = {
            "best_params": best_params,
            "best_mean_score": combo_stats[best_combo]["mean_score"],
            "best_std_score": combo_stats[best_combo]["std_score"],
            "best_worst_score": combo_stats[best_combo]["worst_score"],
            "all_combo_stats": {str(k): v for k, v in combo_stats.items()},
            "n_folds": self.n_folds,
            "n_repeats": self.n_repeats,
            "n_param_combos": len(param_combos)
        }
        
        return best_params, cv_stats
    
    def _sensitivity_analysis(
        self,
        all_results: List[CVResult],
        param_names: List[str],
        best_params: Dict[str, float]
    ) -> Dict[str, Any]:
        """Analyze sensitivity to each parameter."""
        sensitivity = {}
        
        for param_name in param_names:
            # Get all results with best values for other params
            filtered = [
                r for r in all_results
                if all(
                    r.params[n] == best_params[n]
                    for n in param_names if n != param_name
                )
            ]
            
            # Group by this param's value
            by_value = {}
            for r in filtered:
                val = r.params[param_name]
                if val not in by_value:
                    by_value[val] = []
                by_value[val].append(r.metrics.get("score", 0))
            
            # Compute impact
            value_means = {v: np.mean(scores) for v, scores in by_value.items()}
            if value_means:
                max_score = max(value_means.values())
                min_score = min(value_means.values())
                sensitivity[param_name] = {
                    "range": max_score - min_score,
                    "by_value": value_means,
                    "critical": (max_score - min_score) > 0.1
                }
        
        return sensitivity


class Calibrator:
    """
    Main calibration class for AgentBeats evaluator.
    """
    
    def __init__(self, config=None):
        self.config = config or calibration_config
        self.cv = KFoldCV(
            n_folds=self.config.cv_folds,
            n_repeats=self.config.cv_repeats,
            random_seed=self.config.random_seed
        )
    
    def calibrate(
        self,
        tasks: List[Task],
        evaluate_fn: Callable
    ) -> CalibrationResult:
        """
        Run calibration on tasks.
        
        Args:
            tasks: Tasks to calibrate on
            evaluate_fn: Evaluation function
        
        Returns:
            CalibrationResult
        """
        return self.cv.run(
            tasks=tasks,
            param_grid=self.config.param_grid,
            evaluate_fn=evaluate_fn
        )
    
    def generate_report(self, result: CalibrationResult) -> str:
        """Generate markdown calibration report."""
        lines = [
            "# Calibration Report",
            "",
            "## Best Parameters",
            "",
        ]
        
        for param, value in result.best_params.items():
            lines.append(f"- **{param}**: {value}")
        
        lines.extend([
            "",
            "## Cross-Validation Statistics",
            "",
            f"- Folds: {result.cv_stats['n_folds']}",
            f"- Repeats: {result.cv_stats['n_repeats']}",
            f"- Parameter combinations tested: {result.cv_stats['n_param_combos']}",
            "",
            f"### Best Configuration",
            f"- Mean Score: {result.cv_stats['best_mean_score']:.4f}",
            f"- Std Score: {result.cv_stats['best_std_score']:.4f}",
            f"- Worst Fold Score: {result.cv_stats['best_worst_score']:.4f}",
            "",
            "## Sensitivity Analysis",
            "",
        ])
        
        for param, analysis in result.sensitivity_analysis.items():
            critical_marker = "⚠️" if analysis.get("critical") else ""
            lines.append(f"### {param} {critical_marker}")
            lines.append(f"- Range impact: {analysis['range']:.4f}")
            for val, score in analysis.get("by_value", {}).items():
                lines.append(f"  - {val}: {score:.4f}")
            lines.append("")
        
        return "\n".join(lines)
