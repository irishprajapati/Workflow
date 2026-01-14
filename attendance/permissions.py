from rest_framework.permissions import BasePermission
from .models import *
def get_employee(user):
    if not user or not user.is_authenticated:
        return None
    return getattr(user, "Employee_profile", None)

class HasEmployeeProfile(BasePermission):
    def has_permission(self, request, view):
        return get_employee(request.user) is not None
class IsEmployee(BasePermission):
    def has_permission(self, request, view):
        emp = get_employee(request.user)
        return emp and emp.role == "EMPLOYEE"

class IsOfficial(BasePermission):
    """
    HR / Admin / Manager
    Has authority to access sensitive employee data
    """
    def has_permission(self, request, view):
        emp = get_employee(request.user)
        return emp and emp.is_official

class IsEmployeeOrIsOfficial(BasePermission):
    def has_permission(self, request, view):
        emp = get_employee(request.user)
        if not emp:
            return False
        return emp.role in ['EMPLOYEE', 'HR', 'ADMIN', 'MANAGER']

class IsOwnerOrOfficial(BasePermission):
    def has_permission(self, request, view):
        return get_employee(request.user) is not None

    def has_object_permission(self, request, view, obj):
        emp = get_employee(request.user)
        return emp.is_official or obj.employee == emp
