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
        
        # NEW: Handle page_ranges and merge_order from validated data
        page_ranges = validated_data.pop('page_ranges', None)
        merge_order = validated_data.pop('merge_order', None)
        
        job = PdfToolJob.objects.create(**validated_data)
        
        # Store page_ranges or merge_order as JSON strings if they exist
        if page_ranges:
            job.page_ranges = page_ranges
        if merge_order:
            job.merge_order = merge_order
        job.save()

        for file_data in files_data:
            uploaded_file = PdfUploadedFile.objects.create(
                file=file_data,
                original_filename=file_data.name
            )
            job.uploaded_files.add(uploaded_file)
            
        return job