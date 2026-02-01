# app/services/mqtt/base.py
import asyncio
from typing import Optional
from aiomqtt import Client, MqttError
from app.core.logging import get_logger
from app.services.mqtt import config

logger = get_logger(__name__)

class MqttServiceBase:
    def __init__(self, identifier: str):
        self.identifier = identifier
        self.client: Optional[Client] = None
        self.is_running = False

    async def start(self) -> bool:
        self.is_running = True
        asyncio.create_task(self._loop(), name=f"{self.identifier}-loop")
        return True

    async def stop(self) -> None:
        self.is_running = False
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass

    async def _loop(self):
        while self.is_running:
            try:
                async with Client(
                    hostname=config.host(),
                    port=config.port(),
                    identifier=self.identifier,
                ) as client:
                    self.client = client
                    await self.on_connect(client)
                    async for message in client.messages:
                        await self.on_message(message)
            except (MqttError, Exception) as e:
                logger.error(f"{self.identifier} error: {e}")
            finally:
                self.client = None
            if self.is_running:
                await asyncio.sleep(5)

    # To be overridden
    async def on_connect(self, client: Client): ...
    async def on_message(self, message): ...
