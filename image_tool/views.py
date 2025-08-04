from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from django.conf import settings # Make sure settings is imported
from django.core.files.storage import default_storage # Keep this import, though we'll use os.path more directly
from django.http import FileResponse, Http404
import os
import uuid
import json
from .tasks import process_image_task
from .models import ImageConversionJob, UploadedFile
from .serializers import ImageConversionJobSerializer
from .permissions import HasConversionAllowance

class ImageConversionView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [HasConversionAllowance]

    def post(self, request, *args, **kwargs):
        data = {
            'file': request.FILES.get('file'),
            'tool_type': request.data.get('tool_type'),
            'quality': request.data.get('quality'),
            'width': request.data.get('width'),
            'height': request.data.get('height'),
            'target_format': request.data.get('target_format'),
        }

        serializer = ImageConversionJobSerializer(data=data, context={'request': request})

        if serializer.is_valid():
            job = serializer.save(user=request.user if request.user.is_authenticated else None)

            uploaded_file_instance = job.uploaded_file
            file_path_relative_to_media_root = uploaded_file_instance.file.name

            process_image_task.delay(
                job_id=job.id,
                file_path_relative_to_media_root=file_path_relative_to_media_root,
                tool_type=job.tool_type,
                quality=job.quality,
                width=job.width,
                height=job.height,
                target_format=job.target_format
            )

            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ImageConversionJobStatusView(generics.RetrieveAPIView):
    queryset = ImageConversionJob.objects.all()
    serializer_class = ImageConversionJobSerializer
    lookup_field = 'id' # Use 'id' for lookup as per your models.py UUIDField
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except Http404:
            return Response({"error": "Job not found."}, status=status.HTTP_404_NOT_FOUND)

class ImageConversionJobDownloadView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, job_id, *args, **kwargs):
        try:
            # Use 'id' to lookup the job, as that's your primary_key UUIDField
            job = ImageConversionJob.objects.get(id=job_id)
        except ImageConversionJob.DoesNotExist:
            raise Http404("Job not found.")

        # Ensure the job is completed and output_url exists
        if job.status != 'COMPLETED' or not job.output_url:
            return Response({"error": "File not ready for download or conversion failed."}, status=status.HTTP_404_NOT_FOUND)

        # --- THE CRUCIAL CHANGE IS HERE ---
        # 1. Get the URL from the job
        output_url = job.output_url

        # 2. Strip MEDIA_URL prefix to get the path relative to MEDIA_ROOT
        #    This is crucial to avoid the SuspiciousFileOperation
        if output_url.startswith(settings.MEDIA_URL):
            relative_path_in_media = output_url[len(settings.MEDIA_URL):]
        else:
            # This case should ideally not happen if tasks.py always generates URLs correctly
            # But it's a safeguard.
            return Response({"error": "Invalid output URL format."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 3. Construct the absolute file system path
        output_file_path = os.path.join(settings.MEDIA_ROOT, relative_path_in_media)

        # 4. Verify the file exists on the filesystem
        if not os.path.exists(output_file_path):
            return Response({"error": "Converted file not found on server."}, status=status.HTTP_404_NOT_FOUND)

        # 5. Determine the file name for Content-Disposition header
        file_name = os.path.basename(output_file_path)
        
        try:
            # 6. Open the file directly using its absolute path
            #    We cannot use default_storage.open() here because it would internally
            #    perform safe_join with MEDIA_ROOT, leading to the same error.
            response = FileResponse(open(output_file_path, 'rb'), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{file_name}"'
            return response
        except Exception as e:
            return Response({"error": f"Could not prepare file for download: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)