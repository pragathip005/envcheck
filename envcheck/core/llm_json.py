from __future__ import annotations


def extract_json_block(response_text: str) -> str:
    """Pull a JSON object out of an LLM response that may wrap it in markdown
    code fences (```json ... ``` or a plain ``` ... ```), possibly with prose
    before or after. Returns the raw substring for the caller to json.loads -
    doesn't parse it itself, so a genuinely malformed block still raises
    json.JSONDecodeError at the call site, not here.

    Shared by envcheck.probes.certify and c1.evilgenie so both LLM-judge call
    sites parse fences the same way, instead of each maintaining its own
    (previously divergent) copy.
    """
    if "```json" in response_text:
        start = response_text.find("```json") + len("```json")
        end = response_text.find("```", start)
        return response_text[start:end].strip()
    if "```" in response_text:
        start = response_text.find("```") + 3
        end = response_text.find("```", start)
        return response_text[start:end].strip()
    return response_text.strip()
