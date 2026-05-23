from django.urls import path
from . import views

urlpatterns = [
    # Аутентификация
    path('', views.dashboard, name='dashboard'),
    path('login/', views.user_login, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.user_logout, name='logout'),

    # Заявки
    path('requests/', views.request_list, name='request_list'),
    path('requests/create/', views.request_create, name='request_create'),
    path('requests/<int:pk>/', views.request_detail, name='request_detail'),
    path('requests/<int:pk>/take/', views.request_take, name='request_take'),
    path('requests/<int:pk>/status/<str:new_status>/',
         views.request_change_status, name='change_status'),
    path('requests/<int:pk>/upload-document/',
         views.upload_document, name='upload_document'),
    path('documents/<int:pk>/view/',
         views.serve_document, name='serve_document'),
    path('requests/<int:pk>/mark-completed/',
         views.mark_completed, name='mark_completed'),

    # Счета
    path('requests/<int:pk>/create-invoice/',
         views.create_invoice, name='create_invoice'),
    path('invoices/<int:pk>/mark-paid/',
         views.mark_payment, name='mark_payment'),

    # Клиенты
    path('clients/', views.client_list, name='client_list'),
    path('clients/<int:pk>/assign/', views.assign_client, name='assign_client'),

    # Отчеты
    path('reports/', views.reports, name='reports'),

    # Уведомления
    path('notifications/<int:pk>/read/',
         views.mark_notification_read, name='mark_notification_read'),
]