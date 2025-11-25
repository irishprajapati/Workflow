from .models import * 
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers

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
        return data
    
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField() #charfield for storing passwords
