from attendance.models import * 
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth.models import AbstractUser
from rest_framework.validators import UniqueValidator
from datetime import date
from django.db import transaction, IntegrityError
from ...utils import LEAVE_VALIDATION_RULES
"""
serializer to show role and username while logging
"""
class CustomTokenObtainPair(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        return token
    def validate(self,attrs):
        data = super().validate(attrs)
        data['username'] = self.user.username
        data['role'] = self.user.role
        return data
    
class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField() #charfield for storing passwords
class UserRegistrationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True, validators=[UniqueValidator(queryset=User.objects.all(),message="Email already exists")])#email must for login so required is made as True
    username = serializers.CharField(required = True, validators =[UniqueValidator(queryset = User.objects.all(), message="Username already exists")])
    phone = serializers.IntegerField(required=True, validators = [UniqueValidator(queryset=Employee.objects.all(),message="Phone number already exists")])
    password = serializers.CharField(write_only = True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)
    date_of_birth = serializers.DateField(required = True)
    class Meta:
        model = User
        fields = ('username', 'email', 'phone','password', 'password_confirm', 'date_of_birth')
        extra_kwargs ={
            'password':{'write_only':True},
            'password_confirm':{'write_only':True}
        }
    def validate_date_of_birth(self,value):
        dob = value.date() if hasattr(value, "date") else value
        if value > date.today():
            raise serializers.ValidationError("Date of birth cannot be in future")
        return value

    def validate(self,data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({"password": 'Password dont match'})
        return data
    @transaction.atomic
    def create(self,validated_data):
        dob= validated_data.pop('date_of_birth')
        phone=validated_data.pop('phone')
        validated_data.pop('password_confirm')
        user = User.objects.create_user(
            username = validated_data['username'],
            email = validated_data['email'],
            password = validated_data['password'],
            is_verified = False
        )

        Employee.objects.create(
            user=user,
            date_of_birth=dob,
            phone=phone,
            employment_type='FULL_TIME'
        )
        return user
class UserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    class Meta:
        model=User
        fields=['email']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['username']=instance.get_username()
        return data
    
class EmployeeSerializer(serializers.ModelSerializer):
    user = UserSerializer
    class Meta:
        model=Employee
        fields="__all__"
        read_only_fields =["is_active"]

    @transaction.atomic
    def update(self, instance, validated_data):
        user_data=validated_data.pop("user",{})
        user = instance.user
        for attr, value in user_data.items():
            setattr(user,attr, value)
        user.save()
        for attr,value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
class EmployeeProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ['role', 'phone', 'designation', 'employment_type', 'is_offsite', 'is_wfh_enabled', 'department']
class CheckInSerializer(serializers.Serializer):
    remarks = serializers.CharField(required=False, allow_blank=True)
    # employee_id = serializers.IntegerField()
    # check_in_time = serializers.DateTimeField()
class CheckOutSerializer(serializers.Serializer):
    remarks = serializers.CharField(required=False, allow_blank=True)

class AttendaceRecordSerializer(serializers.ModelSerializer):
    employee_username = serializers.CharField(source='employee.user.username', read_only = True)

    class Meta:
        model = AttendanceRecord
        fields = "__all__"
        # read_only_fields = fields

class AttendanceSummarySerializer(serializers.Serializer):
    total_present = serializers.IntegerField()
    total_half_days = serializers.IntegerField()
    total_absent = serializers.IntegerField()
    total_late = serializers.IntegerField()
    records = AttendaceRecordSerializer(many=True)
class LeaveRequestSerializer(serializers.ModelSerializer):
    """Serializer for leave requests with robust validation"""
    class Meta:
        model = LeaveRequest
        fields = "__all__"
        read_only_fields = ["employee", "status", "approved_by", "created_at", "updated_at"]

    def validate(self, data):
        today = timezone.now().date()
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        leave_type = data.get("leave_type") or getattr(self.instance, "leave_type", None)
        reason = data.get("reason") or ""

        # 1️⃣ Required fields
        if not start_date or not end_date:
            raise serializers.ValidationError({"Message": "start_date and end_date are required"})
        if end_date < start_date:
            raise serializers.ValidationError({"end_date": "End date cannot be before start date"})

        # 2️⃣ Leave rules
        rules = LEAVE_VALIDATION_RULES.get(
            leave_type,
            {"min_notice_days": 0, "allow_past_start": False, "max_backdate_days": 0}
        )
        min_notice = rules.get("min_notice_days", 0)
        max_back = rules.get("max_backdate_days", 0)
        allow_past_start = rules.get("allow_past_start", False)

        # 3️⃣ Notice period
        if (start_date - today).days < min_notice:
            raise serializers.ValidationError({
                "start_date": f"{leave_type.capitalize()} requires at least {min_notice} day(s) notice."
            })

        # 4️⃣ Backdating
        if start_date < today:
            if not allow_past_start:
                raise serializers.ValidationError({
                    "start_date": "Retroactive start dates are not allowed for this leave type."
                })
            if (today - start_date).days > max_back:
                raise serializers.ValidationError({
                    "start_date": f"This leave type can be backdated up to {max_back} day(s)."
                })

        # 5️⃣ Start date cannot be before first day of month (if rule)
        if not allow_past_start and start_date < today.replace(day=1):
            raise serializers.ValidationError({
                "start_date": "Start date cannot be before the first day of this month for this leave type."
            })

        # 6️⃣ Overlapping leave check
        emp = getattr(self.context["request"].user, "employee_profile", None)
        if emp:
            overlapping_leaves = LeaveRequest.objects.filter(
                employee=emp,
                start_date__lte=end_date,
                end_date__gte=start_date,
            )
            if self.instance:
                overlapping_leaves = overlapping_leaves.exclude(id=self.instance.id)
            if overlapping_leaves.exists():
                raise serializers.ValidationError({
                    "non_field_errors": "You already have a leave request that overlaps with these dates."
                })

            # Duplicate leave: same type, same dates, same reason
            duplicate_leave = LeaveRequest.objects.filter(
                employee=emp,
                leave_type=leave_type,
                start_date=start_date,
                end_date=end_date,
                reason__iexact=reason.strip()
            )
            if self.instance:
                duplicate_leave = duplicate_leave.exclude(id=self.instance.id)
            if duplicate_leave.exists():
                raise serializers.ValidationError({
                    "non_field_errors": "A leave with the same type, dates, and reason already exists."
                })

        return data
