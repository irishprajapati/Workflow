from attendance.models import * 
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth.models import AbstractUser
from rest_framework.validators import UniqueValidator
from datetime import date
from django.db import transaction, IntegrityError
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