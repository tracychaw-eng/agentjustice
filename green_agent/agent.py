"""
Green Agent - Main Orchestration Agent.

Implements A2A server for evaluation orchestration.
Calls MCP judges, aggregates scores, and logs traces.
"""
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import uuid
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    server_config,
    scorer_config,
    JUDGE_VERSIONS,
    DATASET_PATH,
    ADVERSARIAL_PATH,
    get_config_summary
)
from core.types import Task, TaskTrace, JudgeCall, RunManifest
from core.env import load_canonical_dataset, load_adversarial_dataset
from core.hashing import compute_dataset_hash
from green_agent.mcp_client import MCPClient, get_mcp_client
from green_agent.scorer import HybridScorer, get_scorer
from green_agent.logger import AuditLogger, create_run_logger


# FastAPI A2A Agent
app = FastAPI(
    title="AgentBeats Green Agent",
    description="Orchestration agent for evaluation (A2A)",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== A2A Request/Response Models ==============

class EvaluateTaskRequest(BaseModel):
    """Request to evaluate a single task."""
    task_id: int
    question: str
    gold_answer: str
    rubric: List[Dict[str, str]]
    model_answer: str
    difficulty_level: str = "Unknown"
    question_type: str = "Unknown"
    expert_time_mins: float = 0.0
    source: str = "canonical"
    transformation_type: Optional[str] = None
    expected_outcome: Optional[str] = None


class EvaluationResult(BaseModel):
    """Result of evaluating a single task."""
    task_id: int
    final_score: float
    semantic_score: float
    numeric_score: float
    contradiction_violated: bool
    consistency_flags: List[str]
    error_taxonomy: List[str]
    confidence: float


class RunEvaluationRequest(BaseModel):
    """Request to run full evaluation."""
    dataset: str = "canonical"  # "canonical" or "adversarial"
    run_id: Optional[str] = None
    purple_agent_id: Optional[str] = "purple_agent"  # For AgentBeats leaderboard


class RunEvaluationResponse(BaseModel):
    """Response from full evaluation run."""
    run_id: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    avg_score: float
    logs_dir: str


class AgentCapabilities(BaseModel):
    """A2A Agent Capabilities."""
    streaming: bool = False
    pushNotifications: bool = False
    stateTransitionHistory: bool = False


class AgentSkill(BaseModel):
    """A2A Agent Skill."""
    id: str
    name: str
    description: str
    tags: List[str] = []
    examples: List[str] = []


class AgentCard(BaseModel):
    """A2A Agent Card (Google A2A Standard)."""
    name: str
    description: str
    version: str
    url: str
    capabilities: AgentCapabilities
    defaultInputModes: List[str] = ["text"]
    defaultOutputModes: List[str] = ["text"]
    skills: List[AgentSkill] = []


# ============== Green Agent Implementation ==============

class GreenAgent:
    """
    Green Agent orchestrator.
    
    Coordinates evaluation of tasks:
    1. Gets model answer from Purple Agent
    2. Calls MCP judges
    3. Computes hybrid score
    4. Logs traces
    """
    
    def __init__(self):
        self.mcp_client = get_mcp_client()
        self.scorer = get_scorer()
        self.logger: Optional[AuditLogger] = None
        self.run_id: Optional[str] = None
    
    def start_run(self, run_id: str = None) -> str:
        """Start a new evaluation run."""
        self.run_id = run_id or f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self.logger = create_run_logger(self.run_id)
        return self.run_id
    
    async def get_model_answer(self, task: Task) -> str:
        """
        Get model answer from Purple Agent via A2A.
        
        Args:
            task: The task to get answer for
        
        Returns:
            Model answer string
        """
        # For adversarial tasks with pre-set candidate answer
        if task.source == "adversarial" and task.candidate_answer:
            return task.candidate_answer
        
        # Call Purple Agent
        purple_url = server_config.purple_agent_url
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{purple_url}/a2a/generate",
                    json={
                        "task_id": task.task_id,
                        "question": task.question,
                        "gold_answer": task.gold_answer,  # For gold mode
                        "rubric": task.rubric,  # Pass rubric for LLM mode context
                        "difficulty_level": task.difficulty_level,
                        "question_type": task.question_type
                    }
                )
                response.raise_for_status()
                data = response.json()
                return data.get("answer", "")
        except Exception as e:
            # Fallback: return empty if Purple Agent unavailable
            return f"[Error getting model answer: {str(e)}]"
    
    def evaluate_single(
        self,
        task: Task,
        model_answer: str
    ) -> TaskTrace:
        """
        Evaluate a single task.
        
        Args:
            task: The task to evaluate
            model_answer: Answer from model
        
        Returns:
            Complete task trace
        """
        timestamp = datetime.utcnow().isoformat() + "Z"
        judge_calls = []
        error_taxonomy = []
        
        # Build metadata for judges
        meta = {
            "task_id": task.task_id,
            "difficulty": task.difficulty_level,
            "question_type": task.question_type,
            "source": task.source
        }
        
        # Call semantic judge
        semantic_output = self.mcp_client.call_semantic_judge(
            question=task.question,
            model_answer=model_answer,
            gold_answer=task.gold_answer,
            rubric=task.rubric,
            meta=meta
        )
        judge_calls.append(self.mcp_client.to_judge_call(
            semantic_output,
            {"question": task.question, "model_answer": model_answer, "gold_answer": task.gold_answer}
        ))
        if semantic_output.raw_output.get("error"):
            error_taxonomy.append("semantic_judge_error")
        
        # Call numeric judge
        numeric_output = self.mcp_client.call_numeric_judge(
            question=task.question,
            model_answer=model_answer,
            gold_answer=task.gold_answer,
            rubric=task.rubric,
            meta=meta
        )
        judge_calls.append(self.mcp_client.to_judge_call(
            numeric_output,
            {"question": task.question, "model_answer": model_answer, "gold_answer": task.gold_answer}
        ))
        if numeric_output.raw_output.get("error"):
            error_taxonomy.append("numeric_judge_error")
        
        # Call contradiction judge
        contradiction_output = self.mcp_client.call_contradiction_judge(
            question=task.question,
            model_answer=model_answer,
            gold_answer=task.gold_answer,
            rubric=task.rubric,
            meta=meta
        )
        judge_calls.append(self.mcp_client.to_judge_call(
            contradiction_output,
            {"question": task.question, "model_answer": model_answer, "gold_answer": task.gold_answer}
        ))
        if contradiction_output.raw_output.get("error"):
            error_taxonomy.append("contradiction_judge_error")
        
        # Compute hybrid score
        hybrid_score = self.scorer.compute(
            semantic_output=semantic_output,
            numeric_output=numeric_output,
            contradiction_output=contradiction_output,
            model_answer=model_answer,
            gold_answer=task.gold_answer
        )
        
        # Merge error taxonomies
        error_taxonomy.extend(hybrid_score.error_taxonomy)
        
        # Build intermediate signals
        intermediate_signals = {
            "exact_match": hybrid_score.exact_match,
            "semantic_score": hybrid_score.semantic_score,
            "numeric_score": hybrid_score.numeric_score,
            "contradiction_violated": hybrid_score.contradiction_violated,
            "consistency_flags": hybrid_score.consistency_flags,
            "consistency_penalty": hybrid_score.consistency_penalty,
            "contradiction_penalty": hybrid_score.contradiction_penalty,
            "hedging_penalty": hybrid_score.hedging_penalty
        }
        
        # Create trace
        trace = TaskTrace(
            timestamp=timestamp,
            task_id=task.task_id,
            difficulty_level=task.difficulty_level,
            question_type=task.question_type,
            expert_time_mins=task.expert_time_mins,
            question=task.question,
            gold_answer=task.gold_answer,
            rubric=task.rubric,
            model_answer=model_answer,
            judge_calls=judge_calls,
            intermediate_signals=intermediate_signals,
            hybrid_score=hybrid_score,
            error_taxonomy=list(set(error_taxonomy)),
            source=task.source,
            transformation_type=task.transformation_type,
            expected_outcome=task.expected_outcome
        )
        
        # Log trace
        if self.logger:
            self.logger.log_trace(trace)
        
        return trace
    
    async def run_evaluation(
        self,
        dataset_path: Path = DATASET_PATH,
        is_adversarial: bool = False,
        limit: int = None
    ) -> Dict[str, Any]:
        """
        Run evaluation on full dataset.

        Args:
            dataset_path: Path to dataset file
            is_adversarial: Whether this is adversarial evaluation
            limit: Optional limit on number of tasks to evaluate

        Returns:
            Summary of evaluation results
        """
        # Load dataset
        if is_adversarial:
            env = load_adversarial_dataset(dataset_path)
        else:
            env = load_canonical_dataset(dataset_path)

        results = []
        completed = 0
        failed = 0

        # Iterate through tasks
        for idx, task in enumerate(env):
            if limit and idx >= limit:
                break
            try:
                # Get model answer
                model_answer = await self.get_model_answer(task)
                
                # Evaluate
                trace = self.evaluate_single(task, model_answer)
                
                results.append({
                    "task_id": task.task_id,
                    "difficulty": task.difficulty_level,
                    "score": trace.hybrid_score.final_score,
                    "errors": trace.error_taxonomy
                })
                completed += 1
                
            except Exception as e:
                failed += 1
                results.append({
                    "task_id": task.task_id,
                    "difficulty": task.difficulty_level,
                    "score": 0.0,
                    "errors": [f"evaluation_error: {str(e)}"]
                })
        
        # Compute summary
        scores = [r["score"] for r in results]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        return {
            "run_id": self.run_id,
            "dataset": "adversarial" if is_adversarial else "canonical",
            "total_tasks": len(env),
            "completed": completed,
            "failed": failed,
            "avg_score": avg_score,
            "results": results
        }
    
    def create_manifest(
        self,
        dataset_path: Path,
        total_tasks: int,
        completed_tasks: int,
        failed_tasks: int
    ) -> RunManifest:
        """Create a run manifest."""
        # Get prompt hashes from MCP server
        try:
            version_info = self.mcp_client.get_versions()
            prompt_hashes = version_info.get("prompt_hashes", {})
        except:
            prompt_hashes = {}
        
        manifest = RunManifest(
            run_id=self.run_id or "unknown",
            timestamp=datetime.utcnow().isoformat() + "Z",
            dataset_path=str(dataset_path),
            dataset_hash=compute_dataset_hash(dataset_path) if dataset_path.exists() else "",
            judge_versions=JUDGE_VERSIONS,
            prompt_hashes=prompt_hashes,
            scorer_config=scorer_config.to_dict(),
            random_seed=42,
            llm_config=get_config_summary().get("llm", {}),
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks
        )
        
        if self.logger:
            self.logger.log_manifest(manifest)
        
        return manifest


