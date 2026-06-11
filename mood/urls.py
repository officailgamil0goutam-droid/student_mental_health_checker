from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='userboard'),
    path('checkin/', views.checkin, name='checkin'),
    path('checkin/again/', views.checkin_again, name='checkin_again'),
    path('journal/', views.journal_list, name='journal_list'),
    path('journal/new/', views.journal_new, name='journal_new'),
    path('journal/<int:pk>/', views.journal_detail, name='journal_detail'),
    path('journal/<int:pk>/edit/', views.journal_edit, name='journal_edit'),
    path('journal/<int:pk>/delete/', views.journal_delete, name='journal_delete'),
    path('profile/', views.profile_view, name='profile_view'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('settings/', views.settings_view, name='settings'),
    path('logout/', views.logout_view, name='logout'),
    path('progress/', views.progress_view, name='progress'),
    path('resources/', views.resources_view, name='resources'),
    path('notifications/', views.notifications, name='notifications'),
    path('chat/', views.chat, name='chat'),
    path('delete-account/', views.delete_account, name='delete_account'),
    path('password-change/', views.password_change, name='password_change'),
    path('password-change/done/', views.password_change_done, name='password_change_done'),
]