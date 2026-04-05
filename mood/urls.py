from django.urls import path
from . import views

urlpatterns = [
    path('check/', views.mood_check),
    path('success/', views.success),
]