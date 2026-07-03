"""
Debate transcript and output formatting.

Provides structured transcript storage, Markdown export, HTML rendering with
color-coded speakers and collapsible sections, verdict summaries, and tools
for extracting pivotal moments from the debate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from jinja2 import Template


# ── HTML Template ──────────────────────────────────────────────────────────

_HTML_TEMPLATE = Template("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DebateJudge Transcript — {{ topic }}</title>
<style>
  :root {
    --bg: #0d1117; --card-bg: #161b22; --border: #30363d;
    --text: #c9d1d9; --text-muted: #8b949e; --accent: #58a6ff;
    --a-color: #3fb950; --b-color: #f85149; --judge-color: #d2991d;
    --a-bg: rgba(63,185,80,0.08); --b-bg: rgba(248,81,73,0.08);
    --judge-bg: rgba(210,153,29,0.08);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; padding: 2rem; }
  h1 { font-size: 1.8rem; margin-bottom: 0.3rem; color: #f0f6fc; }
  h2 { font-size: 1.3rem; margin: 1.5rem 0 0.8rem; color: #f0f6fc; border-bottom: 1px solid var(--border); padding-bottom: 0.3rem; }
  h3 { font-size: 1.05rem; margin: 1rem 0 0.5rem; color: #e6edf3; }
  .meta { color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1.5rem; }
  .section { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 1.2rem; margin-bottom: 1rem; }
  .speaker-a { border-left: 3px solid var(--a-color); }
  .speaker-b { border-left: 3px solid var(--b-color); }
  .judge { border-left: 3px solid var(--judge-color); }
  .speaker-label { font-weight: 600; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.5rem; }
  .speaker-label .badge { font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 12px; }
  .badge-a { background: var(--a-bg); color: var(--a-color); }
  .badge-b { background: var(--b-bg); color: var(--b-color); }
  .badge-judge { background: var(--judge-bg); color: var(--judge-color); }
  .phase-tag { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); background: rgba(255,255,255,0.05); padding: 0.1rem 0.5rem; border-radius: 4px; }
  .content { white-space: pre-wrap; font-size: 0.92rem; margin-top: 0.5rem; }
  details { margin: 0.5rem 0; }
  details summary { cursor: pointer; font-weight: 600; color: var(--accent); user-select: none; padding: 0.3rem 0; }
  details summary:hover { opacity: 0.8; }
  .score-card { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin: 1rem 0; }
  .score-box { background: var(--card-bg); border: 1px solid var(--border); border-radius: 6px; padding: 0.8rem; }
  .score-total { font-size: 1.6rem; font-weight: 700; }
  .score-a { color: var(--a-color); }
  .score-b { color: var(--b-color); }
  .criterion-row { display: flex; justify-content: space-between; padding: 0.2rem 0; font-size: 0.85rem; }
  .verdict { background: linear-gradient(135deg, rgba(210,153,29,0.1), rgba(210,153,29,0.02)); border: 1px solid var(--judge-color); border-radius: 8px; padding: 1.5rem; margin-top: 1rem; }
  .verdict-winner { font-size: 1.3rem; font-weight: 700; color: var(--judge-color); }
  table { width: 100%; border-collapse: collapse; margin: 0.5rem 0; }
  th, td { text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid var(--border); font-size: 0.88rem; }
  th { color: var(--text-muted); font-weight: 600; }
  .highlight { background: rgba(88,166,255,0.08); border-left: 2px solid var(--accent); padding: 0.5rem; margin: 0.5rem 0; border-radius: 0 4px 4px 0; }
</style>
</head>
<body>

<h1>{{ topic }}</h1>
<div class="meta">
  {{ format_name }} | {{ meta.debater_a }} ({{ meta.school_a }}) vs {{ meta.debater_b }} ({{ meta.school_b }})
  {% if meta.judge_name %} | Judge: {{ meta.judge_name }}{% endif %}
  | {{ meta.timestamp }}
</div>

{% if verdict %}
<div class="verdict">
  <div class="verdict-winner">Winner: {{ verdict.winner_name }}</div>
  <div style="margin-top:0.3rem;color:var(--text-muted)">Margin: {{ verdict.margin }}</div>
  <div style="margin-top:0.8rem;white-space:pre-wrap">{{ verdict.opinion }}</div>
</div>
{% endif %}

<h2>Debate Transcript</h2>

{% for entry in entries %}
<div class="section {{ 'speaker-a' if entry.speaker == 'a' else 'speaker-b' if entry.speaker == 'b' else 'judge' }}">
  <div class="speaker-label">
    <span class="badge {{ 'badge-a' if entry.speaker == 'a' else 'badge-b' if entry.speaker == 'b' else 'badge-judge' }}">
      {{ entry.speaker_label }}
    </span>
    <span class="phase-tag">{{ entry.phase }}</span>
    {% if entry.scores %}
    <span style="font-size:0.8rem;color:var(--text-muted)">
      Score: {{ "%.1f"|format(entry.scores.get('total', 0)) }}/10
    </span>
    {% endif %}
  </div>
  <details {% if entry.speaker != 'judge' %}open{% endif %}>
    <summary>{{ entry.phase | replace('_', ' ') | title }}</summary>
    <div class="content">{{ entry.content }}</div>
  </details>
</div>
{% endfor %}

{% if key_moments %}
<h2>Key Moments</h2>
{% for km in key_moments %}
<div class="highlight">
  <strong>#{{ loop.index }}</strong> — {{ km.phase | replace('_', ' ') | title }}
  <div style="font-size:0.85rem;color:var(--text-muted);margin-top:0.2rem">{{ km.excerpt[:300] }}...</div>
</div>
{% endfor %}
{% endif %}

{% if round_scores %}
<h2>Round-by-Round Scores</h2>
<table>
  <tr><th>Round</th><th style="text-align:right;color:var(--a-color)">A Score</th><th style="text-align:right;color:var(--b-color)">B Score</th><th>Advantage</th></tr>
  {% for rs in round_scores %}
  <tr>
    <td>{{ rs.name }}</td>
    <td style="text-align:right">{{ "%.1f"|format(rs.a) }}</td>
    <td style="text-align:right">{{ "%.1f"|format(rs.b) }}</td>
    <td>{{ "A" if rs.a > rs.b else "B" if rs.b > rs.a else "—" }}</td>
  </tr>
  {% endfor %}
</table>
{% endif %}

</body>
</html>""")


