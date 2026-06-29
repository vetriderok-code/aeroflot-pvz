# flights/forms.py
from django import forms

class TelegramAuthForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите ваш позывной',
            'autofocus': True
        })
    )

class TelegramCodeForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите 6-значный код',
            'maxlength': '6'
        })
    )