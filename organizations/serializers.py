from rest_framework import serializers

class OrganizationSerializer(serializers.Serializer):
    name=serializers.CharField(max_length=255)
    slug=serializers.CharField(read_only=True) 