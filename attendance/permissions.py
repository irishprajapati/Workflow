from rest_framework.permissions import BasePermission, SAFE_METHODS
from .models import *
from rest_framework import status
from django.http import response
def get_employee(user):
    if not user or not user.is_authenticated:
        return None
    return getattr(user, "Employee_profile", None)

class IsEmployee(BasePermission):
    def has_permission(self, request, view):
        emp = get_employee(request.user)
        return emp is not None and emp.role == "EMPLOYEE"

class IsOfficial(BasePermission):
    def has_permission(self, request, view):
        emp = get_employee(request.user)
        return emp is not None and emp.role in ["HR", "ADMIN", "MANAGER"]

class IsEmployeeOrIsOfficial(BasePermission):
    def has_permission(self, request, view):
        emp = get_employee(request.user)
        if not emp:
            return False
        return emp.role in ['EMPLOYEE', 'HR', 'ADMIN', 'MANAGER']
