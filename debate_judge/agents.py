"""
Debater and Judge agent personas.

Each agent is grounded in a specific economic tradition with well-defined
assumptions, values, rhetorical norms, and behavioral constraints.

DebaterAgent: Represents a position in the debate, drawing on an economic
    framework to construct arguments, rebuttals, and closing statements.

JudgeAgent: Impartial adjudicator that evaluates arguments against a
    formal scoring rubric, provides per-round scoring, and delivers a
    reasoned final opinion.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI


# ── Agent Configuration ────────────────────────────────────────────────────

@dataclass
class AgentConfig:
    """Configuration for an LLM-backed agent.

    Attributes:
        model: Model name to use
        temperature: Sampling temperature (0.7 default for creative but grounded)
        max_tokens: Maximum tokens per response
        api_base: OpenAI-compatible API base URL
        api_key: API key (use "ollama" for local Ollama)
    """

    model: str = "qwen2.5:7b"
    temperature: float = 0.7
    max_tokens: int = 1200
    api_base: str = "http://localhost:11434/v1"
    api_key: str = "ollama"


# ── Persona Definition ─────────────────────────────────────────────────────

@dataclass
class Persona:
    """An economic persona that grounds a debater's reasoning.

    Each persona represents a legitimate economic tradition — not a political
    caricature. The persona defines the assumptions, values, and rhetorical
    style that the debater should adopt, along with constraints that prevent
    the debater from making arguments that violate the tradition's norms.

    Attributes:
        name: Persona name (e.g., "Neoclassical Economist")
        school: Economic school of thought
        key_assumptions: Foundational beliefs about how the economy works
        value_priorities: What this tradition considers most important
        rhetorical_style: How arguments are typically framed
        constraints: Rules the debater must follow
    """

    name: str
    school: str
    key_assumptions: List[str] = field(default_factory=list)
    value_priorities: List[str] = field(default_factory=list)
    rhetorical_style: str = ""
    constraints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "school": self.school,
            "key_assumptions": self.key_assumptions,
            "value_priorities": self.value_priorities,
            "rhetorical_style": self.rhetorical_style,
            "constraints": self.constraints,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Persona":
        return cls(
            name=data.get("name", data.get("school", "Unknown")),
            school=data["school"],
            key_assumptions=data.get("key_assumptions", []),
            value_priorities=data.get("value_priorities", []),
            rhetorical_style=data.get("rhetorical_style", ""),
            constraints=data.get("constraints", []),
        )

    def build_system_prompt(self, role: str, topic: str) -> str:
        """Build a system prompt that instantiates this persona for a debate.

        Args:
            role: "AFFIRMATIVE" or "NEGATIVE" — which side of the debate
            topic: The debate topic/resolution

        Returns:
            System prompt string
        """
        assumptions = "\n".join(f"  - {a}" for a in self.key_assumptions)
        values = "\n".join(f"  - {v}" for v in self.value_priorities)
        constraints = "\n".join(f"  - {c}" for c in self.constraints)

        return f"""You are a {self.school} economist participating in a formal policy debate.

YOUR ECONOMIC FRAMEWORK:
School: {self.school}
Key Assumptions:
{assumptions}

Value Priorities:
{values}

Rhetorical Style: {self.rhetorical_style}

YOUR ROLE: You are arguing the {role} position on the topic: "{topic}"

DEBATE RULES:
1. You MUST stay in character as a {self.school} economist at all times
2. Every argument must be grounded in your economic framework
3. You MUST follow these constraints:
{constraints}
4. You are NOT a political caricature — you represent a legitimate, rigorous economic tradition
5. Acknowledge the strongest counterarguments honestly; do not straw-man
6. Cite mechanisms (how things work), not just correlations or assertions
7. Be specific: use numbers, cases, and institutional details when available
8. Your response must include: POSITION (your claim), EVIDENCE (supporting facts/mechanisms), and COUNTERPOINT_ACKNOWLEDGMENT (strongest objection you recognize)

FORMAT YOUR RESPONSE with these sections:
## Position
[Your core argument in 2-3 sentences]

## Evidence
[Supporting evidence, mechanisms, data, cases]

