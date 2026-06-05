from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError  # type: ignore[import-untyped]

class CleanModelSerializer(serializers.ModelSerializer):
    """
    A base ModelSerializer that automatically runs the model's .clean() method
    during validation. This ensures that Django model validation rules are
    enforced and any DjangoValidationErrors are propagated to the DRF API response.
    """
    def validate(self, attrs):
        attrs = super().validate(attrs)

        ModelClass = getattr(self.Meta, "model", None)
        if not ModelClass:
            return attrs

        instance = self.instance or ModelClass()
        for field, value in attrs.items():
            setattr(instance, field, value)

        try:
            instance.clean()
        except DjangoValidationError as e:
            if hasattr(e, 'message_dict'):
                raise serializers.ValidationError(e.message_dict)
            raise serializers.ValidationError(e.messages)

        return attrs
