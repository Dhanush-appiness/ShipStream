from datetime import timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from .models import Invitation, Membership, Organization
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
def test_admin_can_create_invitation(
    api_client,
    owner,
    organization,
):
    from organizations.models import Membership

    admin = User.objects.create_user(
        email='admin@example.com',
        password='testpass123',
    )
    Membership.objects.create(
        user=admin,
        organization=organization,
        role=Membership.RoleChoices.ADMIN,
    )

    api_client.force_authenticate(user=admin)
    api_client.credentials(HTTP_X_ORG_ID=str(organization.id))

    response = api_client.post(
        reverse('create-invitation', kwargs={'version': 'v1'}),
        {
            'email': 'admin-invite@example.com',
            'role': Invitation.RoleChoices.MEMBER,
        },
        format='json',
    )

    assert response.status_code == 201


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


@pytest.mark.django_db
def test_create_organization_endpoint(api_client,user):
    api_client.force_authenticate(user=user)

    response=api_client.post(
        reverse('create-organization',kwargs={'version':'v1'}),
        {'name':'Brand New Org'},
        format='json',
    )

    assert response.status_code==201
    assert response.data['slug']=='brand-new-org'
    assert response.data['id']==Organization.objects.get(slug='brand-new-org').id
    assert Membership.objects.filter(
        user=user,
        organization__slug='brand-new-org',
        role=Membership.RoleChoices.OWNER,
    ).exists()


@pytest.mark.django_db
def test_create_organization_endpoint_rejects_missing_name(api_client,user):
    api_client.force_authenticate(user=user)

    response=api_client.post(
        reverse('create-organization',kwargs={'version':'v1'}),
        {},
        format='json',
    )

    assert response.status_code==400


@pytest.mark.django_db
def test_list_organizations_only_returns_users_own_orgs(
    api_client,
    user,
    organization,
    membership,
):
    from organizations.models import Organization

    other_org=Organization.objects.create(name='Other Org',slug='other-org')

    api_client.force_authenticate(user=user)

    response=api_client.get(
        reverse('list-organizations',kwargs={'version':'v1'}),
    )

    assert response.status_code==200
    slugs=[org['slug'] for org in response.data['results']]
    assert organization.slug in slugs
    assert other_org.slug not in slugs


@pytest.mark.django_db
def test_retrieve_organization_endpoint(api_client,user,organization,membership):
    api_client.force_authenticate(user=user)

    response=api_client.get(
        reverse('retrieve-organization',kwargs={'version':'v1','slug':organization.slug}),
    )

    assert response.status_code==200
    assert response.data['slug']==organization.slug


@pytest.mark.django_db
def test_retrieve_organization_404_for_non_member(api_client,user,organization):
    api_client.force_authenticate(user=user)

    response=api_client.get(
        reverse('retrieve-organization',kwargs={'version':'v1','slug':organization.slug}),
    )

    assert response.status_code==404


@pytest.mark.django_db
def test_owner_can_update_organization(api_client,owner,organization,owner_membership):
    api_client.force_authenticate(user=owner)

    response=api_client.put(
        reverse('retrieve-organization',kwargs={'version':'v1','slug':organization.slug}),
        {'name':'Renamed Org'},
        format='json',
    )

    assert response.status_code==200
    organization.refresh_from_db()
    assert organization.name=='Renamed Org'

@pytest.mark.django_db
def test_admin_can_update_organization(
    api_client,
    organization,
):
    admin = User.objects.create_user(
        email='admin@example.com',
        password='testpass123',
    )
    Membership.objects.create(
        user=admin,
        organization=organization,
        role=Membership.RoleChoices.ADMIN,
    )

    api_client.force_authenticate(user=admin)

    response = api_client.put(
        reverse(
            'retrieve-organization',
            kwargs={'version': 'v1', 'slug': organization.slug},
        ),
        {'name': 'Admin Renamed Org'},
        format='json',
    )

    assert response.status_code == 200

    organization.refresh_from_db()
    assert organization.name == 'Admin Renamed Org'


@pytest.mark.django_db
def test_member_cannot_update_organization(api_client,user,organization,membership):
    api_client.force_authenticate(user=user)

    response=api_client.put(
        reverse('retrieve-organization',kwargs={'version':'v1','slug':organization.slug}),
        {'name':'Renamed Org'},
        format='json',
    )

    assert response.status_code==403


@pytest.mark.django_db
def test_owner_can_delete_organization(api_client,owner,organization,owner_membership):
    api_client.force_authenticate(user=owner)

    response=api_client.delete(
        reverse('retrieve-organization',kwargs={'version':'v1','slug':organization.slug}),
    )

    assert response.status_code==200

@pytest.mark.django_db
def test_admin_cannot_delete_organization(
    api_client,
    organization,
):
    admin = User.objects.create_user(
        email='admin@example.com',
        password='testpass123',
    )
    Membership.objects.create(
        user=admin,
        organization=organization,
        role=Membership.RoleChoices.ADMIN,
    )

    api_client.force_authenticate(user=admin)

    response = api_client.delete(
        reverse(
            'retrieve-organization',
            kwargs={'version': 'v1', 'slug': organization.slug},
        ),
    )

    assert response.status_code == 403
    assert Organization.objects.filter(id=organization.id).exists()


@pytest.mark.django_db
def test_member_cannot_delete_organization(api_client,user,organization,membership):
    api_client.force_authenticate(user=user)

    response=api_client.delete(
        reverse('retrieve-organization',kwargs={'version':'v1','slug':organization.slug}),
    )

    assert response.status_code==403


@pytest.mark.django_db
def test_current_tenant_returns_active_organization(authenticated_client,organization):
    response=authenticated_client.get(
        reverse('current-tenant',kwargs={'version':'v1'}),
    )

    assert response.status_code==200
    assert response.data['organization_id']==organization.id


@pytest.mark.django_db
def test_current_tenant_returns_none_without_org_header(api_client,user):
    api_client.force_authenticate(user=user)

    response=api_client.get(
        reverse('current-tenant',kwargs={'version':'v1'}),
    )

    assert response.status_code==200
    assert response.data['organization'] is None
