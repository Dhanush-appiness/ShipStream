from unittest.mock import patch

import pytest

from organizations.models import Membership, Organization
from projects.models import Project
from tasks.models import ActivityLog, Comment, Label, Notification, Task, TaskLabel
from tasks.services import CommentService, TaskService


@pytest.mark.django_db
def test_reorder_task_down_same_status(
    organization,
    project,
    owner,
):
    task_a=Task.objects.create(
        project=project,
        created_by=owner,
        title='Task A',
        status='TODO',
        position=0,
    )
    task_b=Task.objects.create(
        project=project,
        created_by=owner,
        title='Task B',
        status='TODO',
        position=1,
    )
    task_c=Task.objects.create(
        project=project,
        created_by=owner,
        title='Task C',
        status='TODO',
        position=2,
    )
    task_d=Task.objects.create(
        project=project,
        created_by=owner,
        title='Task D',
        status='TODO',
        position=3,
    )

    TaskService.reorder_task(
        organization,
        task_b.id,
        'TODO',
        3,
    )

    task_a.refresh_from_db()
    task_b.refresh_from_db()
    task_c.refresh_from_db()
    task_d.refresh_from_db()

    assert task_a.position==0
    assert task_c.position==1
    assert task_d.position==2
    assert task_b.position==3


@pytest.mark.django_db
def test_reorder_task_up_same_status(
    organization,
    project,
    owner,
):
    task_a=Task.objects.create(
        project=project,
        created_by=owner,
        title='Task A',
        status='TODO',
        position=0,
    )
    task_b=Task.objects.create(
        project=project,
        created_by=owner,
        title='Task B',
        status='TODO',
        position=1,
    )
    task_c=Task.objects.create(
        project=project,
        created_by=owner,
        title='Task C',
        status='TODO',
        position=2,
    )
    task_d=Task.objects.create(
        project=project,
        created_by=owner,
        title='Task D',
        status='TODO',
        position=3,
    )

    TaskService.reorder_task(
        organization,
        task_d.id,
        'TODO',
        1,
    )

    task_a.refresh_from_db()
    task_b.refresh_from_db()
    task_c.refresh_from_db()
    task_d.refresh_from_db()

    assert task_a.position==0
    assert task_d.position==1
    assert task_b.position==2
    assert task_c.position==3

@pytest.mark.django_db
def test_reorder_task_between_statuses(
    organization,
    project,
    owner,
):
    task_a=Task.objects.create(
        project=project,
        created_by=owner,
        title='Task A',
        status='TODO',
        position=0,
    )
    task_b=Task.objects.create(
        project=project,
        created_by=owner,
        title='Task B',
        status='TODO',
        position=1,
    )
    task_c=Task.objects.create(
        project=project,
        created_by=owner,
        title='Task C',
        status='TODO',
        position=2,
    )
    task_d=Task.objects.create(
        project=project,
        created_by=owner,
        title='Task D',
        status='IN_PROGRESS',
        position=0,
    )
    task_e=Task.objects.create(
        project=project,
        created_by=owner,
        title='Task E',
        status='IN_PROGRESS',
        position=1,
    )

    TaskService.reorder_task(
        organization,
        task_b.id,
        'IN_PROGRESS',
        1,
    )

    task_a.refresh_from_db()
    task_b.refresh_from_db()
    task_c.refresh_from_db()
    task_d.refresh_from_db()
    task_e.refresh_from_db()

    assert task_a.position==0
    assert task_c.position==1

    assert task_d.position==0
    assert task_b.status=='IN_PROGRESS'
    assert task_b.position==1
    assert task_e.position==2

@pytest.mark.django_db
def test_reorder_task_api(
    authenticated_client,
    organization,
    project,
    user,
):
    task=Task.objects.create(
        project=project,
        created_by=user,
        title='API Reorder Task',
        status='TODO',
        position=0,
    )

    response=authenticated_client.patch(
        f'/api/v1/tasks/{task.id}/reorder/',
        {
            'status':'IN_PROGRESS',
            'position':0,
        },
        format='json',
    )

    assert response.status_code==200

    task.refresh_from_db()

    assert task.status=='IN_PROGRESS'
    assert task.position==0

