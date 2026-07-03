"""
Tests for the DebateJudge system.

Tests cover:
    - Persona loading and validation
    - Format definition and serialization
    - Scoring rubric correctness
    - Fallacy detection accuracy
    - Transcript formatting
    - Agent persona system prompt generation
"""

import json
import os
import sys
import tempfile
import unittest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from debate_judge import (
    DebateArena,
    Persona,
    JudgePersona,
    AgentConfig,
    ScoringRubric,
    DebateTranscript,
    DebateFormat,
    PolicyDebateFormat,
    AcademicSeminarFormat,
    RapidFireFormat,
    get_format,
    list_formats,
)


# ── Test Config (no LLM needed for unit tests) ────────────────────────────

TEST_CONFIG = AgentConfig(
    model="qwen2.5:7b",
    temperature=0.0,  # Deterministic for tests
    max_tokens=400,
    api_base="http://localhost:11434/v1",
    api_key="ollama",
)

MOCK_RESPONSE_A = """## Position
Raising the minimum wage to $15 per hour is a necessary institutional reform that addresses monopsony power in low-wage labor markets.

## Evidence
Card and Krueger (1994) found no employment reduction in fast food restaurants after New Jersey's minimum wage increase, using a difference-in-differences approach. The Seattle minimum wage study found that while hours were reduced slightly, total earnings increased for low-wage workers. The monopsony model predicts that in concentrated labor markets, a moderate minimum wage can increase both wages AND employment.

## Counterpoint Acknowledgment
The strongest counterargument is that a $15 federal minimum wage may be too high for low-cost regions. The evidence from high-cost cities may not generalize to rural Mississippi."""

MOCK_RESPONSE_B = """## Position
A $15 federal minimum wage would destroy jobs in low-wage sectors and regions, particularly harming the very workers it aims to help.

## Evidence
The Congressional Budget Office estimates that a $15 minimum wage would lift 900,000 out of poverty but cost 1.4 million jobs. Neumark and Wascher's meta-analysis finds a consensus employment elasticity of about -0.15 for teenagers. Firms substitute toward automation when labor costs rise, as seen in the restaurant industry's rapid adoption of ordering kiosks. The EITC is a superior policy because it targets low-income workers without creating a price floor that distorts labor markets.

## Counterpoint Acknowledgment
I acknowledge that Card and Krueger (1994) and the Seattle study show minimal employment effects in specific contexts. However, these studies examine moderate increases in high-cost urban areas — a $15 national floor is a fundamentally different policy that would bind in low-wage regions where the bite is much larger."""


class TestScoringRubric(unittest.TestCase):
    """Tests for the scoring rubric."""

    def setUp(self):
        self.rubric = ScoringRubric()

    def test_default_criteria(self):
        """Default criteria should sum to 1.0."""
        total = sum(self.rubric.weights.values())
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_criterion_names(self):
        """Should have all six criteria."""
        expected = {
            "empirical_grounding", "logical_coherence",
            "counterargument_addressing", "policy_feasibility",
            "value_articulation", "rhetorical_effectiveness",
        }
        self.assertEqual(set(self.rubric.criterion_names), expected)

    def test_format_adjustments(self):
        """Format adjustments should modify weights."""
        rubric = ScoringRubric(adjust_for_format={"empirical_grounding": 2.0})
        original = ScoringRubric()
        self.assertGreater(
            rubric.weights["empirical_grounding"],
            original.weights["empirical_grounding"],
        )

    def test_score_exchange(self):
        """Score exchange should return structured results."""
        result = self.rubric.score_exchange(
            MOCK_RESPONSE_A, MOCK_RESPONSE_B, phase="opening_statement"
        )
        self.assertEqual(result.round_name, "opening_statement")
        self.assertGreaterEqual(result.a_total, 0)
        self.assertLessEqual(result.a_total, 10)
        self.assertGreaterEqual(result.b_total, 0)
        self.assertLessEqual(result.b_total, 10)
        self.assertEqual(len(result.a_scores), 6)
        self.assertEqual(len(result.b_scores), 6)

    def test_composite_score(self):
        """Composite scoring should aggregate rounds correctly."""
        r1 = self.rubric.score_exchange(MOCK_RESPONSE_A, MOCK_RESPONSE_B, "round1")
        r2 = self.rubric.score_exchange(MOCK_RESPONSE_B, MOCK_RESPONSE_A, "round2")
        composite = self.rubric.composite_score([r1, r2])
        self.assertIn("winner", composite)
        self.assertIn("rounds", composite)
        self.assertEqual(composite["rounds"], 2)

    def test_fallacy_detection_ad_hominem(self):
        """Should detect ad hominem attacks."""
        text = "My opponent is completely biased and doesn't know what they're talking about. Their argument should be dismissed."
        detections = self.rubric.detect_fallacies(text)
        self.assertTrue(any(d.fallacy_type == "ad_hominem" for d in detections))

    def test_fallacy_detection_straw_man(self):
        """Should detect straw man arguments."""
        text = "My opponent is essentially saying we should just let markets run wild with no regulation whatsoever."
        detections = self.rubric.detect_fallacies(text)
        self.assertTrue(any(d.fallacy_type == "straw_man" for d in detections))

    def test_fallacy_detection_false_dichotomy(self):
        """Should detect false dichotomies."""
        text = "We must either raise the minimum wage or accept that millions will live in poverty. There is no middle ground."
        detections = self.rubric.detect_fallacies(text)
        self.assertTrue(
            any(d.fallacy_type == "false_dichotomy" for d in detections)
        )

    def test_fallacy_detection_clean_text(self):
        """Should not flag clean, well-reasoned text."""
        text = (
            "The empirical evidence on minimum wage effects is mixed. "
            "Card and Krueger (1994) found minimal employment effects, "
            "while Neumark and Wascher found negative effects. "
            "The variation in findings appears to be driven by differences "
            "in methodology and the specific contexts studied."
        )
        detections = self.rubric.detect_fallacies(text)
        self.assertEqual(len(detections), 0)

    def test_evidence_quality(self):
        """Should detect strong evidence indicators."""
        result = self.rubric.evidence_quality_check(MOCK_RESPONSE_A)
        self.assertGreater(result["strong_count"], 0)
        self.assertIn("assessment", result)
        self.assertIn("score", result)

    def test_evidence_quality_weak(self):
        """Should detect weak evidence patterns."""
        text = "Common sense tells us that raising wages must reduce employment. Everyone knows that. It's obvious."
        result = self.rubric.evidence_quality_check(text)
        self.assertGreater(result["weak_count"], 0)


