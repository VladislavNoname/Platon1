from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.core.validators import FileExtensionValidator
import uuid


class UserManager(BaseUserManager):
    """Менеджер пользователей с email аутентификацией"""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email обязателен')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Расширенная модель пользователя с ролями"""

    ROLE_CHOICES = (
        ('client', 'Клиент'),
        ('manager', 'Менеджер'),
        ('admin', 'Администратор'),
    )

    CLIENT_TYPE_CHOICES = (
        (None, 'Не клиент'),
        ('individual', 'Физическое лицо'),
        ('organization', 'Юридическое лицо'),
    )

    email = models.EmailField(unique=True, verbose_name='Email')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, verbose_name='Роль')

    # Общие поля
    full_name = models.CharField(max_length=255, verbose_name='ФИО/Наименование', blank=True)
    phone = models.CharField(max_length=20, blank=True, verbose_name='Телефон')

    # Поля для клиентов
    client_type = models.CharField(max_length=20, choices=CLIENT_TYPE_CHOICES,
                                   null=True, blank=True, verbose_name='Тип клиента')
    inn = models.CharField(max_length=12, blank=True, default='', verbose_name='ИНН')
    kpp = models.CharField(max_length=9, blank=True, default='', verbose_name='КПП')
    legal_address = models.TextField(blank=True, default='', verbose_name='Юридический адрес')

    # Связь с менеджером
    manager = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='managed_clients', limit_choices_to={'role': 'manager'},
        verbose_name='Менеджер'
    )

    is_active = models.BooleanField(default=True, verbose_name='Активен')
    is_staff = models.BooleanField(default=False, verbose_name='Сотрудник')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name or self.email} ({self.get_role_display()})"

    def get_full_name(self):
        return self.full_name or self.email

    def get_short_name(self):
        return self.full_name.split()[0] if self.full_name else self.email

    def is_client(self):
        return self.role == 'client'

    def is_manager(self):
        return self.role == 'manager'

    def is_admin(self):
        return self.role == 'admin'


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
    for_individuals = models.BooleanField(default=True, verbose_name='Доступна для физ. лиц')
    for_organizations = models.BooleanField(default=True, verbose_name='Доступна для юр. лиц')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Услуга'
        verbose_name_plural = 'Услуги'
        ordering = ['name']

    def __str__(self):
        return f"{self.name}"

    def get_price_for_client(self, client):
        """Возвращает цену в зависимости от типа клиента"""
        if client.client_type == 'individual':
            return self.price_individual
        return self.price_organization


class RequiredDocument(models.Model):
    """Обязательные документы для услуги - все документы обязательные"""
    service = models.ForeignKey(Service, on_delete=models.CASCADE,
                                related_name='required_documents',
                                verbose_name='Услуга')
    name = models.CharField(max_length=255, verbose_name='Название документа')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок')

    class Meta:
        verbose_name = 'Обязательный документ'
        verbose_name_plural = 'Обязательные документы'
        ordering = ['order']

    def __str__(self):
        return self.name


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
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requests',
                               limit_choices_to={'role': 'client'}, verbose_name='Клиент')
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='requests',
                                verbose_name='Услуга')
    manager = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_requests', limit_choices_to={'role': 'manager'},
        verbose_name='Менеджер'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', verbose_name='Статус')
    comment = models.TextField(blank=True, default='', verbose_name='Комментарий клиента')
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

    def get_required_documents(self):
        return self.service.required_documents.all()  # все документы обязательные

    def get_missing_documents(self):
        required_docs = self.get_required_documents()
        uploaded_docs = self.documents.values_list('required_document_id', flat=True)
        return required_docs.exclude(id__in=uploaded_docs)

    def are_all_documents_uploaded(self):
        return not self.get_missing_documents().exists()


class RequestDocument(models.Model):
    """Документы, прикрепленные к заявке"""
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE,
                                related_name='documents', verbose_name='Заявка')
    required_document = models.ForeignKey(RequiredDocument, on_delete=models.PROTECT,
                                          verbose_name='Тип документа')
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
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE,
                                related_name='history', verbose_name='Заявка')
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
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE,
                                related_name='invoices', verbose_name='Заявка')
    number = models.CharField(max_length=50, unique=True, editable=False, verbose_name='Номер счета')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Сумма')
    is_paid = models.BooleanField(default=False, verbose_name='Оплачен')
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата оплаты')
    file = models.FileField(upload_to='invoices/', null=True, blank=True, verbose_name='Файл счета')
    payment_proof = models.FileField(upload_to='payment_proofs/', null=True, blank=True, verbose_name='Подтверждение оплаты')
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

    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='notifications', verbose_name='Пользователь')
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