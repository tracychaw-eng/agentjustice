"""
MCP Server for Judge Tools.

Exposes judge tools as MCP-compatible endpoints via FastAPI.
All judges are stateless and return structured JSON.
"""
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import server_config, JUDGE_VERSIONS
from mcp_server.judges import (
    judge_semantic_equivalence,
    judge_numeric_tolerance,
    judge_contradiction,
)
from core.hashing import hash_prompt


# FastAPI app
app = FastAPI(
    title="AgentBeats MCP Judge Server",
    description="Stateless judge tools for semantic, numeric, and contradiction evaluation",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Request/Response Models ==============

class JudgeRequest(BaseModel):
    """Base request for all judge tools."""
    question: str = Field(..., description="The original question")
    model_answer: str = Field(..., description="Answer from model being evaluated")
    gold_answer: str = Field(..., description="Reference correct answer")
    rubric: List[Dict[str, str]] = Field(default_factory=list, description="Evaluation criteria")
    meta: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata")


class NumericJudgeRequest(JudgeRequest):
    """Request for numeric tolerance judge."""
    tolerance: Optional[float] = Field(default=None, description="Relative tolerance override")


class JudgeResponse(BaseModel):
    """Standard response from judge tools."""
    score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str
    judge_version: str
    prompt_hash: str
    latency_ms: float
    raw_output: Dict[str, Any]
    error: Optional[str] = None


class SemanticJudgeResponse(JudgeResponse):
    """Response from semantic judge."""
    criteria_matches: List[Dict[str, Any]] = Field(default_factory=list)


class NumericJudgeResponse(JudgeResponse):
    """Response from numeric judge."""
    parsed_model_values: List[Dict[str, Any]] = Field(default_factory=list)
    parsed_gold_values: List[Dict[str, Any]] = Field(default_factory=list)
    tolerance_used: float
    diff_ratio: Optional[float] = None
    value_comparisons: List[Dict[str, Any]] = Field(default_factory=list)
    failure_reason: Optional[str] = Field(default="none", description="Failure mode: extraction_failed | alignment_failed | tolerance_failed | none")


class ContradictionJudgeResponse(JudgeResponse):
    """Response from contradiction judge."""
    violated: bool
    contradiction_details: List[Dict[str, Any]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    version: str


class VersionResponse(BaseModel):
    """Version information response."""
    server_version: str
    judge_versions: Dict[str, str]
    prompt_hashes: Dict[str, str]


# ============== Endpoints ==============

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat() + "Z",
        version="1.0.0"
    )


@app.get("/version", response_model=VersionResponse)
async def get_version():
    """Get version information for all judges."""
    # Load prompt hashes
    prompts_dir = Path(__file__).parent / "prompts"
    prompt_hashes = {}
    
    for prompt_file in ["semantic.txt", "numeric.txt", "contradiction.txt"]:
        prompt_path = prompts_dir / prompt_file
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                content = f.read()
            judge_name = prompt_file.replace(".txt", "")
            version = JUDGE_VERSIONS.get(judge_name, "v1.0.0")
            prompt_hashes[judge_name] = hash_prompt(content, version)
    
    return VersionResponse(
        server_version="1.0.0",
        judge_versions=JUDGE_VERSIONS,
        prompt_hashes=prompt_hashes
    )


@app.post("/judge/semantic_equivalence", response_model=SemanticJudgeResponse)
async def semantic_equivalence_endpoint(request: JudgeRequest):
    """
    Judge semantic equivalence between model and gold answers.
    
    Evaluates whether the model answer conveys the same meaning
    and contains the same key information as the gold answer.
    """
    try:
        result = judge_semantic_equivalence(
            question=request.question,
            model_answer=request.model_answer,
            gold_answer=request.gold_answer,
            rubric=request.rubric,
            meta=request.meta
        )
        return SemanticJudgeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/judge/numeric_tolerance", response_model=NumericJudgeResponse)
async def numeric_tolerance_endpoint(request: NumericJudgeRequest):
    """
    Judge numeric accuracy with tolerance.
    
    Extracts and compares numeric values from model and gold answers,
    determining if they match within the specified tolerance.
    """
    try:
        result = judge_numeric_tolerance(
            question=request.question,
            model_answer=request.model_answer,
            gold_answer=request.gold_answer,
            rubric=request.rubric,
            meta=request.meta,
            tolerance=request.tolerance
        )
        return NumericJudgeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/judge/contradiction", response_model=ContradictionJudgeResponse)
async def contradiction_endpoint(request: JudgeRequest):
    """
    Judge for contradictions between model and gold answers.
    
    Identifies any statements in the model answer that directly
    contradict information in the gold answer.
    """
    try:
        result = judge_contradiction(
            question=request.question,
            model_answer=request.model_answer,
            gold_answer=request.gold_answer,
            rubric=request.rubric,
            meta=request.meta
        )
        return ContradictionJudgeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== MCP Tool Definitions ==============
# These define the tools for MCP discovery

MCP_TOOLS = [
    {
        "name": "judge_semantic_equivalence",
        "description": "Evaluate semantic equivalence between model and gold answers",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The original question"},
                "model_answer": {"type": "string", "description": "Answer from model"},
                "gold_answer": {"type": "string", "description": "Reference answer"},
                "rubric": {"type": "array", "description": "Evaluation criteria"},
                "meta": {"type": "object", "description": "Optional metadata"}
            },
            "required": ["question", "model_answer", "gold_answer"]
        }
    },
    {
        "name": "judge_numeric_tolerance",
        "description": "Evaluate numeric accuracy with tolerance",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The original question"},
                "model_answer": {"type": "string", "description": "Answer from model"},
                "gold_answer": {"type": "string", "description": "Reference answer"},
                "rubric": {"type": "array", "description": "Evaluation criteria"},
                "meta": {"type": "object", "description": "Optional metadata"},
                "tolerance": {"type": "number", "description": "Relative tolerance"}
            },
            "required": ["question", "model_answer", "gold_answer"]
        }
    },
    {
        "name": "judge_contradiction",
        "description": "Detect contradictions between model and gold answers",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The original question"},
                "model_answer": {"type": "string", "description": "Answer from model"},
                "gold_answer": {"type": "string", "description": "Reference answer"},
                "rubric": {"type": "array", "description": "Evaluation criteria"},
                "meta": {"type": "object", "description": "Optional metadata"}
            },
            "required": ["question", "model_answer", "gold_answer"]
        }
    }
]


@app.get("/mcp/tools")
async def list_mcp_tools():
    """List available MCP tools."""
    return {"tools": MCP_TOOLS}


# ============== MCP Module Init ==============

# Module init
def __init__():
    pass


__all__ = ["app", "MCP_TOOLS"]


def run_server(host: str = None, port: int = None):
    """Run the MCP server."""
    host = host or server_config.mcp_server_host
    port = port or server_config.mcp_server_port
    
    print(f"Starting MCP Judge Server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
