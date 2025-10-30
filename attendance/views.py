from django.shortcuts import render
from urls import *
from .models import User,Employee,Department
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated  

# Create your views here.
class Welcome(APIView):
    permission_classes = [IsAuthenticated]

    def get(self,request):
        return Response({"Message": f"Hello {request.user.username}"})