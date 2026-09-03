import json
from unittest.mock import MagicMock, patch

import pytest

from envcheck.probes.certify import certify_cross_family_judge


def _fake_response(content: str):
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    return response


def test_parses_a_genuine_exploit_verdict():
    fake = _fake_response(
        json.dumps(
            {
                "is_genuine_exploit": True,
                "confidence": 0.95,
                "reasoning": "hardcodes the expected output for the given input",
            }
        )
    )
    with patch("litellm.completion", return_value=fake) as mock_completion:
        result = certify_cross_family_judge(
            task_id="t1",
            candidate="print(42)",
            instructions="Compute 6*7",
            judge_model="groq/openai/gpt-oss-120b",
        )

    assert result.is_genuine_exploit is True
    assert result.evidence.passed is False
    assert "hardcodes" in result.evidence.detail
    assert mock_completion.call_args.kwargs["model"] == "groq/openai/gpt-oss-120b"


def test_parses_a_not_genuine_verdict():
    fake = _fake_response(
        json.dumps({"is_genuine_exploit": False, "confidence": 0.8, "reasoning": "computes it correctly"})
    )
    with patch("litellm.completion", return_value=fake):
        result = certify_cross_family_judge(
            task_id="t2",
            candidate="print(6*7)",
            instructions="Compute 6*7",
            judge_model="groq/openai/gpt-oss-120b",
        )

    assert result.is_genuine_exploit is False
    assert result.evidence.passed is True


def test_strips_markdown_fences_around_json():
    fake = _fake_response(
        '```json\n{"is_genuine_exploit": false, "confidence": 0.5, "reasoning": "ok"}\n```'
    )
    with patch("litellm.completion", return_value=fake):
        result = certify_cross_family_judge(
            task_id="t3", candidate="x", instructions="y", judge_model="groq/openai/gpt-oss-120b"
        )

    assert result.is_genuine_exploit is False


def test_unparseable_response_raises_instead_of_silently_scoring():
    fake = _fake_response("I cannot help with that.")
    with patch("litellm.completion", return_value=fake):
        with pytest.raises(ValueError, match="unparseable"):
            certify_cross_family_judge(
                task_id="t4", candidate="x", instructions="y", judge_model="groq/openai/gpt-oss-120b"
            )


def test_string_boolean_from_judge_raises_instead_of_being_coerced():
    # A judge returning the JSON string "false" (not the literal false) must
    # not be silently coerced by bool("false") == True.
    fake = _fake_response(
        json.dumps({"is_genuine_exploit": "false", "confidence": 0.5, "reasoning": "x"})
    )
    with patch("litellm.completion", return_value=fake):
        with pytest.raises(ValueError, match="unparseable"):
            certify_cross_family_judge(
                task_id="t5", candidate="x", instructions="y", judge_model="groq/openai/gpt-oss-120b"
            )


def test_none_content_raises_a_clean_error_not_an_attributeerror():
    fake = _fake_response(None)
    with patch("litellm.completion", return_value=fake):
        with pytest.raises(ValueError, match="no content"):
            certify_cross_family_judge(
                task_id="t6", candidate="x", instructions="y", judge_model="groq/openai/gpt-oss-120b"
            )
