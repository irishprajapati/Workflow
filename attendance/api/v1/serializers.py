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
        fields = ['user', 'role', 'designation']
class CheckInSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    check_in_time = serializers.DateTimeField()
class CheckOutSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    check_out_time = serializers.DateTimeField()

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
    """optional so that employee can say they first informed"""
    notification_date = serializers.DateField(required=False, write_only=True)
    class Meta:
        model = LeaveRequest
        fields = "__all__"
        read_only_fields = ["status", "approved_by", "created_at", "updated_at"]

    def validate(self, data):
        """
        Global validation logic:
        - start_date and end_date required
        - end_date >= start_date
        - notice periods
        - backdating rules
        - month boundary rules
        """
        today = timezone.now().date()
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        notification_date = data.get("notification_date")

        # For updates
        leave_type = data.get("leave_type") or getattr(self.instance, "leave_type", None)

        # Required fields
        if not start_date or not end_date:
            raise serializers.ValidationError({
                "Message": "start_date and end_date are required"
            })

        # Date ordering
        if end_date < start_date:
            raise serializers.ValidationError({
                "end_date": "End date cannot be before start date"
            })

        # Determine request date
        if notification_date:
            request_date = notification_date
        elif self.instance and getattr(self.instance, "created_at", None):
            request_date = self.instance.created_at.date()
        else:
            request_date = today

        # Rule set
        rules = LEAVE_VALIDATION_RULES.get(
            leave_type,
            {"min_notice_days": 0, "allow_past_start": False, "max_backdate_days": 0}
        )

        min_notice = rules.get("min_notice_days", 0)
        max_back = rules.get("max_backdate_days", 0)
        allow_past_start = rules.get("allow_past_start", False)

        # Notice period
        days_between_request_and_start = (start_date - request_date).days
        if days_between_request_and_start < min_notice:
            raise serializers.ValidationError({
                "start_date": (
                    f"{leave_type.capitalize()} requires at least "
                    f"{min_notice} day(s) notice."
                )
            })

        # Backdating rules
        if start_date < today:
            if not allow_past_start:
                raise serializers.ValidationError({
                    "start_date": "Retroactive start dates are not allowed for this leave type."
                })

            backdated_days = (today - start_date).days
            if backdated_days > max_back:
                raise serializers.ValidationError({
                    "start_date": (
                        f"This leave type may be backdated up to {max_back} day(s). "
                        f"Currently backdated {backdated_days} day(s)."
                    )
                })

        # Start date cannot be before first day of month
        current_first_day = today.replace(day=1)
        if not allow_past_start and start_date < current_first_day:
            raise serializers.ValidationError({
                "start_date": (
                    "Start date cannot be before the first day of this month "
                    "for this leave type."
                )
            })

        return data
