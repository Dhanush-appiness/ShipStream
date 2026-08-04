from datetime import timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from .models import Invitation, Membership
from .services import accept_invitation, create_invitation


@pytest.mark.django_db
def test_create_invitation(owner,organization):
    invitation=create_invitation(
        owner,
        organization,
        {
            'email':'newuser@example.com',
            'role':Invitation.RoleChoices.MEMBER,
        },
    )

    assert invitation.organization==organization
    assert invitation.invited_by==owner
    assert invitation.email=='newuser@example.com'
    assert invitation.status==Invitation.StatusChoices.PENDING
    assert invitation.token


@pytest.mark.django_db
def test_cannot_invite_existing_member(owner,organization,membership):
    with pytest.raises(ValueError):
        create_invitation(
            owner,
            organization,
            {
                'email':'member@example.com',
                'role':Invitation.RoleChoices.MEMBER,
            },
        )


@pytest.mark.django_db
def test_cannot_create_duplicate_pending_invitation(owner,organization):
    data={
        'email':'newuser@example.com',
        'role':Invitation.RoleChoices.MEMBER,
    }

    create_invitation(owner,organization,data)

    with pytest.raises(ValueError):
        create_invitation(owner,organization,data)


@pytest.mark.django_db
def test_accept_invitation(owner,organization):
    invited_user=User.objects.create_user(
        email='newuser@example.com',
        password='testpass123',
    )

    invitation=create_invitation(
        owner,
        organization,
        {
            'email':invited_user.email,
            'role':Invitation.RoleChoices.MEMBER,
        },
    )

    membership=accept_invitation(
        invited_user,
        {'token':invitation.token},
    )

    invitation.refresh_from_db()

    assert membership.user==invited_user
    assert membership.organization==organization
    assert membership.role==Membership.RoleChoices.MEMBER
    assert invitation.status==Invitation.StatusChoices.ACCEPTED


@pytest.mark.django_db
def test_wrong_user_cannot_accept_invitation(owner,organization):
    invited_user=User.objects.create_user(
        email='invited@example.com',
        password='testpass123',
    )
    wrong_user=User.objects.create_user(
        email='wrong@example.com',
        password='testpass123',
    )

    invitation=create_invitation(
        owner,
        organization,
        {
            'email':invited_user.email,
            'role':Invitation.RoleChoices.MEMBER,
        },
    )

    with pytest.raises(ValueError):
        accept_invitation(
            wrong_user,
            {'token':invitation.token},
        )

    assert not Membership.objects.filter(
        user=wrong_user,
        organization=organization,
    ).exists()


@pytest.mark.django_db
def test_expired_invitation_cannot_be_accepted(owner,organization):
    invited_user=User.objects.create_user(
        email='expired@example.com',
        password='testpass123',
    )

    invitation=create_invitation(
        owner,
        organization,
        {
            'email':invited_user.email,
            'role':Invitation.RoleChoices.MEMBER,
        },
    )

    invitation.expires_at=timezone.now()-timedelta(hours=1)
    invitation.save(update_fields=['expires_at'])

    with pytest.raises(ValueError):
        accept_invitation(
            invited_user,
            {'token':invitation.token},
        )

    assert not Membership.objects.filter(
        user=invited_user,
        organization=organization,
    ).exists()


@pytest.mark.django_db
def test_accepted_invitation_cannot_be_reused(owner,organization):
    invited_user=User.objects.create_user(
        email='reuse@example.com',
        password='testpass123',
    )

    invitation=create_invitation(
        owner,
        organization,
        {
            'email':invited_user.email,
            'role':Invitation.RoleChoices.MEMBER,
        },
    )

    accept_invitation(
        invited_user,
        {'token':invitation.token},
    )

    with pytest.raises(ValueError):
        accept_invitation(
            invited_user,
            {'token':invitation.token},
        )

