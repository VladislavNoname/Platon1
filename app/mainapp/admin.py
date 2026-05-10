from django.contrib import admin
from .models import (
    User, Client, Service, ServiceRequest,
    RequestHistory, RequestDocument, RequiredDocument,
    Invoice, Notification
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['email', 'role', 'is_active', 'phone']
    list_filter = ['role', 'is_active']
    search_fields = ['email', 'first_name', 'phone']
    ordering = ['email']


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'client_type', 'manager', 'created_at']
    list_filter = ['client_type', 'created_at']
    search_fields = ['full_name', 'email', 'phone', 'inn']
    raw_id_fields = ['user', 'manager']
    ordering = ['-created_at']


class RequiredDocumentInline(admin.TabularInline):
    model = RequiredDocument
    extra = 1
    fields = ['name', 'is_required', 'order']


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
    list_display = ['name', 'service', 'is_required', 'order']
    list_filter = ['is_required', 'service']
    list_editable = ['is_required', 'order']
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