## Counterpoint Acknowledgment
[The strongest argument against your position, honestly stated]
"""


# ── Debater Agent ──────────────────────────────────────────────────────────

class DebaterAgent:
    """A persona-driven debater agent.

    Represents one side of a debate, grounded in a specific economic
    tradition. Uses an LLM (via OpenAI-compatible API) to generate
    arguments that are consistent with the persona's framework.

    Attributes:
        name: Display name for the debater
        persona: The economic persona grounding this debater
        config: LLM configuration
        role: "affirmative" or "negative"
        context: Accumulated debate history for context
    """

    def __init__(
        self,
        name: str,
        persona: Persona,
        config: Optional[AgentConfig] = None,
        role: str = "affirmative",
    ) -> None:
        """
        Args:
            name: Display name
            persona: Economic persona definition
            config: LLM configuration (uses defaults if not provided)
            role: "affirmative" or "negative"
        """
        self.name = name
        self.persona = persona
        self.config = config or AgentConfig()
        self.role = role
        self.context: List[Dict[str, str]] = []
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        """Lazy-initialized OpenAI client."""
        if self._client is None:
            self._client = OpenAI(
                base_url=self.config.api_base,
                api_key=self.config.api_key,
            )
        return self._client

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Make an LLM call with the given prompts.

        Args:
            system_prompt: System-level instruction
            user_prompt: User-level message
            max_tokens: Override default max_tokens

        Returns:
            Generated response text
        """
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.config.temperature,
                max_tokens=max_tokens or self.config.max_tokens,
            )
            content = response.choices[0].message.content or ""
            return content.strip()
        except Exception as e:
            return (
                f"[LLM Error: {e}]\n\n"
                f"As a {self.persona.school} economist, I would argue that "
                f"this topic requires careful analysis of the mechanisms at work. "
                f"Without proper empirical grounding, no firm conclusion can be drawn."
            )

    def opening_statement(self, topic: str, context: str = "") -> str:
        """Generate the opening statement for this debater.

        For the affirmative: makes the case FOR the policy.
        For the negative: makes the case AGAINST the policy.

        Args:
            topic: The debate topic/resolution
            context: Optional additional context (opponent's persona, format, etc.)

        Returns:
            The opening statement text
        """
        role_label = "AFFIRMATIVE" if self.role == "affirmative" else "NEGATIVE"
        system_prompt = self.persona.build_system_prompt(role_label, topic)

        user_prompt = f"""You are delivering your OPENING STATEMENT.

Topic: {topic}
Your position: {role_label}

{context}

This is your opening statement. You should:
1. State your core position clearly
2. Present your strongest arguments with economic reasoning
3. Establish the framework through which you will evaluate the policy
4. Preview the key points you will develop during the debate

Write a complete opening statement as a {self.persona.school} economist."""

        response = self._call_llm(system_prompt, user_prompt, max_tokens=1000)
        self.context.append({"role": "assistant", "content": response})
        self.context.append({"phase": "opening_statement"})
        return response

    def rebuttal(self, opponent_statement: str, topic: str) -> str:
        """Generate a structured rebuttal to the opponent's argument.

        Follows a 3-point rebuttal format:
        1. Identify the strongest point and address it
        2. Identify a logical or empirical weakness
        3. Re-center on your framework's strengths

        Args:
            opponent_statement: The opponent's most recent argument
            topic: The debate topic

        Returns:
            Rebuttal text in 3-point format
        """
        role_label = "AFFIRMATIVE" if self.role == "affirmative" else "NEGATIVE"
        system_prompt = self.persona.build_system_prompt(role_label, topic)

        user_prompt = f"""You are delivering your REBUTTAL.

The opponent just argued:
---
{opponent_statement[:2000]}
---

Structure your rebuttal in THREE points:
1. ENGAGEMENT: Address the opponent's strongest claim directly. Do not dodge.
2. CRITIQUE: Identify a specific weakness — empirical, logical, or institutional.
3. RE-CENTER: Reframe the issue through your {self.persona.school} framework.

Be specific. Cite mechanisms. Acknowledge what the opponent got right before critiquing."""

        response = self._call_llm(system_prompt, user_prompt, max_tokens=800)
        self.context.append({"role": "assistant", "content": response})
        self.context.append({"phase": "rebuttal"})
        return response

    def cross_examination_response(self, questions: str, topic: str) -> str:
        """Answer cross-examination questions under pressure.

        Args:
            questions: The opponent's cross-examination questions
            topic: The debate topic

        Returns:
            Answers to the cross-examination questions
        """
        role_label = "AFFIRMATIVE" if self.role == "affirmative" else "NEGATIVE"
        system_prompt = self.persona.build_system_prompt(role_label, topic)

        user_prompt = f"""You are being CROSS-EXAMINED.

The opponent asks:
---
{questions}
---

Answer each question directly. Rules:
1. Answer YES/NO where possible, then elaborate
2. If you must concede a point, do so honestly — then explain why it doesn't undermine your core argument
3. Do not filibuster or evade
4. Show intellectual honesty; the judge will penalize evasion"""

        response = self._call_llm(system_prompt, user_prompt, max_tokens=600)
        self.context.append({"role": "assistant", "content": response})
        self.context.append({"phase": "cross_examination_response"})
        return response

    def closing_statement(self, topic: str, debate_history: str) -> str:
        """Generate a closing statement that synthesizes the debate.

        Must address the strongest counterargument and make a final appeal
        grounded in the persona's value priorities.

        Args:
            topic: The debate topic
            debate_history: Summary of the full debate so far

        Returns:
            Closing statement text
        """
        role_label = "AFFIRMATIVE" if self.role == "affirmative" else "NEGATIVE"
        system_prompt = self.persona.build_system_prompt(role_label, topic)

        user_prompt = f"""You are delivering your CLOSING STATEMENT.

Debate summary:
{debate_history[:2000]}

Your closing statement must:
1. Synthesize your strongest points from this debate
2. Directly address the SINGLE strongest counterargument from your opponent
3. Explain why, even considering that counterargument, your position is correct
4. Close with an appeal grounded in your value priorities: {', '.join(self.persona.value_priorities)}
5. End with a memorable concluding statement"""

        response = self._call_llm(system_prompt, user_prompt, max_tokens=600)
        self.context.append({"role": "assistant", "content": response})
        self.context.append({"phase": "closing_statement"})
        return response

    def generate(self, custom_prompt: str, context: str = "") -> str:
        """Direct LLM call for flexible use (position papers, panel discussion, etc.).

        Args:
            custom_prompt: The instruction for this response
            context: Additional context

        Returns:
            Generated response
        """
        role_label = "AFFIRMATIVE" if self.role == "affirmative" else "NEGATIVE"
        system_prompt = self.persona.build_system_prompt(role_label, "Policy Debate")

        user_prompt = f"""Context: {context}

{custom_prompt}

Respond as a {self.persona.school} economist."""

        response = self._call_llm(system_prompt, user_prompt)
        self.context.append({"role": "assistant", "content": response})
        return response

    def __repr__(self) -> str:
        return (
            f"DebaterAgent(name={self.name!r}, school={self.persona.school!r}, "
            f"role={self.role!r})"
        )


