from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
from datetime import datetime, timezone
from django.utils import timezone

# Create your models here.

"""
Inheriting and using abstractuser
"""
# Validator for Nepali phone numbers
nepali_phone_regex = RegexValidator(
    regex=r'^9[6-8]\d{8}$',
    message=_("Kindly enter valid phone numbers")
)

def make_aware_if_naive(dt):
    if dt is None:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt

class Department(models.Model):
    name = models.CharField(max_length=155, db_index=True, unique=True)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    work_start_time = models.TimeField(default="09:00")
    work_end_time = models.TimeField(default="17:00")
    working_days_per_week=models.IntegerField(default=6)

    def __str__(self):
        return self.name
class User(AbstractUser):
    email = models.EmailField(unique=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email
    is_verified = models.BooleanField(default=False)
    department = models.ForeignKey(Department, null = True, on_delete=models.SET_NULL)

class Employee(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other')
    ]
    EMPLOYMENT_TYPE = [
        ('FULL_TIME', 'Full Time'),
        ('PART_TIME', 'Part Time'),
        ('CONTRACT', 'Contract'),
        ('INTERN', 'Intern')
    ]
    ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('HR', 'HR'),
        ('MANAGER', 'Manager'),
        ("EMPLOYEE", 'Employee')]
    user = models.OneToOneField(User, on_delete=models.CASCADE, db_index=True, related_name='Employee_profile')
    role = models.CharField(max_length=20, choices = ROLE_CHOICES, default='EMPLOYEE', db_index=True)
    phone = models.CharField(_('Phone'), max_length=10, validators=[nepali_phone_regex], unique=True, db_index=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    date_of_birth = models.DateField(null=False, blank = False)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    designation = models.CharField(max_length=200, null = False)
    employment_type = models.CharField(max_length=20, choices = EMPLOYMENT_TYPE, default = "FULL_TIME")
    date_joined = models.DateTimeField(auto_now_add=True)
    date_left = models.DateField(null = True, blank = True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    location = models.CharField(max_length=25, blank=True)
    is_offsite=models.BooleanField(default=False)
    is_wfh_enabled=models.BooleanField(default=False)

    @property
    def is_official(self):
        return self.role in ["HR", "ADMIN", "MANAGER"]

    def __str__(self):
        return f"{self.user.username}"
class AttendanceRecord(models.Model):
    ATTENDANCE_CHOICES = [
        ('preseent', 'Present'),
        ('half_day', 'Half Day'),
        ('on_leave', 'On leave'),
        ('unpaid_leave', 'Unpaid Leave'),
        ('holiday', 'Holiday'),
        ('weekend', 'Weekend'),
        ('absent', 'Absent')
    ]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendance_records")
    date=models.DateField(default=timezone.now)
    check_in = models.DateTimeField(null=True, blank=True)
    check_out=models.DateTimeField(null=True, blank=True)
    status=models.CharField(
        max_length=20, choices=ATTENDANCE_CHOICES, default='absent'
    )
    hours_worked = models.DecimalField(max_digits=4, decimal_places=2, default=0.00)
    late_minutes = models.IntegerField(default=0)
    overtime_hours = models.DecimalField(max_digits=4, decimal_places=2, default=0.00)
    remarks=models.TextField(blank=True, null=True)
    is_auto_checkout = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together=('employee', 'date') #one employee per day record

    def calculate_status_and_hours(self):
        #skipping the fixed status
        """this logic states that if some employee is in these condition they will be marked as absent"""
        if self.status in {'on_leave', 'unpaid_leave', 'holiday', 'weekend'}:
            self.hours_worked = 0
            self.hours_minutes = 0
            self.overtime_hours = 0
        if not self.check_in or not self.check_out:
            self.status = 'absent'
            self.hours_worked = 0
            self.hours_minutes = 0
            self.overtime_hours = 0
            return
        dept = self.employee.department
        if not dept:
            self.status = 'absent'
            return
        
        check_in = make_aware_if_naive(self.check_in)
        check_out = make_aware_if_naive(self.check_out)
        shift_start = make_aware_if_naive(
            datetime.combine(self.date, dept.work_start_time)
        )
        shift_end = make_aware_if_naive(
            datetime.combine(self.date, dept.work_end_time)
        )
        effective_checkout = min(check_out, shift_end)
        worked_minutes = int(
            max(0, (effective_checkout- check_in).total_seconds() // 60)
        )
        self.hours_worked = round(worked_minutes / 60,2)
        if worked_minutes >= 480:
            self.status = 'present'
        elif worked_minutes >=240:
            self.status = 'half_day'
        else:
            self.status = 'absent'
        #the logic that handles the late minutes arrival
        if self.status in {'present', 'half_day'}:
            if check_in > shift_start:
                late = int((check_in - shift_start).total_seconds() // 60)
                #TODO: check the grace minutes in department and set it otherwise it will create the bug of not having grace minutes
                grace = getattr(dept, 'grace_minutes', 0)
                self.late_minutes = max(0, late - grace)
            else:
                self.late_minutes = 0
        else:
            self.late_minutes = 0

        """Overtime logic"""
        if check_out > shift_end:
            overtime_minutes = int((check_out-shift_end).total_seconds() // 60)
            self.overtime_hours = round(overtime_minutes / 60, 2)
        else:
            self.overtime_hours = 0

    def __str__(self):
        return f"{self.employee.user.username}-{self.date}-{self.status}"

class LeaveRequest(models.Model):
    LEAVE_TYPE = [
        ('annual', 'Annual Leave'),
        ('sick', 'Sick Leave'),
        ('casual', 'Casual Leave'),
        ('maternity', 'Maternity Leave'),
        ('paternity', 'Paternity Leave'),
        ('unpaid', 'Unpaid Leave')
    ]
    LEAVE_STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected') 
    ]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.CharField(max_length=50, choices=LEAVE_TYPE)
    start_date = models.DateField()
    end_date = models.DateField()
    reason=models.TextField(blank=True)
    status =models.CharField(max_length=20, choices=LEAVE_STATUS, default='pending')
    approved_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves')
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee.user.username} - {self.leave_type} - {self.start_date} to {self.end_date}"