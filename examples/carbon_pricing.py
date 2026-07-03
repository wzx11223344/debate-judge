"""
Example: Carbon Pricing Debate
===============================

Public Choice Theorist (carbon tax) vs Institutional Economist (cap-and-trade),
with a Behavioral Economist serving as judge.

This debate explores the institutional design of carbon pricing mechanisms:
    - Carbon tax: price certainty, simpler administration, but politically vulnerable
    - Cap-and-trade: quantity certainty, built-in flexibility, but market design risks

The key question is not WHETHER to price carbon, but HOW to design the mechanism
that is most likely to survive politically and work effectively.

Usage:
    python examples/carbon_pricing.py
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
    AcademicSeminarFormat,
    ScoringRubric,
)


def main() -> None:
    """Run the carbon pricing debate in academic seminar format."""

    # ── Configure LLM ──────────────────────────────────────────────────
    config = AgentConfig(
        model="qwen2.5:7b",
        temperature=0.7,
        max_tokens=1200,
        api_base="http://localhost:11434/v1",
        api_key="ollama",
    )

    # ── Define Personas ────────────────────────────────────────────────

    public_choice = Persona(
        name="Public Choice Theorist",
        school="Public Choice",
        key_assumptions=[
            "Political actors respond to incentives; policy design must account for this",
            "Concentrated benefits and diffuse costs shape regulatory outcomes",
            "Price instruments are harder to manipulate than quantity instruments",
            "Carbon pricing revenue creates its own political economy dynamics",
        ],
        value_priorities=[
            "Institutional robustness to rent-seeking",
            "Price certainty for investment planning",
            "Revenue neutrality and fiscal responsibility",
            "Transparency and simplicity in policy design",
        ],
        rhetorical_style=(
            "Incentive-focused, institutionally skeptical. Cites the EU ETS price "
            "collapse of 2006-2012, the BC carbon tax experience, and public choice "
            "analysis of regulatory capture. Emphasizes the political economy of "
            "carbon pricing — not just the economics."
        ),
        constraints=[
            "Must identify specific rent-seeking or political manipulation risks",
            "Must propose constitutional/institutional safeguards",
            "Must acknowledge cases where cap-and-trade has worked (SO2 program)",
            "Must address the 'tax' framing problem in US politics",
        ],
    )

    institutional = Persona(
        name="Institutional Economist",
        school="Institutional",
        key_assumptions=[
            "Market design matters as much as market existence",
            "Institutional evolution can improve policy over time",
            "Quantity-based instruments can create more durable political coalitions",
            "Carbon markets can link across jurisdictions, creating path dependency",
        ],
        value_priorities=[
            "Environmental effectiveness (quantity certainty)",
            "International coordination and market linking",
            "Political durability through stakeholder buy-in",
            "Adaptive governance and learning",
        ],
        rhetorical_style=(
            "Comparative institutional analysis. Cites the SO2 Acid Rain Program "
            "success, EU ETS evolution through phases, RGGI experience, and the "
            "California-Quebec linkage. Emphasizes that institutions can be designed "
            "to improve over time through learning."
        ),
        constraints=[
            "Must address the EU ETS Phase I price collapse",
            "Must explain why cap-and-trade succeeded for SO2 but faces challenges for CO2",
            "Must address the political durability of carbon taxes vs. cap-and-trade",
            "Must specify market design features that prevent manipulation",
        ],
    )

    behavioral_judge = JudgePersona(
        name="Behavioral Policy Analyst",
        school="Evidence-Based Policy",
        description=(
            "A behavioral economist evaluating carbon pricing mechanisms through "
            "the lens of real-world implementation. Considers both economic efficiency "
            "and political feasibility, recognizing that the best policy on paper "
            "is worthless if it cannot be implemented and sustained."
        ),
        value_priorities=[
            "Empirical track record of implemented policies",
            "Behavioral realism about political and market actors",
            "Policy durability across political cycles",
            "Distributional effects and public acceptance",
        ],
        scoring_philosophy=(
            "In carbon pricing, the theoretically optimal mechanism loses if it "
            "cannot survive political reality. Rewards concrete institutional "
            "design proposals. Penalizes 'in theory' arguments without institutional "
            "analysis. Both sides must address the other's strongest empirical case."
        ),
    )

    # ── Create and Run Arena ───────────────────────────────────────────
    # Using Academic Seminar format for a more scholarly exchange

    # Format the rubric to emphasize feasibility and empirical grounding
    rubric = ScoringRubric()

    arena = DebateArena(
        topic="Resolved: A revenue-neutral carbon tax is superior to cap-and-trade as the primary mechanism for carbon pricing",
        debater_a_persona=public_choice,   # Affirmative: carbon tax
        debater_b_persona=institutional,   # Negative: cap-and-trade
        judge_persona=behavioral_judge,
        format="seminar",  # Academic Seminar format for deep analysis
        config=config,
        rubric=rubric,
    )

    print("Carbon Pricing Mechanism Debate")
    print("=" * 60)
    print(f"  A (Affirmative - Carbon Tax): {arena.debater_a.name}")
    print(f"  B (Negative - Cap-and-Trade): {arena.debater_b.name}")
    print(f"  Format: {arena.format.name}")
    print(f"  Judge: {arena.judge.name}")
    print()

    # Run the debate
    result = arena.run()

    # ── Output ─────────────────────────────────────────────────────────

    output_dir = os.path.dirname(os.path.abspath(__file__))

    md_path = os.path.join(output_dir, "carbon_pricing_transcript.md")
    html_path = os.path.join(output_dir, "carbon_pricing_transcript.html")

    arena.save_transcript(md_path, format="markdown")
    arena.save_transcript(html_path, format="html")

    # Print criterion breakdown
    print(f"\nCriterion Breakdown:")
    breakdown = result.get("criterion_breakdown", {})
    if "round_scores" in result:
        # Try from verdict
        pass
    for name, data in breakdown.items():
        print(f"  {name}: A={data['a_avg']:.1f} B={data['b_avg']:.1f} (Advantage: {data['a_advantage']:+.1f})")

    print(f"\nFiles saved:")
    print(f"  Markdown: {md_path}")
    print(f"  HTML: {html_path}")


if __name__ == "__main__":
    main()