# ── Judge Agent ────────────────────────────────────────────────────────────

@dataclass
class JudgePersona:
    """Configuration for a judge agent.

    Attributes:
        name: Judge name
        school: Judging philosophy label
        description: How the judge approaches adjudication
        value_priorities: What the judge considers important
        scoring_philosophy: How the judge assigns scores
    """

    name: str = "Impartial Economist"
    school: str = "Methodological Pluralist"
    description: str = "An impartial adjudicator trained in multiple economic traditions."
    value_priorities: List[str] = field(default_factory=lambda: [
        "Rigorous empiricism",
        "Logical consistency",
        "Constructive scholarly exchange",
    ])
    scoring_philosophy: str = (
        "Rewards evidence quality and honest engagement with opposing views. "
        "Penalizes fallacy, evasion, and appeals to authority without mechanism."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "school": self.school,
            "description": self.description,
            "value_priorities": self.value_priorities,
            "scoring_philosophy": self.scoring_philosophy,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JudgePersona":
        return cls(
            name=data.get("name", "Impartial Economist"),
            school=data.get("school", "Methodological Pluralist"),
            description=data.get("description", ""),
            value_priorities=data.get("value_priorities", []),
            scoring_philosophy=data.get("scoring_philosophy", ""),
        )


class JudgeAgent:
    """An impartial adjudicator agent.

    Evaluates debate rounds using a formal scoring rubric and produces
    both per-round scores and a comprehensive final opinion.

    The judge does NOT favor any economic tradition — it evaluates the
    quality of argumentation, evidence, and engagement, not ideological
    alignment.

    Attributes:
        name: Display name for the judge
        persona: Judge persona configuration
        rubric: The scoring rubric to use
        config: LLM configuration
    """

    def __init__(
        self,
        name: str = "Judge",
        persona: Optional[JudgePersona] = None,
        rubric: Optional[Any] = None,  # ScoringRubric, imported lazily
        config: Optional[AgentConfig] = None,
    ) -> None:
        """
        Args:
            name: Display name
            persona: Judge persona configuration
            rubric: ScoringRubric instance (imported from scoring.py)
            config: LLM configuration
        """
        self.name = name
        self.persona = persona or JudgePersona()
        self._rubric = rubric
        self.config = config or AgentConfig()
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                base_url=self.config.api_base,
                api_key=self.config.api_key,
            )
        return self._client

    @property
    def rubric(self):
        """Lazy import of ScoringRubric to avoid circular imports."""
        if self._rubric is None:
            from debate_judge.scoring import ScoringRubric
            self._rubric = ScoringRubric()
        return self._rubric

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Make an LLM call for judge evaluation."""
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,  # Lower temperature for judging — more consistent
                max_tokens=max_tokens or self.config.max_tokens,
            )
            content = response.choices[0].message.content or ""
            return content.strip()
        except Exception as e:
            return f"[LLM Error: {e}]"

    def _build_judge_system_prompt(self) -> str:
        """Build the system prompt for the judge."""
        priorities = "\n".join(f"  - {p}" for p in self.persona.value_priorities)
        return f"""You are an impartial debate judge: {self.persona.name}.

