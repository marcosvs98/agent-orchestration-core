from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

from fastapi.sse import ServerSentEvent

from domain.conversation.schemas.conversation import ConversationEvent


class SSEWriter:
    def __init__(
        self,
        queue: asyncio.Queue[ConversationEvent | None],
        start_event_id: int = 0,
    ) -> None:
        self._queue = queue
        self._next_event_id = start_event_id

    async def stream(self) -> AsyncGenerator[ServerSentEvent, None]:
        while True:
            item = await self._queue.get()

            if item is None:
                break

            self._next_event_id = self._next_event_id + 1
            yield ServerSentEvent(
                data=item.payload,
                event=item.event_type.value,
                id=str(self._next_event_id),
                retry=5000,
            )
