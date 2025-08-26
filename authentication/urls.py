# authentication/urls.py

from django.urls import path
from .views import RegisterView, LoginView, LogoutView, UserDetailUpdateView, GetCSRFToken, PasswordResetRequestView, PasswordResetConfirmView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('user/', UserDetailUpdateView.as_view(), name='user-detail-update'),
    path('csrf/', GetCSRFToken.as_view(), name='csrf-token'),
    
    path('password-reset/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]