YOUR JUDGING PHILOSOPHY:
School: {self.persona.school}
{self.persona.description}

Value Priorities:
{priorities}

Scoring Philosophy: {self.persona.scoring_philosophy}

JUDGING RULES:
1. You do NOT favor any economic ideology — you evaluate argument QUALITY
2. Score based on: evidence quality, logic, engagement with counterarguments, feasibility, value clarity, rhetoric
3. You MUST provide specific justification for every score
4. Identify specific strengths and weaknesses in each debater's performance
5. Your final opinion must be detailed, reasoned, and fair to both sides
6. If a debater made a factual error, note it. If they dodged a question, flag it.
7. The better argument wins, regardless of which position you personally prefer
"""

    def evaluate_round(
        self,
        debater_a: DebaterAgent,
        debater_b: DebaterAgent,
        exchange: Dict[str, str],
        rubric: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Score a single round of debate.

        Uses both rule-based scoring (from ScoringRubric) and LLM evaluation
        for nuanced judgment.

        Args:
            debater_a: First debater
            debater_b: Second debater
            exchange: Dict with keys like "a_text", "b_text", "phase"
            rubric: Optional ScoringRubric override

        Returns:
            Dict with scores, justifications, and LLM commentary
        """
        r = rubric or self.rubric

        # Rule-based baseline scoring
        round_score = r.score_exchange(
            exchange.get("a_text", ""),
            exchange.get("b_text", ""),
            phase=exchange.get("phase", ""),
        )

        # LLM-enhanced evaluation
        a_name = debater_a.name
        b_name = debater_b.name
        a_text = exchange.get("a_text", "")
        b_text = exchange.get("b_text", "")
        phase = exchange.get("phase", "exchange")

        user_prompt = f"""Evaluate this debate round: {phase}

{a_name} ({debater_a.persona.school}):
---
{a_text[:1500]}
---

{b_name} ({debater_b.persona.school}):
---
{b_text[:1500]}
---

For each debater, provide:
1. A brief assessment of their strongest point
2. A brief assessment of their weakest point
3. Whether they engaged honestly with the opponent's argument
4. A recommended score adjustment (if any) to the baseline scores below

Baseline scores: {a_name}={round_score.a_total:.1f}, {b_name}={round_score.b_total:.1f}

Return your evaluation as a JSON object with keys: a_assessment, b_assessment, score_adjustment_a, score_adjustment_b, notes"""

        llm_response = self._call_llm(
            self._build_judge_system_prompt(),
            user_prompt,
            max_tokens=800,
        )

        # Try to extract JSON from response
        llm_data: Dict[str, Any] = {}
        try:
            json_match = re.search(r"\{[\s\S]*\}", llm_response)
            if json_match:
                llm_data = json.loads(json_match.group())
        except (json.JSONDecodeError, AttributeError):
            llm_data = {"notes": llm_response}

        # Merge rule-based and LLM scores
        adjustment_a = float(llm_data.get("score_adjustment_a", 0))
        adjustment_b = float(llm_data.get("score_adjustment_b", 0))

        final_a = round(max(0, min(10, round_score.a_total + adjustment_a)), 2)
        final_b = round(max(0, min(10, round_score.b_total + adjustment_b)), 2)

        return {
            "phase": phase,
            "a_debater": a_name,
            "b_debater": b_name,
            "a_total": final_a,
            "b_total": final_b,
            "a_scores": [
                {"criterion": s.criterion, "score": s.score, "justification": s.justification}
                for s in round_score.a_scores
            ],
            "b_scores": [
                {"criterion": s.criterion, "score": s.score, "justification": s.justification}
                for s in round_score.b_scores
            ],
            "llm_assessment": llm_data.get("notes", llm_response[:300]),
            "a_assessment": llm_data.get("a_assessment", ""),
            "b_assessment": llm_data.get("b_assessment", ""),
            "winner": "a" if final_a > final_b else "b" if final_b > final_a else "tie",
        }

    def final_adjudication(
        self,
        full_transcript: str,
        round_scores: List[Dict[str, Any]],
        debater_a: DebaterAgent,
        debater_b: DebaterAgent,
    ) -> Dict[str, Any]:
        """Deliver comprehensive final ruling.

        Args:
            full_transcript: Complete debate transcript
            round_scores: Per-round evaluation results
            debater_a: First debater
            debater_b: Second debater

        Returns:
            Dict with winner, scores, reasoning, and opinion
        """
        # Compute composite score
        from debate_judge.scoring import RoundScore

        composite_round_scores = []
        for rs in round_scores:
            cs = RoundScore(round_name=rs["phase"])
            cs.a_total = rs["a_total"]
            cs.b_total = rs["b_total"]
            composite_round_scores.append(cs)

        composite = self.rubric.composite_score(composite_round_scores)

        # LLM final opinion
        user_prompt = f"""Deliver your FINAL ADJUDICATION.

Debate Topic: {full_transcript[:200]}

Debaters:
- {debater_a.name} ({debater_a.persona.school}): {debater_a.persona.rhetorical_style}
- {debater_b.name} ({debater_b.persona.school}): {debater_b.persona.rhetorical_style}

Round Scores:
{json.dumps(composite['round_scores'], indent=2)}

Composite: Winner={composite['winner']}, Margin={composite['margin']}

Write a detailed final opinion that:
1. Declares the winner and explains why
2. Analyzes the decisive factors that determined the outcome
3. Notes the strongest argument from EACH side
4. Identifies where the losing debater could have improved
5. Provides a reasoned, fair, scholarly judgment

Format your response with sections: ## Verdict, ## Decisive Factors, ## Strengths (both sides), ## Areas for Improvement, ## Final Remarks"""

        opinion = self._call_llm(
            self._build_judge_system_prompt(),
            user_prompt,
            max_tokens=1200,
        )

        return {
            "winner": composite["winner"],
            "winner_name": debater_a.name if composite["winner"] == "a" else debater_b.name if composite["winner"] == "b" else "Tie",
            "margin": composite["margin"],
            "a_average": composite["a_average"],
            "b_average": composite["b_average"],
            "round_scores": composite["round_scores"],
            "criterion_breakdown": composite["criterion_breakdown"],
            "opinion": opinion,
        }

    def write_opinion(
        self, victor: str, reasoning: str, key_factors: List[str]
    ) -> str:
        """Generate a reasoned judgment.

        Args:
            victor: Name of the winning debater or "Tie"
            reasoning: The core reasoning for the decision
            key_factors: List of decisive factors

        Returns:
            Formatted opinion text
        """
        factors_text = "\n".join(f"  {i+1}. {f}" for i, f in enumerate(key_factors))

        return f"""## Judgment of {self.name}

**Winner: {victor}**

### Reasoning
{reasoning}

### Key Factors
{factors_text}

### Judging Philosophy
{self.persona.scoring_philosophy}

---
*This judgment reflects the quality of argumentation and evidence presented, 
not the ideological alignment of the judge with any position.*
"""

    def __repr__(self) -> str:
        return f"JudgeAgent(name={self.name!r}, school={self.persona.school!r})"
