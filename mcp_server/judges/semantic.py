"""
Semantic Equivalence Judge.

Evaluates whether model answer is semantically equivalent to gold answer.
"""
import json
import time
from pathlib import Path
from typing import Dict, Any, List

from openai import OpenAI
from pydantic import BaseModel, Field

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import llm_config, JUDGE_VERSIONS
from core.hashing import hash_prompt, hash_string


# Load pinned prompt
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "semantic.txt"
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

PROMPT_HASH = hash_prompt(SYSTEM_PROMPT, JUDGE_VERSIONS["semantic"])


class CriteriaMatchResult(BaseModel):
    criteria: str
    matched: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""


class SemanticJudgeOutput(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    criteria_matches: List[CriteriaMatchResult] = Field(default_factory=list)


class SemanticJudge:
    """
    Semantic equivalence judge using LLM.
    
    Stateless - each call is independent.
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=llm_config.get_api_key())
        self.model = llm_config.model
        self.temperature = llm_config.temperature
        self.max_tokens = llm_config.max_tokens
        self.version = JUDGE_VERSIONS["semantic"]
        self.prompt_hash = PROMPT_HASH
    
    def judge(
        self,
        question: str,
        model_answer: str,
        gold_answer: str,
        rubric: List[Dict[str, str]],
        meta: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Judge semantic equivalence.
        
        Args:
            question: The original question
            model_answer: Answer from model being evaluated
            gold_answer: Reference correct answer
            rubric: List of evaluation criteria
            meta: Optional metadata (task_id, difficulty, etc.)
        
        Returns:
            Structured judgment result
        """
        start_time = time.perf_counter()
        
        # Filter for correctness criteria
        correctness_criteria = [
            c for c in rubric 
            if c.get("operator") == "correctness"
        ]
        
        # Build user prompt
        user_prompt = self._build_user_prompt(
            question, model_answer, gold_answer, correctness_criteria
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            # Parse response
            content = response.choices[0].message.content
            result = json.loads(content)
            
            # Validate with Pydantic
            validated = SemanticJudgeOutput(**result)
            
            return {
                "score": validated.score,
                "confidence": validated.confidence,
                "reason": validated.reason,
                "criteria_matches": [cm.model_dump() for cm in validated.criteria_matches],
                "judge_version": self.version,
                "prompt_hash": self.prompt_hash,
                "latency_ms": latency_ms,
                "raw_output": result,
                "error": None
            }
            
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return {
                "score": 0.0,
                "confidence": 0.0,
                "reason": f"Judge error: {str(e)}",
                "criteria_matches": [],
                "judge_version": self.version,
                "prompt_hash": self.prompt_hash,
                "latency_ms": latency_ms,
                "raw_output": {},
                "error": str(e)
            }
    
    def _build_user_prompt(
        self,
        question: str,
        model_answer: str,
        gold_answer: str,
        criteria: List[Dict[str, str]]
    ) -> str:
        """Build the user prompt for evaluation."""
        criteria_text = "\n".join([
            f"- {c.get('criteria', '')}" for c in criteria
        ]) if criteria else "No specific criteria provided."
        
        return f"""## QUESTION
{question}

## MODEL ANSWER
{model_answer}

## GOLD ANSWER
{gold_answer}

## RUBRIC CRITERIA
{criteria_text}

Please evaluate and return your judgment as JSON."""


# Singleton instance
_judge_instance = None

def get_judge() -> SemanticJudge:
    global _judge_instance
    if _judge_instance is None:
        _judge_instance = SemanticJudge()
    return _judge_instance


def judge_semantic_equivalence(
    question: str,
    model_answer: str,
    gold_answer: str,
    rubric: List[Dict[str, str]],
    meta: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Public interface for semantic judgment.
    
    This is the function called by the MCP server.
    """
    judge = get_judge()
    return judge.judge(question, model_answer, gold_answer, rubric, meta)
