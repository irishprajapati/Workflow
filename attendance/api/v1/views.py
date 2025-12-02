from ...models import User,Employee,Department
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import action, permission_classes
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
from rest_framework.viewsets import GenericViewSet
from django.core.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from ...permissions import *
from ...utils import has_role
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

class AttendanceViewset(GenericViewSet):
    serializer_class = CheckInSerializer
    queryset = Employee.objects.all()
    def get_employee(self):
        user = self.request.user
        if not user.is_authenticated:
            raise ValidationError("User is not authenticated")
        try:
            return user.Employee_profile 
        except Employee.DoesNotExist:
            raise ValidationError("Employee profile doesnot exist for this user")
    
    @action(detail = False, methods = ['post'], permission_classes = [IsAuthenticated])
    def check_in(self, request):
        emp = self.get_employee()
        today = timezone.now().date()

        with transaction.atomic():
            record, created = AttendanceRecord.objects.select_for_update().get_or_create(
                employee = emp,
                date=today
            )
            if record.check_in:
                return Response({
                    "error": "Already checked in today"
                }, status = status.HTTP_400_BAD_REQUEST)
            record.check_in = timezone.now()
            record.save()
        return Response({"Message":"Checked in successfully"}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def check_out(self, request):
        emp = self.get_employee()
        today=timezone.now().date()
        try:
            record = AttendanceRecord.objects.get(employee = emp, date=today)
        except AttendanceRecord.DoesNotExist:
            return Response({"Error":"No check-in found for today"},status = status.HTTP_400_BAD_REQUEST)
        if record.check_out:
            return Response({"Error":"Already checked out today"}, status=status.HTTP_400_BAD_REQUEST)
        
        record.check_out = timezone.now()
        record.save()
        return Response({"Message":"Checked out successfully"}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods = ['get'], permission_classes = [IsEmployee, IsHR])
    def my_attendance(self, request):
        """Employee can view their attendance logs for previous 30 days"""
        emp = self.get_employee()
        records = AttendanceRecord.objects.filter(
            employee=emp,
            date__gte=timezone.now().date() - timezone.timedelta(days=30)
        ).order_by('-date')
        summary = {
            'total_present':records.filter(status='present').count(),
            'total_half_days':records.filter(status='half_day').count(),
            'total_absent':records.filter(status='absent').count(),
            'total_late': records.filter(late_minutes__gt=0).count(),
            'records': records,
        }
        serializer = AttendanceSummarySerializer(summary)
        return Response(serializer.data)
    
    @action(detail =False, methods=['get'], permission_classes = [IsHR])
    def overall_attendance(self,request):
        records = AttendanceRecord.objects.filter(
            date__gte=timezone.now().date() - timezone.timedelta(days=30)
        ).order_by('-date')
        serializer = AttendaceRecordSerializer(records, many = True)
        return Response(serializer.data)
class EmployeeProfileViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeProfileSerializer
    lookup_field = 'id'
    http_method_names = ['get']
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        # If user is anonymous, return nothing
        if not user or user.is_anonymous:
            return Employee.objects.none()

        # Check roles
        role = user.Employee_profile.role

        # HR / Admin / Manager → can view all employees
        if role in ['HR', 'ADMIN', 'MANAGER']:
            return Employee.objects.all().order_by("id")

        # Normal employee → only their own profile
        return Employee.objects.filter(user=user)
