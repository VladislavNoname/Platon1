from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
from django.http import HttpResponse, Http404
import os

from .models import (
    User, Service, ServiceRequest,
    RequestHistory, RequestDocument, RequiredDocument,
    Invoice, Notification
)
from .forms import CustomUserCreationForm, ServiceRequestForm


def user_login(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        user = authenticate(request, email=email, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                messages.success(request, f'Добро пожаловать, {user.full_name or user.email}!')
                return redirect('dashboard')
            else:
                messages.error(request, 'Ваша учетная запись заблокирована')
        else:
            messages.error(request, 'Неверный email или пароль')
    return render(request, 'mainapp/login.html')


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'client'
            user.client_type = form.cleaned_data['client_type']
            if user.client_type == 'organization':
                user.inn = form.cleaned_data.get('inn', '')
                user.kpp = form.cleaned_data.get('kpp', '')
                user.legal_address = form.cleaned_data.get('legal_address', '')
            user.save()
            user.backend = 'mainapp.backends.EmailBackend'
            managers = User.objects.filter(role='manager', is_active=True)
            for manager in managers:
                Notification.objects.create(
                    user=manager,
                    notification_type='registration',
                    message=f'Зарегистрирован новый клиент: {user.full_name} ({user.email})'
                )
            Notification.objects.create(
                user=user,
                notification_type='registration',
                message='Добро пожаловать в Баланс CRM! Ваша учетная запись успешно создана.'
            )
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
    logout(request)
    messages.info(request, 'Вы вышли из системы')
    return redirect('login')


@login_required
def dashboard(request):
    user = request.user
    context = {'user': user}
    if user.role == 'client':
        requests = ServiceRequest.objects.filter(client=user)
    elif user.role == 'manager':
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
    context['notifications'] = Notification.objects.filter(user=user, is_read=False)[:5]
    return render(request, 'mainapp/dashboard.html', context)


@login_required
def request_create(request):
    if request.user.role != 'client':
        messages.error(request, 'Только клиенты могут создавать заявки')
        return redirect('dashboard')
    if request.method == 'POST':
        form = ServiceRequestForm(request.POST)
        if form.is_valid():
            service = form.cleaned_data['service']
            comment = form.cleaned_data.get('comment', '')
            if request.user.client_type == 'individual' and service.for_individuals == False:
                messages.error(request, 'Эта услуга недоступна для физических лиц')
                return redirect('request_create')
            if request.user.client_type == 'organization' and service.for_organizations == False:
                messages.error(request, 'Эта услуга недоступна для юридических лиц')
            price = service.get_price_for_client(request.user)
            service_request = ServiceRequest.objects.create(
                client=request.user,
                service=service,
                price=price,
                comment=comment,
                deadline=timezone.now().date() + timedelta(days=service.default_deadline)
            )
            RequestHistory.objects.create(
                request=service_request,
                changed_by=request.user,
                field_name='status',
                new_value='Новая',
                comment=f'Заявка создана. Услуга: {service.name}. Комментарий: {comment}' if comment else f'Заявка создана. Услуга: {service.name}'
            )
            managers = User.objects.filter(role='manager', is_active=True)
            for manager in managers:
                Notification.objects.create(
                    user=manager,
                    notification_type='new_request',
                    message=f'Новая заявка {service_request.number} от клиента {request.user.full_name}'
                )
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
    if request.user.client_type == 'individual':
        services = Service.objects.filter(is_active=True, for_individuals=True)
    else:
        services = Service.objects.filter(is_active=True, for_organizations=True)
    return render(request, 'mainapp/request_form.html', {'form': form, 'services': services})


@login_required
def request_list(request):
    user = request.user
    if user.role == 'client':
        requests = ServiceRequest.objects.filter(client=user)
    elif user.role == 'manager':
        requests = ServiceRequest.objects.all()
    elif user.role == 'admin':
        requests = ServiceRequest.objects.all()
    else:
        requests = ServiceRequest.objects.none()
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
    service_request = get_object_or_404(
        ServiceRequest.objects.select_related('client', 'service', 'manager'),
        pk=pk
    )
    user = request.user
    if user.role == 'client':
        if service_request.client != user:
            messages.error(request, 'Доступ запрещен')
            return redirect('dashboard')
    history = service_request.history.all().order_by('-timestamp')
    documents = service_request.documents.all()
    invoices = service_request.invoices.all()
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
    if request.user.role != 'manager':
        messages.error(request, 'Только менеджер может взять заявку в работу')
        return redirect('request_detail', pk=pk)
    service_request = get_object_or_404(ServiceRequest, pk=pk)
    if service_request.manager is not None:
        messages.warning(request, f'Эта заявка уже назначена менеджеру {service_request.manager.full_name}')
        return redirect('request_detail', pk=pk)
    old_status = service_request.get_status_display()
    service_request.manager = request.user
    service_request.status = 'in_progress'
    service_request.save()
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
    Notification.objects.create(
        user=service_request.client,
        notification_type='status_change',
        message=f'Менеджер {request.user.full_name} взял в работу вашу заявку {service_request.number}'
    )
    messages.success(request, f'Вы взяли заявку {service_request.number} в работу')
    return redirect('request_detail', pk=pk)


@login_required
def request_change_status(request, pk, new_status):
    if request.user.role not in ['manager', 'admin']:
        messages.error(request, 'Недостаточно прав')
        return redirect('request_detail', pk=pk)
    service_request = get_object_or_404(ServiceRequest, pk=pk)
    old_status = service_request.get_status_display()
    if request.user.role == 'manager':
        if service_request.manager and service_request.manager != request.user:
            messages.error(request, 'Вы не можете менять статус чужой заявки')
            return redirect('request_detail', pk=pk)
    valid_transitions = {
        'new': ['in_progress', 'rejected'],
        'awaiting_payment': ['in_progress', 'rejected'],
        'in_progress': ['completed', 'rejected'],
        'completed': [],
        'rejected': []
    }
    if new_status in valid_transitions.get(service_request.status, []):
        if new_status == 'in_progress':
            if not service_request.manager:
                service_request.manager = request.user
        service_request.status = new_status
        if new_status == 'rejected':
            service_request.rejection_reason = request.POST.get('reason', '')
        service_request.save()
        RequestHistory.objects.create(
            request=service_request,
            changed_by=request.user,
            field_name='status',
            old_value=old_status,
            new_value=service_request.get_status_display(),
            comment=request.POST.get('comment', '')
        )
        Notification.objects.create(
            user=service_request.client,
            notification_type='status_change',
            message=f'Статус вашей заявки {service_request.number} изменен на "{service_request.get_status_display()}"'
        )
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
    service_request = get_object_or_404(ServiceRequest, pk=pk)
    if request.user.role == 'client':
        if service_request.client != request.user:
            messages.error(request, 'Доступ запрещен')
            return redirect('dashboard')
    if request.method == 'POST':
        required_doc_id = request.POST.get('required_document')
        file = request.FILES.get('file')
        if file and required_doc_id:
            if file.size > 10 * 1024 * 1024:
                messages.error(request, 'Размер файла не должен превышать 10 МБ')
                return redirect('request_detail', pk=pk)
            if not file.name.lower().endswith('.pdf'):
                messages.error(request, 'Допустимы только PDF файлы')
                return redirect('request_detail', pk=pk)
            required_doc = get_object_or_404(RequiredDocument, pk=required_doc_id)
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
    if request.user.role not in ['manager', 'admin']:
        messages.error(request, 'Недостаточно прав')
        return redirect('request_detail', pk=pk)
    service_request = get_object_or_404(ServiceRequest, pk=pk)
    if not service_request.are_all_documents_uploaded():
        missing = service_request.get_missing_documents().values_list('name', flat=True)
        messages.error(request, 'Не все обязательные документы загружены. Требуется загрузить: ' +
                       ', '.join(missing))
        return redirect('request_detail', pk=pk)
    existing_invoice = service_request.invoices.filter(is_paid=False).first()
    if existing_invoice:
        messages.warning(request, f'Уже есть неоплаченный счет {existing_invoice.number}')
        return redirect('request_detail', pk=pk)
    invoice = Invoice.objects.create(
        request=service_request,
        amount=service_request.price
    )
    old_status = service_request.get_status_display()
    service_request.status = 'awaiting_payment'
    service_request.save()
    RequestHistory.objects.create(
        request=service_request,
        changed_by=request.user,
        field_name='status',
        old_value=old_status,
        new_value='Ожидает оплаты',
        comment=f'Создан счет {invoice.number}'
    )
    Notification.objects.create(
        user=service_request.client,
        notification_type='payment_required',
        message=f'Выставлен счет {invoice.number} на оплату заявки {service_request.number} на сумму {invoice.amount} руб.'
    )
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
    if request.user.role not in ['manager', 'admin']:
        messages.error(request, 'Недостаточно прав')
        return redirect('request_detail', pk=pk)
    invoice = get_object_or_404(Invoice, pk=pk)
    if invoice.is_paid:
        messages.warning(request, 'Этот счет уже оплачен')
        return redirect('request_detail', pk=invoice.request.pk)
    invoice.is_paid = True
    invoice.paid_at = timezone.now()
    invoice.save()
    service_request = invoice.request
    old_status = service_request.get_status_display()
    service_request.status = 'in_progress'
    if not service_request.manager:
        service_request.manager = request.user
    service_request.save()
    RequestHistory.objects.create(
        request=service_request,
        changed_by=request.user,
        field_name='status',
        old_value=old_status,
        new_value='В работе',
        comment=f'Оплата по счету {invoice.number} подтверждена'
    )
    Notification.objects.create(
        user=service_request.client,
        notification_type='status_change',
        message=f'Оплата по счету {invoice.number} подтверждена. Заявка {service_request.number} перешла в статус "В работе"'
    )
    messages.success(request, 'Оплата подтверждена')
    return redirect('request_detail', pk=service_request.pk)


@login_required
def mark_completed(request, pk):
    if request.user.role not in ['manager', 'admin']:
        messages.error(request, 'Недостаточно прав')
        return redirect('request_detail', pk=pk)
    service_request = get_object_or_404(ServiceRequest, pk=pk)
    if service_request.status != 'in_progress':
        messages.error(request, 'Заявка должна быть в статусе "В работе"')
        return redirect('request_detail', pk=pk)
    old_status = service_request.get_status_display()
    service_request.status = 'completed'
    service_request.save()
    RequestHistory.objects.create(
        request=service_request,
        changed_by=request.user,
        field_name='status',
        old_value=old_status,
        new_value='Выполнена',
        comment='Заявка выполнена'
    )
    Notification.objects.create(
        user=service_request.client,
        notification_type='completed',
        message=f'Заявка {service_request.number} выполнена'
    )
    messages.success(request, 'Заявка отмечена как выполненная')
    return redirect('request_detail', pk=pk)


@login_required
def client_list(request):
    user = request.user
    if user.role == 'manager':
        clients = User.objects.filter(role='client')
    elif user.role == 'admin':
        clients = User.objects.filter(role='client')
    else:
        clients = User.objects.none()
    search = request.GET.get('search')
    if search:
        clients = clients.filter(
            Q(full_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search) |
            Q(inn__icontains=search)
        )
    return render(request, 'mainapp/client_list.html', {'clients': clients})


@login_required
def assign_client(request, pk):
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
        status_key = item['status'] + '_count'
        if status_key in reports_data:
            reports_data[status_key] = item['count']

    reports_data['total_count'] = sum(reports_data.values())

    # Среднее время обработки (для выполненных заявок)
    completed_requests = ServiceRequest.objects.filter(status='completed', **filters)

    avg_time_seconds = 0
    avg_time_hours = 0
    for req in completed_requests:
        completed_history = req.history.filter(field_name='status', new_value='Выполнена').first()
        if completed_history:
            time_diff = completed_history.timestamp - req.created_at
            avg_time_seconds += time_diff.total_seconds()

    if completed_requests.count() > 0:
        avg_time_seconds = avg_time_seconds / completed_requests.count()
        avg_time_hours = round(avg_time_seconds / 3600, 1)

    # Загрузка менеджеров
    manager_load = []
    managers = User.objects.filter(role='manager')
    for manager in managers:
        manager_filters = {'manager': manager}
        if date_from:
            manager_filters['created_at__gte'] = date_from
        if date_to:
            manager_filters['created_at__lte'] = date_to
        request_count = ServiceRequest.objects.filter(**manager_filters).count()
        if not date_from and not date_to:
            today = timezone.now()
            request_count = ServiceRequest.objects.filter(
                manager=manager,
                created_at__year=today.year,
                created_at__month=today.month
            ).count()
        if request_count > 0 or manager.full_name:
            manager_load.append({
                'name': manager.full_name or manager.email,
                'count': request_count
            })

    # Финансовые показатели — считаем по ценам заявок, а не по счетам
    request_filters = {}
    if date_from:
        request_filters['created_at__gte'] = date_from
    if date_to:
        request_filters['created_at__lte'] = date_to

    total_sum = ServiceRequest.objects.filter(
        status__in=['awaiting_payment', 'in_progress', 'completed'], **request_filters
    ).aggregate(total=Sum('price'))['total']
    total_invoices = float(total_sum) if total_sum is not None else 0

    paid_sum = ServiceRequest.objects.filter(
        status='completed', **request_filters
    ).aggregate(total=Sum('price'))['total']
    paid_invoices = float(paid_sum) if paid_sum is not None else 0

    return render(request, 'mainapp/reports.html', {
        'reports': reports_data,
        'avg_time_hours': avg_time_hours,
        'manager_load': manager_load,
        'total_invoices': total_invoices,
        'paid_invoices': paid_invoices,
        'date_from': date_from,
        'date_to': date_to
    })


@login_required
def serve_document(request, pk):
    """Просмотр PDF документа прямо в браузере"""
    doc = get_object_or_404(RequestDocument, pk=pk)
    if request.user.role == 'client' and doc.request.client != request.user:
        raise Http404
    file_path = doc.file.path
    if not os.path.exists(file_path):
        raise Http404
    with open(file_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(file_path)}"'
        return response


@login_required
def mark_notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save()
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))