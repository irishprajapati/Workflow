from urls import *
from .models import User,Employee,Department
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated  
from .serializers import LoginSerializer
from rest_framework.response import response
from django.contrib.auth import authenticate
class LoginAPI(APIView):
    def post(self, request):
        try:
            data = request.data 
            serializer = LoginSerializer(data = data)
            if serializer.is_valid():
                email = serializer.data['email']
                password = serializer.data['password']
                user = authenticate(email = email, password = password)
                if user is None:
                    return response({
                    'status': 400,
                    'message': 'wrong credentials',
                    'data': {}
                })

            refresh = RefreshToken.for_user(user)
            return {
                'refresh' : str(refresh),
                'access': str(refresh.access_token)
            }

#sending the wrong credentials message
            return response({
                'status': 400,
                'message': 'wrong credentials',
                'data': serializer.errors
            })
        except Exception as e:
            print(e)
