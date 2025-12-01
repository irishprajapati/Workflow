from .views import LoginAPI, UserRegistrationView, VerifyEmail, AttendanceViewset
from django.urls import path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'attendance', AttendanceViewset, basename='attendance')
urlpatterns = [
    path('login/', LoginAPI.as_view(), name='login'),
    path('register/', UserRegistrationView.as_view(), name='signup'),
    path("verify/<path:token>/",VerifyEmail.as_view())
]

urlpatterns += router.urls