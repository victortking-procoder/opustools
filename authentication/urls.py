# authentication/urls.py

from django.urls import path
from .views import RegisterView, LoginView, LogoutView, UserDetailUpdateView, GetCSRFToken # Import new view name

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('user/', UserDetailUpdateView.as_view(), name='user-detail-update'), # Changed to new view
    path('csrf/', GetCSRFToken.as_view(), name='csrf-token'),
    # Djoser's password reset URLs will be included from the project-level urls.py
]