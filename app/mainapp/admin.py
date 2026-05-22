from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Service, ServiceRequest,
    RequestHistory, RequestDocument, RequiredDocument,
    Invoice, Notification
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'full_name', 'role', 'client_type', 'is_active', 'phone']
    list_filter = ['role', 'client_type', 'is_active']
    search_fields = ['email', 'full_name', 'phone']
    ordering = ['email']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Основная информация', {'fields': ('full_name', 'phone', 'role')}),
        ('Данные клиента', {'fields': ('client_type', 'inn', 'kpp', 'legal_address', 'manager')}),
        ('Права доступа', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Важные даты', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'phone', 'password1', 'password2', 'role'),
        }),
    )

    readonly_fields = ['created_at', 'updated_at']


class RequiredDocumentInline(admin.TabularInline):
    model = RequiredDocument
    extra = 1
    fields = ['name', 'order']


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'price_individual', 'price_organization', 'default_deadline', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']
    inlines = [RequiredDocumentInline]
    list_editable = ['is_active']


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ['number', 'service', 'client', 'status', 'price', 'manager', 'created_at']
    list_filter = ['status', 'service', 'created_at']
    search_fields = ['number', 'client__full_name', 'service__name']
    raw_id_fields = ['client', 'manager']
    readonly_fields = ['number', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Основная информация', {
            'fields': ('number', 'service', 'client', 'status', 'price')
        }),
        ('Сроки и ответственные', {
            'fields': ('manager', 'deadline')
        }),
        ('Дополнительно', {
            'fields': ('rejection_reason', 'created_at', 'updated_at')
        }),
    )


@admin.register(RequestHistory)
class RequestHistoryAdmin(admin.ModelAdmin):
    list_display = ['request', 'changed_by', 'field_name', 'timestamp']
    list_filter = ['field_name', 'timestamp']
    search_fields = ['request__number']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'


@admin.register(RequestDocument)
class RequestDocumentAdmin(admin.ModelAdmin):
    list_display = ['request', 'required_document', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['request__number', 'required_document__name']
    raw_id_fields = ['request']
    date_hierarchy = 'uploaded_at'


@admin.register(RequiredDocument)
class RequiredDocumentAdmin(admin.ModelAdmin):
    list_display = ['name', 'service', 'order']
    list_filter = ['service']
    list_editable = ['order']
    search_fields = ['name', 'service__name']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['number', 'request', 'amount', 'is_paid', 'paid_at', 'created_at']
    list_filter = ['is_paid', 'created_at']
    search_fields = ['number', 'request__number']
    readonly_fields = ['number', 'created_at']
    raw_id_fields = ['request']
    date_hierarchy = 'created_at'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__email', 'message']
    raw_id_fields = ['user']
    list_editable = ['is_read']
    date_hierarchy = 'created_at'