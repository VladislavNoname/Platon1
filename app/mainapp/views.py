from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.db.models import Q
from .models import User, Client, ServiceRequest, RequestHistory, Task
from .forms import ServiceRequestForm, TaskForm


# -------------------------- АВТОРИЗАЦИЯ --------------------------
def user_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.email}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Неверный email или пароль')
    return render(request, 'mainapp/login.html')


def user_logout(request):
    logout(request)
    messages.info(request, 'Вы вышли из системы')
    return redirect('login')


# -------------------------- ДАШБОРД --------------------------
@login_required
def dashboard(request):
    user = request.user
    requests = ServiceRequest.objects.none()

    try:
        if user.role == 'client' and hasattr(user, 'client_profile'):
            requests = ServiceRequest.objects.filter(client=user.client_profile)
        elif user.role == 'manager':
            requests = ServiceRequest.objects.filter(client__manager=user)
        elif user.role == 'admin':
            requests = ServiceRequest.objects.all()
    except Exception:
        messages.warning(request, 'Ошибка загрузки данных.')

    # Исправляем подсчеты
    context = {
        'requests': requests,
        'new_count': requests.filter(status='new').count(),
        'in_progress_count': requests.filter(status='in_progress').count(),
        'completed_count': requests.filter(status='completed').count(),
    }
    return render(request, 'mainapp/dashboard.html', context)


# -------------------------- ЗАЯВКИ --------------------------
@login_required
def request_list(request):
    user = request.user
    requests = ServiceRequest.objects.all()

    if user.role == 'client' and hasattr(user, 'client_profile'):
        requests = requests.filter(client=user.client_profile)
    elif user.role == 'manager':
        requests = requests.filter(client__manager=user)
    elif user.role != 'admin':
        requests = ServiceRequest.objects.none()

    status_filter = request.GET.get('status')
    priority_filter = request.GET.get('priority')
    if status_filter:
        requests = requests.filter(status=status_filter)
    if priority_filter:
        requests = requests.filter(priority=priority_filter)
    return render(request, 'mainapp/request_list.html', {'requests': requests})


@login_required
def request_detail(request, pk):
    req = get_object_or_404(ServiceRequest, pk=pk)
    history = req.history.all().order_by('-timestamp')
    return render(request, 'mainapp/request_detail.html', {
        'req': req,
        'history': history
    })


@login_required
def request_create(request):
    if not hasattr(request.user, 'client_profile'):
        messages.error(request, 'У вас нет профиля клиента.')
        return redirect('dashboard')
    if request.method == 'POST':
        form = ServiceRequestForm(request.POST)
        if form.is_valid():
            req = form.save(commit=False)
            req.client = request.user.client_profile
            req.save()
            messages.success(request, f'Заявка {req.number} создана!')
            return redirect('request_detail', pk=req.pk)
    else:
        form = ServiceRequestForm()
    return render(request, 'mainapp/request_form.html', {'form': form})


@login_required
def request_change_status(request, pk, new_status):
    if request.user.role not in ['manager', 'admin']:
        messages.error(request, 'Недостаточно прав')
        return redirect('request_detail', pk=pk)
    req = get_object_or_404(ServiceRequest, pk=pk)
    old_status = req.get_status_display()
    req.status = new_status
    req.save()
    RequestHistory.objects.create(
        request=req,
        changed_by=request.user,
        field_name='status',
        old_value=old_status,
        new_value=req.get_status_display()
    )
    messages.success(request, f'Статус изменён на "{req.get_status_display()}"')
    return redirect('request_detail', pk=pk)


# -------------------------- КЛИЕНТЫ --------------------------
@login_required
def client_list(request):
    user = request.user
    clients = Client.objects.none()
    if user.role == 'manager':
        clients = Client.objects.filter(manager=user)
    elif user.role == 'admin':
        clients = Client.objects.all()
    search = request.GET.get('search')
    if search:
        clients = clients.filter(
            Q(full_name__icontains=search) | Q(email__icontains=search) |
            Q(phone__icontains=search) | Q(organization_name__icontains=search)
        )
    return render(request, 'mainapp/client_list.html', {'clients': clients})


# -------------------------- ЗАДАЧИ --------------------------
@login_required
def task_create(request, request_id=None):
    if request.user.role not in ['manager', 'admin']:
        messages.error(request, 'Недостаточно прав')
        return redirect('dashboard')
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            if request_id:
                task.request = get_object_or_404(ServiceRequest, pk=request_id)
            task.save()
            messages.success(request, 'Задача создана!')
            return redirect('request_detail', pk=request_id) if request_id else redirect('dashboard')
    else:
        form = TaskForm()
    return render(request, 'mainapp/task_form.html', {
        'form': form,
        'request_id': request_id
    })


# -------------------------- ОТЧЁТЫ --------------------------
@login_required
def reports(request):
    if request.user.role != 'admin':
        messages.error(request, 'Доступ запрещён')
        return redirect('dashboard')
    return render(request, 'mainapp/reports.html')


# -------------------------- РЕГИСТРАЦИЯ --------------------------
def register(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        full_name = request.POST.get('full_name')
        phone = request.POST.get('phone', '')

        if password != password_confirm:
            messages.error(request, 'Пароли не совпадают')
            return render(request, 'mainapp/register.html')
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Пользователь с таким email уже существует')
            return render(request, 'mainapp/register.html')
        if len(password) < 6:
            messages.error(request, 'Пароль должен быть не менее 6 символов')
            return render(request, 'mainapp/register.html')

        user = User.objects.create_user(
            email=email,
            username=email.split('@')[0],
            password=password,
            role='client',
            first_name=full_name
        )
        # Данные клиента заполняются из формы
        Client.objects.create(
            user=user,
            full_name=full_name,
            phone=phone,
            email=email
        )
        auth_login(request, user)
        messages.success(request, 'Регистрация успешна! Добро пожаловать!')
        return redirect('dashboard')
    return render(request, 'mainapp/register.html')