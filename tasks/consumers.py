import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger=logging.getLogger(__name__)

class TaskConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        logger.info("WebSocket connected")
        await self.channel_layer.group_add(
            'tasks',
            self.channel_name,
        )
        await self.accept()
    async def disconnect(self, close_code):
        logger.info("WebSocket disconnected: %s", close_code)
        await self.channel_layer.group_discard(
            'tasks',
            self.channel_name,
        )
    async def task_updated(self, event):
        logger.info("Sending websocket event: %s", event)
        await self.send(
            text_data=json.dumps(event)
        )
