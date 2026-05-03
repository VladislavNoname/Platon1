from django import forms
from .models import ServiceRequest, Task

class ServiceRequestForm(forms.ModelForm):
    class Meta:
        model = ServiceRequest
        fields = ['topic', 'description', 'priority']
        widgets = {
            'topic': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите тему заявки'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Опишите проблему'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'topic': 'Тема заявки',
            'description': 'Описание',
            'priority': 'Приоритет',
        }

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'due_date', 'assigned_to']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'due_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'title': 'Название задачи',
            'description': 'Описание',
            'due_date': 'Срок выполнения',
            'assigned_to': 'Назначить сотруднику',
        }