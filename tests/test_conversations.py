from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from i2rsi.conversations import ConversationService


def test_conversations_persist_archive_and_bound_prompt_history(tmp_path: Path) -> None:
    root = tmp_path / "conversations"
    service = ConversationService(root)
    conversation = service.create()
    for index in range(9):
        service.append_exchange(
            conversation.id,
            user_content=f"问题 {index}",
            assistant_content=f"回答 {index}",
            executed_tools=["inspect_model_card"] if index == 0 else [],
            cancelled_tools=[],
            allow_actions=False,
        )

    restored = ConversationService(root).get(conversation.id)
    assert restored.title == "问题 0"
    assert len(restored.messages) == 18
    assert restored.messages[1].executed_tools == ["inspect_model_card"]
    history = service.prompt_history(conversation.id)
    assert len(history) == 16
    assert history[0] == {"role": "user", "content": "问题 1"}
    assert history[-1] == {"role": "assistant", "content": "回答 8"}

    service.update(conversation.id, title="道路实验讨论", archived=True)
    assert service.list() == []
    assert service.list(include_archived=True)[0].title == "道路实验讨论"


def test_agent_chat_api_continues_persisted_conversation(
    client: TestClient,
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    histories: list[list[dict[str, str]]] = []

    def fake_chat(message: str, **kwargs: Any) -> dict[str, Any]:
        histories.append(kwargs["history"])
        return {
            "answer": f"收到：{message}",
            "executed_tools": ["list_interpretation_workflows"],
            "cancelled_tools": [],
            "action_mode": kwargs["allow_actions"],
        }

    monkeypatch.setattr(app.state.agent_bridge, "chat", fake_chat)
    first = client.post("/api/v1/agent/chat", json={"message": "检查道路工作流"})

    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]
    assert histories[0] == []

    second = client.post(
        "/api/v1/agent/chat",
        json={"message": "它现在是什么状态？", "conversation_id": conversation_id},
    )
    assert second.status_code == 200
    assert histories[1] == [
        {"role": "user", "content": "检查道路工作流"},
        {"role": "assistant", "content": "收到：检查道路工作流"},
    ]

    detail = client.get(f"/api/v1/agent/conversations/{conversation_id}").json()
    assert detail["title"] == "检查道路工作流"
    assert [message["role"] for message in detail["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    summaries = client.get("/api/v1/agent/conversations").json()
    assert summaries[0]["message_count"] == 4
    assert summaries[0]["preview"] == "收到：它现在是什么状态？"

    archived = client.patch(
        f"/api/v1/agent/conversations/{conversation_id}",
        json={"archived": True},
    )
    assert archived.status_code == 200
    assert client.get("/api/v1/agent/conversations").json() == []
    continued = client.post(
        "/api/v1/agent/chat",
        json={"message": "继续", "conversation_id": conversation_id},
    )
    assert continued.status_code == 409