@pytest.mark.django_db
@patch('organizations.tasks.send_mail')
def test_send_invitation_email(mock_send_mail,owner,organization):
    from .tasks import send_invitation_email
    invitation=Invitation.objects.create(
        organization=organization,
        invited_by=owner,
        email='invited@example.com',
        role=Invitation.RoleChoices.MEMBER,
        token='test-token',
        expires_at=timezone.now()+timedelta(hours=24),
    )
    send_invitation_email.run(invitation.id)
    mock_send_mail.assert_called_once()
    kwargs=mock_send_mail.call_args.kwargs
    assert kwargs['recipient_list']==['invited@example.com']
    assert 'test-token' in kwargs['message']
    assert organization.name in kwargs['message']

@pytest.mark.django_db
@patch('organizations.tasks.send_mail')
def test_invitation_email_not_sent_when_not_pending(
    mock_send_mail,
    owner,
    organization,
):
    from .tasks import send_invitation_email
    invitation=Invitation.objects.create(
        organization=organization,
        invited_by=owner,
        email='accepted@example.com',
        role=Invitation.RoleChoices.MEMBER,
        token='accepted-token',
        status=Invitation.StatusChoices.ACCEPTED,
        expires_at=timezone.now()+timedelta(hours=24),
    )
    send_invitation_email.run(invitation.id)
    mock_send_mail.assert_not_called()

@pytest.mark.django_db
def test_owner_can_create_invitation(
    api_client,
    owner,
    owner_membership,
    organization,
):
    api_client.force_authenticate(user=owner)
    api_client.credentials(HTTP_X_ORG_ID=str(organization.id))

    response=api_client.post(
        reverse('create-invitation',kwargs={'version':'v1'}),
        {
            'email':'api-invite@example.com',
            'role':Invitation.RoleChoices.MEMBER,
        },
        format='json',
    )

    assert response.status_code==201
    assert Invitation.objects.filter(
        email='api-invite@example.com',
        organization=organization,
    ).exists()


@pytest.mark.django_db
def test_guest_cannot_create_invitation(
    api_client,
    guest,
    guest_membership,
    organization,
):
    api_client.force_authenticate(user=guest)
    api_client.credentials(HTTP_X_ORG_ID=str(organization.id))

    response=api_client.post(
        reverse('create-invitation',kwargs={'version':'v1'}),
        {
            'email':'guest-invite@example.com',
            'role':Invitation.RoleChoices.MEMBER,
        },
        format='json',
    )

    assert response.status_code==403


@pytest.mark.django_db
@patch('organizations.tasks.send_invitation_email.delay')
def test_user_can_accept_invitation(mock_send_email,api_client,owner,organization,):
    invited_user=User.objects.create_user(
        email='api-accept@example.com',
        password='testpass123',
    )

    invitation=create_invitation(
        owner,
        organization,
        {
            'email':invited_user.email,
            'role':Invitation.RoleChoices.MEMBER,
        },
    )

    api_client.force_authenticate(user=invited_user)

    response=api_client.post(
        reverse('accept-invitation',kwargs={'version':'v1'}),
        {'token':invitation.token},
        format='json',
    )

    assert response.status_code==200
    assert Membership.objects.filter(
        user=invited_user,
        organization=organization,
        role=Membership.RoleChoices.MEMBER,
    ).exists()


@pytest.mark.django_db
@patch('organizations.tasks.send_invitation_email.retry')
@patch('organizations.tasks.send_mail')
def test_invitation_email_retries_on_failure(
    mock_send_mail,
    mock_retry,
    owner,
    organization,
):
    from .tasks import send_invitation_email

    invitation=Invitation.objects.create(
        organization=organization,
        invited_by=owner,
        email='retry@example.com',
        role=Invitation.RoleChoices.MEMBER,
        token='retry-token',
        expires_at=timezone.now()+timedelta(hours=24),
    )

    error=Exception('Email server failed')
    mock_send_mail.side_effect=error
    mock_retry.side_effect=RuntimeError('Retry triggered')

    with pytest.raises(RuntimeError,match='Retry triggered'):
        send_invitation_email.run(invitation.id)

    mock_retry.assert_called_once_with(
        exc=error,
        countdown=60,
    )
