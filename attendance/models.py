from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

# Create your models here.

"""
Inheriting and using abstractuser
"""
# Validator for Nepali phone numbers
nepali_phone_regex = RegexValidator(
    regex=r'^9[6-8]\d{8}$',
    message=_("Kindly enter valid phone numbers")
)

class Department(models.Model):
    name = models.CharField(max_length=155, db_index=True, unique=True)
    description = models.TextField()
    created_at = models.DateField()
    updated_at = models.DateField()

    def __str__(self):
        return self.name
class User(AbstractUser):
    ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('HR', 'HR'),
        ('MANAGER', 'Manager'),
        ("EMPLOYEE", 'Employee')]
    
    role = models.CharField(max_length=20, choices = ROLE_CHOICES, default='EMPLOYEE', db_index=True)
    department = models.ForeignKey(Department, null = True, on_delete=models.SET_NULL)
class Employee(models.Model):
    GENDER_CHOICES = [
        ('MALE', 'M'),
        ('FEMALE', 'F'),
        ('OTHER', 'O')
    ]
    EMPLOYMENT_TYPE = [
        ('FULL_TIME', 'Full Time'),
        ('PART_TIME', 'Part Time'),
        ('CONTRACT', 'Contract'),
        ('INTERN', 'Intern')
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, db_index=True, related_name='Employee_profile')
    phone = models.CharField(_('Phone'), max_length=10, validators=[nepali_phone_regex], unique=True, db_index=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    date_of_birth = models.DateField(null=False, blank = False)

    #company related information
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    designation = models.CharField(max_length=200, null = False)
    employment_type = models.CharField(max_length=20, choices = EMPLOYMENT_TYPE, default = "FULL_TIME")
    date_joined = models.DateTimeField(auto_now_add=True)
    date_left = models.DateField(null = True, blank = True)

    #status and tracking
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.department.name if self.department else 'No Dept'})"