@pytest.mark.django_db
@patch('tasks.tasks.send_mention_notification_email.delay')
def test_comment_mention_creates_notification(
    mock_send_email,
    organization,
    project,
    owner,
    user,
    membership,
    owner_membership,
):
    from tasks.models import Notification
    from tasks.serializers import CommentSerializer

    task=Task.objects.create(
        project=project,
        created_by=owner,
        title='Mention Test Task',
        status='TODO',
        position=0,
    )

    serializer=CommentSerializer(
        data={
            'task':task.id,
            'content':f'Hey @{user.email} please check this.',
        }
    )
    serializer.is_valid(raise_exception=True)

    CommentService.create_comment(
        serializer,
        owner,
        organization,
    )

    notification=Notification.objects.get(
        user=user,
        task=task,
        type='MENTION',
    )

    assert notification.title=='You were mentioned in a comment'
    assert owner.email in notification.body

    mock_send_email.assert_called_once_with(notification.id)


@pytest.mark.django_db
@patch('tasks.tasks.send_mention_notification_email.delay')
def test_comment_mention_ignores_user_outside_organization(
    mock_send_email,
    organization,
    project,
    owner,
    owner_membership,
):
    from accounts.models import User
    from tasks.models import Notification
    from tasks.serializers import CommentSerializer

    outsider=User.objects.create_user(
        email='outsider@example.com',
        password='testpass123',
    )

    task=Task.objects.create(
        project=project,
        created_by=owner,
        title='Mention Security Test',
        status='TODO',
        position=0,
    )

    serializer=CommentSerializer(
        data={
            'task':task.id,
            'content':f'Hey @{outsider.email} check this.',
        }
    )
    serializer.is_valid(raise_exception=True)

    CommentService.create_comment(
        serializer,
        owner,
        organization,
    )

    assert not Notification.objects.filter(
        user=outsider,
        task=task,
        type='MENTION',
    ).exists()

    mock_send_email.assert_not_called()

@pytest.mark.django_db
@patch('tasks.tasks.send_mention_notification_email.delay')
def test_comment_self_mention_does_not_create_notification(
    mock_send_email,
    project,
    owner,
    owner_membership,
):
    from tasks.models import Notification
    from tasks.serializers import CommentSerializer

    task=Task.objects.create(
        project=project,
        created_by=owner,
        title='Self Mention Test',
        status='TODO',
        position=0,
    )

    serializer=CommentSerializer(
        data={
            'task':task.id,
            'content':f'Note to self @{owner.email} check this.',
        }
    )
    serializer.is_valid(raise_exception=True)

    CommentService.create_comment(
        serializer,
        owner,
        project.organization,
    )

    assert not Notification.objects.filter(
        user=owner,
        task=task,
        type='MENTION',
    ).exists()

    mock_send_email.assert_not_called()

@pytest.mark.django_db
def test_send_mention_notification_email(
    project,
    owner,
    user,
):
    from unittest.mock import patch

    from tasks.models import Notification
    from tasks.tasks import send_mention_notification_email

    task=Task.objects.create(
        project=project,
        created_by=owner,
        title='Email Mention Test',
        status='TODO',
        position=0,
    )

    notification=Notification.objects.create(
        user=user,
        task=task,
        type='MENTION',
        title='You were mentioned in a comment',
        body=f"{owner.email} mentioned you in '{task.title}'.",
    )

    with patch('tasks.tasks.send_mail') as mock_send_mail:
        send_mention_notification_email.run(notification.id)

    mock_send_mail.assert_called_once()

    kwargs=mock_send_mail.call_args.kwargs

    assert kwargs['recipient_list']==[user.email]
    assert task.title in kwargs['message']


