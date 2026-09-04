from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .models import (
    AgentConversation,
    AgentConversationSummary,
    AgentMessage,
    AgentMessageRole,
)


class ConversationNotFoundError(KeyError):
    pass


class ConversationService:
    """Persist GeoAgent conversations and prepare bounded prompt memory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conversations: dict[str, AgentConversation] = {}
        self._load_existing()

    def create(self, title: str = "新对话") -> AgentConversation:
        now = datetime.now(UTC)
        conversation = AgentConversation(
            id=uuid.uuid4().hex,
            title=self._normalise_title(title),
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._conversations[conversation.id] = conversation
            self._persist(conversation)
        return conversation.model_copy(deep=True)

    def get(self, conversation_id: str) -> AgentConversation:
        with self._lock:
            conversation = self._conversations.get(conversation_id)
            if conversation is None:
                raise ConversationNotFoundError(conversation_id)
            return conversation.model_copy(deep=True)

    def list(
        self,
        *,
        limit: int = 50,
        include_archived: bool = False,
    ) -> list[AgentConversationSummary]:
        with self._lock:
            conversations = sorted(
                self._conversations.values(),
                key=lambda item: item.updated_at,
                reverse=True,
            )
            if not include_archived:
                conversations = [item for item in conversations if not item.archived]
            return [self._summary(item) for item in conversations[:limit]]

    def update(
        self,
        conversation_id: str,
        *,
        title: str | None = None,
        archived: bool | None = None,
    ) -> AgentConversation:
        with self._lock:
            conversation = self._mutable(conversation_id)
            if title is not None:
                conversation.title = self._normalise_title(title)
            if archived is not None:
                conversation.archived = archived
            conversation.updated_at = datetime.now(UTC)
            self._persist(conversation)
            return conversation.model_copy(deep=True)

    def append_exchange(
        self,
        conversation_id: str,
        *,
        user_content: str,
        assistant_content: str,
        executed_tools: list[str],
        cancelled_tools: list[str],
        allow_actions: bool,
    ) -> AgentConversation:
        with self._lock:
            conversation = self._mutable(conversation_id)
            now = datetime.now(UTC)
            conversation.messages.extend(
                [
                    AgentMessage(
                        id=uuid.uuid4().hex,
                        role=AgentMessageRole.USER,
                        content=user_content.strip(),
                        created_at=now,
                        allow_actions=allow_actions,
                    ),
                    AgentMessage(
                        id=uuid.uuid4().hex,
                        role=AgentMessageRole.ASSISTANT,
                        content=assistant_content.strip(),
                        created_at=now,
                        executed_tools=executed_tools,
                        cancelled_tools=cancelled_tools,
                    ),
                ]
            )
            if conversation.title == "新对话":
                conversation.title = self._title_from_message(user_content)
            conversation.updated_at = now
            self._persist(conversation)
            return conversation.model_copy(deep=True)

    def prompt_history(
        self,
        conversation_id: str,
        *,
        max_messages: int = 16,
        max_characters: int = 12_000,
    ) -> list[dict[str, str]]:
        conversation = self.get(conversation_id)
        selected: list[AgentMessage] = []
        characters = 0
        for message in reversed(conversation.messages[-max_messages:]):
            length = len(message.content)
            if selected and characters + length > max_characters:
                break
            selected.append(message)
            characters += length
        return [
            {"role": message.role.value, "content": message.content}
            for message in reversed(selected)
        ]

    def _mutable(self, conversation_id: str) -> AgentConversation:
        conversation = self._conversations.get(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        return conversation

    def _summary(self, conversation: AgentConversation) -> AgentConversationSummary:
        preview = conversation.messages[-1].content if conversation.messages else ""
        return AgentConversationSummary(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            archived=conversation.archived,
            message_count=len(conversation.messages),
            preview=" ".join(preview.split())[:100],
        )

    @staticmethod
    def _normalise_title(title: str) -> str:
        value = " ".join(title.split())[:80]
        return value or "新对话"

    @classmethod
    def _title_from_message(cls, message: str) -> str:
        value = cls._normalise_title(message)
        return f"{value[:36]}…" if len(value) > 36 else value

    def _persist(self, conversation: AgentConversation) -> None:
        target = self.root / f"{conversation.id}.json"
        temporary = self.root / f".{conversation.id}.tmp"
        temporary.write_text(
            json.dumps(conversation.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)

    def _load_existing(self) -> None:
        for path in self.root.glob("*.json"):
            try:
                conversation = AgentConversation.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
            except (OSError, ValueError):
                continue
            self._conversations[conversation.id] = conversation
