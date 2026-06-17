from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import PurchaseRequest, CustomUser

# Форма для заявок
class PurchaseRequestForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequest
        # ДОБАВЛЕНО ПОЛЕ attached_file
        fields = ['item', 'quantity', 'justification', 'attached_file']
        widgets = {
            'item': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'justification': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4, 
                'placeholder': 'Укажите, для каких целей необходима данная закупка...'
            }),
            # ДОБАВЛЕН ВИДЖЕТ ДЛЯ ФАЙЛА (чтобы красиво выглядел через Bootstrap)
            'attached_file': forms.FileInput(attrs={'class': 'form-control'}),
        }

# Форма для регистрации
class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        # Указываем, какие поля хотим видеть при регистрации
        fields = UserCreationForm.Meta.fields + ('first_name', 'last_name', 'role')
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Применяем Bootstrap-классы ко всем полям автоматически
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            if field_name == 'role':
                field.widget.attrs['class'] = 'form-select'