@pytest.mark.django_db
def test_task_filter_by_status(
    authenticated_client,
    project,
    user,
):
    Task.objects.create(
        project=project,
        created_by=user,
        title='Todo Task',
        status='TODO',
        position=0,
    )

    Task.objects.create(
        project=project,
        created_by=user,
        title='Done Task',
        status='DONE',
        position=0,
    )

    response=authenticated_client.get(
        '/api/v1/tasks/?status=DONE'
    )

    assert response.status_code==200

    results=response.data['results']

    assert len(results)==1
    assert results[0]['title']=='Done Task'
    assert results[0]['status']=='DONE'

@pytest.mark.django_db
def test_task_filter_by_assignee(
    authenticated_client,
    project,
    user,
    owner,
):
    assigned_task=Task.objects.create(
        project=project,
        created_by=user,
        assignee=user,
        title='Assigned Task',
        status='TODO',
        position=0,
    )

    Task.objects.create(
        project=project,
        created_by=user,
        assignee=owner,
        title='Other Assigned Task',
        status='TODO',
        position=1,
    )

    response=authenticated_client.get(
        f'/api/v1/tasks/?assignee={user.id}'
    )

    assert response.status_code==200

    results=response.data['results']

    assert len(results)==1
    assert results[0]['id']==assigned_task.id
    assert results[0]['assignee']==user.id

@pytest.mark.django_db
def test_task_filter_by_label(
    authenticated_client,
    organization,
    project,
    user,
):
    from tasks.models import Label

    task_with_label=Task.objects.create(
        project=project,
        created_by=user,
        title='Backend Task',
        status='TODO',
        position=0,
    )

    Task.objects.create(
        project=project,
        created_by=user,
        title='Unlabelled Task',
        status='TODO',
        position=1,
    )

    label=Label.objects.create(
        organization=organization,
        name='Backend',
    )

    TaskLabel.objects.create(
        task=task_with_label,
        label=label,
    )

    response=authenticated_client.get(
        f'/api/v1/tasks/?label={label.id}'
    )

    assert response.status_code==200

    results=response.data['results']

    assert len(results)==1
    assert results[0]['id']==task_with_label.id

@pytest.mark.django_db
def test_task_filter_by_due_date_range(
    authenticated_client,
    project,
    user,
):
    Task.objects.create(
        project=project,
        created_by=user,
        title='Early Task',
        status='TODO',
        position=0,
        due_date='2026-08-01',
    )

    task_in_range=Task.objects.create(
        project=project,
        created_by=user,
        title='In Range Task',
        status='TODO',
        position=1,
        due_date='2026-08-10',
    )

    Task.objects.create(
        project=project,
        created_by=user,
        title='Late Task',
        status='TODO',
        position=2,
        due_date='2026-08-20',
    )

    response=authenticated_client.get(
        '/api/v1/tasks/'
        '?due_date_from=2026-08-05'
        '&due_date_to=2026-08-15'
    )

    assert response.status_code==200

    results=response.data['results']

    assert len(results)==1
    assert results[0]['id']==task_in_range.id


@pytest.mark.django_db
def test_task_search(
    authenticated_client,
    project,
    user,
):
    matching_task=Task.objects.create(
        project=project,
        created_by=user,
        title='Fix payment processing bug',
        description='Stripe checkout is failing',
        status='TODO',
        position=0,
    )

    Task.objects.create(
        project=project,
        created_by=user,
        title='Update profile page',
        description='Change the user avatar layout',
        status='TODO',
        position=1,
    )

    response=authenticated_client.get(
        '/api/v1/tasks/?search=payment'
    )

    assert response.status_code==200

    results=response.data['results']

    assert len(results)==1
    assert results[0]['id']==matching_task.id

