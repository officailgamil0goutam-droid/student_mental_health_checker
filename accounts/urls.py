from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # landing
    path('', views.accounts, name='accounts'),

    # auth pages
    path('login/', views.login_view, name='login'),
    path('register/', views.register, name='register'),

    # custom forgot password page
    path('forget_password/', views.forget_password, name='forget_password'),

    # custom OTP API endpoints (called by forget_password.html via fetch)
    path('send-otp/', views.send_otp, name='send_otp'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('reset-password/', views.reset_password, name='reset_password'),

    # Django built-in password reset (used for logged-in password change)
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='accounts/password_reset.html'
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html'
    ), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html'
    ), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html'
    ), name='password_reset_complete'),
]