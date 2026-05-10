from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta

from .models import (
    User, Client, Service, ServiceRequest,
    RequestHistory, RequestDocument, RequiredDocument,
    Invoice, Notification
)
from .forms import CustomUserCreationForm, ServiceRequestForm


def user_login(request):
    """Авторизация пользователя"""
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        print(f"Попытка входа: {email}")  # Для отладки

        # Аутентификация по email
        user = authenticate(request, email=email, password=password)

        if user is not None:
            if user.is_active:
                login(request, user)
                messages.success(request, f'Добро пожаловать, {user.email}!')

                # Перенаправление в зависимости от роли
                if user.role == 'admin':
                    return redirect('dashboard')
                elif user.role == 'manager':
                    return redirect('dashboard')
                else:
                    return redirect('dashboard')
            else:
                messages.error(request, 'Ваша учетная запись заблокирована')
        else:
            print("Ошибка аутентификации")  # Для отладки
            messages.error(request, 'Неверный email или пароль')

    return render(request, 'mainapp/login.html')


def register(request):
    """Регистрация нового клиента"""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            # Создаем пользователя
            user = User.objects.create_user(
                email=form.cleaned_data['email'],
                username=form.cleaned_data['email'].split('@')[0],
                password=form.cleaned_data['password1'],
                role='client',
                first_name=form.cleaned_data['full_name'],
                phone=form.cleaned_data['phone']
            )

            # Устанавливаем backend для пользователя
            user.backend = 'mainapp.backends.EmailBackend'

            # Создаем профиль клиента
            Client.objects.create(
                user=user,
                client_type=form.cleaned_data['client_type'],
                full_name=form.cleaned_data['full_name'],
                phone=form.cleaned_data['phone'],
                email=form.cleaned_data['email'],
                inn=form.cleaned_data.get('inn', ''),
                kpp=form.cleaned_data.get('kpp', ''),
                legal_address=form.cleaned_data.get('legal_address', '')
            )

            # Создаем уведомление
            Notification.objects.create(
                user=user,
                notification_type='registration',
                message='Добро пожаловать в Platon CRM! Ваша учетная запись успешно создана.'
            )

            # Авторизуем пользователя
            login(request, user)
            messages.success(request, 'Регистрация успешна!')
            return redirect('dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = CustomUserCreationForm()

    return render(request, 'mainapp/register.html', {'form': form})


@login_required
def user_logout(request):
    """Выход из системы"""
    logout(request)
    messages.info(request, 'Вы вышли из системы')
    return redirect('login')


@login_required
def dashboard(request):
    """Панель управления"""
    user = request.user
    context = {'user': user}

    if user.role == 'client' and hasattr(user, 'client_profile'):
        requests = ServiceRequest.objects.filter(client=user.client_profile)
        context['requests'] = requests.order_by('-created_at')[:10]
        context['total_requests'] = requests.count()
        context['new_count'] = requests.filter(status='new').count()
        context['in_progress_count'] = requests.filter(status='in_progress').count()
        context['completed_count'] = requests.filter(status='completed').count()

    elif user.role == 'manager':
        requests = ServiceRequest.objects.filter(client__manager=user)
        context['requests'] = requests.order_by('-created_at')[:10]
        context['total_requests'] = requests.count()
        context['new_count'] = requests.filter(status='new').count()
        context['in_progress_count'] = requests.filter(status='in_progress').count()
        context['completed_count'] = requests.filter(status='completed').count()

    elif user.role == 'admin':
        requests = ServiceRequest.objects.all()
        context['requests'] = requests.order_by('-created_at')[:10]
        context['total_requests'] = requests.count()
        context['new_count'] = requests.filter(status='new').count()
        context['in_progress_count'] = requests.filter(status='in_progress').count()
        context['completed_count'] = requests.filter(status='completed').count()

    # Уведомления
    context['notifications'] = Notification.objects.filter(
        user=user,
        is_read=False
    )[:5]

    return render(request, 'mainapp/dashboard.html', context)


@login_required
def request_create(request):
    """Создание заявки"""
    if not hasattr(request.user, 'client_profile'):
        messages.error(request, 'У вас нет профиля клиента')
        return redirect('dashboard')

    if request.method == 'POST':
        form = ServiceRequestForm(request.POST)
        if form.is_valid():
            client = request.user.client_profile
            service = form.cleaned_data['service']

            # Определяем цену в зависимости от типа клиента
            price = service.get_price_for_client(client)

            # Создаем заявку
            service_request = ServiceRequest.objects.create(
                client=client,
                service=service,
                price=price,
                deadline=timezone.now().date() + timedelta(days=service.default_deadline)
            )

            # Создаем запись в истории
            RequestHistory.objects.create(
                request=service_request,
                changed_by=request.user,
                field_name='status',
                new_value='Новая'
            )

            messages.success(request, f'Заявка {service_request.number} создана!')
            return redirect('request_detail', pk=service_request.pk)
    else:
        form = ServiceRequestForm()

    # Показываем только активные услуги
    services = Service.objects.filter(is_active=True)

    return render(request, 'mainapp/request_form.html', {
        'form': form,
        'services': services
    })


@login_required
def request_list(request):
    """Список заявок"""
    user = request.user

    if user.role == 'client' and hasattr(user, 'client_profile'):
        requests = ServiceRequest.objects.filter(client=user.client_profile)
    elif user.role == 'manager':
        requests = ServiceRequest.objects.filter(client__manager=user)
    elif user.role == 'admin':
        requests = ServiceRequest.objects.all()
    else:
        requests = ServiceRequest.objects.none()

    # Фильтрация
    status_filter = request.GET.get('status')
    if status_filter:
        requests = requests.filter(status=status_filter)

    return render(request, 'mainapp/request_list.html', {
        'requests': requests.select_related('client', 'service', 'manager')
    })


@login_required
def request_detail(request, pk):
    """Детали заявки"""
    service_request = get_object_or_404(
        ServiceRequest.objects.select_related('client', 'service', 'manager'),
        pk=pk
    )

    # Проверка доступа
    user = request.user
    if user.role == 'client':
        if not hasattr(user, 'client_profile') or service_request.client != user.client_profile:
            messages.error(request, 'Доступ запрещен')
            return redirect('dashboard')
    elif user.role == 'manager':
        if service_request.client.manager != user:
            messages.error(request, 'Доступ запрещен')
            return redirect('dashboard')

    history = service_request.history.all().order_by('-timestamp')
    documents = service_request.documents.all()
    invoices = service_request.invoices.all()

    # Проверяем, все ли обязательные документы загружены
    required_docs = service_request.service.required_documents.filter(is_required=True)
    uploaded_docs = documents.values_list('required_document_id', flat=True)
    missing_docs = required_docs.exclude(id__in=uploaded_docs)

    return render(request, 'mainapp/request_detail.html', {
        'req': service_request,
        'history': history,
        'documents': documents,
        'invoices': invoices,
        'missing_docs': missing_docs
    })


@login_required
def request_change_status(request, pk, new_status):
    """Изменение статуса заявки"""
    if request.user.role not in ['manager', 'admin']:
        messages.error(request, 'Недостаточно прав')
        return redirect('request_detail', pk=pk)

    service_request = get_object_or_404(ServiceRequest, pk=pk)
    old_status = service_request.get_status_display()

    # Проверка доступа для менеджера
    if request.user.role == 'manager':
        if service_request.client.manager != request.user:
            messages.error(request, 'Доступ запрещен')
            return redirect('dashboard')

    # Логика переходов статусов
    valid_transitions = {
        'new': ['awaiting_payment', 'rejected'],
        'awaiting_payment': ['in_progress', 'rejected'],
        'in_progress': ['completed', 'rejected'],
        'completed': [],
        'rejected': []
    }

    if new_status in valid_transitions.get(service_request.status, []):
        service_request.status = new_status

        if new_status == 'rejected':
            service_request.rejection_reason = request.POST.get('reason', '')

        service_request.save()

        # Создаем запись в истории
        RequestHistory.objects.create(
            request=service_request,
            changed_by=request.user,
            field_name='status',
            old_value=old_status,
            new_value=service_request.get_status_display(),
            comment=request.POST.get('comment', '')
        )

        # Создаем уведомление для клиента
        Notification.objects.create(
            user=service_request.client.user,
            notification_type='status_change',
            message=f'Статус вашей заявки {service_request.number} изменен на "{service_request.get_status_display()}"'
        )

        # Отправляем email
        send_mail(
            f'Изменение статуса заявки {service_request.number}',
            f'Статус вашей заявки изменен на "{service_request.get_status_display()}"',
            settings.DEFAULT_FROM_EMAIL,
            [service_request.client.email],
            fail_silently=True
        )

        messages.success(request, f'Статус изменен на "{service_request.get_status_display()}"')
    else:
        messages.error(request, 'Недопустимый переход статуса')

    return redirect('request_detail', pk=pk)


@login_required
def upload_document(request, pk):
    """Загрузка документа к заявке"""
    service_request = get_object_or_404(ServiceRequest, pk=pk)

    # Проверка доступа
    if request.user.role == 'client':
        if not hasattr(request.user, 'client_profile') or service_request.client != request.user.client_profile:
            messages.error(request, 'Доступ запрещен')
            return redirect('dashboard')

    if request.method == 'POST':
        required_doc_id = request.POST.get('required_document')
        file = request.FILES.get('file')

        if file and required_doc_id:
            # Проверка размера файла (10 МБ)
            if file.size > 10 * 1024 * 1024:
                messages.error(request, 'Размер файла не должен превышать 10 МБ')
                return redirect('request_detail', pk=pk)

            # Проверка типа файла
            if not file.name.lower().endswith('.pdf'):
                messages.error(request, 'Допустимы только PDF файлы')
                return redirect('request_detail', pk=pk)

            required_doc = get_object_or_404(RequiredDocument, pk=required_doc_id)

            RequestDocument.objects.create(
                request=service_request,
                required_document=required_doc,
                file=file
            )

            messages.success(request, 'Документ загружен')
        else:
            messages.error(request, 'Выберите тип документа и файл')

    return redirect('request_detail', pk=pk)


@login_required
def create_invoice(request, pk):
    """Создание счета на оплату"""
    if request.user.role not in ['manager', 'admin']:
        messages.error(request, 'Недостаточно прав')
        return redirect('request_detail', pk=pk)

    service_request = get_object_or_404(ServiceRequest, pk=pk)

    # Проверяем, что все обязательные документы загружены
    missing_docs = service_request.service.required_documents.filter(
        is_required=True
    ).exclude(
        id__in=service_request.documents.values_list('required_document_id', flat=True)
    )

    if missing_docs.exists():
        messages.error(request, 'Не все обязательные документы загружены')
        return redirect('request_detail', pk=pk)

    # Создаем счет
    invoice = Invoice.objects.create(
        request=service_request,
        amount=service_request.price
    )

    # Меняем статус заявки
    old_status = service_request.get_status_display()
    service_request.status = 'awaiting_payment'
    service_request.save()

    # История
    RequestHistory.objects.create(
        request=service_request,
        changed_by=request.user,
        field_name='status',
        old_value=old_status,
        new_value='Ожидает оплаты'
    )

    # Уведомление клиенту
    Notification.objects.create(
        user=service_request.client.user,
        notification_type='payment_required',
        message=f'Выставлен счет {invoice.number} на оплату заявки {service_request.number}'
    )

    # Отправляем email со счетом
    send_mail(
        f'Счет на оплату {invoice.number}',
        f'Выставлен счет на оплату заявки {service_request.number}. Сумма: {invoice.amount} руб.',
        settings.DEFAULT_FROM_EMAIL,
        [service_request.client.email],
        fail_silently=True
    )

    messages.success(request, f'Счет {invoice.number} создан')
    return redirect('request_detail', pk=pk)


@login_required
def mark_payment(request, pk):
    """Отметка об оплате"""
    if request.user.role not in ['manager', 'admin']:
        messages.error(request, 'Недостаточно прав')
        return redirect('request_detail', pk=pk)

    invoice = get_object_or_404(Invoice, pk=pk)
    invoice.is_paid = True
    invoice.paid_at = timezone.now()
    invoice.save()

    # Меняем статус заявки
    service_request = invoice.request
    old_status = service_request.get_status_display()
    service_request.status = 'in_progress'
    service_request.save()

    # История
    RequestHistory.objects.create(
        request=service_request,
        changed_by=request.user,
        field_name='status',
        old_value=old_status,
        new_value='В работе'
    )

    messages.success(request, 'Оплата отмечена')
    return redirect('request_detail', pk=service_request.pk)


@login_required
def client_list(request):
    """Список клиентов"""
    user = request.user

    if user.role == 'manager':
        clients = Client.objects.filter(manager=user)
    elif user.role == 'admin':
        clients = Client.objects.all()
    else:
        clients = Client.objects.none()

    # Поиск
    search = request.GET.get('search')
    if search:
        clients = clients.filter(
            Q(full_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search) |
            Q(inn__icontains=search)
        )

    return render(request, 'mainapp/client_list.html', {
        'clients': clients.select_related('manager')
    })


@login_required
def reports(request):
    """Отчеты (только для администраторов)"""
    if request.user.role != 'admin':
        messages.error(request, 'Доступ запрещен')
        return redirect('dashboard')

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    filters = {}
    if date_from:
        filters['created_at__gte'] = date_from
    if date_to:
        filters['created_at__lte'] = date_to

    # Статистика по статусам
    status_stats = ServiceRequest.objects.filter(**filters).values('status').annotate(
        count=Count('id')
    )

    reports_data = {
        'new_count': 0,
        'awaiting_payment_count': 0,
        'in_progress_count': 0,
        'completed_count': 0,
        'rejected_count': 0,
    }

    for item in status_stats:
        reports_data[item['status'] + '_count'] = item['count']

    # Финансовые показатели
    invoices = Invoice.objects.filter(**filters)
    total_amount = invoices.aggregate(total=Sum('amount'))['total'] or 0
    paid_amount = invoices.filter(is_paid=True).aggregate(total=Sum('amount'))['total'] or 0

    # Загрузка менеджеров
    manager_load = User.objects.filter(role='manager').annotate(
        request_count=Count('assigned_requests', filter=models.Q(
            assigned_requests__created_at__gte=date_from if date_from else timezone.now().replace(day=1),
            assigned_requests__created_at__lte=date_to if date_to else timezone.now()
        ))
    ).values('first_name', 'email', 'request_count')

    return render(request, 'mainapp/reports.html', {
        'reports': reports_data,
        'total_amount': total_amount,
        'paid_amount': paid_amount,
        'manager_load': manager_load,
        'date_from': date_from,
        'date_to': date_to
    })


@login_required
def mark_notification_read(request, pk):
    """Отметить уведомление как прочитанное"""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save()
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))