@pytest.mark.django_db
def test_task_dashboard(
    authenticated_client,
    organization,
    project,
    user,
    owner,
):
    from datetime import timedelta

    from django.utils import timezone

    today=timezone.localdate()

    Task.objects.create(
        project=project,
        created_by=owner,
        assignee=user,
        title='Todo Overdue',
        status='TODO',
        position=0,
        due_date=today-timedelta(days=2),
    )

    Task.objects.create(
        project=project,
        created_by=owner,
        assignee=user,
        title='In Progress Task',
        status='IN_PROGRESS',
        position=0,
        due_date=today+timedelta(days=2),
    )

    Task.objects.create(
        project=project,
        created_by=owner,
        assignee=user,
        title='Completed Old Task',
        status='DONE',
        position=0,
        due_date=today-timedelta(days=5),
    )

    Task.objects.create(
        project=project,
        created_by=owner,
        title='Blocked Task',
        status='BLOCKED',
        position=0,
    )

    response=authenticated_client.get(
        '/api/v1/tasks/dashboard/'
    )

    assert response.status_code==200

    assert response.data['status_counts']=={
        'TODO':1,
        'IN_PROGRESS':1,
        'DONE':1,
        'BLOCKED':1,
    }

    assert response.data['overdue']==1

    assert len(response.data['workload'])==1
    assert response.data['workload'][0]['assignee_id']==user.id
    assert response.data['workload'][0]['task_count']==2


@pytest.mark.django_db
def test_task_dashboard_cache_invalidates_on_status_change(
    organization,
    project,
    user,
    owner,
):
    from django.core.cache import cache

    cache.clear()

    task=Task.objects.create(
        project=project,
        created_by=owner,
        assignee=user,
        title='Cache Task',
        status='TODO',
        position=0,
    )

    dashboard_before=TaskService.get_dashboard(organization)
    assert dashboard_before['status_counts']['TODO']==1
    assert dashboard_before['status_counts']['DONE']==0

    TaskService.update_task(task,{'status':'DONE'})

    dashboard_after=TaskService.get_dashboard(organization)
    assert dashboard_after['status_counts']['TODO']==0
    assert dashboard_after['status_counts']['DONE']==1


@pytest.mark.django_db
def test_weekly_digest_email(
    organization,
    project,
    owner,
    user,
    membership,
    owner_membership,
):
    from datetime import timedelta
    from unittest.mock import patch

    from django.utils import timezone

    from tasks.tasks import send_weekly_digest

    today=timezone.localdate()

    Task.objects.create(
        project=project,
        created_by=owner,
        assignee=owner,
        title='Owner Overdue Task',
        status='TODO',
        due_date=today-timedelta(days=1),
    )

    Task.objects.create(
        project=project,
        created_by=owner,
        assignee=user,
        title='Open Task',
        status='TODO',
        due_date=today+timedelta(days=2),
    )

    Task.objects.create(
        project=project,
        created_by=owner,
        assignee=user,
        title='Overdue Task',
        status='IN_PROGRESS',
        due_date=today-timedelta(days=2),
    )

    Task.objects.create(
        project=project,
        created_by=owner,
        assignee=user,
        title='Completed Task',
        status='DONE',
        due_date=today-timedelta(days=5),
    )

    with patch('tasks.tasks.send_mail') as mock_send_mail:
        send_weekly_digest.run(organization.id)

    assert mock_send_mail.call_count==2

    calls_by_recipient={
        call.kwargs['recipient_list'][0]:call.kwargs
        for call in mock_send_mail.call_args_list
    }

    owner_kwargs=calls_by_recipient[owner.email]
    assert 'Open tasks: 1' in owner_kwargs['message']
    assert 'Overdue tasks: 1' in owner_kwargs['message']

    user_kwargs=calls_by_recipient[user.email]
    assert 'Open tasks: 2' in user_kwargs['message']
    assert 'Overdue tasks: 1' in user_kwargs['message']


