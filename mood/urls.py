from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='userboard'),
    path('checkin/', views.checkin, name='checkin'),
    path('checkin/again/', views.checkin_again, name='checkin_again'),
    path('journal/new/', views.journal_new, name='journal_new'),
    path('profile/', views.profile_view, name='profile_view'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('settings/', views.settings_view, name='settings'),
    path('logout/', views.logout_view, name='logout'),
    path('progress/', views.progress_view, name='progress'),
    path('resources/', views.resources_view, name='resources'),
    path('notifications/', views.notifications, name='notifications'),
    path('chat/', views.chat, name='chat'),
    path('delete-account/', views.delete_account, name='delete_account'),
]