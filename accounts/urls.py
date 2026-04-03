from django.urls import path
from . import views

urlpatterns = [
   
    path('', views.accounts, name="accounts"),
    path('login/', views.login, name="login"),
    path('register/', views.register, name="register"),
    path('forget_password/', views.forget_password, name="forget_password"),
]