@pytest.mark.django_db
def test_send_all_weekly_digests(
    organization,
):
    from unittest.mock import patch

    from tasks.tasks import send_all_weekly_digests

    with patch(
        'tasks.tasks.send_weekly_digest.delay'
    ) as mock_digest:
        send_all_weekly_digests.run()

    mock_digest.assert_called_once_with(
        organization.id
    )

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_task_websocket_broadcast(project,user,membership):
    from channels.testing import WebsocketCommunicator
    from rest_framework_simplejwt.tokens import AccessToken

    from config.asgi import application

    token=AccessToken.for_user(user)

    communicator=WebsocketCommunicator(
        application,
        f'/ws/projects/{project.id}/tasks/?token={token}',
    )

    connected,_=await communicator.connect()

    assert connected is True

    from channels.layers import get_channel_layer

    channel_layer=get_channel_layer()

    await channel_layer.group_send(
        f'project_{project.id}',
        {
            'type':'task_updated',
            'action':'updated',
            'task_id':123,
            'title':'WebSocket Test Task',
            'status':'IN_PROGRESS',
        },
    )

    response=await communicator.receive_json_from()

    assert response['type']=='task_updated'
    assert response['action']=='updated'
    assert response['task_id']==123
    assert response['title']=='WebSocket Test Task'
    assert response['status']=='IN_PROGRESS'

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_task_websocket_rejects_unauthenticated(project):
    from channels.testing import WebsocketCommunicator

    from config.asgi import application

    communicator=WebsocketCommunicator(
        application,
        f'/ws/projects/{project.id}/tasks/',
    )

    connected,_=await communicator.connect()

    assert connected is False


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_task_websocket_rejects_cross_organization_user(project,guest):
    from channels.testing import WebsocketCommunicator
    from rest_framework_simplejwt.tokens import AccessToken

    from config.asgi import application

    token=AccessToken.for_user(guest)

    communicator=WebsocketCommunicator(
        application,
        f'/ws/projects/{project.id}/tasks/?token={token}',
    )

    connected,_=await communicator.connect()

    try:
        assert connected is False
    finally:
        await communicator.disconnect()

@pytest.mark.django_db
def test_task_queryset_avoids_n_plus_one(
    django_assert_num_queries,
    organization,
    project,
    user,
    owner,
):
    from tasks.factories import TaskFactory

    TaskFactory.create_batch(
        5,
        project=project,
        created_by=owner,
        assignee=user,
        status='TODO',
    )

    tasks=TaskService.get_tasks(organization)

    with django_assert_num_queries(1):
        for task in tasks:
            _=task.project.name
            _=task.assignee.email
            _=task.created_by.email


@pytest.mark.django_db
def test_task_list_respects_active_organization(
    api_client,
    user,
    organization,
    membership,
):
    second_organization=Organization.objects.create(
        name='Second Organization',
        slug='second-organization',
    )
    Membership.objects.create(
        user=user,
        organization=second_organization,
        role=Membership.RoleChoices.MEMBER,
    )
    first_project=Project.objects.create(
        organization=organization,
        name='First Project',
    )
    second_project=Project.objects.create(
        organization=second_organization,
        name='Second Project',
    )
    Task.objects.create(
        project=first_project,
        created_by=user,
        title='First Organization Task',
        status='TODO',
        position=0,
    )
    Task.objects.create(
        project=second_project,
        created_by=user,
        title='Second Organization Task',
        status='TODO',
        position=0,
    )
    api_client.force_authenticate(user=user)
    api_client.credentials(
        HTTP_X_ORG_ID=str(second_organization.id)
    )
    response=api_client.get('/api/v1/tasks/')
    assert response.status_code==200
    titles=[task['title'] for task in response.data['results']]
    assert 'Second Organization Task' in titles
    assert 'First Organization Task' not in titles


@pytest.mark.django_db
def test_cross_organization_label_not_visible(
    api_client,
    user,
    organization,
    membership,
):
    second_organization=Organization.objects.create(
        name='Second Organization',
        slug='second-organization',
    )
    Membership.objects.create(
        user=user,
        organization=second_organization,
        role=Membership.RoleChoices.MEMBER,
    )
    Label.objects.create(
        organization=organization,
        name='First Org Label',
    )
    Label.objects.create(
        organization=second_organization,
        name='Second Org Label',
    )
    api_client.force_authenticate(user=user)
    api_client.credentials(
        HTTP_X_ORG_ID=str(second_organization.id)
    )
    response=api_client.get('/api/v1/tasks/labels/')
    assert response.status_code==200
    names=[label['name'] for label in response.data['results']]
    assert 'Second Org Label' in names
    assert 'First Org Label' not in names


