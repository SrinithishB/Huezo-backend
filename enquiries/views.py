

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from .serializers import EnquiryCreateSerializer, EnquiryResponseSerializer


class EnquiryCreateView(APIView):
    permission_classes = [AllowAny]  # Public endpoint — no login required

    def post(self, request):
        serializer = EnquiryCreateSerializer(data=request.data)
        if serializer.is_valid():
            enquiry = serializer.save()
            response = EnquiryResponseSerializer(enquiry)
            return Response(
                {
                    "message": "Enquiry submitted successfully.",
                    "data": response.data
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)