# Global agent instance
_agent = None

def get_agent() -> GreenAgent:
    global _agent
    if _agent is None:
        _agent = GreenAgent()
    return _agent


# ============== A2A Endpoints ==============

@app.get("/a2a/card", response_model=AgentCard)
async def get_agent_card():
    """Get A2A agent card."""
    # Get advertised URL from app state or use default
    url = getattr(app.state, 'card_url', None) or f"http://localhost:{server_config.green_agent_port}"

    return AgentCard(
        name="Green Agent (Evaluator)",
        description="Orchestration agent for AgentBeats Phase-1 evaluation",
        version="1.0.0",
        url=url,
        capabilities=AgentCapabilities(
            streaming=False,
            pushNotifications=False,
            stateTransitionHistory=False
        ),
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        skills=[
            AgentSkill(
                id="evaluate_task",
                name="Evaluate Task",
                description="Evaluate a single financial Q&A task",
                tags=["evaluation", "finance"],
                examples=["Evaluate this answer against the gold standard"]
            ),
            AgentSkill(
                id="run_evaluation",
                name="Run Full Evaluation",
                description="Run evaluation on canonical or adversarial dataset",
                tags=["evaluation", "batch"],
                examples=["Run evaluation on canonical dataset"]
            )
        ]
    )


@app.get("/.well-known/agent-card.json", response_model=AgentCard)
async def get_wellknown_agent_card():
    """Get A2A agent card (Google A2A standard discovery endpoint)."""
    return await get_agent_card()


