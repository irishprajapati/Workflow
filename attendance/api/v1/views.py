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
from django.core.cache import cache
from ...utils import *
from datetime import timedelta
#redis function 
def get_or_set_cache(key, func, timeout = 3600):
    data = cache.get(key)
    if not data:
        data = func()
        cache.set(key, data, timeout)
    return data

class LoginAPI(APIView):
    @swagger_auto_schema(request_body=UserLoginSerializer,tags=['Authentication'])
    def post(self, request):
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
        now = timezone.localtime()
        today = now().date()
        serializer = CheckInSerializer(data = request.data)
        serializer.is_valid(raise_exception=True)
        remarks = serializer.validated_data.get('remarks', '')

        with transaction.atomic():
            record, created = AttendanceRecord.objects.select_for_update().get_or_create(
                employee = emp,
                date=today
            )
            if record.check_in:
                return Response({
                    "error": "Already checked in today"
                }, status = status.HTTP_400_BAD_REQUEST)
            record.check_in = now()
            record.remarks = remarks
            record.save(update_fields=['check_in', 'remarks'])
        return Response({"Message":"Checked in successfully", "check_in": now}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def check_out(self, request):
        emp = self.get_employee()
        now = timezone.localtime()
        today=now().date()
        serializer = CheckOutSerializer(data = request.data)
        serializer.is_valid(raise_exception=True)
        remarks = serializer.validated_data.get('remarks', '')
        dept = emp.department
        if not dept:
            return Response({
                "Error":"Employee not assigned to department"
            }, status = status.HTTP_400_BAD_REQUEST)
        shift_start = timezone.make_aware(datetime.combine(today, dept.work_start_time))
        shift_start = timezone.localtime(shift_start)
        shift_end = timezone.make_aware(datetime.combine(today, dept.work_end_time))
        shift_end = timezone.localtime(shift_end)

        full_day_minutes = int((shift_end-shift_start).total_seconds() // 60)
        half_day_minutes = full_day_minutes // 2
        with transaction.atomic():
            try:
                record = AttendanceRecord.objects.get(employee = emp, date=today)
            except AttendanceRecord.DoesNotExist:
                return Response({"Error":"No check-in found for today"},status = status.HTTP_400_BAD_REQUEST)
            if record.check_out:
                return Response({"Error":"Already checked out today"}, status=status.HTTP_400_BAD_REQUEST)
        actual_checkout = now
        effective_checkout  = min(actual_checkout, shift_end)

        #worked minutes for attendance
        worked_minutes = int(max(0, (effective_checkout - record.check_in).total_seconds() // 60))
        record.hours_worked = round(worked_minutes / 60, 2)
        #attendance_status 
        if worked_minutes >= full_day_minutes:
            record.status = 'present'
        elif worked_minutes>= half_day_minutes:
            record.status = 'half_day'
        else:
            record.status = 'absent'

        # Late minutes (only if present or half-day)
        if record.status in {'present', 'half_day'}:
            if record.check_in > shift_start:
                late = int((record.check_in - shift_start).total_seconds() // 60)
                grace = getattr(dept, 'grace_minutes', 0)
                record.late_minutes = max(0, late - grace)
            else:
                record.late_minutes = 0
        else:
            record.late_minutes = 0

        # Overtime beyond shift end
        if actual_checkout > shift_end:
            overtime_minutes = int((actual_checkout - shift_end).total_seconds() // 60)
            record.overtime_hours = round(overtime_minutes / 60, 2)
        else:
            record.overtime_hours = 0

        # Save actual checkout and optional remarks
        record.check_out = actual_checkout
        if remarks:
            record.remarks = remarks
        record.save()

        return Response(
            {
                "message": "Checked out successfully",
                "status": record.status,
                "hours_worked": record.hours_worked,
                "late_minutes": record.late_minutes,
                "overtime_hours": record.overtime_hours,
            },
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'], permission_classes=[IsEmployee])
    def my_attendance(self, request):
        """Employee can view their attendance logs for previous 30 days"""
        emp = self.get_employee()
        cache_key = f"attendance_{emp.id}_30days"

        def fetch_attendance():
            # only fetch this employee's last 30 days
            return list(
                AttendanceRecord.objects.filter(
                    employee=emp,
                    date__gte=timezone.now().date() - timezone.timedelta(days=30)
                ).values(
                    'id', 'date', 'status', 'late_minutes'
                )
            )

        records = get_or_set_cache(cache_key, fetch_attendance, timeout=60*40)  # 40 minutes
        total_present = sum(1 for r in records if r['status'] == 'present')
        total_half_days = sum(1 for r in records if r['status'] == 'half_day')
        total_absent = sum(1 for r in records if r['status'] == 'absent')
        total_late = sum(1 for r in records if r['late_minutes'] > 0)

        summary = {
            'total_present': total_present,
            'total_half_days': total_half_days,
            'total_absent': total_absent,
            'total_late': total_late,
            'records': records,
        }

        serializer = AttendanceSummarySerializer(summary)
        return Response(serializer.data)

    @action(detail =False, methods=['get'], permission_classes = [IsOfficial])
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
        if not user or user.is_anonymous:
            return Employee.objects.none()
        role = user.Employee_profile.role

        if role in ['HR', 'ADMIN', 'MANAGER']:
            cache_key = "all_employees"
            def fetch_all_employees():
                return list(Employee.objects.all().values_list('id', flat = True))
            employee_ids = get_or_set_cache(cache_key, fetch_all_employees, timeout=60*40)
            return Employee.objects.filter(id__in = employee_ids).order_by("id")
        #normal employee cache individually
        cache_key = f"employee_{user.id}"
        def fetch_self():
            return list(Employee.objects.filter(user=user).values_list('id', flat=True))
        employee_ids = get_or_set_cache(cache_key, fetch_self, timeout=60*40)
        return Employee.objects.filter(id__in=employee_ids)

class LeaveRequestViewSet(viewsets.ModelViewSet):
    serializer_class = LeaveRequestSerializer
    # Permissions
    def get_permissions(self):
        if self.action in ["list", "retrieve", "create"]:
            return [IsEmployeeOrIsOfficial()]
        elif self.action in ["update", "partial_update", "destroy"]:
            return [IsOfficial()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        employee = getattr(user, "employee_profile", None)
        if not employee:
            return LeaveRequest.objects.none()
        if employee.role in ["HR", "ADMIN", "MANAGER"]:
            return LeaveRequest.objects.all()
        return LeaveRequest.objects.filter(employee=employee)

    # Creation logic
    def perform_create(self, serializer):
        user = self.request.user
        employee = getattr(user, "employee_profile", None)

        if not employee:
            raise serializers.ValidationError({"Message": "Employee profile not found"})

        # Employee can only create their own requests
        if employee.role == "EMPLOYEE":
            serializer.save(employee=employee)
            return

        # HR / Admin / Manager can create for specific employee
        provided_employee_id = self.request.data.get("employee")
        if provided_employee_id:
            try:
                target_emp = Employee.objects.get(id=provided_employee_id)
            except Employee.DoesNotExist:
                raise serializers.ValidationError({
                    "Message": "Employee does not exist with this ID"
                })
            serializer.save(employee=target_emp)
            return

        # Provided employee not given
        raise serializers.ValidationError({
            "Message": "Employee ID is required for privileged roles"
        })

    # Standard create override
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        self.perform_create(serializer)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)