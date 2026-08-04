import logging
import secrets
from datetime import timedelta

from django.db import transaction
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
    logger.info(f'Creating organization:{name}')
    try:
        organization=Organization.objects.create(
            name=name,
            slug=slugify(name),
        )
        Membership.objects.create(
            user=user,
            organization=organization,
            role="ADMIN",
        )
        logger.info(f'Organization created successfully:{name}')
        return organization
    except Exception as e:
        logger.error(f'Organization creation failed:{str(e)}')
        raise

def list_organizations():
    """
    Retrieve all organizations.
    """

    logger.info('Retrieving all organizations')
    try:
        organizations=Organization.objects.all()
        logger.info('Organizations retrieved successfully.')
        return organizations
    except Exception as e:
        logger.error(f'Failed to retrieve organizations: {str(e)}')
        raise

def get_organization(slug):
    """
    Retrieve an organization using its slug.
    """

    logger.info(f'Retrieving organization with slug: {slug}')
    try:
        organization=Organization.objects.get(slug=slug)
        logger.info(f'Organization retrieved successfully: {slug}')
        return organization
    except Exception as e:
        logger.error(f'Failed to retrieve organization: {slug}: {str(e)}')
        raise

def update_organization(slug,validated_data):
    """
    Update organization
    """

    logger.info(f'Updating organization: {slug}')
    try:
        organization=Organization.objects.get(slug=slug)
        logger.info(f'Successfully retrieved organization: {slug}')
        organization.name=validated_data['name']
        organization.slug=slugify(validated_data['name'])
        organization.save()
        logger.info(f'Successfully updated organization {slug}')
        return organization
    except Exception as e:
        logger.error(f'Failed to update organization: {slug}: {str(e)}')
        raise

def delete_organization(slug):
    """
    Delete organization
    """

    logger.info(f'Deleting organization: {slug}')
    try:
        organization=Organization.objects.get(slug=slug)
        logger.info(f'Retrieved organization: {slug}')
        organization.delete()
        logger.info(f'Deleted organization: {slug}')
    except Exception as e:
        logger.error(f'Failed to delete organization: {slug}: {str(e)}')
        raise


def create_invitation(user,organization,validated_data):
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
    return invitation

@transaction.atomic
def accept_invitation(user,validated_data):
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
    return membership

