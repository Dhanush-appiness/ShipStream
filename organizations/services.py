from django.utils.text import slugify
from .models import Organization, Membership
import logging 

logger=logging.getLogger(__name__)

def create_organization(user,validated_data):
    """
    Create a new organization with a generated slug
    and make the creator its ADMIN.
    """

    name=validated_data["name"]
    logger.info(f"Creating organization:{name}")
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
        logger.info(f"Organization created successfully:{name}")
        return organization
    except Exception as e:
        logger.error(f"Organization creation failed:{str(e)}")
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
    