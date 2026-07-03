"""
Debate format definitions.

Each format specifies turn structure, timing constraints, and scoring adjustments.
Formats are serializable (YAML) and can be composed into custom structures.

Supports:
    - PolicyDebateFormat: Classic policy debate (opening → cross-exam → rebuttal → closing)
    - AcademicSeminarFormat: Seminar-style with position papers and revision rounds
    - RapidFireFormat: Fast-paced exchanges with instant verdict
"""

from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Turn:
    """A single turn in a debate round.

    Attributes:
        speaker: Which debater speaks ("a" or "b")
        phase: Phase name (e.g., "opening_statement", "rebuttal")
        description: Human-readable description of what happens in this turn
        token_limit: Approximate maximum tokens for this turn's response
        requires_response: Whether the other debater is expected to engage with this
        scoring_weight: How much this turn contributes to overall scoring (0.0-1.0)
    """

    speaker: str
    phase: str
    description: str
    token_limit: int = 800
    requires_response: bool = True
    scoring_weight: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "speaker": self.speaker,
            "phase": self.phase,
            "description": self.description,
            "token_limit": self.token_limit,
            "requires_response": self.requires_response,
            "scoring_weight": self.scoring_weight,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Turn":
        return cls(**data)


@dataclass
class DebateFormat:
    """Base class for debate formats.

    A debate format defines the complete structure of a debate: what sequence
    of turns occurs, what each turn entails, and how scoring is adjusted.

    Attributes:
        name: Human-readable format name
        description: What this format is designed for
        turns: Ordered list of Turn objects defining the debate flow
        scoring_adjustments: Per-criterion scoring weight modifications
    """

    name: str
    description: str
    turns: List[Turn] = field(default_factory=list)
    scoring_adjustments: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.turns:
            self._build_turns()

    def _build_turns(self) -> None:
        """Override in subclasses to define turn sequence."""
        raise NotImplementedError

    @property
    def num_turns(self) -> int:
        return len(self.turns)

    @property
    def phases(self) -> List[str]:
        """Return unique phase names in order."""
        seen: List[str] = []
        for t in self.turns:
            if t.phase not in seen:
                seen.append(t.phase)
        return seen

    def get_turns_for_phase(self, phase: str) -> List[Turn]:
        """Get all turns belonging to a given phase."""
        return [t for t in self.turns if t.phase == phase]

    def get_adjusted_criteria(self, base_weights: Dict[str, float]) -> Dict[str, float]:
        """Apply format-specific scoring adjustments to base criteria weights."""
        adjusted = dict(base_weights)
        for criterion, adjustment in self.scoring_adjustments.items():
            if criterion in adjusted:
                adjusted[criterion] *= adjustment
        # Re-normalize
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}
        return adjusted

    def to_yaml(self) -> str:
        """Serialize format to YAML string."""
        return yaml.dump(self.to_dict(), allow_unicode=True, sort_keys=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "turns": [t.to_dict() for t in self.turns],
            "scoring_adjustments": self.scoring_adjustments,
        }

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "DebateFormat":
        """Deserialize a format from YAML string."""
        data = yaml.safe_load(yaml_str)
        fmt = cls.__new__(cls)
        fmt.name = data["name"]
        fmt.description = data["description"]
        fmt.turns = [Turn.from_dict(t) for t in data["turns"]]
        fmt.scoring_adjustments = data.get("scoring_adjustments", {})
        return fmt

    def save(self, filepath: str) -> None:
        """Save format definition to a YAML file."""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_yaml())

    @classmethod
    def load(cls, filepath: str) -> "DebateFormat":
        """Load format definition from a YAML file."""
        with open(filepath, "r", encoding="utf-8") as f:
            return cls.from_yaml(f.read())

    def __repr__(self) -> str:
        return f"DebateFormat(name={self.name!r}, turns={self.num_turns})"