class TestPersona(unittest.TestCase):
    """Tests for persona definitions."""

    def test_persona_creation(self):
        """Should create a persona with all fields."""
        p = Persona(
            name="Test Economist",
            school="Test School",
            key_assumptions=["Assumption 1", "Assumption 2"],
            value_priorities=["Value 1"],
            rhetorical_style="Test-driven",
            constraints=["Must cite tests"],
        )
        self.assertEqual(p.name, "Test Economist")
        self.assertEqual(p.school, "Test School")

    def test_persona_system_prompt(self):
        """System prompt should contain key persona information."""
        p = Persona(
            name="Test Economist",
            school="Institutional",
            key_assumptions=["Institutions matter"],
            value_priorities=["Fairness"],
            rhetorical_style="Historical",
            constraints=["Must cite examples"],
        )
        prompt = p.build_system_prompt("AFFIRMATIVE", "Test topic")
        self.assertIn("Institutional", prompt)
        self.assertIn("AFFIRMATIVE", prompt)
        self.assertIn("Test topic", prompt)
        self.assertIn("Institutions matter", prompt)

    def test_persona_serialization(self):
        """Persona should round-trip through dict."""
        p = Persona(
            name="Round Trip",
            school="Neoclassical",
            key_assumptions=["Rational agents"],
            value_priorities=["Efficiency"],
        )
        data = p.to_dict()
        p2 = Persona.from_dict(data)
        self.assertEqual(p2.name, p.name)
        self.assertEqual(p2.school, p.school)

    def test_judge_persona_creation(self):
        """Judge persona should create correctly."""
        jp = JudgePersona(
            name="Test Judge",
            school="Test School",
            description="A test judge",
            value_priorities=["Rigor"],
            scoring_philosophy="Test philosophy",
        )
        self.assertEqual(jp.name, "Test Judge")
        data = jp.to_dict()
        jp2 = JudgePersona.from_dict(data)
        self.assertEqual(jp2.name, "Test Judge")