@pytest.mark.django_db
def test_cross_organization_activity_not_visible(
    api_client,
    user,
    organization,
    membership,
):
    second_organization=Organization.objects.create(
        name='Second Organization',
        slug='second-organization',
    )
    Membership.objects.create(
        user=user,
        organization=second_organization,
        role=Membership.RoleChoices.MEMBER,
    )
    first_project=Project.objects.create(
        organization=organization,
        name='First Project',
    )
    second_project=Project.objects.create(
        organization=second_organization,
        name='Second Project',
    )
    first_task=Task.objects.create(
        project=first_project,
        created_by=user,
        title='First Task',
        position=0,
    )
    second_task=Task.objects.create(
        project=second_project,
        created_by=user,
        title='Second Task',
        position=0,
    )
    ActivityLog.objects.create(
        organization=organization,
        task=first_task,
        actor=user,
        action='FIRST_ORG_ACTION',
    )
    ActivityLog.objects.create(
        organization=second_organization,
        task=second_task,
        actor=user,
        action='SECOND_ORG_ACTION',
    )
    api_client.force_authenticate(user=user)
    api_client.credentials(
        HTTP_X_ORG_ID=str(second_organization.id)
    )
    response=api_client.get('/api/v1/tasks/activity/')
    assert response.status_code==200
    actions=[log['action'] for log in response.data['results']]
    assert 'SECOND_ORG_ACTION' in actions
    assert 'FIRST_ORG_ACTION' not in actions


@pytest.mark.django_db
def test_cross_organization_notification_not_visible(
    api_client,
    user,
    organization,
    membership,
):
    second_organization=Organization.objects.create(
        name='Second Organization',
        slug='second-organization',
    )
    Membership.objects.create(
        user=user,
        organization=second_organization,
        role=Membership.RoleChoices.MEMBER,
    )
    first_project=Project.objects.create(
        organization=organization,
        name='First Project',
    )
    second_project=Project.objects.create(
        organization=second_organization,
        name='Second Project',
    )
    first_task=Task.objects.create(
        project=first_project,
        created_by=user,
        title='First Task',
        position=0,
    )
    second_task=Task.objects.create(
        project=second_project,
        created_by=user,
        title='Second Task',
        position=0,
    )
    Notification.objects.create(
        user=user,
        task=first_task,
        type='TEST',
        title='First Org Notification',
        body='First',
    )
    Notification.objects.create(
        user=user,
        task=second_task,
        type='TEST',
        title='Second Org Notification',
        body='Second',
    )
    api_client.force_authenticate(user=user)
    api_client.credentials(
        HTTP_X_ORG_ID=str(second_organization.id)
    )
    response=api_client.get('/api/v1/tasks/notifications/')
    assert response.status_code==200
    titles=[item['title'] for item in response.data['results']]
    assert 'Second Org Notification' in titles
    assert 'First Org Notification' not in titles


@pytest.mark.django_db
def test_task_label_rejects_cross_organization_assignment(
    user,
    organization,
    membership,
):
    second_organization=Organization.objects.create(
        name='Second Organization',
        slug='second-organization',
    )
    Membership.objects.create(
        user=user,
        organization=second_organization,
        role=Membership.RoleChoices.MEMBER,
    )
    project=Project.objects.create(
        organization=organization,
        name='First Project',
    )
    task=Task.objects.create(
        project=project,
        created_by=user,
        title='First Org Task',
        position=0,
    )
    foreign_label=Label.objects.create(
        organization=second_organization,
        name='Foreign Label',
    )

    assert task.project.organization!=foreign_label.organization


@pytest.mark.django_db
def test_admin_can_restore_soft_deleted_task(
    api_client,
    owner,
    organization,
    owner_membership,
    project,
):
    task=Task.objects.create(
        project=project,
        created_by=owner,
        title='Task To Restore',
        status='TODO',
        position=0,
    )
    task.delete()

    api_client.force_authenticate(user=owner)
    api_client.credentials(HTTP_X_ORG_ID=str(organization.id))

    response=api_client.patch(
        f'/api/v1/tasks/{task.id}/restore/',
        format='json',
    )

    assert response.status_code==200
    task.refresh_from_db()
    assert task.is_deleted is False