@dataclass
class PolicyDebateFormat(DebateFormat):
    """Classic policy debate format.

    Structure:
        1. Opening Statement A (5 min equivalent)
        2. Opening Statement B (5 min)
        3. Cross-Examination: A questions B (3 min)
        4. Rebuttal: B addresses critiques, A engages (4 min)
        5. Cross-Examination: B questions A (3 min)
        6. Rebuttal: A addresses critiques, B engages (4 min)
        7. Closing Statement A (3 min)
        8. Closing Statement B (3 min)
        9. Adjudication by Judge
    """

    name: str = "Policy Debate"
    description: str = (
        "Classic policy debate format with opening statements, "
        "structured cross-examination, rebuttals, and closing arguments. "
        "Designed for rigorous economic policy analysis."
    )

    def _build_turns(self) -> None:
        self.turns = [
            Turn("a", "opening_statement",
                 "Opening statement: Make the affirmative case. Present core argument, "
                 "theoretical framework, key evidence, and policy mechanism.",
                 token_limit=1000, scoring_weight=1.0),

            Turn("b", "opening_statement",
                 "Opening statement: Make the opposing case. Challenge framing, "
                 "present alternative framework, offer counter-evidence.",
                 token_limit=1000, scoring_weight=1.0),

            Turn("a", "cross_examination",
                 "Cross-examination: A questions B. Probe assumptions, identify gaps, "
                 "expose tensions in the opposing argument.",
                 token_limit=600, scoring_weight=0.8),

            Turn("b", "cross_examination_response",
                 "Cross-examination response: B answers A's questions. Defend positions, "
                 "clarify ambiguities, concede where appropriate.",
                 token_limit=600, scoring_weight=0.8),

            Turn("a", "rebuttal",
                 "Rebuttal: A addresses B's challenges. Refine argument in light of "
                 "cross-examination. Strengthen weakest points, exploit B's concessions.",
                 token_limit=800, scoring_weight=1.2),

            Turn("b", "cross_examination",
                 "Cross-examination: B questions A. Pressure-test A's refined argument, "
                 "identify contradictions introduced in rebuttal.",
                 token_limit=600, scoring_weight=0.8),

            Turn("a", "cross_examination_response",
                 "Cross-examination response: A answers B's questions.",
                 token_limit=600, scoring_weight=0.8),

            Turn("b", "rebuttal",
                 "Rebuttal: B addresses A's challenges. Final substantive engagement "
                 "before closing statements.",
                 token_limit=800, scoring_weight=1.2),

            Turn("a", "closing_statement",
                 "Closing statement: A synthesizes the debate. Summarize strongest "
                 "points, address the most compelling counterargument, make final appeal.",
                 token_limit=600, scoring_weight=1.0),

            Turn("b", "closing_statement",
                 "Closing statement: B synthesizes the debate. Summarize strongest "
                 "points, address the most compelling counterargument, make final appeal.",
                 token_limit=600, scoring_weight=1.0),
        ]
        self.scoring_adjustments = {
            "counterargument_addressing": 1.3,   # Cross-examination rewards engagement
            "logical_coherence": 1.1,
            "policy_feasibility": 1.2,
        }


@dataclass
class AcademicSeminarFormat(DebateFormat):
    """Academic seminar debate format.

    Structure:
        1. Position Papers (both sides submit independently)
        2. Peer Critique (each critiques the other's position paper)
        3. Revision (each revises based on critique)
        4. Panel Discussion (open exchange moderated by judge)
        5. Consensus Statement (attempt to find common ground)
        6. Adjudication
    """

    name: str = "Academic Seminar"
    description: str = (
        "Academic seminar format emphasizing scholarly exchange. "
        "Begins with position papers, proceeds through structured peer critique, "
        "revision, moderated discussion, and attempts to find consensus. "
        "Ideal for complex theoretical debates."
    )

    def _build_turns(self) -> None:
        self.turns = [
            Turn("a", "position_paper",
                 "Position Paper A: Present full position with theoretical framework, "
                 "literature review, methodology, and conclusions.",
                 token_limit=1200, scoring_weight=1.0),

            Turn("b", "position_paper",
                 "Position Paper B: Present alternative position with full scholarly apparatus.",
                 token_limit=1200, scoring_weight=1.0),

            Turn("b", "peer_critique",
                 "Peer Critique: B critically evaluates A's position paper. Identify "
                 "methodological concerns, theoretical gaps, empirical weaknesses.",
                 token_limit=800, scoring_weight=1.2),

            Turn("a", "peer_critique",
                 "Peer Critique: A critically evaluates B's position paper.",
                 token_limit=800, scoring_weight=1.2),

            Turn("a", "revision",
                 "Revision: A revises position in response to B's critique. Acknowledge "
                 "valid points, defend where appropriate, refine arguments.",
                 token_limit=1000, scoring_weight=1.3),

            Turn("b", "revision",
                 "Revision: B revises position in response to A's critique.",
                 token_limit=1000, scoring_weight=1.3),

            Turn("a", "panel_discussion",
                 "Panel Discussion: Open exchange between both debaters. "
                 "Direct engagement on points of disagreement.",
                 token_limit=600, scoring_weight=0.8),

            Turn("b", "panel_discussion",
                 "Panel Discussion: Continued exchange.",
                 token_limit=600, scoring_weight=0.8),

            Turn("a", "consensus_statement",
                 "Consensus Statement A: Identify areas of agreement, "
                 "remaining disagreements, and paths for reconciliation.",
                 token_limit=600, scoring_weight=0.7),

            Turn("b", "consensus_statement",
                 "Consensus Statement B: Same — identify common ground and "
                 "remaining fault lines.",
                 token_limit=600, scoring_weight=0.7),
        ]
        self.scoring_adjustments = {
            "empirical_grounding": 1.4,          # Seminar format rewards evidence
            "counterargument_addressing": 1.3,    # Peer critique is central
            "logical_coherence": 1.2,
            "rhetorical_effectiveness": 0.7,      # Less emphasis on rhetoric
        }


