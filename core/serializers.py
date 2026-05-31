from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError

class CleanModelSerializer(serializers.ModelSerializer):
    """
    A base ModelSerializer that automatically runs the model's .clean() method
    during validation. This ensures that Django model validation rules are
    enforced and any DjangoValidationErrors are propagated to the DRF API response.
    """
    def validate(self, attrs):
        # Call parent validate
        attrs = super().validate(attrs)
        
        # Instantiate the model in memory to run validation
        ModelClass = self.Meta.model
        instance = ModelClass(**attrs)
        
        # If it's an update, apply the changes to the existing instance
        if self.instance:
            for attr, value in attrs.items():
                setattr(instance, attr, value)
                
        try:
            # Force the model's business logic validation
            instance.clean()
        except DjangoValidationError as e:
            # Convert Django error to DRF format so the frontend can consume it
            if hasattr(e, 'message_dict'):
                raise serializers.ValidationError(e.message_dict)
            raise serializers.ValidationError(e.messages)
            
        return attrs
