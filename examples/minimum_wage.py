"""
Example: Minimum Wage Debate
=============================

Institutional Economist (pro-raise) vs Neoclassical Economist (anti-raise),
with a Behavioral Economist serving as judge.

This example demonstrates:
    - Custom persona loading from persona definitions
    - PolicyDebateFormat with full turn structure
    - Multi-criterion scoring and fallacy detection
    - HTML and Markdown transcript generation

Usage:
    python examples/minimum_wage.py
"""

import os
import sys

# Add parent directory to path for local development
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from debate_judge import (
    DebateArena,
    Persona,
    JudgePersona,
    AgentConfig,
)


def main() -> None:
    """Run the minimum wage debate."""

    # ── Configure LLM ──────────────────────────────────────────────────
    # Default: local Ollama with qwen2.5:7b
    # Change these to use a different model or API endpoint
    config = AgentConfig(
        model="qwen2.5:7b",
        temperature=0.7,
        max_tokens=1200,
        api_base="http://localhost:11434/v1",
        api_key="ollama",
    )

    # ── Define Personas ────────────────────────────────────────────────

    institutional = Persona(
        name="Institutional Economist",
        school="Institutional",
        key_assumptions=[
            "Labor markets are embedded in social and institutional contexts",
            "Minimum wages can counter monopsony power in labor markets",
            "Higher wages increase productivity through efficiency wage effects",
            "Institutional change can shift equilibria, not just move along curves",
        ],
        value_priorities=[
            "Worker welfare and living standards",
            "Reducing inequality",
            "Institutional quality",
            "Long-run productivity growth",
        ],
        rhetorical_style=(
            "Empirically grounded, institutionally aware. Cites Card & Krueger (1994), "
            "the Seattle minimum wage study, and cross-country institutional comparisons. "
            "Emphasizes monopsony, efficiency wages, and the institutional context of "
            "low-wage labor markets."
        ),
        constraints=[
            "Must cite specific empirical studies on minimum wage effects",
            "Must acknowledge that very high minimum wages can reduce employment",
            "Must specify the institutional mechanisms by which minimum wages work",
            "Must address the EITC as an alternative policy instrument",
        ],
    )

    neoclassical = Persona(
        name="Neoclassical Economist",
        school="Neoclassical",
        key_assumptions=[
            "Labor markets clear through price adjustment in competitive markets",
            "Price floors above equilibrium create deadweight loss",
            "Firms substitute capital for labor when labor becomes more expensive",
            "The EITC targets low-income workers without distorting labor markets",
        ],
        value_priorities=[
            "Allocative efficiency",
            "Employment maximization",
            "Consumer welfare (lower prices)",
            "Targeted transfers over price controls",
        ],
        rhetorical_style=(
            "Model-driven, marginal analysis. Cites Neumark & Wascher, CBO estimates, "
            "and meta-analyses of employment elasticities. Uses supply-and-demand "
            "frameworks and emphasizes substitution effects."
        ),
        constraints=[
            "Must acknowledge the Card & Krueger findings and monopsony literature",
            "Must address why low-wage workers may lack bargaining power",
            "Must propose alternative policies for helping low-wage workers",
            "Must cite specific elasticity estimates with confidence intervals",
        ],
    )

    behavioral_judge = JudgePersona(
        name="Behavioral Policy Evaluator",
        school="Evidence-Based Policy",
        description=(
            "A behavioral economist serving as impartial judge. Evaluates arguments "
            "based on empirical grounding, logical coherence, engagement with "
            "counterarguments, and policy feasibility. Does not favor any economic "
            "tradition — rewards rigorous argumentation and honest debate."
        ),
        value_priorities=[
            "Causal evidence from well-identified studies",
            "Acknowledgment of heterogeneous treatment effects",
            "Honest engagement with the strongest counterarguments",
            "Policies that work in practice, not just in theory",
        ],
        scoring_philosophy=(
            "Rewards specific evidence (named studies, reported magnitudes) over "
            "general assertions. Penalizes straw-man arguments, evasion of "
            "cross-examination questions, and rhetorical tricks over substance. "
            "Acknowledge when the evidence is mixed — dogmatism loses points."
        ),
    )

    # ── Create and Run Arena ───────────────────────────────────────────

    arena = DebateArena(
        topic="Resolved: The federal minimum wage should be raised to $15 per hour and indexed to inflation",
        debater_a_persona=institutional,
        debater_b_persona=neoclassical,
        judge_persona=behavioral_judge,
        format="standard",
        config=config,
    )

    print("Debaters:")
    print(f"  A (Affirmative): {arena.debater_a.name}")
    print(f"     School: {arena.debater_a.persona.school}")
    print(f"     Values: {', '.join(arena.debater_a.persona.value_priorities)}")
    print(f"  B (Negative): {arena.debater_b.name}")
    print(f"     School: {arena.debater_b.persona.school}")
    print(f"     Values: {', '.join(arena.debater_b.persona.value_priorities)}")
    print()

    # Run the debate
    result = arena.run()

    # ── Output ─────────────────────────────────────────────────────────

    # Save transcripts
    output_dir = os.path.dirname(os.path.abspath(__file__))

    md_path = os.path.join(output_dir, "minimum_wage_transcript.md")
    html_path = os.path.join(output_dir, "minimum_wage_transcript.html")

    arena.save_transcript(md_path, format="markdown")
    arena.save_transcript(html_path, format="html")

    print(f"\nResults:")
    print(f"  Winner: {result['winner_name']}")
    print(f"  Margin: {result['margin']}")
    print(f"  Markdown: {md_path}")
    print(f"  HTML: {html_path}")


if __name__ == "__main__":
    main()
