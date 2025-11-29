from rest_framework.permissions import BasePermission, SAFE_METHODS
from .models import *
from rest_framework import status
from django.http import response
def get_employee_role(user):
    """sends the request and get response as authenticated and unauthenticated user"""
    if not user or not user.is_authenticated:
        return response({"Message":"User is not authenticated"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        return user.Employee_profile
    except(Employee.DoesNotExist, AttributeError):
        return response({"Message":"Employee doesnot exists"}, status = status.HTTP_400_BAD_REQUEST)
    
def has_role(user, *roles):
    """checking what role does employee holds"""
    return get_employee_role(user) in roles

class IsEmployee(BasePermission):
    """allow access only to general employee user"""
    def has_permission(self, request, view):
        return has_role(request.user, Employee.EMPLOYEE)
    
class IsHR(BasePermission):
    """allow access only to users who are in hr department"""
    def has_permission(self, request, view):
        if not request or not request.user.is_authenticated:
            return response({"Message":"User is not authenticated"})
        employee = getattr(request.user, 'employee_profile', None)
        if not employee:
            return #TODO:

