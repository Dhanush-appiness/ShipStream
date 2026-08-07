import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from organizations.models import Membership
from projects.models import Project

logger=logging.getLogger(__name__)


@database_sync_to_async
def get_authorized_project(user,project_id):
    project=Project.objects.filter(id=project_id).first()
    if project is None:
        return None
    is_member=Membership.objects.filter(
        user=user,
        organization=project.organization,
    ).exists()
    if not is_member:
        return None
    return project


class TaskConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.project_id=self.scope['url_route']['kwargs']['project_id']
        user=self.scope['user']

        if not user.is_authenticated:
            logger.info('WebSocket rejected: unauthenticated')
            await self.close(code=4401)
            return

        project=await get_authorized_project(user,self.project_id)
        if project is None:
            logger.info('WebSocket rejected: user %s not authorized for project %s',user.id,self.project_id)
            await self.close(code=4403)
            return

        self.group_name=f'project_{self.project_id}'
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )
        await self.accept()
        logger.info('WebSocket connected: user %s to project %s',user.id,self.project_id)

    async def disconnect(self,close_code):
        if hasattr(self,'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )
        logger.info('WebSocket disconnected: %s',close_code)

    async def task_updated(self,event):
        logger.info('Sending websocket event: %s',event)
        await self.send(
            text_data=json.dumps(event)
        )
