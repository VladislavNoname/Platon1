from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.core.validators import FileExtensionValidator
import uuid


class User(AbstractUser):
    """Расширенная модель пользователя"""
    ROLE_CHOICES = (
        ('client', 'Клиент'),
        ('manager', 'Менеджер'),
        ('admin', 'Администратор'),
    )

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='client', verbose_name='Роль')
    email = models.EmailField(unique=True, verbose_name='Email')
    phone = models.CharField(max_length=20, blank=True, verbose_name='Телефон')
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='Группы',
        blank=True,
        related_name="mainapp_user_groups",
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='Права',
        blank=True,
        related_name="mainapp_user_permissions",
        related_query_name="user",
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return f"{self.get_full_name() or self.email} ({self.get_role_display()})"


class Client(models.Model):
    """Модель клиента"""
    TYPE_CHOICES = (
        ('individual', 'Физическое лицо'),
        ('organization', 'Юридическое лицо'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='client_profile',
                                verbose_name='Пользователь')
    client_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='individual',
                                   verbose_name='Тип клиента')
    full_name = models.CharField(max_length=255, verbose_name='ФИО/Наименование')
    phone = models.CharField(max_length=20, verbose_name='Телефон')
    email = models.EmailField(verbose_name='Email')
    inn = models.CharField(max_length=12, blank=True, default='', verbose_name='ИНН')
    kpp = models.CharField(max_length=9, blank=True, default='', verbose_name='КПП')
    legal_address = models.TextField(blank=True, default='', verbose_name='Юридический адрес')
    manager = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='managed_clients', limit_choices_to={'role': 'manager'},
        verbose_name='Менеджер'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} ({self.get_client_type_display()})"


class Service(models.Model):
    """Каталог услуг"""
    name = models.CharField(max_length=255, verbose_name='Название услуги')
    description = models.TextField(default='', blank=True, verbose_name='Описание услуги')
    price_individual = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                           verbose_name='Стоимость для физ. лиц')
    price_organization = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                             verbose_name='Стоимость для юр. лиц')
    default_deadline = models.PositiveIntegerField(default=5, verbose_name='Срок исполнения (дни)')
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Услуга'
        verbose_name_plural = 'Услуги'
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_price_for_client(self, client):
        if client.client_type == 'individual':
            return self.price_individual
        return self.price_organization


class RequiredDocument(models.Model):
    """Обязательные документы для услуги"""
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='required_documents',
                                verbose_name='Услуга')
    name = models.CharField(max_length=255, verbose_name='Название документа')
    is_required = models.BooleanField(default=True, verbose_name='Обязательный')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок')

    class Meta:
        verbose_name = 'Обязательный документ'
        verbose_name_plural = 'Обязательные документы'
        ordering = ['order']

    def __str__(self):
        return f"{self.name} ({'Обязательный' if self.is_required else 'Дополнительный'})"


class ServiceRequest(models.Model):
    """Заявка на услугу"""
    STATUS_CHOICES = (
        ('new', 'Новая'),
        ('awaiting_payment', 'Ожидает оплаты'),
        ('in_progress', 'В работе'),
        ('completed', 'Исполнена'),
        ('rejected', 'Отклонена'),
    )

    number = models.CharField(max_length=20, unique=True, editable=False, verbose_name='Номер заявки')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='requests', verbose_name='Клиент')
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='requests', verbose_name='Услуга')
    manager = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_requests', verbose_name='Менеджер'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', verbose_name='Статус')
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Стоимость')
    deadline = models.DateField(default=timezone.now, verbose_name='Срок исполнения')
    rejection_reason = models.TextField(blank=True, default='', verbose_name='Причина отклонения')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Заявка'
        verbose_name_plural = 'Заявки'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = f"RQ-{uuid.uuid4().hex[:8].upper()}-{timezone.now().strftime('%Y%m%d')}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} - {self.service.name}"


class RequestDocument(models.Model):
    """Документы, прикрепленные к заявке"""
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='documents',
                                verbose_name='Заявка')
    required_document = models.ForeignKey(RequiredDocument, on_delete=models.PROTECT, verbose_name='Тип документа')
    file = models.FileField(
        upload_to='documents/%Y/%m/',
        validators=[FileExtensionValidator(['pdf'])],
        verbose_name='Файл'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата загрузки')

    class Meta:
        verbose_name = 'Документ заявки'
        verbose_name_plural = 'Документы заявок'

    def __str__(self):
        return f"{self.required_document.name} для {self.request.number}"


class RequestHistory(models.Model):
    """История изменений заявки"""
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='history', verbose_name='Заявка')
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Изменил')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Время изменения')
    field_name = models.CharField(max_length=50, blank=True, default='', verbose_name='Поле')
    old_value = models.TextField(blank=True, default='', verbose_name='Старое значение')
    new_value = models.TextField(blank=True, default='', verbose_name='Новое значение')
    comment = models.TextField(blank=True, default='', verbose_name='Комментарий')

    class Meta:
        verbose_name = 'История изменений'
        verbose_name_plural = 'История изменений'
        ordering = ['-timestamp']

    def __str__(self):
        return f"История {self.request.number} - {self.timestamp}"


class Invoice(models.Model):
    """Счет на оплату"""
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='invoices',
                                verbose_name='Заявка')
    number = models.CharField(max_length=50, unique=True, editable=False, verbose_name='Номер счета')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Сумма')
    is_paid = models.BooleanField(default=False, verbose_name='Оплачен')
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата оплаты')
    file = models.FileField(upload_to='invoices/', null=True, blank=True, verbose_name='Файл счета')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')

    class Meta:
        verbose_name = 'Счет'
        verbose_name_plural = 'Счета'

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = f"INV-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Счет {self.number}"


class Notification(models.Model):
    """Уведомления"""
    NOTIFICATION_TYPES = (
        ('registration', 'Регистрация'),
        ('status_change', 'Изменение статуса'),
        ('payment_required', 'Ожидание оплаты'),
        ('completed', 'Заявка выполнена'),
        ('new_request', 'Новая заявка'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', verbose_name='Пользователь')
    notification_type = models.CharField(
        max_length=20, choices=NOTIFICATION_TYPES, default='registration',
        verbose_name='Тип уведомления'
    )
    message = models.TextField(default='', verbose_name='Сообщение')
    is_read = models.BooleanField(default=False, verbose_name='Прочитано')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']

    def __str__(self):
        return f"Уведомление для {self.user.email}"