class TestFormats(unittest.TestCase):
    """Tests for debate format definitions."""

    def test_policy_format_turns(self):
        """Policy format should have the right turn structure."""
        fmt = PolicyDebateFormat()
        phases = [t.phase for t in fmt.turns]
        self.assertIn("opening_statement", phases)
        self.assertIn("rebuttal", phases)
        self.assertIn("closing_statement", phases)
        self.assertIn("cross_examination", phases)
        self.assertIn("cross_examination_response", phases)

    def test_seminar_format_turns(self):
        """Seminar format should have position paper and critique phases."""
        fmt = AcademicSeminarFormat()
        phases = [t.phase for t in fmt.turns]
        self.assertIn("position_paper", phases)
        self.assertIn("peer_critique", phases)
        self.assertIn("revision", phases)
        self.assertIn("consensus_statement", phases)

    def test_rapid_fire_format(self):
        """Rapid fire should have many exchange turns."""
        fmt = RapidFireFormat()
        self.assertGreater(len(fmt.turns), 10)

    def test_format_serialization(self):
        """Format should serialize to and from YAML."""
        fmt = PolicyDebateFormat()
        yaml_str = fmt.to_yaml()
        restored = fmt.from_yaml(yaml_str)
        self.assertEqual(restored.name, fmt.name)
        self.assertEqual(len(restored.turns), len(fmt.turns))

    def test_format_file_save_load(self):
        """Format should save to and load from file."""
        fmt = PolicyDebateFormat()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            tmp_path = f.name
            fmt.save(tmp_path)

        try:
            loaded = DebateFormat.load(tmp_path)  # type: ignore
            self.assertEqual(loaded.name, fmt.name)
            self.assertEqual(len(loaded.turns), len(fmt.turns))
        finally:
            os.unlink(tmp_path)

    def test_get_format(self):
        """get_format should return correct format by name."""
        self.assertIsInstance(get_format("standard"), PolicyDebateFormat)
        self.assertIsInstance(get_format("policy"), PolicyDebateFormat)
        self.assertIsInstance(get_format("seminar"), AcademicSeminarFormat)
        self.assertIsInstance(get_format("rapid"), RapidFireFormat)

    def test_get_format_invalid(self):
        """get_format should raise on invalid format name."""
        with self.assertRaises(ValueError):
            get_format("nonexistent_format")

    def test_list_formats(self):
        """list_formats should return format descriptions."""
        formats = list_formats()
        self.assertGreater(len(formats), 0)

    def test_scoring_adjustments(self):
        """Format adjustments should modify scoring weights."""
        fmt = PolicyDebateFormat()
        base = {"a": 0.5, "b": 0.5}
        adjusted = fmt.get_adjusted_criteria(base)
        # With adjustments targeting specific criteria, totals should still sum to ~1
        self.assertAlmostEqual(sum(adjusted.values()), 1.0, places=2)


class TestTranscript(unittest.TestCase):
    """Tests for debate transcript."""

    def setUp(self):
        self.transcript = DebateTranscript(
            topic="Test Topic",
            format_name="Policy Debate",
        )

    def test_append_entry(self):
        """Should append entries correctly."""
        entry = self.transcript.append(
            speaker="a",
            speaker_label="Debater A",
            phase="opening_statement",
            content="Test content",
            school="Neoclassical",
        )
        self.assertEqual(len(self.transcript), 1)
        self.assertEqual(entry.speaker, "a")
        self.assertEqual(entry.content, "Test content")

    def test_markdown_output(self):
        """Should generate valid Markdown."""
        self.transcript.append("a", "A", "opening_statement", "Content A")
        self.transcript.append("b", "B", "opening_statement", "Content B")
        md = self.transcript.to_markdown()
        self.assertIn("Test Topic", md)
        self.assertIn("Content A", md)
        self.assertIn("Content B", md)

    def test_html_output(self):
        """Should generate valid HTML."""
        self.transcript.append("a", "A", "opening_statement", "Content A")
        html = self.transcript.to_html()
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Test Topic", html)
        self.assertIn("Content A", html)

    def test_verdict_summary(self):
        """Should generate verdict summary."""
        self.transcript.set_verdict({
            "winner": "a",
            "winner_name": "Debater A",
            "margin": 1.5,
            "a_average": 7.5,
            "b_average": 6.0,
            "opinion": "Debater A wins on empirical grounding.",
            "round_scores": [
                {"name": "opening", "a": 7.5, "b": 6.0},
            ],
        })
        summary = self.transcript.verdict_summary()
        self.assertIn("Winner", summary)
        self.assertIn("Debater A", summary)

    def test_highlight_key_moments(self):
        """Should extract key moments from transcript."""
        self.transcript.append(
            "a", "A", "rebuttal",
            "I concede that my opponent makes a fair point about transition costs. "
            "However, the fundamental flaw in their argument is that they ignore "
            "the RCT evidence from Oregon.",
        )
        moments = self.transcript.highlight_key_moments(n=3)
        self.assertGreater(len(moments), 0)

    def test_search(self):
        """Should search transcript for text."""
        self.transcript.append("a", "A", "opening", "Card and Krueger 1994 study")
        self.transcript.append("b", "B", "opening", "Neumark and Wascher meta-analysis")
        results = self.transcript.search("Card")
        self.assertEqual(len(results), 1)
        results = self.transcript.search("nonexistent")
        self.assertEqual(len(results), 0)

    def test_to_dict(self):
        """Should serialize to dict."""
        self.transcript.append("a", "A", "opening", "Test")
        d = self.transcript.to_dict()
        self.assertEqual(d["topic"], "Test Topic")
        self.assertEqual(len(d["entries"]), 1)

    def test_verdict_no_verdict(self):
        """Should handle missing verdict gracefully."""
        result = self.transcript.verdict_summary()
        self.assertIn("No verdict", result)


