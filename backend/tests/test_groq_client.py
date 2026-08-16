import json

import respx
from httpx import Response

from research_agent.config import Settings
from research_agent.groq_client import GroqClient
from research_agent.quota import QuotaManager


@respx.mock
def test_browser_agent_receives_only_web_search_and_exact_domains(session) -> None:  # type: ignore[no-untyped-def]
    captured: dict = {}

    def handler(request):  # type: ignore[no-untyped-def]
        captured.update(json.loads(request.content))
        return Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "A cited research draft",
                            "executed_tools": [
                                {
                                    "search_results": {
                                        "results": [
                                            {
                                                "title": "Research",
                                                "url": "https://www.nature.com/articles/example",
                                                "content": "snippet",
                                                "score": 0.9,
                                            }
                                        ]
                                    }
                                }
                            ],
                        }
                    }
                ],
                "usage": {"total_tokens": 3000},
            },
        )

    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(side_effect=handler)
    settings = Settings(groq_api_key="test", database_url="sqlite://")
    client = GroqClient(settings, QuotaManager(settings))

    result = client.research(
        session,
        "What changed?",
        ["science"],
        ["Existing confirmed fact"],
        [["www.nature.com"]],
    )

    assert captured["search_settings"] == {"include_domains": ["www.nature.com"]}
    assert captured["compound_custom"] == {"tools": {"enabled_tools": ["web_search"]}}
    assert "citation_options" not in captured
    assert "tools" not in captured or captured["compound_custom"]["tools"]["enabled_tools"] == [
        "web_search"
    ]
    assert result.report_text == "A cited research draft"


def test_prompt_guard_labels_fail_closed(session, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    settings = Settings(groq_api_key="test", database_url="sqlite://")
    client = GroqClient(settings, QuotaManager(settings))

    monkeypatch.setattr(
        client,
        "_post",
        lambda *args, **kwargs: {"choices": [{"message": {"content": "LABEL_0"}}]},
    )
    assert client.scan_prompt_injection(session, "ordinary research text") is False

    monkeypatch.setattr(
        client,
        "_post",
        lambda *args, **kwargs: {"choices": [{"message": {"content": "LABEL_1"}}]},
    )
    assert client.scan_prompt_injection(session, "hidden instructions") is True