# ============== A2A JSON-RPC Endpoint ==============

class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 Request."""
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[str] = None


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 Response."""
    jsonrpc: str = "2.0"
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[str] = None


@app.post("/")
async def jsonrpc_endpoint(request: JSONRPCRequest):
    """
    A2A JSON-RPC endpoint.

    Handles A2A protocol methods like message/send.
    """
    try:
        if request.method == "message/send":
            # Extract message from params
            params = request.params or {}
            message = params.get("message", {})
            parts = message.get("parts", [])

            # Extract text from message parts
            text_content = ""
            for part in parts:
                if part.get("kind") == "text":
                    text_content += part.get("text", "")

            # Process the message - run evaluation
            agent = get_agent()
            if not agent.run_id:
                agent.start_run()

            # Default response
            response_text = f"Evaluation started. Run ID: {agent.run_id}"

            # Get task limit from environment (default to None = all tasks)
            import os
            task_limit = int(os.getenv("TASK_LIMIT", "0")) or None

            # Check if requesting canonical, adversarial, or both evaluations
            if "both" in text_content.lower():
                # Run both canonical and adversarial evaluations
                canonical_results = None
                adversarial_results = None

                if DATASET_PATH.exists():
                    print(f"[Green Agent] Running canonical evaluation...")
                    canonical_results = await agent.run_evaluation(DATASET_PATH, is_adversarial=False, limit=task_limit)

                if ADVERSARIAL_PATH.exists():
                    print(f"[Green Agent] Running adversarial evaluation...")
                    adversarial_results = await agent.run_evaluation(ADVERSARIAL_PATH, is_adversarial=True, limit=task_limit)

                # Build combined response
                parts = []
                total_tasks = 0
                if canonical_results:
                    parts.append(f"Canonical: {canonical_results['completed']} tasks, {canonical_results['avg_score']:.2%}")
                    total_tasks += canonical_results['completed']
                if adversarial_results:
                    parts.append(f"Adversarial: {adversarial_results['completed']} tasks, {adversarial_results['avg_score']:.2%}")
                    total_tasks += adversarial_results['completed']

                response_text = f"Both evaluations complete. {' | '.join(parts)}. Total: {total_tasks} tasks"

            elif "adversarial" in text_content.lower():
                if ADVERSARIAL_PATH.exists():
                    results = await agent.run_evaluation(ADVERSARIAL_PATH, is_adversarial=True, limit=task_limit)
                    response_text = f"Adversarial evaluation complete. Tasks: {results['completed']}, Avg Score: {results['avg_score']:.2%}"
            elif "canonical" in text_content.lower() or "evaluate" in text_content.lower():
                if DATASET_PATH.exists():
                    results = await agent.run_evaluation(DATASET_PATH, is_adversarial=False, limit=task_limit)
                    response_text = f"Canonical evaluation complete. Tasks: {results['completed']}, Avg Score: {results['avg_score']:.2%}"

            # Write results with purple agent's AgentBeats ID
            if agent.logger:
                # Try to read purple agent ID from scenario config
                purple_agent_id = "purple_agent"  # Default fallback
                scenario_path = Path("/app/scenario.toml")
                if scenario_path.exists():
                    try:
                        import tomli
                        with open(scenario_path, "rb") as f:
                            scenario = tomli.load(f)
                        participants = scenario.get("participants", [])
                        print(f"[Green Agent] Found {len(participants)} participants in scenario")
                        for p in participants:
                            print(f"[Green Agent] Participant: role={p.get('role')}, id={p.get('agentbeats_id', 'N/A')}")
                            if p.get("role") == "purple_agent" and "agentbeats_id" in p:
                                purple_agent_id = p["agentbeats_id"]
                                print(f"[Green Agent] Using purple agent ID: {purple_agent_id}")
                                break
                    except Exception as e:
                        print(f"[Green Agent] Error reading scenario: {e}")
                agent.logger.write_agentbeats_results(purple_agent_id)

            # Return A2A response format (Message directly in result)
            return JSONRPCResponse(
                jsonrpc="2.0",
                result={
                    "messageId": str(uuid.uuid4()),
                    "role": "agent",
                    "parts": [{"kind": "text", "text": response_text}]
                },
                id=request.id
            )

        else:
            return JSONRPCResponse(
                jsonrpc="2.0",
                error={"code": -32601, "message": f"Method not found: {request.method}"},
                id=request.id
            )

    except Exception as e:
        return JSONRPCResponse(
            jsonrpc="2.0",
            error={"code": -32603, "message": str(e)},
            id=request.id
        )


