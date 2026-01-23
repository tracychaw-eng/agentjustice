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
from typing import Dict, Any, Optional

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
    candidate_answer: Optional[str] = None  # For adversarial mode
    difficulty_level: str = "Unknown"
    question_type: str = "Unknown"


class GenerateResponse(BaseModel):
    """Response with generated answer."""
    task_id: int
    answer: str
    mode: str
    generated_at: str


class AgentCard(BaseModel):
    """A2A Agent Card."""
    name: str
    description: str
    version: str
    capabilities: list
    mode: str


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
        **kwargs
    ) -> str:
        """
        Generate an answer based on mode.
        
        Args:
            question: The question to answer
            gold_answer: Gold answer (for gold mode)
            candidate_answer: Pre-set answer (for adversarial mode)
            **kwargs: Additional context
        
        Returns:
            Generated answer string
        """
        if self.mode == "gold":
            return self._gold_mode(gold_answer)
        elif self.mode == "llm":
            return self._llm_mode(question, **kwargs)
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
        """Generate answer using LLM."""
        if self.llm_client is None:
            self.llm_client = OpenAI(api_key=llm_config.get_api_key())
        
        difficulty = kwargs.get("difficulty_level", "Unknown")
        question_type = kwargs.get("question_type", "Unknown")
        
        system_prompt = """You are a financial analyst answering questions about company financials, 
market trends, and business metrics. Provide accurate, concise answers based on financial data.
Be specific with numbers, dates, and metrics."""
        
        user_prompt = f"""Question Type: {question_type}
Difficulty: {difficulty}

Question: {question}

Please provide a clear, accurate answer."""
        
        try:
            response = self.llm_client.chat.completions.create(
                model=llm_config.model,
                temperature=0.7,  # Some creativity for answer generation
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
    return AgentCard(
        name="Purple Agent (Answering)",
        description="Answer generation agent for AgentBeats Phase-1",
        version="1.0.0",
        capabilities=["generate_answer"],
        mode=agent.mode
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

def run_server(host: str = None, port: int = None):
    """Run the Purple Agent server."""
    host = host or server_config.purple_agent_host
    port = port or server_config.purple_agent_port
    
    print(f"Starting Purple Agent on {host}:{port} (mode: {purple_agent_config.mode})")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
