from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView
)
from .serializers import CustomTokenObtainPair
urlpatterns = [
    # path('api/login/', CustomTokenObtainPair.as_view(), name="token_obtain_pair"), #login
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh_view') #refresh
]
