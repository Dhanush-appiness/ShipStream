import logging
import secrets
from datetime import timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify

from .models import Invitation, Membership, Organization
from .tasks import send_invitation_email

logger=logging.getLogger(__name__)

def create_organization(user,validated_data):
    """
    Create a new organization with a generated slug
    and make the creator its ADMIN.
    """

    name=validated_data["name"]
    try:
        organization=Organization.objects.create(
            name=name,
            slug=slugify(name),
        )
        Membership.objects.create(
            user=user,
            organization=organization,
            role=Membership.RoleChoices.ADMIN,
        )
        logger.info(f'Organization created successfully:{name}')
        return organization
    except Exception as e:
        logger.error(f'Organization creation failed:{str(e)}')
        raise

def list_organizations(user):
    """
    Retrieve organizations the user belongs to
    """

    logger.info(f'Retrieving organizations for user: {user.email}')
    return Organization.objects.filter(
        membership__user=user,
        is_active=True,
    ).distinct()

def get_organization(slug,user):
    """
    Retrieve organization the user belongs to
    """

    return get_object_or_404(
        Organization,
        slug=slug,
        membership__user=user,
        is_active=True,
    )

def update_organization(organization,validated_data):
    """
    Update organization
    """

    try:
        organization.name=validated_data['name']
        organization.slug=slugify(validated_data['name'])
        organization.save()
        logger.info(f'Successfully updated organization: {organization.slug}')
        return organization
    except Exception as e:
        logger.error(f'Failed to update organization: {organization.slug}: {str(e)}')
        raise

def delete_organization(organization):
    """
    Delete organization
    """

    try:
        organization.delete()
        logger.info(f'Successfully deleted organization: {organization.slug}')
    except Exception as e:
        logger.error(f'Failed to delete organization: {organization.slug}: {str(e)}')
        raise


def create_invitation(user,organization,validated_data):
    """
    Create a pending invitation for an email to join the organization, then
    schedule the invitation email on Celery once the enclosing transaction
    commits (so we never email someone about a row that got rolled back).
    Rejects the email if it already belongs to a member, or already has a
    pending invitation, to avoid duplicate invites.
    """
    logger.info(
        f'Creating invitation for {validated_data["email"]} to organization: {organization.slug}'
    )
    try:
        if Membership.objects.filter(
            user__email=validated_data['email'],
            organization=organization,
        ).exists():
            raise ValueError('User is already a member of the organization')
        if Invitation.objects.filter(
            email=validated_data['email'],
            organization=organization,
            status=Invitation.StatusChoices.PENDING,
        ).exists():
            raise ValueError('A pending invite already exists for this email')
        token=secrets.token_urlsafe(32)
        expires_at=timezone.now()+timedelta(hours=24)
        invitation=Invitation.objects.create(
            organization=organization,
            invited_by=user,
            email=validated_data['email'],
            role=validated_data['role'],
            token=token,
            expires_at=expires_at,
        )
        transaction.on_commit(
        lambda:send_invitation_email.delay(invitation.id)
        )
        logger.info(f'Invitation created for {validated_data["email"]}')
        return invitation
    except Exception as e:
        logger.error(f'Failed to create invitation for {validated_data["email"]}: {str(e)}')
        raise

@transaction.atomic
def accept_invitation(user,validated_data):
    """
    Accept a pending invitation by token, creating (or reusing) the
    corresponding Membership. Rejects tokens that are unknown, already
    used, expired (marking the invitation EXPIRED as a side effect), or
    addressed to a different email than the accepting user's.
    """
    try:
        token=validated_data['token']
        invitation=Invitation.objects.filter(
            token=token
        ).first()
        if invitation is None:
            raise ValueError('Invalid invitation token')
        if invitation.status!=Invitation.StatusChoices.PENDING:
            raise ValueError('Invitation no longer valid')
        if invitation.expires_at<=timezone.now():
            invitation.status=Invitation.StatusChoices.EXPIRED
            invitation.save(update_fields=['status'])
            raise ValueError('Invitation has expired')
        if invitation.email.lower()!=user.email.lower():
            raise ValueError('This invitation belongs to another user')
        membership,created=Membership.objects.get_or_create(
            user=user,
            organization=invitation.organization,
            defaults={
                'role':invitation.role,
            },
        )
        invitation.status=Invitation.StatusChoices.ACCEPTED
        invitation.save(update_fields=['status'])
        logger.info(f'Invitation accepted by {user.email}')
        return membership
    except Exception as e:
        logger.error(f'Failed to accept invitation: {str(e)}')
        raise


def user_can_manage_organization(user,organization):
    """Return True if the user is an OWNER or ADMIN of the organization."""
    return Membership.objects.filter(
        user=user,
        organization=organization,
        role__in=[
            Membership.RoleChoices.OWNER,
            Membership.RoleChoices.ADMIN,
        ],
    ).exists()
