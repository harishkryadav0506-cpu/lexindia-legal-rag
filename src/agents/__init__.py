"""
LexIndia Multi-Agent System Package.
Provides LangGraph StateGraph, 4 specialized agents, and end-to-end query execution.
"""

from src.agents.state import LexIndiaState, AgentTraceEntry, CitationEntry
from src.agents.supervisor import SupervisorAgent
from src.agents.researcher import ResearcherAgent
from src.agents.calculator import CalculatorAgent
from src.agents.compliance_verifier import ComplianceVerifierAgent
from src.agents.graph import LexIndiaGraphBuilder, get_graph, run_query, resume_query_review
from src.agents.review_store import review_store, ReviewStore

__all__ = [
    "LexIndiaState",
    "AgentTraceEntry",
    "CitationEntry",
    "SupervisorAgent",
    "ResearcherAgent",
    "CalculatorAgent",
    "ComplianceVerifierAgent",
    "LexIndiaGraphBuilder",
    "get_graph",
    "run_query",
    "resume_query_review",
    "review_store",
    "ReviewStore",
]