@dataclass
class RapidFireFormat(DebateFormat):
    """Fast-paced rapid-fire debate format.

    Structure:
        1. Opening A (1 min equivalent)
        2. Opening B (1 min)
        3-5. Three rounds: A argues → B responds → A rebuts (30 sec each)
        6-8. Three rounds: B argues → A responds → B rebuts (30 sec each)
        9. Closing A (1 min)
        10. Closing B (1 min)
        11. Instant Verdict
    """

    name: str = "Rapid Fire"
    description: str = (
        "Fast-paced debate format designed for quick exchanges. "
        "Short openings, three rounds of rapid back-and-forth, "
        "short closings, and instant adjudication. "
        "Rewards clarity, concision, and quick thinking."
    )

    def _build_turns(self) -> None:
        self.turns = [
            Turn("a", "opening_statement",
                 "Opening: A makes core case in one concise statement.",
                 token_limit=300, scoring_weight=1.0),

            Turn("b", "opening_statement",
                 "Opening: B makes core case in one concise statement.",
                 token_limit=300, scoring_weight=1.0),
        ]
        # Three rapid exchange rounds (A initiates)
        for i in range(1, 4):
            self.turns.extend([
                Turn("a", f"exchange_{i}a",
                     f"Exchange {i}: A presents a pointed argument.",
                     token_limit=200, scoring_weight=0.9),

                Turn("b", f"exchange_{i}b",
                     f"Exchange {i}: B responds and counter-argues.",
                     token_limit=200, scoring_weight=0.9),

                Turn("a", f"exchange_{i}c",
                     f"Exchange {i}: A's final word on this point.",
                     token_limit=200, scoring_weight=0.9),
            ])
        # Three rapid exchange rounds (B initiates)
        for i in range(4, 7):
            self.turns.extend([
                Turn("b", f"exchange_{i}a",
                     f"Exchange {i}: B presents a pointed argument.",
                     token_limit=200, scoring_weight=0.9),

                Turn("a", f"exchange_{i}b",
                     f"Exchange {i}: A responds and counter-argues.",
                     token_limit=200, scoring_weight=0.9),

                Turn("b", f"exchange_{i}c",
                     f"Exchange {i}: B's final word on this point.",
                     token_limit=200, scoring_weight=0.9),
            ])
        self.turns.extend([
            Turn("a", "closing_statement",
                 "Closing: A's final synthesis (must be under 1 minute).",
                 token_limit=300, scoring_weight=1.2),

            Turn("b", "closing_statement",
                 "Closing: B's final synthesis (must be under 1 minute).",
                 token_limit=300, scoring_weight=1.2),
        ])
        self.scoring_adjustments = {
            "rhetorical_effectiveness": 1.5,   # Clarity under time pressure
            "logical_coherence": 1.2,
            "empirical_grounding": 0.8,         # Less time for deep evidence
        }


# Registry of built-in formats
_BUILTIN_FORMATS: Dict[str, type] = {
    "standard": PolicyDebateFormat,
    "policy": PolicyDebateFormat,
    "seminar": AcademicSeminarFormat,
    "academic": AcademicSeminarFormat,
    "rapid": RapidFireFormat,
    "rapid_fire": RapidFireFormat,
    "rapidfire": RapidFireFormat,
}


def get_format(name: str = "standard") -> DebateFormat:
    """Get a debate format by name.

    Args:
        name: Format name. One of: "standard", "policy", "seminar",
              "academic", "rapid", "rapid_fire", "rapidfire"

    Returns:
        An instance of the requested format.

    Raises:
        ValueError: If the format name is not recognized.
    """
    key = name.lower().replace("-", "_").replace(" ", "_")
    if key not in _BUILTIN_FORMATS:
        available = ", ".join(sorted(set(_BUILTIN_FORMATS.keys())))
        raise ValueError(
            f"Unknown format: {name!r}. Available formats: {available}"
        )
    return _BUILTIN_FORMATS[key]()


def list_formats() -> List[Dict[str, str]]:
    """List all available debate formats with descriptions."""
    seen: set = set()
    result = []
    for key, fmt_cls in _BUILTIN_FORMATS.items():
        instance = fmt_cls()
        entry = (instance.name, instance.description)
        if entry not in seen:
            seen.add(entry)
            result.append({"key": key, "name": instance.name, "description": instance.description})
    return result
