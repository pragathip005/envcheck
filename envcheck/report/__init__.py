"""Renders scored results as JSON and a human-readable summary.

HTML rendering and CI exit-code wiring live here too eventually (plan.md §3);
for now this only ships the two pieces that are actually implemented and
tested - to_dict for machine consumption, render_text for a human/CLI view.
"""

from envcheck.report.types import render_text, to_dict

__all__ = ["render_text", "to_dict"]
