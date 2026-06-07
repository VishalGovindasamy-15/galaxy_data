"""Message bus — async event bus for inter-agent communication."""
import asyncio
import logging
from collections import defaultdict
from galaxy.types import AgentMessage

log = logging.getLogger("galaxy.agents")


class MessageBus:
    """Simple async message bus using asyncio.Queue per topic."""
    
    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._subscribers: dict[str, list[callable]] = defaultdict(list)
    
    async def publish(self, topic: str, message: AgentMessage):
        """Publish message to a topic."""
        await self._queues[topic].put(message)
        for callback in self._subscribers.get(topic, []):
            try:
                await callback(message)
            except Exception as e:
                log.error(f"Subscriber error on {topic}: {e}")
    
    def subscribe(self, topic: str, callback: callable):
        """Subscribe to a topic."""
        self._subscribers[topic].append(callback)
    
    async def consume(self, topic: str, timeout: float = 5.0) -> AgentMessage | None:
        """Consume one message from topic."""
        try:
            return await asyncio.wait_for(self._queues[topic].get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
    
    def publish_sync(self, topic: str, message: AgentMessage):
        """Synchronous publish (for non-async code)."""
        self._queues[topic].put_nowait(message)
    
    def consume_sync(self, topic: str) -> AgentMessage | None:
        """Synchronous consume."""
        try:
            return self._queues[topic].get_nowait()
        except asyncio.QueueEmpty:
            return None
