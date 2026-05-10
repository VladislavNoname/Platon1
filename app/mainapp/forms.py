from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import (
    User, Client, ServiceRequest, Invoice,
    Service, RequiredDocument, RequestDocument
)


class CustomUserCreationForm(UserCreationForm):
    """Форма регистрации с выбором типа клиента"""
    client_type = forms.ChoiceField(
        choices=Client.TYPE_CHOICES,
        label='Тип клиента',
        widget=forms.RadioSelect
    )
    full_name = forms.CharField(
        max_length=255,
        label='ФИО',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Иванов Иван Иванович',
            'id': 'id_full_name'
        })
    )
    phone = forms.CharField(
        max_length=20,
        label='Телефон',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+7 (999) 123-45-67',
            'id': 'id_phone'
        })
    )

    # Поля для юридических лиц
    inn = forms.CharField(
        max_length=12,
        required=False,
        label='ИНН',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '1234567890',
            'id': 'id_inn'
        })
    )
    kpp = forms.CharField(
        max_length=9,
        required=False,
        label='КПП',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '123456789',
            'id': 'id_kpp'
        })
    )
    legal_address = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': 'г. Москва, ул. Примерная, д. 1',
            'id': 'id_legal_address'
        }),
        required=False,
        label='Юридический адрес'
    )

    class Meta:
        model = User
        fields = ['email', 'password1', 'password2']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'example@mail.ru',
                'id': 'id_email'
            }),
            'password1': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Минимум 8 символов',
                'id': 'id_password1'
            }),
            'password2': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Повторите пароль',
                'id': 'id_password2'
            }),
        }
        labels = {
            'email': 'Email',
            'password1': 'Пароль',
            'password2': 'Подтверждение пароля'
        }

    def clean(self):
        cleaned_data = super().clean()
        client_type = cleaned_data.get('client_type')

        if client_type == 'organization':
            inn = cleaned_data.get('inn')
            kpp = cleaned_data.get('kpp')
            legal_address = cleaned_data.get('legal_address')

            if not inn:
                self.add_error('inn', 'ИНН обязателен для юридических лиц')
            if not kpp:
                self.add_error('kpp', 'КПП обязателен для юридических лиц')
            if not legal_address:
                self.add_error('legal_address', 'Юридический адрес обязателен для юридических лиц')

        return cleaned_data


class ServiceRequestForm(forms.ModelForm):
    """Форма создания заявки"""

    class Meta:
        model = ServiceRequest
        fields = ['service']
        labels = {
            'service': 'Выберите услугу'
        }
        widgets = {
            'service': forms.Select(attrs={'class': 'form-control'})
        }


class InvoiceForm(forms.ModelForm):
    """Форма создания счета"""

    class Meta:
        model = Invoice
        fields = []