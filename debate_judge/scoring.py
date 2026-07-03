"""
Scoring rubric for debate adjudication.

Provides multi-criterion scoring with weighted aggregation, fallacy detection,
evidence quality assessment, and round-by-round tracking.

Philosophy:
    The rubric rewards substantive engagement over rhetorical flourish.
    It penalizes logical fallacies, unsubstantiated claims, and evasion of
    counterarguments. It does NOT reward ideological alignment with the judge.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ── Fallacy Detection Patterns ─────────────────────────────────────────────

_FALLACY_PATTERNS: Dict[str, List[str]] = {
    "ad_hominem": [
        r"\b(opponent|you|they)\s+(is|are)\s+(biased|unqualified|ignorant|stupid)\b",
        r"\bpersonally\s+attack",
        r"\b(not\s+credible|can'?t\s+be\s+trusted)\s+(because\s+of\s+who\s+they\s+are|as\s+a\s+person)",
        r"\bdoesn'?t\s+know\s+what\s+(?:they|he|she)(?:'?s|'?re| is)\s+talking\s+about\b",
    ],
    "straw_man": [
        r"\b(?:my\s+)?(?:you|they|opponent)\s+(?:is|are|was|were)\s+(?:essentially|basically|just|simply)\s+saying\b",
        r"\bwhat\s+(?:you|they|my opponent)\s+(?:really|actually)\s+mean\b",
        r"\b(?:reduces?|boils?\s+down)\s+(?:your|their)\s+argument\s+to\b",
        r"\b(?:you|they)\s+(?:seem|appear)\s+to\s+be\s+(?:arguing|claiming|saying)\b",
    ],
    "false_dichotomy": [
        r"\b(?:either|only\s+two|there\s+are\s+only)\s+(?:options|choices|alternatives|possibilities)\b",
        r"\b(?:must\s+either|either\s+we)\s+.*?\s+(?:or\s+(?:else|we))\b",
        r"\b(?:it'?s\s+either|either\s+it'?s)\s+.*?\s+or\b",
        r"\bno\s+(?:middle\s+ground|alternative|third\s+way|other\s+option)\b",
    ],
    "appeal_to_authority": [
        r"\b(?:according\s+to|as)\s+(?:the\s+)?(?:famous|renowned|noted|eminent|great)\s+(?:economist|scholar|expert)\b",
        r"\b(?:everyone\s+knows|it\s+is\s+well\s+known|obviously|clearly)\b",
        r"\b(?:the\s+consensus|most\s+economists|the\s+majority\s+of)\s+(?:agrees?|believes?|thinks?)\b",
        r"\b(?:as\s+(?:Nobel\s+)?laureate|esteemed)\s",
    ],
    "slippery_slope": [
        r"\b(?:if\s+we\s+allow|once\s+we\s+start).*?(?:then|will)\s+(?:inevitably|inexorably|necessarily)\b",
        r"\b(?:slippery\s+slope|domino\s+effect|thin\s+end\s+of\s+the\s+wedge)\b",
        r"\b(?:this\s+will\s+lead\s+to|next\s+thing\s+you\s+know|before\s+long)\b",
    ],
    "appeal_to_emotion": [
        r"\b(?:think\s+of\s+the|what\s+about\s+the)\s+(?:children|poor|vulnerable|elderly)\b",
        r"\b(?:catastrophic|disastrous|devastating|horrific)\s+(?:consequences|effects|results)\b",
        r"\b(?:imagine|picture)\s+(?:a\s+world|millions\s+of|families\s+suffering)\b",
    ],
    "begging_the_question": [
        r"\b(?:obviously|clearly|undoubtedly|without\s+question|it\s+goes\s+without\s+saying)\b",
        r"\b(?:as\s+we\s+all\s+know|everyone\s+agrees\s+that|it\s+is\s+undeniable\s+that)\b",
    ],
    "post_hoc": [
        r"\b(?:since|after|following)\s+.*?(?:therefore|thus|consequently|it\s+follows)\b",
        r"\b(?:led\s+to|caused|resulted\s+in)\b.*?\b(?:without|no|not|never)\b.*?\b(?:evidence|proof|mechanism|study)\b",
    ],
}

# Evidence quality indicators
_STRONG_EVIDENCE_PATTERNS: List[str] = [
    r"\b(?:RCT|randomized\s+controlled\s+trial|natural\s+experiment|difference-in-differences?|regression\s+discontinuity|instrumental\s+variable|IV\s+approach|panel\s+data|meta.analysis|systematic\s+review)\b",
    r"\b(?:elasticity\s+of|elasticities|DWL|deadweight\s+loss|marginal\s+(?:cost|benefit|rate|tax|utility|product)|Laffer|Phillips)\b",
    r"\b(?:NBER|CBO|JPE|AER|QJE|Econometrica|IMF|OECD|World\s+Bank|Federal\s+Reserve|BLS|Bureau\s+of)\b",
    r"\b(?:study|paper|research|evidence|data|finding)\s+(?:by|from|in)\s+(?:\d{4}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b",
    r"\b(?:percentage\s+point|basis\s+point|standard\s+deviation|confidence\s+interval|p.value|statistically\s+significant|effect\s+size)\b",
]

_WEAK_EVIDENCE_PATTERNS: List[str] = [
    r"\b(?:common\s+sense|everyone\s+knows|it\s+is\s+obvious|intuitively|plainly)\b",
    r"\b(?:assume\s+for\s+the\s+sake\s+of\s+argument|let'?s\s+suppose|imagine\s+that|hypothetically)\b",
    r"\b(?:anecdote|anecdotal|in\s+my\s+experience|I'?ve\s+seen|I\s+remember|one\s+time)\b",
]


@dataclass
class CriterionScore:
    """Score for a single scoring criterion.

    Attributes:
        criterion: Name of the criterion
        score: Numerical score (0-10)
        justification: Brief explanation of why this score was assigned
    """

    criterion: str
    score: float
    justification: str = ""

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 10:
            raise ValueError(f"Score must be between 0 and 10, got {self.score}")


@dataclass
class RoundScore:
    """Complete scoring for one debate round/exchange.

    Attributes:
        round_name: Identifier for this round (e.g., "opening_statement", "rebuttal_1")
        a_scores: Per-criterion scores for Debater A
        b_scores: Per-criterion scores for Debater B
        a_total: Weighted total score for Debater A
        b_total: Weighted total score for Debater B
    """

    round_name: str
    a_scores: List[CriterionScore] = field(default_factory=list)
    b_scores: List[CriterionScore] = field(default_factory=list)
    a_total: float = 0.0
    b_total: float = 0.0

    @property
    def winner(self) -> Optional[str]:
        """Which debater won this round ("a", "b", or None if tie)."""
        if self.a_total > self.b_total:
            return "a"
        elif self.b_total > self.a_total:
            return "b"
        return None

    @property
    def margin(self) -> float:
        """Score margin (positive = A ahead, negative = B ahead)."""
        return self.a_total - self.b_total


@dataclass
class FallacyDetection:
    """Result of fallacy detection on a piece of text.

    Attributes:
        fallacy_type: Type of fallacy detected
        matched_text: The text segment that triggered detection
        confidence: How confident the detection is (0.0-1.0)
    """

    fallacy_type: str
    matched_text: str
    confidence: float = 0.5


class ScoringRubric:
    """Multi-criterion scoring rubric for debate adjudication.

    The rubric evaluates debates across six dimensions, each with its own
    weight. Scores are on a 0-10 scale per criterion. The rubric also
    provides fallacy detection and evidence quality assessment.

    Criteria (with default weights):
        - empirical_grounding (0.25): Evidence quality and citation
        - logical_coherence (0.20): Internal logic, no fallacies
        - counterargument_addressing (0.20): How well objections are handled
        - policy_feasibility (0.15): Real-world implementability
        - value_articulation (0.10): Clarity of normative foundation
        - rhetorical_effectiveness (0.10): Persuasiveness and clarity
    """

    DEFAULT_CRITERIA: Dict[str, Dict[str, Any]] = {
        "empirical_grounding": {
            "weight": 0.25,
            "description": "Evidence quality and citation. Does the argument rest on "
            "empirical findings, data, or documented cases? Are claims supported by "
            "specific studies, mechanisms, or quantitative estimates?",
        },
        "logical_coherence": {
            "weight": 0.20,
            "description": "Internal logic and absence of fallacies. Does the argument "
            "follow from its premises? Are there hidden contradictions? Are fallacies "
            "(straw man, false dichotomy, ad hominem) avoided?",
        },
        "counterargument_addressing": {
            "weight": 0.20,
            "description": "Engagement with opposing arguments. Does the debater "
            "acknowledge and respond to the strongest counterarguments? Or do they "
            "ignore, evade, or misrepresent the opposition?",
        },
        "policy_feasibility": {
            "weight": 0.15,
            "description": "Real-world implementability. Is the proposed policy "
            "administratively feasible? Are transition costs, political constraints, "
            "and institutional capacity considered?",
        },
        "value_articulation": {
            "weight": 0.10,
            "description": "Clarity of normative foundation. Does the argument make "
            "its value premises explicit? Is the normative framework coherent and "
            "applied consistently?",
        },
        "rhetorical_effectiveness": {
            "weight": 0.10,
            "description": "Persuasiveness and clarity. Is the argument well-structured, "
            "clearly expressed, and rhetorically effective without relying on fallacies "
            "or emotional manipulation?",
        },
    }

    def __init__(
        self,
        criteria: Optional[Dict[str, Dict[str, Any]]] = None,
        adjust_for_format: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Args:
            criteria: Override default criteria. Maps criterion name to
                      dict with 'weight' and 'description' keys.
            adjust_for_format: Per-criterion weight multipliers from debate format.
        """
        self.criteria = copy.deepcopy(criteria) if criteria else copy.deepcopy(dict(self.DEFAULT_CRITERIA))
        if adjust_for_format:
            self._apply_adjustments(adjust_for_format)

    def _apply_adjustments(self, adjustments: Dict[str, float]) -> None:
        """Apply format-specific weight adjustments and re-normalize."""
        for criterion, multiplier in adjustments.items():
            if criterion in self.criteria:
                self.criteria[criterion]["weight"] *= multiplier
        total = sum(c["weight"] for c in self.criteria.values())
        if total > 0:
            for c in self.criteria.values():
                c["weight"] /= total

    @property
    def weights(self) -> Dict[str, float]:
        """Get criterion names mapped to their weights."""
        return {name: info["weight"] for name, info in self.criteria.items()}

    @property
    def criterion_names(self) -> List[str]:
        """Get ordered list of criterion names."""
        return list(self.criteria.keys())

    def score_exchange(
        self,
        response_a: str,
        response_b: str,
        phase: str = "",
    ) -> RoundScore:
        """Score a single exchange between the two debaters.

        Args:
            response_a: Debater A's response text
            response_b: Debater B's response text
            phase: Which debate phase this exchange belongs to

        Returns:
            RoundScore with per-criterion scores for both debaters
        """
        round_score = RoundScore(round_name=phase or "exchange")

        for criterion_name, criterion_info in self.criteria.items():
            weight = criterion_info["weight"]

            score_a = self._score_side(response_a, response_b, criterion_name)
            score_b = self._score_side(response_b, response_a, criterion_name)

            round_score.a_scores.append(CriterionScore(
                criterion=criterion_name,
                score=score_a,
                justification=self._brief_justification(criterion_name, score_a, response_a),
            ))
            round_score.b_scores.append(CriterionScore(
                criterion=criterion_name,
                score=score_b,
                justification=self._brief_justification(criterion_name, score_b, response_b),
            ))

        # Compute weighted totals
        round_score.a_total = sum(
            s.score * self.criteria[s.criterion]["weight"]
            for s in round_score.a_scores
        )
        round_score.b_total = sum(
            s.score * self.criteria[s.criterion]["weight"]
            for s in round_score.b_scores
        )

        return round_score

    def composite_score(self, round_scores: List[RoundScore]) -> Dict[str, Any]:
        """Compute weighted composite score across all rounds.

        Args:
            round_scores: List of per-round scores in order

        Returns:
            Dict with total scores, per-criterion breakdowns, and winner
        """
        total_a = 0.0
        total_b = 0.0
        criterion_totals: Dict[str, Dict[str, float]] = {
            name: {"a": 0.0, "b": 0.0, "count": 0.0}
            for name in self.criterion_names
        }

        round_count = len(round_scores)
        for rs in round_scores:
            total_a += rs.a_total
            total_b += rs.b_total
            for s in rs.a_scores:
                criterion_totals[s.criterion]["a"] += s.score
                criterion_totals[s.criterion]["count"] += 1
            for s in rs.b_scores:
                criterion_totals[s.criterion]["b"] += s.score
                criterion_totals[s.criterion]["count"] += 1

        # Average per criterion
        criterion_averages = {}
        for name, totals in criterion_totals.items():
            n = totals["count"] / 2  # divide by 2 since each round counts both
            if n > 0:
                criterion_averages[name] = {
                    "a_avg": round(totals["a"] / (round_count), 2),
                    "b_avg": round(totals["b"] / (round_count), 2),
                    "a_advantage": round(
                        (totals["a"] - totals["b"]) / round_count, 2
                    ),
                }

        # Average per round
        avg_a = total_a / round_count if round_count > 0 else 0.0
        avg_b = total_b / round_count if round_count > 0 else 0.0

        winner = "a" if avg_a > avg_b else "b" if avg_b > avg_a else "tie"
        margin = abs(avg_a - avg_b)

        return {
            "rounds": round_count,
            "a_average": round(avg_a, 2),
            "b_average": round(avg_b, 2),
            "winner": winner,
            "margin": round(margin, 2),
            "criterion_breakdown": criterion_averages,
            "round_scores": [
                {"name": rs.round_name, "a": round(rs.a_total, 2), "b": round(rs.b_total, 2)}
                for rs in round_scores
            ],
        }

    def detect_fallacies(self, text: str) -> List[FallacyDetection]:
        """Detect logical fallacies in argument text.

        Uses pattern matching to identify common fallacies. This is a
        heuristic tool, not a definitive logical analysis. False positives
        are possible — use as a flag for closer reading, not a verdict.

        Args:
            text: The argument text to analyze

        Returns:
            List of FallacyDetection objects for detected fallacies
        """
        detections: List[FallacyDetection] = []
        text_lower = text.lower()

        for fallacy_type, patterns in _FALLACY_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text_lower)
                for match in matches:
                    # Get surrounding context (50 chars on each side)
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end].strip()

                    # Heuristic confidence based on match specificity
                    confidence = min(0.9, 0.4 + len(match.group()) / 40.0)

                    detections.append(FallacyDetection(
                        fallacy_type=fallacy_type,
                        matched_text=context,
                        confidence=confidence,
                    ))

        return detections

    def evidence_quality_check(self, text: str) -> Dict[str, Any]:
        """Assess evidence quality in an argument.

        Checks for indicators of strong evidence (specific studies, quantitative
        estimates, recognized data sources) and weak evidence (assertions without
        backing, anecdotal reasoning, hand-waving).

        Args:
            text: The argument text to analyze

        Returns:
            Dict with strong_count, weak_count, strong_indicators, weak_indicators, and score
        """
        text_lower = text.lower()
        strong_indicators: List[str] = []
        weak_indicators: List[str] = []

        for pattern in _STRONG_EVIDENCE_PATTERNS:
            matches = re.findall(pattern, text_lower)
            strong_indicators.extend(matches)

        for pattern in _WEAK_EVIDENCE_PATTERNS:
            matches = re.findall(pattern, text_lower)
            weak_indicators.extend(matches)

        strong_count = len(strong_indicators)
        weak_count = len(weak_indicators)

        # Score from 0-10: strong evidence adds, weak evidence subtracts
        # Normalize by text length to avoid penalizing longer responses
        text_len = max(len(text.split()), 1)
        strong_density = strong_count / (text_len / 100)  # per 100 words
        weak_density = weak_count / (text_len / 100)

        score = max(0, min(10, 5.0 + strong_density * 2.0 - weak_density * 2.0))

        return {
            "strong_count": strong_count,
            "weak_count": weak_count,
            "strong_indicators": strong_indicators[:10],  # cap for readability
            "weak_indicators": weak_indicators[:10],
            "score": round(score, 1),
            "assessment": (
                "Excellent evidence base"
                if score >= 8
                else "Good evidence grounding"
                if score >= 6
                else "Adequate evidence"
                if score >= 4
                else "Weak evidence support"
                if score >= 2
                else "Insufficient evidence"
            ),
        }

    # ── Internal helpers ──────────────────────────────────────────────────

    def _score_side(self, own_text: str, opponent_text: str, criterion: str) -> float:
        """Heuristic scoring for one side on one criterion.

        This is a rule-based approximation. In production, the JudgeAgent
        would use an LLM for more nuanced evaluation. This method provides
        a baseline that can be overridden or supplemented.
        """
        own_lower = own_text.lower()
        opp_lower = opponent_text.lower()
        length = max(len(own_text.split()), 1)

        if criterion == "empirical_grounding":
            evidence = self.evidence_quality_check(own_text)
            return evidence["score"]

        elif criterion == "logical_coherence":
            fallacies = self.detect_fallacies(own_text)
            # Fewer fallacies = higher score. Base at 7, deduct per fallacy.
            fallacy_count = len(fallacies)
            return max(0, min(10, 7.0 - fallacy_count * 1.5))

        elif criterion == "counterargument_addressing":
            # Check if opponent's key terms appear in response
            opp_keywords = set(re.findall(r"\b[a-zA-Z]{4,}\b", opp_lower))
            own_keywords = set(re.findall(r"\b[a-zA-Z]{4,}\b", own_lower))
            if opp_keywords:
                overlap = len(opp_keywords & own_keywords) / len(opp_keywords)
                return max(0, min(10, 3.0 + overlap * 10.0))
            return 5.0  # Neutral if no opponent text to compare

        elif criterion == "policy_feasibility":
            feasibility_markers = [
                r"\b(?:implement|administration|bureaucracy|agency|enforcement|compliance|cost|budget|transition|phase.in|pilot|trial|municipal|state|federal|local)\b",
                r"\b(?:feasib|practic|workable|realistic|achievable|operational)\b",
            ]
            count = sum(
                len(re.findall(p, own_lower)) for p in feasibility_markers
            )
            density = count / (length / 100)
            return max(0, min(10, 3.0 + density * 2.0))

        elif criterion == "value_articulation":
            value_markers = [
                r"\b(?:value|normative|principle|right|justice|fairness|freedom|liberty|equality|dignity|welfare|well.being|utilitarian|deontolog|rights.based)\b",
                r"\b(?:we\s+should|we\s+ought|it\s+is\s+(?:right|wrong|good|bad|better|worse|important|essential|critical))\b",
            ]
            count = sum(len(re.findall(p, own_lower)) for p in value_markers)
            return max(0, min(10, 3.0 + count * 0.8))

        elif criterion == "rhetorical_effectiveness":
            # Structure, clarity, persuasiveness
            structure_score = 0.0
            # Check for clear structure markers
            if re.search(r"\b(?:first|second|third|finally|in\s+conclusion|to\s+summarize)\b", own_lower):
                structure_score += 2.0
            # Check paragraph organization
            paragraphs = [p for p in own_text.split("\n\n") if p.strip()]
            if 2 <= len(paragraphs) <= 6:
                structure_score += 1.0
            # Check sentence length variety (heuristic)
            sentences = re.split(r"[.!?]+", own_text)
            if sentences:
                lengths = [len(s.split()) for s in sentences if s.strip()]
                if lengths:
                    avg_len = sum(lengths) / len(lengths)
                    if 10 < avg_len < 40:
                        structure_score += 1.0
            return max(0, min(10, 5.0 + structure_score))

        return 5.0  # Default neutral score

    def _brief_justification(self, criterion: str, score: float, text: str) -> str:
        """Generate a brief justification for a score."""
        if criterion == "empirical_grounding":
            evidence = self.evidence_quality_check(text)
            return f"Evidence quality: {evidence['assessment']} ({evidence['strong_count']} strong, {evidence['weak_count']} weak indicators)"
        elif criterion == "logical_coherence":
            fallacies = self.detect_fallacies(text)
            if fallacies:
                types = set(f.fallacy_type for f in fallacies)
                return f"Detected {len(fallacies)} potential fallacies: {', '.join(sorted(types))}"
            return "No obvious fallacies detected"
        elif criterion == "counterargument_addressing":
            return f"Counterargument engagement score: {score:.1f}/10"
        elif criterion == "policy_feasibility":
            return f"Policy feasibility score: {score:.1f}/10"
        elif criterion == "value_articulation":
            return f"Value articulation score: {score:.1f}/10"
        elif criterion == "rhetorical_effectiveness":
            return f"Rhetorical effectiveness score: {score:.1f}/10"
        return f"Score: {score:.1f}/10"
