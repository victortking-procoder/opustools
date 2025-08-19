# --- views.py ---
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from django.conf import settings
from django.http import FileResponse, Http404
import os
import uuid
import json
from .tasks import process_file_task
from .models import PdfToolJob, PdfUploadedFile
from .serializers import PdfToolJobSerializer
from .permissions import HasConversionAllowance

class PdfToolJobView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [HasConversionAllowance]

    def post(self, request, *args, **kwargs):
        tool_type = request.data.get('tool_type')
        if not tool_type or tool_type not in ['pdf_converter', 'file_compressor', 'pdf_merger', 'pdf_splitter']:
            return Response({"error": "tool_type is required and must be 'pdf_converter', 'file_compressor', 'pdf_merger', or 'pdf_splitter'."}, status=status.HTTP_400_BAD_REQUEST)

        data = {
            'tool_type': tool_type,
            'target_format': request.data.get('target_format'),
            'compression_level': request.data.get('compression_level'),
            # NEW: Add fields for splitting and merging
            'page_ranges': request.data.get('page_ranges'),
            'merge_order': request.data.get('merge_order'),
        }

        # Handle file uploads based on tool_type
        if tool_type in ['pdf_merger', 'file_compressor']:
            files = request.FILES.getlist('files')
            if not files:
                return Response({"error": "No files provided for this operation."}, status=status.HTTP_400_BAD_REQUEST)
            data['files'] = files
        elif tool_type in ['pdf_converter', 'pdf_splitter']:
            file = request.FILES.get('file')
            if not file:
                return Response({"error": "No file provided for this operation."}, status=status.HTTP_400_BAD_REQUEST)
            data['files'] = [file]
        else:
            return Response({"error": "Invalid tool_type provided."}, status=status.HTTP_400_BAD_REQUEST)
            
        serializer = PdfToolJobSerializer(data=data, context={'request': request})
        
        if serializer.is_valid():
            job = serializer.save(user=request.user if request.user.is_authenticated else None)
            process_file_task.delay(job_id=job.id)

            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PdfToolJobStatusView(generics.RetrieveAPIView):
    queryset = PdfToolJob.objects.all()
    serializer_class = PdfToolJobSerializer
    lookup_field = 'id'
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except Http404:
            return Response({"error": "Job not found."}, status=status.HTTP_404_NOT_FOUND)

class PdfToolJobDownloadView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, job_id, *args, **kwargs):
        try:
            job = PdfToolJob.objects.get(id=job_id)
        except PdfToolJob.DoesNotExist:
            raise Http404("Job not found.")

        if job.status != 'COMPLETED' or not job.output_url:
            return Response({"error": "File not ready for download or job failed."}, status=status.HTTP_404_NOT_FOUND)

        output_url = job.output_url
        if not output_url.startswith(settings.MEDIA_URL):
            return Response({"error": "Invalid output URL format."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        relative_path_in_media = output_url[len(settings.MEDIA_URL):]
        output_file_path = os.path.join(settings.MEDIA_ROOT, relative_path_in_media)

        if not os.path.exists(output_file_path):
            return Response({"error": "Processed file not found on server."}, status=status.HTTP_404_NOT_FOUND)
        
        file_name = os.path.basename(output_file_path)

        try:
            response = FileResponse(open(output_file_path, 'rb'), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{file_name}"'
            return response
        except Exception as e:
            return Response({"error": f"Could not prepare file for download: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)