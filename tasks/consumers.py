import json
from channels.generic.websocket import AsyncWebsocketConsumer

class TaskConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print("✅ WebSocket connected")
        await self.channel_layer.group_add(
            'tasks',
            self.channel_name,
        )
        await self.accept()
    async def disconnect(self, close_code):
        print(f"❌ WebSocket disconnected: {close_code}")
        await self.channel_layer.group_discard(
            'tasks',
            self.channel_name,
        )
    async def task_updated(self, event):
        print("📢 Sending:", event)
        await self.send(
            text_data=json.dumps(event)
        )