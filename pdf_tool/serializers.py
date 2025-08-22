# --- serializers.py ---
from rest_framework import serializers
from .models import PdfToolJob, PdfUploadedFile
import json

class PdfUploadedFileSerializer(serializers.ModelSerializer):
    """
    Serializer for the PdfUploadedFile model.
    """
    class Meta:
        model = PdfUploadedFile
        fields = ['id', 'file', 'original_filename', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at', 'original_filename']

class PdfToolJobSerializer(serializers.ModelSerializer):
    """
    Serializer for the PdfToolJob model.
    Handles PDF conversion, compression, merging, and splitting jobs.
    """
    uploaded_files = PdfUploadedFileSerializer(many=True, read_only=True)
    files = serializers.ListField(
        child=serializers.FileField(max_length=100000, allow_empty_file=False, use_url=False),
        write_only=True,
        required=False,
        help_text="File(s) to be processed. For conversion/splitting, upload a single file. For merging/compression, upload multiple."
    )
    
    class Meta:
        model = PdfToolJob
        fields = [
            'id', 'user', 'tool_type', 'target_format', 'compression_level', 'page_ranges', 'merge_order',
            'status', 'output_url', 'error_message', 'created_at', 'uploaded_files', 'files'
        ]
        read_only_fields = ['id', 'user', 'status', 'output_url', 'error_message', 'created_at']

    def create(self, validated_data):
        files_data = validated_data.pop('files', [])

        # Manually parse merge_order if it arrives as a string
        merge_order_data = validated_data.pop('merge_order', None)
        if merge_order_data and isinstance(merge_order_data, str):
            try:
                # Load the JSON string into a proper Python list
                validated_data['merge_order'] = json.loads(merge_order_data)
            except json.JSONDecodeError:
                raise serializers.ValidationError({"merge_order": "Invalid JSON format."})

        page_ranges = validated_data.pop('page_ranges', None)

        job = PdfToolJob.objects.create(**validated_data)

        if page_ranges:
            job.page_ranges = page_ranges
        job.save()


        for file_data in files_data:
            uploaded_file = PdfUploadedFile.objects.create(
                file=file_data,
                original_filename=file_data.name
            )
            job.uploaded_files.add(uploaded_file)

        return job