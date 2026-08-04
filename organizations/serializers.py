from rest_framework import serializers

from .models import Invitation


class OrganizationSerializer(serializers.Serializer):
    name=serializers.CharField(max_length=255)
    slug=serializers.CharField(read_only=True)

class InvitationCreateSerializer(serializers.Serializer):
    email=serializers.EmailField()
    role=serializers.ChoiceField(
        choices=Invitation.RoleChoices.choices
    )

class InvitationAcceptSerializer(serializers.Serializer):
    token=serializers.CharField(max_length=255)