class TestDebateArena(unittest.TestCase):
    """Integration-style tests for the arena (without LLM calls)."""

    def setUp(self):
        self.arena = DebateArena(
            topic="Test: Should X be implemented?",
            format="standard",
            config=TEST_CONFIG,
        )

    def test_arena_creation(self):
        """Arena should create debaters and judge."""
        self.assertIsNotNone(self.arena.debater_a)
        self.assertIsNotNone(self.arena.debater_b)
        self.assertIsNotNone(self.arena.judge)
        self.assertIsNotNone(self.arena.transcript)
        self.assertEqual(self.arena.topic, "Test: Should X be implemented?")

    def test_arena_repr(self):
        """Arena repr should show key info."""
        r = repr(self.arena)
        self.assertIn("DebateArena", r)
        self.assertIn("Test", r)

    def test_default_personas(self):
        """Default personas should be assigned when none provided."""
        self.assertEqual(self.arena.debater_a.persona.school, "Institutional")
        self.assertEqual(self.arena.debater_b.persona.school, "Neoclassical")

    def test_custom_personas(self):
        """Custom personas should be used when provided."""
        p_a = Persona(name="Custom A", school="Custom School A")
        p_b = Persona(name="Custom B", school="Custom School B")
        jp = JudgePersona(name="Custom Judge")
        arena = DebateArena(
            topic="Test",
            debater_a_persona=p_a,
            debater_b_persona=p_b,
            judge_persona=jp,
            config=TEST_CONFIG,
        )
        self.assertEqual(arena.debater_a.persona.school, "Custom School A")
        self.assertEqual(arena.debater_b.persona.school, "Custom School B")
        self.assertEqual(arena.judge.persona.name, "Custom Judge")


class TestAgentConfiguration(unittest.TestCase):
    """Tests for agent configuration."""

    def test_agent_config_defaults(self):
        """AgentConfig should have sensible defaults."""
        config = AgentConfig()
        self.assertEqual(config.model, "qwen2.5:7b")
        self.assertEqual(config.temperature, 0.7)
        self.assertGreater(config.max_tokens, 0)

    def test_agent_config_custom(self):
        """AgentConfig should accept custom values."""
        config = AgentConfig(
            model="gpt-4",
            temperature=0.5,
            api_base="https://api.openai.com/v1",
            api_key="sk-test",
        )
        self.assertEqual(config.model, "gpt-4")
        self.assertEqual(config.temperature, 0.5)


class TestYamlPersonaLoading(unittest.TestCase):
    """Tests for loading personas from YAML config."""

    def setUp(self):
        import yaml
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "personas.yaml",
        )
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

    def test_personas_loaded(self):
        """Personas YAML should contain all expected schools."""
        personas = self.config.get("personas", {})
        self.assertIn("neoclassical_economist", personas)
        self.assertIn("institutional_economist", personas)
        self.assertIn("behavioral_economist", personas)
        self.assertIn("public_choice_theorist", personas)
        self.assertIn("keynesian_economist", personas)
        self.assertIn("austrian_economist", personas)
        self.assertIn("marxist_economist", personas)
        self.assertIn("capabilities_economist", personas)

    def test_judges_loaded(self):
        """Personas YAML should contain judge definitions."""
        judges = self.config.get("judges", {})
        self.assertIn("impartial_economist", judges)
        self.assertIn("devil_advocate", judges)
        self.assertIn("policy_practitioner", judges)

    def test_load_persona_from_yaml(self):
        """Should be able to create Persona objects from YAML data."""
        data = self.config["personas"]["neoclassical_economist"]
        persona = Persona.from_dict(data)
        self.assertEqual(persona.school, "Neoclassical")
        self.assertTrue(len(persona.key_assumptions) > 0)
        self.assertTrue(len(persona.value_priorities) > 0)
        self.assertTrue(len(persona.constraints) > 0)

    def test_personas_have_required_fields(self):
        """Every persona should have all required fields."""
        for key, data in self.config["personas"].items():
            with self.subTest(persona=key):
                self.assertIn("school", data)
                self.assertIn("key_assumptions", data)
                self.assertIn("value_priorities", data)
                self.assertIn("rhetorical_style", data)
                self.assertIn("constraints", data)

    def test_judges_have_required_fields(self):
        """Every judge should have all required fields."""
        for key, data in self.config["judges"].items():
            with self.subTest(judge=key):
                self.assertIn("school", data)
                self.assertIn("description", data)
                self.assertIn("value_priorities", data)
                self.assertIn("scoring_philosophy", data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
