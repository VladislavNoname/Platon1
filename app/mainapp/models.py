from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import uuid

class User(AbstractUser):
    ROLE_CHOICES = (
        ('client', 'Клиент'),
        ('manager', 'Менеджер'),
        ('admin', 'Администратор'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='client')
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    telegram_id = models.CharField(max_length=50, blank=True)

    # Фикс для избежания конфликтов с related_name
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name="mainapp_user_groups",
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name="mainapp_user_permissions",
        related_query_name="user",
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"

class Client(models.Model):
    TYPE_CHOICES = (
        ('individual', 'Физическое лицо'),
        ('organization', 'Организация'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='client_profile')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='individual')
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    organization_name = models.CharField(max_length=255, blank=True)
    legal_details = models.TextField(blank=True, verbose_name='Юридические реквизиты')
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='managed_clients', limit_choices_to={'role': 'manager'})
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name

class ServiceRequest(models.Model):
    STATUS_CHOICES = (
        ('new', 'Новая'),
        ('in_progress', 'В работе'),
        ('on_approval', 'На согласовании'),
        ('completed', 'Выполнена'),
        ('rejected', 'Отклонена'),
    )
    PRIORITY_CHOICES = (
        ('low', 'Низкий'),
        ('medium', 'Средний'),
        ('high', 'Высокий'),
        ('critical', 'Критический'),
    )
    number = models.CharField(max_length=20, unique=True, editable=False)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='requests')
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_requests')
    responsible = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='responsible_for')
    topic = models.CharField(max_length=255)
    description = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = f"RQ-{uuid.uuid4().hex[:8].upper()}-{timezone.now().strftime('%Y%m%d')}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} - {self.topic}"

class RequestHistory(models.Model):
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='history')
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    field_name = models.CharField(max_length=50, blank=True)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    comment = models.TextField(blank=True)

class Task(models.Model):
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='tasks', null=True, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_date = models.DateTimeField()
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class Document(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='documents', null=True, blank=True)
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='documents', null=True, blank=True)
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

class Invoice(models.Model):
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='invoices')
    number = models.CharField(max_length=50, unique=True, editable=False)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    issued_at = models.DateTimeField(default=timezone.now)
    paid = models.BooleanField(default=False)
    file = models.FileField(upload_to='invoices/', null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = f"INV-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)