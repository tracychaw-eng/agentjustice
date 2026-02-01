"""
Purple Agent - Answer Generation Agent.

Implements A2A server for answer generation with three modes:
- gold: Returns gold answer (for testing evaluator)
- llm: Generates answer using LLM
- adversarial: Returns pre-set adversarial candidate answer
"""
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import server_config, purple_agent_config, llm_config


# FastAPI A2A Agent
app = FastAPI(
    title="AgentBeats Purple Agent",
    description="Answer generation agent (A2A) with multiple modes",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Request/Response Models ==============

class GenerateRequest(BaseModel):
    """Request to generate an answer."""
    task_id: int
    question: str
    gold_answer: Optional[str] = None
    rubric: Optional[List[Dict[str, str]]] = None  # Evaluation criteria for context
    candidate_answer: Optional[str] = None  # For adversarial mode
    difficulty_level: str = "Unknown"
    question_type: str = "Unknown"


class GenerateResponse(BaseModel):
    """Response with generated answer."""
    task_id: int
    answer: str
    mode: str
    generated_at: str


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


# ============== Purple Agent Implementation ==============

class PurpleAgent:
    """
    Purple Agent for answer generation.
    
    Three modes:
    - gold: Returns the gold answer directly (for evaluator testing)
    - llm: Generates answer using LLM
    - adversarial: Returns pre-set adversarial candidate
    """
    
    def __init__(self, mode: str = None):
        """
        Initialize Purple Agent.
        
        Args:
            mode: Operating mode (gold, llm, adversarial)
        """
        self.mode = mode or purple_agent_config.mode
        
        # Initialize LLM client if needed
        if self.mode == "llm":
            self.llm_client = OpenAI(api_key=llm_config.get_api_key())
        else:
            self.llm_client = None
    
    def generate(
        self,
        question: str,
        gold_answer: str = None,
        candidate_answer: str = None,
        rubric: List[Dict[str, str]] = None,
        **kwargs
    ) -> str:
        """
        Generate an answer based on mode.

        Args:
            question: The question to answer
            gold_answer: Gold answer (for gold mode)
            candidate_answer: Pre-set answer (for adversarial mode)
            rubric: Evaluation criteria (for LLM mode context)
            **kwargs: Additional context

        Returns:
            Generated answer string
        """
        if self.mode == "gold":
            return self._gold_mode(gold_answer)
        elif self.mode == "llm":
            return self._llm_mode(question, rubric=rubric, **kwargs)
        elif self.mode == "adversarial":
            return self._adversarial_mode(candidate_answer)
        else:
            raise ValueError(f"Unknown mode: {self.mode}")
    
    def _gold_mode(self, gold_answer: str) -> str:
        """Return gold answer directly."""
        if gold_answer is None:
            return "[Gold answer not provided]"
        return gold_answer
    
    def _llm_mode(self, question: str, **kwargs) -> str:
        """Generate answer using LLM with rubric context."""
        if self.llm_client is None:
            self.llm_client = OpenAI(api_key=llm_config.get_api_key())

        difficulty = kwargs.get("difficulty_level", "Unknown")
        question_type = kwargs.get("question_type", "Unknown")
        rubric = kwargs.get("rubric", [])

        # Extract key facts from rubric criteria
        key_facts = []
        for item in rubric:
            if item.get("operator") == "correctness":
                key_facts.append(item.get("criteria", ""))

        system_prompt = """You are a financial analyst answering questions about company financials,
market trends, and business metrics. Provide accurate, concise answers based on the provided context.
Be specific with numbers, dates, and metrics. Synthesize the key facts into a coherent answer."""

        # Build user prompt with context
        context_section = ""
        if key_facts:
            context_section = "\n\nKey facts to include in your answer:\n" + "\n".join(f"- {fact}" for fact in key_facts)

        user_prompt = f"""Question Type: {question_type}
Difficulty: {difficulty}

Question: {question}{context_section}

Based on the key facts above, provide a clear, accurate, and well-structured answer that addresses the question comprehensively."""

        try:
            response = self.llm_client.chat.completions.create(
                model=llm_config.model,
                temperature=0.3,  # Lower temperature for more factual answers
                max_tokens=1024,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"[LLM generation error: {str(e)}]"
    
    def _adversarial_mode(self, candidate_answer: str) -> str:
        """Return pre-set adversarial candidate."""
        if candidate_answer is None:
            return "[Adversarial candidate not provided]"
        return candidate_answer


# Global agent instance
_agent = None

def get_agent() -> PurpleAgent:
    global _agent
    if _agent is None:
        _agent = PurpleAgent()
    return _agent

def set_mode(mode: str):
    """Change agent mode."""
    global _agent
    _agent = PurpleAgent(mode=mode)


# ============== A2A Endpoints ==============

@app.get("/a2a/card", response_model=AgentCard)
async def get_agent_card():
    """Get A2A agent card."""
    agent = get_agent()
    # Get advertised URL from app state or use default
    url = getattr(app.state, 'card_url', None) or f"http://localhost:{server_config.purple_agent_port}"

    return AgentCard(
        name="Purple Agent (Answering)",
        description=f"Answer generation agent for AgentBeats Phase-1 (mode: {agent.mode})",
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
                id="generate_answer",
                name="Generate Answer",
                description="Generate an answer to a financial question",
                tags=["generation", "finance"],
                examples=["Answer this financial question"]
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
    import uuid

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

            # Generate answer
            agent = get_agent()
            answer = agent.generate(
                question=text_content,
                gold_answer=None,
                candidate_answer=None
            )

            # Return A2A response format (Message directly in result)
            return JSONRPCResponse(
                jsonrpc="2.0",
                result={
                    "messageId": str(uuid.uuid4()),
                    "role": "agent",
                    "parts": [{"kind": "text", "text": answer}]
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
    return {
        "status": "ready",
        "mode": agent.mode,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@app.post("/a2a/generate", response_model=GenerateResponse)
async def generate_answer(request: GenerateRequest):
    """Generate an answer via A2A."""
    agent = get_agent()

    answer = agent.generate(
        question=request.question,
        gold_answer=request.gold_answer,
        candidate_answer=request.candidate_answer,
        rubric=request.rubric,  # Pass rubric for LLM mode context
        difficulty_level=request.difficulty_level,
        question_type=request.question_type
    )
    
    return GenerateResponse(
        task_id=request.task_id,
        answer=answer,
        mode=agent.mode,
        generated_at=datetime.utcnow().isoformat() + "Z"
    )


@app.post("/a2a/set_mode")
async def change_mode(mode: str):
    """Change agent mode."""
    valid_modes = ["gold", "llm", "adversarial"]
    if mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"Invalid mode. Must be one of: {valid_modes}")
    
    set_mode(mode)
    return {"status": "ok", "mode": mode}


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat() + "Z"}


# ============== Module Interface ==============

def run_server(host: str = None, port: int = None, card_url: str = None):
    """Run the Purple Agent server."""
    host = host or server_config.purple_agent_host
    port = port or server_config.purple_agent_port

    # Store card_url for agent card endpoint if provided
    if card_url:
        app.state.card_url = card_url

    print(f"Starting Purple Agent on {host}:{port} (mode: {purple_agent_config.mode})")
    if card_url:
        print(f"Advertised card URL: {card_url}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Purple Agent A2A Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8003, help="Port to listen on")
    parser.add_argument("--card-url", dest="card_url", help="Advertised agent URL for A2A card")

    args = parser.parse_args()
    run_server(host=args.host, port=args.port, card_url=args.card_url)