@app.get("/a2a/status")
async def get_status():
    """Get agent status."""
    agent = get_agent()
    mcp_healthy = agent.mcp_client.health_check()
    
    return {
        "status": "ready" if mcp_healthy else "degraded",
        "mcp_server": "healthy" if mcp_healthy else "unavailable",
        "current_run": agent.run_id,
        "logger_stats": agent.logger.get_stats() if agent.logger else None
    }


@app.post("/a2a/evaluate", response_model=EvaluationResult)
async def evaluate_task(request: EvaluateTaskRequest):
    """Evaluate a single task via A2A."""
    agent = get_agent()
    
    # Ensure run is started
    if not agent.run_id:
        agent.start_run()
    
    # Create task from request
    task = Task(
        task_id=request.task_id,
        question=request.question,
        gold_answer=request.gold_answer,
        rubric=request.rubric,
        question_type=request.question_type,
        expert_time_mins=request.expert_time_mins,
        difficulty_level=request.difficulty_level,
        source=request.source,
        transformation_type=request.transformation_type,
        expected_outcome=request.expected_outcome
    )
    
    # Evaluate
    trace = agent.evaluate_single(task, request.model_answer)
    
    return EvaluationResult(
        task_id=task.task_id,
        final_score=trace.hybrid_score.final_score,
        semantic_score=trace.hybrid_score.semantic_score,
        numeric_score=trace.hybrid_score.numeric_score,
        contradiction_violated=trace.hybrid_score.contradiction_violated,
        consistency_flags=trace.hybrid_score.consistency_flags,
        error_taxonomy=trace.error_taxonomy,
        confidence=trace.hybrid_score.confidence
    )


