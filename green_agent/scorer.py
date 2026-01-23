"""
Hybrid Scorer for AgentBeats.

Computes final scores from multiple judge outputs with consistency checks.
"""
from typing import List, Optional
from dataclasses import dataclass

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import scorer_config, ScorerConfig
from core.types import JudgeOutput, HybridScore


@dataclass
class ScorerResult:
    """Detailed scoring result."""
    hybrid_score: HybridScore
    breakdown: dict


class HybridScorer:
    """
    Computes hybrid scores from judge outputs.
    
    Scoring Formula:
    1. Base = weighted combination of semantic and numeric scores
    2. Consistency penalty for disagreements
    3. Contradiction penalty if violated
    4. Hedging penalty for uncertain answers
    5. Final = max(0, Base - penalties)
    """
    
    def __init__(self, config: ScorerConfig = None):
        """
        Initialize scorer with configuration.
        
        Args:
            config: Scorer configuration (uses global config if not provided)
        """
        self.config = config or scorer_config
    
    def compute_exact_match(
        self,
        model_answer: str,
        gold_answer: str
    ) -> bool:
        """
        Check for exact string match (case-insensitive, normalized).
        
        This is a cheap baseline check.
        """
        # Normalize: lowercase, strip, collapse whitespace
        def normalize(s: str) -> str:
            return " ".join(s.lower().strip().split())
        
        return normalize(model_answer) == normalize(gold_answer)
    
    def compute(
        self,
        semantic_output: JudgeOutput,
        numeric_output: JudgeOutput,
        contradiction_output: JudgeOutput,
        model_answer: str = "",
        gold_answer: str = ""
    ) -> HybridScore:
        """
        Compute hybrid score from judge outputs.
        
        Args:
            semantic_output: Output from semantic judge
            numeric_output: Output from numeric judge
            contradiction_output: Output from contradiction judge
            model_answer: Original model answer (for exact match)
            gold_answer: Gold answer (for exact match)
        
        Returns:
            HybridScore with all components
        """
        # Initialize tracking
        consistency_flags = []
        error_taxonomy = []

        # Check for judge errors using judge_ok field
        semantic_ok = getattr(semantic_output, 'judge_ok', True)
        numeric_ok = getattr(numeric_output, 'judge_ok', True)
        contradiction_ok = getattr(contradiction_output, 'judge_ok', True)

        if not semantic_ok:
            error_taxonomy.append("semantic_judge_error")
        if not numeric_ok:
            error_taxonomy.append("numeric_judge_error")
        if not contradiction_ok:
            error_taxonomy.append("contradiction_judge_error")

        # Extract scores - only use if judge succeeded
        semantic_score = semantic_output.score if semantic_ok else 0.0
        numeric_score = numeric_output.score if numeric_ok else 0.0

        # Contradiction: only set True if judge succeeded AND returned violated=True
        # If judge failed or returned None, contradiction_violated should be False
        contradiction_violated = False
        if contradiction_ok and contradiction_output.violated is not None:
            contradiction_violated = contradiction_output.violated
        
        # Exact match check
        exact_match = self.compute_exact_match(model_answer, gold_answer) if model_answer and gold_answer else False

        # Base score: weighted average of semantic and numeric
        # Handle cases where judges fail
        if not semantic_ok and not numeric_ok:
            # Both judges failed - cannot score reliably, use conservative fallback
            base_score = 0.0
            consistency_flags.append("all_judges_failed")
        elif not semantic_ok:
            # Semantic failed, use numeric only
            base_score = numeric_score
            consistency_flags.append("semantic_judge_unavailable")
        elif not numeric_ok:
            # Numeric failed, use semantic only
            base_score = semantic_score
        elif numeric_output.tolerance_used is None or not numeric_output.parsed_gold_values:
            # No numeric content detected - use semantic only
            base_score = semantic_score
        else:
            # Both semantic and numeric available and relevant
            base_score = (semantic_score * 0.5) + (numeric_score * 0.5)
        
        # Consistency checks - only apply if judges succeeded
        consistency_penalty = 0.0

        # Case 1: Semantic pass + Numeric fail (only if both judges succeeded)
        if semantic_ok and numeric_ok and semantic_score > 0.8 and numeric_score < 0.3:
            consistency_flags.append("numeric_error")
            # Penalty proportional to confidence in disagreement
            max_conf = max(semantic_output.confidence, numeric_output.confidence)
            consistency_penalty += self.config.consistency_penalty * max_conf

        # Case 2: Numeric pass + Semantic fail (only if both judges succeeded)
        if semantic_ok and numeric_ok and numeric_score > 0.8 and semantic_score < 0.3:
            consistency_flags.append("wrong_metric")
            max_conf = max(semantic_output.confidence, numeric_output.confidence)
            consistency_penalty += self.config.consistency_penalty * max_conf

        # Contradiction penalty - only apply if contradiction judge succeeded
        contradiction_penalty_val = 0.0
        if contradiction_ok and contradiction_violated:
            contradiction_penalty_val = self.config.contradiction_penalty * contradiction_output.confidence
            consistency_flags.append("contradiction_violated")
        
        # Hedging penalty (detect explicit uncertainty language)
        # NOTE: Only trigger on clear uncertainty expressions, NOT on:
        # - "approximately" / "around" (common in financial reporting with specific numbers)
        # - Truncation or verbosity
        # - Repetition
        hedging_penalty_val = 0.0
        hedging_indicators = [
            # Explicit uncertainty phrases (must express doubt, not just approximation)
            "i'm not sure", "i am not sure", "not certain",
            "uncertain about", "unsure about", "unsure whether",
            "might be wrong", "could be wrong", "may be incorrect",
            "i don't know", "i do not know", "cannot determine",
            "possibly incorrect", "potentially wrong",
            # Speculative framing (expressing personal belief vs stating facts)
            "i think it might", "i believe it could", "it seems like maybe",
            "this could possibly", "this might possibly"
        ]
        if model_answer:
            model_lower = model_answer.lower()
            hedging_count = sum(1 for h in hedging_indicators if h in model_lower)
            # Require at least 1 explicit uncertainty phrase
            if hedging_count >= 1:
                hedging_penalty_val = self.config.hedging_penalty
                consistency_flags.append("hedged_answer")
        
        # Final score
        total_penalty = consistency_penalty + contradiction_penalty_val + hedging_penalty_val
        final_score = max(0.0, base_score - total_penalty)
        
        # Aggregate confidence
        confidences = [semantic_output.confidence, numeric_output.confidence, contradiction_output.confidence]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        return HybridScore(
            exact_match=exact_match,
            semantic_score=semantic_score,
            numeric_score=numeric_score,
            contradiction_violated=contradiction_violated,
            consistency_penalty=consistency_penalty,
            contradiction_penalty=contradiction_penalty_val,
            hedging_penalty=hedging_penalty_val,
            final_score=final_score,
            confidence=avg_confidence,
            consistency_flags=consistency_flags,
            error_taxonomy=error_taxonomy
        )
    
    def compute_with_breakdown(
        self,
        semantic_output: JudgeOutput,
        numeric_output: JudgeOutput,
        contradiction_output: JudgeOutput,
        model_answer: str = "",
        gold_answer: str = ""
    ) -> ScorerResult:
        """
        Compute hybrid score with detailed breakdown.
        
        Returns:
            ScorerResult with hybrid score and breakdown details
        """
        hybrid_score = self.compute(
            semantic_output,
            numeric_output,
            contradiction_output,
            model_answer,
            gold_answer
        )
        
        # Build breakdown
        breakdown = {
            "base_semantic": semantic_output.score,
            "base_numeric": numeric_output.score,
            "semantic_confidence": semantic_output.confidence,
            "numeric_confidence": numeric_output.confidence,
            "contradiction_confidence": contradiction_output.confidence,
            "contradiction_violated": hybrid_score.contradiction_violated,
            "consistency_penalty": hybrid_score.consistency_penalty,
            "contradiction_penalty": hybrid_score.contradiction_penalty,
            "hedging_penalty": hybrid_score.hedging_penalty,
            "total_penalty": (
                hybrid_score.consistency_penalty + 
                hybrid_score.contradiction_penalty + 
                hybrid_score.hedging_penalty
            ),
            "final_score": hybrid_score.final_score,
            "consistency_flags": hybrid_score.consistency_flags,
            "error_taxonomy": hybrid_score.error_taxonomy,
            "config_used": self.config.to_dict()
        }
        
        return ScorerResult(
            hybrid_score=hybrid_score,
            breakdown=breakdown
        )


# Singleton scorer
_scorer_instance = None

def get_scorer(config: ScorerConfig = None) -> HybridScorer:
    """Get or create scorer singleton."""
    global _scorer_instance
    if _scorer_instance is None or config is not None:
        _scorer_instance = HybridScorer(config)
    return _scorer_instance
