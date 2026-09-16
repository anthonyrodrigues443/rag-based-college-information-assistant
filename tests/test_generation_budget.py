"""The rewrite and answer must share the configured generator wait budget."""
import pytest

from app import config, generate


@pytest.mark.parametrize("rewrite_elapsed,expected_calls", [(2.0, 2), (5.0, 1)])
def test_followup_does_not_receive_two_full_timeouts(monkeypatch, rewrite_elapsed, expected_calls):
    clock = [0.0]
    calls = []
    monkeypatch.setattr(config, "GEN_TIMEOUT", 5.0)
    monkeypatch.setattr(config, "USE_RERANKER", False)
    monkeypatch.setattr(generate.time, "perf_counter", lambda: clock[0])
    monkeypatch.setattr(generate.llm, "provider", lambda: "ollama")
    monkeypatch.setattr(generate.retrieve, "search", lambda question: ([{
        "title": "Fees", "text": "Fees\nM.E. tuition fee is Rs. 96,000 per year.",
        "doc_id": "fee-source", "entity": 1,
    }], {}))

    def complete(messages, **kwargs):
        calls.append(kwargs["timeout"])
        if len(calls) == 1:
            clock[0] += rewrite_elapsed
            if rewrite_elapsed >= 5:
                raise generate.llm.Timeout("rewrite stalled")
            return "How much does one year of ME cost?"
        clock[0] += kwargs["timeout"]
        raise generate.llm.Timeout("answer stalled")

    monkeypatch.setattr(generate.llm, "complete", complete)
    result = generate.answer("and the annual fee?", [
        {"role": "user", "content": "Tell me about the ME programme"},
    ])
    assert len(calls) == expected_calls
    assert clock[0] <= config.GEN_TIMEOUT
    assert result["degraded"]["reason"] == "timeout"
    assert "96,000" in result["answer"]
    assert result["citations"][0]["doc_id"] == "fee-source"