# ── Data Classes ───────────────────────────────────────────────────────────

@dataclass
class TranscriptEntry:
    """A single entry in the debate transcript.

    Attributes:
        speaker: "a", "b", or "judge"
        speaker_label: Human-readable speaker name
        phase: Phase identifier (opening_statement, rebuttal, etc.)
        content: The text content of this entry
        scores: Optional scoring data for this entry
        metadata: Additional metadata
    """

    speaker: str
    speaker_label: str
    phase: str
    content: str
    scores: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KeyMoment:
    """A pivotal moment extracted from the transcript.

    Attributes:
        phase: Which phase the moment occurred in
        turn_index: Index in the transcript
        excerpt: The relevant text excerpt
        significance: Why this moment is noteworthy
    """

    phase: str
    turn_index: int
    excerpt: str
    significance: str = ""


# ── DebateTranscript ───────────────────────────────────────────────────────

class DebateTranscript:
    """Structured transcript of a complete debate.

    Collects all entries, provides formatting and search, and can export
    to Markdown and styled HTML with scoring data.

    Attributes:
        topic: The debate topic
        entries: Ordered list of transcript entries
        format_name: Name of the debate format used
        verdict: Optional final adjudication data
    """

    def __init__(
        self,
        topic: str = "",
        format_name: str = "Policy Debate",
    ) -> None:
        """
        Args:
            topic: The debate topic/resolution
            format_name: Name of the debate format used
        """
        self.topic: str = topic
        self.format_name: str = format_name
        self.entries: List[TranscriptEntry] = []
        self.verdict: Optional[Dict[str, Any]] = None
        self._created_at: datetime = datetime.now()

    def append(
        self,
        speaker: str,
        speaker_label: str,
        phase: str,
        content: str,
        scores: Optional[Dict[str, Any]] = None,
        **metadata: Any,
    ) -> TranscriptEntry:
        """Add an entry to the transcript.

        Args:
            speaker: "a", "b", or "judge"
            speaker_label: Human-readable name
            phase: Phase identifier
            content: The text content
            scores: Optional scoring data
            **metadata: Additional metadata

        Returns:
            The added TranscriptEntry
        """
        entry = TranscriptEntry(
            speaker=speaker,
            speaker_label=speaker_label,
            phase=phase,
            content=content,
            scores=scores,
            metadata=metadata,
        )
        self.entries.append(entry)
        return entry

    def set_verdict(self, verdict: Dict[str, Any]) -> None:
        """Record the final adjudication verdict."""
        self.verdict = verdict

    def to_markdown(self) -> str:
        """Export the full transcript as Markdown.

        Returns:
            Complete Markdown string with all entries, scores, and verdict
        """
        lines = [
            f"# Debate Transcript: {self.topic}",
            "",
            f"**Format:** {self.format_name}",
            f"**Date:** {self._created_at.strftime('%Y-%m-%d %H:%M')}",
            "",
        ]

        # Group entries by phase
        current_phase = None
        for i, entry in enumerate(self.entries):
            if entry.phase != current_phase:
                current_phase = entry.phase
                lines.extend([
                    "---",
                    f"## {current_phase.replace('_', ' ').title()}",
                    "",
                ])

            label = entry.speaker_label
            if entry.scores and "total" in entry.scores:
                label += f" (Score: {entry.scores['total']:.1f}/10)"

            lines.extend([
                f"### {label}",
                "",
                entry.content,
                "",
            ])

        # Verdict
        if self.verdict:
            lines.extend([
                "---",
                "## Verdict",
                "",
                f"**Winner: {self.verdict.get('winner_name', 'Unknown')}**",
                f"**Margin: {self.verdict.get('margin', 'N/A')}**",
                "",
                self.verdict.get("opinion", ""),
                "",
            ])

            # Score breakdown
            lines.extend(["### Score Breakdown", ""])
            round_scores = self.verdict.get("round_scores", [])
            if round_scores:
                lines.append("| Round | A | B | Advantage |")
                lines.append("|-------|---|---|-----------|")
                for rs in round_scores:
                    adv = "A" if rs["a"] > rs["b"] else "B" if rs["b"] > rs["a"] else "="
                    lines.append(f"| {rs['name']} | {rs['a']:.1f} | {rs['b']:.1f} | {adv} |")
                lines.append("")

            criterion_breakdown = self.verdict.get("criterion_breakdown", {})
            if criterion_breakdown:
                lines.extend(["### Criterion Breakdown", ""])
                lines.append("| Criterion | A Avg | B Avg | Advantage |")
                lines.append("|-----------|-------|-------|-----------|")
                for name, data in criterion_breakdown.items():
                    adv = f"A (+{data['a_advantage']:.1f})" if data['a_advantage'] > 0 else f"B (+{abs(data['a_advantage']):.1f})" if data['a_advantage'] < 0 else "="
                    lines.append(f"| {name} | {data['a_avg']:.1f} | {data['b_avg']:.1f} | {adv} |")
                lines.append("")

        return "\n".join(lines)

    def to_html(self) -> str:
        """Export as styled HTML with color-coded speakers and collapsible sections.

        Returns:
            Complete HTML string
        """
        # Collect metadata
        a_entries = [e for e in self.entries if e.speaker == "a"]
        b_entries = [e for e in self.entries if e.speaker == "b"]

        meta = {
            "debater_a": a_entries[0].speaker_label if a_entries else "Debater A",
            "debater_b": b_entries[0].speaker_label if b_entries else "Debater B",
            "school_a": a_entries[0].metadata.get("school", "") if a_entries else "",
            "school_b": b_entries[0].metadata.get("school", "") if b_entries else "",
            "judge_name": next(
                (e.speaker_label for e in self.entries if e.speaker == "judge"), ""
            ),
            "timestamp": self._created_at.strftime("%Y-%m-%d %H:%M"),
        }

        entries_data = []
        for entry in self.entries:
            entries_data.append({
                "speaker": entry.speaker,
                "speaker_label": entry.speaker_label,
                "phase": entry.phase,
                "content": entry.content,
                "scores": entry.scores,
            })

        key_moments_data = []
        moments = self.highlight_key_moments(n=5)
        for km in moments:
            key_moments_data.append({
                "phase": km.phase,
                "excerpt": km.excerpt,
            })

        round_scores_data = []
        if self.verdict:
            for rs in self.verdict.get("round_scores", []):
                round_scores_data.append(rs)

        return _HTML_TEMPLATE.render(
            topic=self.topic,
            format_name=self.format_name,
            meta=meta,
            entries=entries_data,
            verdict=self.verdict,
            key_moments=key_moments_data,
            round_scores=round_scores_data,
        )

    def verdict_summary(self) -> str:
        """Generate a one-page verdict summary.

        Returns:
            Verdict summary as Markdown string
        """
        if not self.verdict:
            return "No verdict has been recorded."

        v = self.verdict
        lines = [
            f"# Verdict: {self.topic}",
            "",
            f"**Winner:** {v.get('winner_name', 'Unknown')}",
            f"**Margin:** {v.get('margin', 'N/A')}",
            f"**Average Scores:** A: {v.get('a_average', 'N/A')} | B: {v.get('b_average', 'N/A')}",
            "",
            "## Judge's Opinion",
            "",
            v.get("opinion", "No opinion recorded."),
            "",
            "## Round Summary",
            "",
        ]

        for rs in v.get("round_scores", []):
            lines.append(f"- **{rs['name']}**: A {rs['a']:.1f} — B {rs['b']:.1f}")

        return "\n".join(lines)

    def highlight_key_moments(self, n: int = 5) -> List[KeyMoment]:
        """Extract pivotal exchanges from the transcript.

        Uses heuristics: looks for turns where the debate dynamic shifts —
        high engagement with opponent's arguments, concessions, pointed critiques,
        and judge commentary.

        Args:
            n: Maximum number of key moments to extract

        Returns:
            List of KeyMoment objects
        """
        moments: List[KeyMoment] = []

        for i, entry in enumerate(self.entries):
            content_lower = entry.content.lower()
            significance = ""

            # Check for concession language
            if re.search(
                r"\b(?:concede|grant|admit|acknowledge|fair\s+point|valid\s+criticism|you'?re\s+right)\b",
                content_lower,
            ):
                significance = "Notable concession or acknowledgment"

            # Check for pointed critique
            elif re.search(
                r"\b(?:fundamental\s+(?:flaw|problem|error|mistake)|fails?\s+to\s+account|contradicts?|ignores?)\b",
                content_lower,
            ):
                significance = "Pointed critique of opponent's argument"

            # Check for evidence deployment
            elif re.search(
                r"\b(?:RCT|randomized|natural\s+experiment|difference.in.differences|IV\s+estimate|meta.analysis)\b",
                content_lower,
            ):
                significance = "Strong evidence deployment"

            # Check for framing moment
            elif re.search(
                r"\b(?:the\s+real\s+question|what\s+we\s+should\s+be\s+asking|the\s+core\s+issue|at\s+stake\s+here)\b",
                content_lower,
            ):
                significance = "Reframing of the debate"

            # Judge verdict is always a key moment
            if entry.speaker == "judge":
                significance = "Judge's evaluation"

            if significance:
                # Get a meaningful excerpt
                excerpt = entry.content[:400].replace("\n", " ").strip()
                moments.append(KeyMoment(
                    phase=entry.phase,
                    turn_index=i,
                    excerpt=excerpt,
                    significance=significance,
                ))

        # Sort by significance priority (judge moments first, then concessions, etc.)
        priority = {"judge": 0, "concession": 1, "evidence": 2, "critique": 3, "framing": 4}
        def sort_key(km: KeyMoment) -> int:
            for k, v in priority.items():
                if k in km.significance.lower():
                    return v
            return 5

        moments.sort(key=sort_key)
        return moments[:n]

    def search(self, query: str, case_sensitive: bool = False) -> List[TranscriptEntry]:
        """Search the transcript for entries matching a query.

        Args:
            query: Search string
            case_sensitive: Whether to match case

        Returns:
            List of matching TranscriptEntry objects
        """
        results = []
        q = query if case_sensitive else query.lower()
        for entry in self.entries:
            content = entry.content if case_sensitive else entry.content.lower()
            if q in content:
                results.append(entry)
        return results

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the full transcript to a dictionary."""
        return {
            "topic": self.topic,
            "format_name": self.format_name,
            "created_at": self._created_at.isoformat(),
            "entries": [
                {
                    "speaker": e.speaker,
                    "speaker_label": e.speaker_label,
                    "phase": e.phase,
                    "content": e.content,
                    "scores": e.scores,
                    "metadata": e.metadata,
                }
                for e in self.entries
            ],
            "verdict": self.verdict,
        }

    def __len__(self) -> int:
        return len(self.entries)

    def __repr__(self) -> str:
        return (
            f"DebateTranscript(topic={self.topic!r}, entries={len(self)}, "
            f"format={self.format_name!r})"
        )
