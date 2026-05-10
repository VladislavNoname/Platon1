from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import (
    User, ServiceRequest, Invoice,
    Service, RequiredDocument, RequestDocument
)


class CustomUserCreationForm(UserCreationForm):
    """Форма регистрации с выбором типа клиента"""

    client_type = forms.ChoiceField(
        choices=[('', 'Выберите тип')] + list(User.CLIENT_TYPE_CHOICES)[1:],
        label='Тип клиента',
        widget=forms.RadioSelect
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
        fields = ['email', 'full_name', 'phone', 'password1', 'password2']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'example@mail.ru',
                'id': 'id_email'
            }),
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Иванов Иван Иванович',
                'id': 'id_full_name'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+7 (999) 123-45-67',
                'id': 'id_phone'
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
            'email': 'Email *',
            'full_name': 'ФИО/Наименование *',
            'phone': 'Телефон *',
            'password1': 'Пароль *',
            'password2': 'Подтверждение пароля *'
        }

    def clean(self):
        cleaned_data = super().clean()
        client_type = cleaned_data.get('client_type')

        if not client_type:
            self.add_error('client_type', 'Выберите тип клиента')
            return cleaned_data

        if client_type == 'organization':
            inn = cleaned_data.get('inn')
            kpp = cleaned_data.get('kpp')
            legal_address = cleaned_data.get('legal_address')

            if not inn:
                self.add_error('inn', 'ИНН обязателен для юридических лиц')
            elif len(inn) not in [10, 12]:
                self.add_error('inn', 'ИНН должен содержать 10 или 12 цифр')

            if not kpp:
                self.add_error('kpp', 'КПП обязателен для юридических лиц')
            elif len(kpp) != 9:
                self.add_error('kpp', 'КПП должен содержать 9 цифр')

            if not legal_address:
                self.add_error('legal_address', 'Юридический адрес обязателен для юридических лиц')

        return cleaned_data


class ServiceRequestForm(forms.ModelForm):
    """Форма создания заявки"""

    comment = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Опишите дополнительную информацию по заявке...'
        }),
        required=False,
        label='Комментарий к заявке'
    )

    class Meta:
        model = ServiceRequest
        fields = ['service']
        widgets = {
            'service': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_service'
            })
        }
        labels = {
            'service': 'Выберите услугу'
        }


class InvoiceForm(forms.ModelForm):
    """Форма создания счета"""

    class Meta:
        model = Invoice
        fields = []