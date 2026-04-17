from services.chat.nodes.router import route_message


def test_router_prefers_analysis_for_why_questions() -> None:
    state = {"user_message": "Why did our Q1 ads underperform?", "selected_agents": []}
    out = route_message(state)  # type: ignore[arg-type]
    assert out["selected_agents"]
    assert out["selected_agents"][0] == "analysis"


def test_router_direct_for_greeting() -> None:
    state = {"user_message": "hello there", "selected_agents": []}
    out = route_message(state)  # type: ignore[arg-type]
    assert out.get("direct_response")
