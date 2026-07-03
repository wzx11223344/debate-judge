"""
DebateJudge — Structured Policy Debate System
===============================================

A rigorous economics-focused debate engine with formal adjudication.
Not a generic "two AIs arguing" tool — this is a structured debate platform
with persona-driven debaters, formal scoring rubrics, fallacy detection,
and comprehensive transcript generation.

Key components:
    - DebateArena: Orchestration engine that runs structured debates
    - DebaterAgent: Persona-driven debaters grounded in economic traditions
    - JudgeAgent: Impartial adjudicator with formal scoring rubric
    - ScoringRubric: Multi-criterion scoring with fallacy detection
    - DebateTranscript: Full transcript with HTML/Markdown output
"""

__version__ = "0.1.0"
__author__ = "DebateJudge Contributors"

from debate_judge.arena import DebateArena
from debate_judge.agents import (
    AgentConfig,
    DebaterAgent,
    JudgeAgent,
    JudgePersona,
    Persona,
)
from debate_judge.formats import (
    DebateFormat,
    PolicyDebateFormat,
    AcademicSeminarFormat,
    RapidFireFormat,
    Turn,
    get_format,
    list_formats,
)
from debate_judge.scoring import ScoringRubric
from debate_judge.transcript import DebateTranscript

__all__ = [
    "DebateArena",
    "DebaterAgent",
    "JudgeAgent",
    "Persona",
    "JudgePersona",
    "AgentConfig",
    "DebateFormat",
    "PolicyDebateFormat",
    "AcademicSeminarFormat",
    "RapidFireFormat",
    "Turn",
    "get_format",
    "list_formats",
    "ScoringRubric",
    "DebateTranscript",
]
