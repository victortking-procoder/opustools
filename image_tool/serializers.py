# image_tool/serializers.py

from rest_framework import serializers
from .models import UploadedFile, ImageConversionJob
import os

class UploadedFileSerializer(serializers.ModelSerializer):
    """
    Serializer for the UploadedFile model. Used to represent details of the
    original uploaded image within the ImageConversionJob response.
    """
    # The 'file' field will typically be served by MEDIA_URL in production,
    # so we represent it as a URL.
    file = serializers.FileField(read_only=True)

    class Meta:
        model = UploadedFile
        fields = ['id', 'original_filename', 'file', 'uploaded_at']
        read_only_fields = ['id', 'original_filename', 'file', 'uploaded_at']


class ImageConversionJobSerializer(serializers.ModelSerializer):
    """
    Serializer for the ImageConversionJob model.
    It validates incoming data and maps it to the model fields.
    """
    # The 'uploaded_file' field is required for POST requests
    uploaded_file = serializers.FileField(write_only=True)
    
    class Meta:
        model = ImageConversionJob
        fields = [
            'id', 'tool_type', 'uploaded_file', 'quality',
            'width', 'height', 'target_format', 'status', 'output_url'
        ]
        read_only_fields = ['id', 'status', 'output_url']

    def create(self, validated_data):
        """
        Custom create method to handle the nested creation of UploadedFile
        and ImageConversionJob instances.
        """
        uploaded_file_data = validated_data.pop('uploaded_file')
        
        # Create the UploadedFile instance first
        uploaded_file_instance = UploadedFile.objects.create(
            file=uploaded_file_data,
            original_filename=uploaded_file_data.name
        )
        
        # Create the ImageConversionJob instance, linking it to the new UploadedFile
        job = ImageConversionJob.objects.create(
            uploaded_file=uploaded_file_instance,
            **validated_data
        )
        return job

    def validate(self, data):
        """
        Custom validation to ensure that the request contains the
        correct data for the specified tool type.
        """
        tool_type = data.get('tool_type')
        
        # Check if a tool_type was provided
        if not tool_type:
            raise serializers.ValidationError({"tool_type": "This field is required."})

        # --- Conditional Validation based on tool_type ---
        if tool_type == 'image_resizer':
            # For resizer, either width or height must be provided
            if not data.get('width') and not data.get('height'):
                raise serializers.ValidationError(
                    {"width": "At least one of 'width' or 'height' is required for image resizing."},
                    code='required'
                )
            
            # Ensure provided dimensions are valid integers
            if data.get('width') is not None and not isinstance(data.get('width'), int):
                raise serializers.ValidationError({"width": "Width must be an integer."})
            if data.get('height') is not None and not isinstance(data.get('height'), int):
                raise serializers.ValidationError({"height": "Height must be an integer."})

        elif tool_type == 'image_compressor':
            # For compressor, quality or target_format are optional, but if quality is provided, validate it
            if data.get('quality') is not None:
                quality = data.get('quality')
                if not isinstance(quality, int) or not (0 <= quality <= 100):
                    raise serializers.ValidationError({"quality": "Quality must be an integer between 0 and 100."})
            
        elif tool_type == 'image_converter':
            # For converter, target_format is required
            if not data.get('target_format'):
                raise serializers.ValidationError(
                    {"target_format": "This field is required for format conversion."},
                    code='required'
                )
        
        else:
            # Handle unknown tool types
            raise serializers.ValidationError({"tool_type": f"Invalid tool type: {tool_type}. "
                                                            "Choices are 'image_resizer', 'image_compressor', 'image_converter'."})
        
        return data