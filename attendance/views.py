from .models import User,Employee,Department
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.db import IntegrityError, transaction
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
from django.core.mail import send_mail
from django.conf import settings
from .serializers import *
from rest_framework.response import Response
from django.contrib.auth import authenticate
from rest_framework import status, viewsets
class LoginAPI(APIView):
    @swagger_auto_schema(request_body=UserLoginSerializer,tags=['Authentication'])
    def post(self, request): #hit the post request
        try:
            serializer = UserLoginSerializer(data = request.data)
            if not serializer.is_valid():
                return Response({
                    'status': 400,
                    'message':'invalid data sent',
                    'errors': serializer.errors

                },status = status.HTTP_400_BAD_REQUEST)
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            user = authenticate(email = email, password = password)
            if user is None:
                return Response({
                    'status':400,
                    'message' : 'wrong credentials',
                    'data':{}
                }, status = status.HTTP_400_BAD_REQUEST)
            #now the access token for the employee works here
            refresh=RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token)

            }, status = status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'status':500,
                'message':'internal server error',
                'error':str(e)
            }, status= status.HTTP_500_INTERNAL_SERVER_ERROR)
class UserRegistrationView(APIView):
    @swagger_auto_schema(request_body=UserRegistrationSerializer,tags=['Authentication'])
    def post(self, request):
        serializer = UserRegistrationSerializer(data = request.data)
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    user = serializer.save()
                    user.is_verified = False
                    signer = TimestampSigner()
                    token = signer.sign(user.pk)
                    verification_url = f"http://127.0.0.1:8000/attendance/verify/{token}/"

                    send_mail(
                        subject = 'verify your account',
                        message = f"Click here to verify your account: {verification_url}",
                        from_email=settings.EMAIL_HOST_USER,
                        recipient_list=[user.email],
                        fail_silently=False
                    )
                return Response({"Message":"User registered. Check your email to verify"}, status=status.HTTP_201_CREATED)
            except IntegrityError as e:
                return Response({
                    "error": "Integrity Error: " + str(e) 
                }, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
class VerifyEmail(APIView):
    def get(self,request, token):
        signer = TimestampSigner()
        try:
            user_id = signer.unsign(token, max_age=86400)
        except SignatureExpired:
            return Response({"Message":"Verification link expired"}, status= 400)
        except BadSignature:
            return Response({"Message": "Invalid verification link"}, status = 400)
        user = User.objects.get(pk=user_id)
        user.is_active = True
        user.save()
        return Response({"Message": "Email verified successfully. You can now login"})
    

class EmployeeView(viewsets.ModelViewset):
    serializer = EmployeeSerializer