@app.post("/a2a/run", response_model=RunEvaluationResponse)
async def run_evaluation(request: RunEvaluationRequest):
    """Run full evaluation on dataset via A2A."""
    agent = get_agent()

    # Start new run
    run_id = agent.start_run(request.run_id)

    # Determine dataset
    if request.dataset == "adversarial":
        dataset_path = ADVERSARIAL_PATH
        is_adversarial = True
    else:
        dataset_path = DATASET_PATH
        is_adversarial = False

    if not dataset_path.exists():
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_path}")

    # Run evaluation
    results = await agent.run_evaluation(dataset_path, is_adversarial)

    # Create manifest
    agent.create_manifest(
        dataset_path=dataset_path,
        total_tasks=results["total_tasks"],
        completed_tasks=results["completed"],
        failed_tasks=results["failed"]
    )

    # Write AgentBeats-compatible results JSON
    if agent.logger:
        results_file = agent.logger.write_agentbeats_results(request.purple_agent_id)
        print(f"[Green Agent] Results written to: {results_file}")

    return RunEvaluationResponse(
        run_id=run_id,
        total_tasks=results["total_tasks"],
        completed_tasks=results["completed"],
        failed_tasks=results["failed"],
        avg_score=results["avg_score"],
        logs_dir=str(agent.logger.run_dir) if agent.logger else ""
    )


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat() + "Z"}


# ============== Module Interface ==============

def run_server(host: str = None, port: int = None, card_url: str = None):
    """Run the Green Agent server."""
    host = host or server_config.green_agent_host
    port = port or server_config.green_agent_port

    # Store card_url for agent card endpoint if provided
    if card_url:
        app.state.card_url = card_url

    print(f"Starting Green Agent on {host}:{port}")
    if card_url:
        print(f"Advertised card URL: {card_url}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Green Agent A2A Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8002, help="Port to listen on")
    parser.add_argument("--card-url", dest="card_url", help="Advertised agent URL for A2A card")

    args = parser.parse_args()
    run_server(host=args.host, port=args.port, card_url=args.card_url)
