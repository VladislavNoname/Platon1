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
    User, Service, ServiceRequest,
    RequestHistory, RequestDocument, RequiredDocument,
    Invoice, Notification
)
from .forms import CustomUserCreationForm, ServiceRequestForm


def user_login(request):
    """Авторизация пользователя"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        # Аутентификация по email
        user = authenticate(request, email=email, password=password)

        if user is not None:
            if user.is_active:
                login(request, user)
                messages.success(request, f'Добро пожаловать, {user.full_name or user.email}!')

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
            messages.error(request, 'Неверный email или пароль')

    return render(request, 'mainapp/login.html')


def register(request):
    """Регистрация нового клиента"""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            # Создаем пользователя
            user = form.save(commit=False)
            user.role = 'client'
            user.client_type = form.cleaned_data['client_type']

            if user.client_type == 'organization':
                user.inn = form.cleaned_data.get('inn', '')
                user.kpp = form.cleaned_data.get('kpp', '')
                user.legal_address = form.cleaned_data.get('legal_address', '')

            user.save()

            # ВАЖНО: Устанавливаем backend перед login()
            user.backend = 'mainapp.backends.EmailBackend'

            # Создаем уведомление для всех менеджеров о новом клиенте
            managers = User.objects.filter(role='manager', is_active=True)
            for manager in managers:
                Notification.objects.create(
                    user=manager,
                    notification_type='registration',
                    message=f'Зарегистрирован новый клиент: {user.full_name} ({user.email})'
                )

            # Создаем уведомление для пользователя
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

    if user.role == 'client':
        requests = ServiceRequest.objects.filter(client=user)
    elif user.role == 'manager':
        # Менеджер видит все заявки и своих клиентов
        requests = ServiceRequest.objects.all()
        my_clients = User.objects.filter(role='client', manager=user)
        my_requests = ServiceRequest.objects.filter(manager=user)

        context['my_clients_count'] = my_clients.count()
        context['my_requests_count'] = my_requests.count()
    elif user.role == 'admin':
        requests = ServiceRequest.objects.all()
    else:
        requests = ServiceRequest.objects.none()

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
    """Создание заявки клиентом"""
    if request.user.role != 'client':
        messages.error(request, 'Только клиенты могут создавать заявки')
        return redirect('dashboard')

    if request.method == 'POST':
        form = ServiceRequestForm(request.POST)
        if form.is_valid():
            service = form.cleaned_data['service']
            comment = form.cleaned_data.get('comment', '')

            # Определяем цену в зависимости от типа клиента
            price = service.get_price_for_client(request.user)

            # Создаем заявку
            service_request = ServiceRequest.objects.create(
                client=request.user,
                service=service,
                price=price,
                comment=comment,
                deadline=timezone.now().date() + timedelta(days=service.default_deadline)
            )

            # Создаем запись в истории
            RequestHistory.objects.create(
                request=service_request,
                changed_by=request.user,
                field_name='status',
                new_value='Новая',
                comment=f'Заявка создана. Услуга: {service.name}. Комментарий: {comment}' if comment else f'Заявка создана. Услуга: {service.name}'
            )

            # Уведомление всем менеджерам о новой заявке
            managers = User.objects.filter(role='manager', is_active=True)
            for manager in managers:
                Notification.objects.create(
                    user=manager,
                    notification_type='new_request',
                    message=f'Новая заявка {service_request.number} от клиента {request.user.full_name}'
                )

            # Уведомление менеджеру клиента (если есть)
            if request.user.manager:
                Notification.objects.create(
                    user=request.user.manager,
                    notification_type='new_request',
                    message=f'Новая заявка {service_request.number} от вашего клиента {request.user.full_name}'
                )

            messages.success(request, f'Заявка {service_request.number} успешно создана!')
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

    if user.role == 'client':
        requests = ServiceRequest.objects.filter(client=user)
    elif user.role == 'manager':
        # Менеджер видит ВСЕ заявки
        requests = ServiceRequest.objects.all()
    elif user.role == 'admin':
        requests = ServiceRequest.objects.all()
    else:
        requests = ServiceRequest.objects.none()

    # Фильтрация
    status_filter = request.GET.get('status')
    if status_filter:
        requests = requests.filter(status=status_filter)

    # Поиск по номеру заявки или клиенту
    search = request.GET.get('search')
    if search:
        requests = requests.filter(
            Q(number__icontains=search) |
            Q(client__full_name__icontains=search) |
            Q(service__name__icontains=search)
        )

    return render(request, 'mainapp/request_list.html', {
        'requests': requests.select_related('client', 'service', 'manager').order_by('-created_at')
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
        if service_request.client != user:
            messages.error(request, 'Доступ запрещен')
            return redirect('dashboard')
    # Менеджер и админ видят все заявки

    history = service_request.history.all().order_by('-timestamp')
    documents = service_request.documents.all()
    invoices = service_request.invoices.all()

    # Документы, которые нужно загрузить
    missing_docs = service_request.get_missing_documents()

    return render(request, 'mainapp/request_detail.html', {
        'req': service_request,
        'history': history,
        'documents': documents,
        'invoices': invoices,
        'missing_docs': missing_docs
    })


@login_required
def request_take(request, pk):
    """Менеджер берет заявку в работу"""
    if request.user.role != 'manager':
        messages.error(request, 'Только менеджер может взять заявку в работу')
        return redirect('request_detail', pk=pk)

    service_request = get_object_or_404(ServiceRequest, pk=pk)

    if service_request.manager is not None:
        messages.warning(request, f'Эта заявка уже назначена менеджеру {service_request.manager.full_name}')
        return redirect('request_detail', pk=pk)

    # Назначаем менеджера и меняем статус
    old_status = service_request.get_status_display()
    service_request.manager = request.user
    service_request.status = 'in_progress'
    service_request.save()

    # История
    RequestHistory.objects.create(
        request=service_request,
        changed_by=request.user,
        field_name='manager',
        old_value='Не назначен',
        new_value=request.user.full_name,
        comment='Менеджер взял заявку в работу'
    )

    RequestHistory.objects.create(
        request=service_request,
        changed_by=request.user,
        field_name='status',
        old_value=old_status,
        new_value='В работе'
    )

    # Уведомление клиенту
    Notification.objects.create(
        user=service_request.client,
        notification_type='status_change',
        message=f'Менеджер {request.user.full_name} взял в работу вашу заявку {service_request.number}'
    )

    messages.success(request, f'Вы взяли заявку {service_request.number} в работу')
    return redirect('request_detail', pk=pk)


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
        # Менеджер может менять статус только если заявка назначена ему или никому не назначена
        if service_request.manager and service_request.manager != request.user:
            messages.error(request, 'Вы не можете менять статус чужой заявки. Сначала возьмите её в работу.')
            return redirect('request_detail', pk=pk)

    # Логика переходов статусов
    valid_transitions = {
        'new': ['in_progress', 'rejected'],
        'awaiting_payment': ['in_progress', 'rejected'],
        'in_progress': ['completed', 'rejected'],
        'completed': [],
        'rejected': []
    }

    if new_status in valid_transitions.get(service_request.status, []):
        # Проверка на наличие всех документов при переходе
        if new_status == 'in_progress':
            if not service_request.manager:
                service_request.manager = request.user

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
            user=service_request.client,
            notification_type='status_change',
            message=f'Статус вашей заявки {service_request.number} изменен на "{service_request.get_status_display()}"'
        )

        # Отправляем email
        try:
            send_mail(
                f'Изменение статуса заявки {service_request.number}',
                f'Статус вашей заявки изменен на "{service_request.get_status_display()}"',
                settings.DEFAULT_FROM_EMAIL,
                [service_request.client.email],
                fail_silently=True
            )
        except:
            pass

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
        if service_request.client != request.user:
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

            # Проверка MIME типа
            if file.content_type != 'application/pdf':
                messages.error(request, 'Файл должен быть формата PDF')
                return redirect('request_detail', pk=pk)

            required_doc = get_object_or_404(RequiredDocument, pk=required_doc_id)

            # Проверяем, что документ относится к услуге заявки
            if required_doc.service != service_request.service:
                messages.error(request, 'Этот тип документа не относится к выбранной услуге')
                return redirect('request_detail', pk=pk)

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
    if not service_request.are_all_documents_uploaded():
        missing = service_request.get_missing_documents().values_list('name', flat=True)
        messages.error(request, 'Не все обязательные документы загружены. Требуется загрузить: ' +
                       ', '.join(missing))
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
        new_value='Ожидает оплаты',
        comment=f'Создан счет {invoice.number}'
    )

    # Уведомление клиенту
    Notification.objects.create(
        user=service_request.client,
        notification_type='payment_required',
        message=f'Выставлен счет {invoice.number} на оплату заявки {service_request.number} на сумму {invoice.amount} руб.'
    )

    # Отправляем email со счетом
    try:
        send_mail(
            f'Счет на оплату {invoice.number}',
            f'Выставлен счет на оплату заявки {service_request.number}.\n\n' +
            f'Сумма: {invoice.amount} руб.\n\n' +
            f'Для просмотра счета войдите в личный кабинет.',
            settings.DEFAULT_FROM_EMAIL,
            [service_request.client.email],
            fail_silently=True
        )
    except:
        pass

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

    # Назначаем менеджера, если еще не назначен
    if not service_request.manager:
        service_request.manager = request.user

    service_request.save()

    # История
    RequestHistory.objects.create(
        request=service_request,
        changed_by=request.user,
        field_name='status',
        old_value=old_status,
        new_value='В работе',
        comment='Оплата получена'
    )

    messages.success(request, 'Оплата отмечена')
    return redirect('request_detail', pk=service_request.pk)


@login_required
def client_list(request):
    """Список клиентов"""
    user = request.user

    if user.role == 'manager':
        # Менеджер видит всех клиентов
        clients = User.objects.filter(role='client')
    elif user.role == 'admin':
        clients = User.objects.filter(role='client')
    else:
        clients = User.objects.none()

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
        'clients': clients
    })


@login_required
def assign_client(request, pk):
    """Менеджер берет клиента себе"""
    if request.user.role != 'manager':
        messages.error(request, 'Только менеджер может взять клиента')
        return redirect('client_list')

    client = get_object_or_404(User, pk=pk, role='client')

    if client.manager and client.manager != request.user:
        messages.warning(request, f'Клиент уже закреплен за менеджером {client.manager.full_name}')
    else:
        client.manager = request.user
        client.save()
        messages.success(request, f'Клиент {client.full_name} закреплен за вами')

    return redirect('client_list')


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
    if date_from and date_to:
        manager_load = User.objects.filter(role='manager').annotate(
            request_count=Count('assigned_requests', filter=Q(
                assigned_requests__created_at__gte=date_from,
                assigned_requests__created_at__lte=date_to
            ))
        ).values('full_name', 'email', 'request_count')
    else:
        # Если даты не указаны, показываем за текущий месяц
        today = timezone.now()
        manager_load = User.objects.filter(role='manager').annotate(
            request_count=Count('assigned_requests', filter=Q(
                assigned_requests__created_at__year=today.year,
                assigned_requests__created_at__month=today.month
            ))
        ).values('full_name', 'email', 'request_count')

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