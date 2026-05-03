from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.user_login, name='login'),
    path('register/', views.register, name='register'),  # ← ДОБАВИТЬ ЭТУ СТРОКУ
    path('logout/', views.user_logout, name='logout'),
    path('requests/', views.request_list, name='request_list'),
    path('requests/<int:pk>/', views.request_detail, name='request_detail'),
    path('requests/create/', views.request_create, name='request_create'),
    path('requests/<int:pk>/status/<str:new_status>/', views.request_change_status, name='change_status'),
    path('clients/', views.client_list, name='client_list'),
    path('tasks/create/', views.task_create, name='task_create'),
    path('tasks/create/<int:request_id>/', views.task_create, name='task_create_for_request'),
    path('reports/', views.reports, name='reports'),
]