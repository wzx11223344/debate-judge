"""
Debate orchestration engine.

DebateArena is the central coordinator that runs structured debates between
two persona-driven debater agents, with a judge agent providing per-round
scoring and a final verdict.

The arena enforces the debate format (turn structure, timing constraints),
feeds context between rounds, and produces a complete transcript with scores.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from debate_judge.agents import (
    AgentConfig,
    DebaterAgent,
    JudgeAgent,
    JudgePersona,
    Persona,
)
from debate_judge.formats import DebateFormat, PolicyDebateFormat, Turn
from debate_judge.scoring import ScoringRubric
from debate_judge.transcript import DebateTranscript


class DebateArena:
    """Central orchestration engine for structured policy debates.

    Coordinates the full debate lifecycle:
        1. Initialize debaters and judge with personas
        2. Execute turns according to the debate format
        3. Feed context between rounds
        4. Score each exchange
        5. Produce final verdict and transcript

    Each step returns structured output that feeds into the next step.
    The arena enforces the debate format's turn structure and ensures
    that all LLM calls use consistent configuration.

    Attributes:
        topic: The debate topic/resolution
        debater_a: First debater agent
        debater_b: Second debater agent
        judge: Judge agent
        format: Debate format definition
        transcript: Accumulated transcript
        round_scores: Per-round scoring data
    """

    def __init__(
        self,
        topic: str,
        debater_a_persona: Optional[Persona] = None,
        debater_b_persona: Optional[Persona] = None,
        judge_persona: Optional[JudgePersona] = None,
        format: str = "standard",
        config: Optional[AgentConfig] = None,
        rubric: Optional[ScoringRubric] = None,
    ) -> None:
        """
        Args:
            topic: The debate topic/resolution (e.g., "Minimum wage increases
                   should be indexed to inflation")
            debater_a_persona: Persona for Debater A (affirmative).
                               Defaults to Institutional Economist.
            debater_b_persona: Persona for Debater B (negative).
                               Defaults to Neoclassical Economist.
            judge_persona: Persona for the judge.
                           Defaults to Impartial Economist.
            format: Debate format name ("standard", "seminar", "rapid", or custom)
            config: LLM configuration for all agents
            rubric: Custom scoring rubric
        """
        self.topic = topic
        self.config = config or AgentConfig()

        # Set up personas
        self._debater_a_persona = debater_a_persona or Persona(
            name="Institutional Economist",
            school="Institutional",
            key_assumptions=[
                "Institutions shape incentives",
                "Path dependency matters",
                "Bounded rationality",
            ],
            value_priorities=["Fairness", "Institutional quality", "Distribution"],
            rhetorical_style="Historical, comparative, case-study driven",
            constraints=[
                "Must provide institutional examples",
                "Must address transition costs",
            ],
        )
        self._debater_b_persona = debater_b_persona or Persona(
            name="Neoclassical Economist",
            school="Neoclassical",
            key_assumptions=[
                "Rational agents",
                "Market efficiency",
                "Price signals",
            ],
            value_priorities=["Efficiency", "Growth", "Consumer welfare"],
            rhetorical_style="Quantitative, model-driven, equilibrium-focused",
            constraints=[
                "Must cite economic mechanisms",
                "Must acknowledge market failures",
            ],
        )
        self._judge_persona = judge_persona or JudgePersona()

        # Set up format
        from debate_judge.formats import get_format
        self.format = get_format(format)

        # Set up rubric with format adjustments
        if rubric is None:
            self.rubric = ScoringRubric(
                adjust_for_format=self.format.scoring_adjustments,
            )
        else:
            self.rubric = rubric

        # Initialize agents
        self.debater_a = DebaterAgent(
            name=f"Debater A ({self._debater_a_persona.school})",
            persona=self._debater_a_persona,
            config=self.config,
            role="affirmative",
        )
        self.debater_b = DebaterAgent(
            name=f"Debater B ({self._debater_b_persona.school})",
            persona=self._debater_b_persona,
            config=self.config,
            role="negative",
        )
        self.judge = JudgeAgent(
            name=f"Judge ({self._judge_persona.name})",
            persona=self._judge_persona,
            rubric=self.rubric,
            config=self.config,
        )

        # State
        self.transcript = DebateTranscript(
            topic=self.topic,
            format_name=self.format.name,
        )
        self.round_scores: List[Dict[str, Any]] = []
        self._debate_history: List[str] = []

    def run(self, max_rounds: int = 3) -> Dict[str, Any]:
        """Run the full debate and return the verdict.

        Executes all turns defined by the debate format, scoring each exchange,
        and concluding with a final adjudication.

        Args:
            max_rounds: Maximum exchange rounds (for formats that allow iteration).
                        The PolicyDebateFormat ignores this and runs all its turns.

        Returns:
            Dict with keys: winner, margin, round_scores, transcript, opinion,
            html_transcript, markdown_transcript
        """
        print(f"\n{'='*60}")
        print(f"DEBATE: {self.topic}")
        print(f"Format: {self.format.name}")
        print(f"A: {self.debater_a.name}")
        print(f"B: {self.debater_b.name}")
        print(f"Judge: {self.judge.name}")
        print(f"{'='*60}\n")

        turns = self.format.turns
        turn_index = 0
        last_response_a = ""
        last_response_b = ""

        # Process turns according to the format
        for turn in turns:
            turn_index += 1
            phase = turn.phase
            speaker_agent = self.debater_a if turn.speaker == "a" else self.debater_b
            opponent_agent = self.debater_b if turn.speaker == "a" else self.debater_a
            opponent_last = last_response_b if turn.speaker == "a" else last_response_a

            print(f"[Turn {turn_index}/{len(turns)}] {phase} — {speaker_agent.name}")

            response_text = self._execute_turn(
                turn=turn,
                speaker=speaker_agent,
                opponent=opponent_agent,
                opponent_last=opponent_last,
            )

            # Store response for context
            if turn.speaker == "a":
                last_response_a = response_text
            else:
                last_response_b = response_text

            # Add to transcript
            self.transcript.append(
                speaker=turn.speaker,
                speaker_label=speaker_agent.name,
                phase=phase,
                content=response_text,
                school=speaker_agent.persona.school,
            )

            # After pairs of turns (one from each side), score the exchange
            if self._should_score_phase(phase, turns, turn_index):
                self._score_current_state(last_response_a, last_response_b, phase)

            self._debate_history.append(
                f"[{phase}] {speaker_agent.name}: {response_text[:300]}..."
            )

        # Final adjudication
        print(f"\n{'='*60}")
        print("FINAL ADJUDICATION")
        print(f"{'='*60}")

        debate_summary = "\n".join(self._debate_history)
        verdict = self.judge.final_adjudication(
            full_transcript=debate_summary,
            round_scores=self.round_scores,
            debater_a=self.debater_a,
            debater_b=self.debater_b,
        )

        # Record verdict in transcript
        self.transcript.set_verdict(verdict)
        self.transcript.append(
            speaker="judge",
            speaker_label=self.judge.name,
            phase="final_adjudication",
            content=verdict.get("opinion", ""),
            scores={
                "winner": verdict["winner"],
                "margin": verdict["margin"],
            },
        )

        print(f"\nWinner: {verdict['winner_name']}")
        print(f"Margin: {verdict['margin']}")
        print(f"A Average: {verdict['a_average']} | B Average: {verdict['b_average']}")

        return {
            "winner": verdict["winner"],
            "winner_name": verdict["winner_name"],
            "margin": verdict["margin"],
            "round_scores": verdict["round_scores"],
            "transcript": verdict.get("opinion", ""),
            "opinion": verdict.get("opinion", ""),
            "html_transcript": self.transcript.to_html(),
            "markdown_transcript": self.transcript.to_markdown(),
        }

    def _execute_turn(
        self,
        turn: Turn,
        speaker: DebaterAgent,
        opponent: DebaterAgent,
        opponent_last: str,
    ) -> str:
        """Execute a single debate turn based on its phase.

        Maps turn phases to the appropriate DebaterAgent methods.
        """
        phase = turn.phase

        if phase == "opening_statement":
            return speaker.opening_statement(
                topic=self.topic,
                context=f"Opponent is a {opponent.persona.school} economist arguing the opposite position.",
            )

        elif phase == "rebuttal":
            return speaker.rebuttal(
                opponent_statement=opponent_last,
                topic=self.topic,
            )

        elif phase == "cross_examination":
            # This turn is the questioner — the actual Q&A is handled in the next turn
            return self._generate_cross_examination_questions(
                questioner=speaker,
                opponent_last=opponent_last,
            )

        elif phase == "cross_examination_response":
            # Find the preceding cross-examination questions
            questions = self._find_last_entry_of_type("cross_examination")
            return speaker.cross_examination_response(
                questions=questions or opponent_last,
                topic=self.topic,
            )

        elif phase == "closing_statement":
            history = "\n".join(self._debate_history[-6:])  # Last 6 exchanges
            return speaker.closing_statement(
                topic=self.topic,
                debate_history=history,
            )

        elif phase == "position_paper":
            return speaker.generate(
                custom_prompt=f"Write a complete position paper on: {self.topic}",
                context="This is an academic seminar format. Write a scholarly position paper.",
            )

        elif phase == "peer_critique":
            return speaker.generate(
                custom_prompt=f"Critically evaluate the opponent's position paper:\n\n{opponent_last[:1500]}",
                context=f"Provide a rigorous peer critique as a {speaker.persona.school} economist.",
            )

        elif phase == "revision":
            return speaker.generate(
                custom_prompt=(
                    f"Revise your position in light of the critique:\n\n"
                    f"Your original position: [presented earlier]\n"
                    f"Critique received: {opponent_last[:1000]}\n\n"
                    f"Revise your position. Acknowledge valid criticisms, "
                    f"defend where appropriate, refine your arguments."
                ),
                context="Academic seminar revision round.",
            )

        elif phase == "panel_discussion":
            return speaker.generate(
                custom_prompt=(
                    f"Panel discussion on: {self.topic}\n\n"
                    f"Your opponent just said: {opponent_last[:500]}\n\n"
                    f"Respond in a scholarly panel discussion format."
                ),
                context="Academic panel discussion.",
            )

        elif phase == "consensus_statement":
            return speaker.generate(
                custom_prompt=(
                    f"Identify areas of agreement and remaining disagreement "
                    f"on: {self.topic}\n\n"
                    f"Debate summary: {' '.join(self._debate_history[-4:])}"
                ),
                context="Consensus-seeking statement.",
            )

        elif phase.startswith("exchange_"):
            # Rapid-fire exchange turns
            return speaker.generate(
                custom_prompt=(
                    f"Rapid exchange on: {self.topic}\n\n"
                    f"Opponent's last point: {opponent_last[:300]}\n\n"
                    f"Make ONE pointed argument in 2-4 sentences. Be direct."
                ),
                context="Rapid-fire exchange.",
            )

        else:
            # Generic fallback
            return speaker.generate(
                custom_prompt=f"Debate phase: {phase} on topic: {self.topic}",
                context=opponent_last[:500],
            )

    def _generate_cross_examination_questions(
        self,
        questioner: DebaterAgent,
        opponent_last: str,
    ) -> str:
        """Generate cross-examination questions from the questioner."""
        system_prompt = questioner.persona.build_system_prompt(
            "AFFIRMATIVE" if questioner.role == "affirmative" else "NEGATIVE",
            self.topic,
        )

        user_prompt = f"""You are conducting CROSS-EXAMINATION.

The opponent just argued:
---
{opponent_last[:1000]}
---

Ask 3 pointed questions that:
1. Probe the weakest assumption or empirical claim
2. Expose a tension or contradiction
3. Force a choice between two undesirable implications

Your questions should be specific, referenced to what they actually said.
Number them 1, 2, 3."""

        return questioner._call_llm(system_prompt, user_prompt, max_tokens=400)

    def _should_score_phase(self, phase: str, turns: List[Turn], current_index: int) -> bool:
        """Determine if we should score after this turn.

        Score after pairs of substantive turns, not after every individual turn.
        """
        # Score after these paired phases
        score_phases = {
            "opening_statement", "rebuttal", "closing_statement",
            "cross_examination_response", "revision", "consensus_statement",
        }

        if phase not in score_phases:
            return False

        # For paired phases, only score after BOTH sides have spoken
        # Check if the other side has already had this same phase
        for i in range(current_index - 1):
            if turns[i].phase == phase and turns[i].speaker != turns[current_index - 1].speaker:
                return True

        # For closing statements, score after the second one
        if phase == "closing_statement":
            if current_index >= len(turns):
                return True

        return False

    def _score_current_state(
        self, response_a: str, response_b: str, phase: str
    ) -> None:
        """Score the current state of the debate."""
        print(f"  [Scoring] {phase}...")
        score = self.judge.evaluate_round(
            debater_a=self.debater_a,
            debater_b=self.debater_b,
            exchange={
                "a_text": response_a,
                "b_text": response_b,
                "phase": phase,
            },
        )
        self.round_scores.append(score)

        # Record scores in transcript
        winner = score.get("winner", "?")
        print(f"  Scores: A={score['a_total']:.1f} | B={score['b_total']:.1f} | Round to: {winner}")

    def _find_last_entry_of_type(self, phase: str) -> Optional[str]:
        """Find the content of the last transcript entry of a given phase."""
        for entry in reversed(self.transcript.entries):
            if entry.phase == phase:
                return entry.content
        return None

    def run_cross_examination(
        self,
        speaker: DebaterAgent,
        opponent: DebaterAgent,
        opponent_last: str,
        max_questions: int = 3,
    ) -> Dict[str, str]:
        """Run a structured cross-examination session.

        This is a standalone method for running Q&A outside the full
        debate flow, useful for targeted interrogation of specific claims.

        Args:
            speaker: The debater asking questions
            opponent: The debater answering questions
            opponent_last: The opponent's statement being challenged
            max_questions: Maximum number of questions to ask

        Returns:
            Dict with 'questions' and 'answers' keys
        """
        questions = self._generate_cross_examination_questions(
            questioner=speaker,
            opponent_last=opponent_last,
        )

        answers = opponent.cross_examination_response(
            questions=questions,
            topic=self.topic,
        )

        return {"questions": questions, "answers": answers}

    def save_transcript(self, filepath: str, format: str = "markdown") -> None:
        """Save the debate transcript to a file.

        Args:
            filepath: Output file path
            format: "markdown" or "html"
        """
        if format == "html":
            content = self.transcript.to_html()
        else:
            content = self.transcript.to_markdown()

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"Transcript saved to: {filepath}")

    def __repr__(self) -> str:
        return (
            f"DebateArena(topic={self.topic!r}, "
            f"format={self.format.name!r}, "
            f"a={self.debater_a.persona.school!r}, "
            f"b={self.debater_b.persona.school!r})"
        )