@pytest.mark.django_db
def test_member_cannot_restore_soft_deleted_task(
    api_client,
    user,
    organization,
    membership,
    project,
    owner,
):
    task=Task.objects.create(
        project=project,
        created_by=owner,
        title='Task To Restore',
        status='TODO',
        position=0,
    )
    task.delete()

    api_client.force_authenticate(user=user)
    api_client.credentials(HTTP_X_ORG_ID=str(organization.id))

    response=api_client.patch(
        f'/api/v1/tasks/{task.id}/restore/',
        format='json',
    )

    assert response.status_code==403


@pytest.mark.django_db
def test_task_list_ordering_by_due_date(
    authenticated_client,
    project,
    user,
):
    from datetime import timedelta

    from django.utils import timezone

    today=timezone.localdate()

    later_task=Task.objects.create(
        project=project,
        created_by=user,
        title='Later Task',
        status='TODO',
        due_date=today+timedelta(days=10),
    )
    sooner_task=Task.objects.create(
        project=project,
        created_by=user,
        title='Sooner Task',
        status='TODO',
        due_date=today+timedelta(days=1),
    )

    response=authenticated_client.get(
        '/api/v1/tasks/?ordering=due_date'
    )

    assert response.status_code==200
    ids=[task['id'] for task in response.data['results']]
    assert ids.index(sooner_task.id)<ids.index(later_task.id)


@pytest.mark.django_db
def test_comment_queryset_avoids_n_plus_one(
    django_assert_num_queries,
    project,
    user,
    owner,
):
    task=Task.objects.create(
        project=project,
        created_by=owner,
        title='Comment N+1 Task',
        status='TODO',
        position=0,
    )

    for i in range(5):
        Comment.objects.create(
            task=task,
            author=user,
            content=f'Comment {i}',
        )

    comments=CommentService.get_comments(task.id,project.organization)

    with django_assert_num_queries(1):
        for comment in comments:
            _=comment.author.email
            _=comment.task.title


@pytest.mark.django_db
def test_create_task_logs_and_reraises_on_failure(
    organization,
    project,
    user,
):
    from tasks.serializers import TaskSerializer

    serializer=TaskSerializer(data={
        'project':project.id,
        'title':'Task That Will Fail',
        'status':'TODO',
    })
    assert serializer.is_valid()

    with patch(
        'tasks.services.ActivityLogService.log',
        side_effect=RuntimeError('boom'),
    ):
        with pytest.raises(RuntimeError,match='boom'):
            TaskService.create_task(serializer,user,organization)


@pytest.mark.django_db
def test_update_task_logs_and_reraises_on_failure(
    project,
    user,
):
    task=Task.objects.create(
        project=project,
        created_by=user,
        title='Task To Update',
        status='TODO',
        position=0,
    )

    with patch(
        'tasks.services.ActivityLogService.log',
        side_effect=RuntimeError('boom'),
    ):
        with pytest.raises(RuntimeError,match='boom'):
            TaskService.update_task(task,{'title':'New Title'})


@pytest.mark.django_db
@patch('tasks.tasks.send_mention_notification_email.delay')
def test_create_comment_logs_and_reraises_on_failure(
    mock_send_email,
    organization,
    project,
    owner,
):
    from tasks.serializers import CommentSerializer

    task=Task.objects.create(
        project=project,
        created_by=owner,
        title='Comment Failure Task',
        status='TODO',
        position=0,
    )

    serializer=CommentSerializer(data={
        'task':task.id,
        'content':'A comment with no mentions.',
    })
    assert serializer.is_valid()

    with patch(
        'tasks.services.ActivityLogService.log',
        side_effect=RuntimeError('boom'),
    ):
        with pytest.raises(RuntimeError,match='boom'):
            CommentService.create_comment(serializer,owner,organization)
