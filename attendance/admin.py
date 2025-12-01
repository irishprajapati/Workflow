from django.contrib import admin
from django import forms
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import *
# Register your models here.

admin.site.register(User)
admin.site.register(Department)
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    pass
admin.site.register(AttendanceRecord)
admin.site.register(LeaveRequest)