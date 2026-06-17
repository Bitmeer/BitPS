from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.generic import ListView, CreateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django_fsm import TransitionNotAllowed
from django.db.models import Count, Q
from django.http import HttpResponse
from django.conf import settings
import json
import openpyxl
import requests  # Нужен для отправки HTTP-запросов к API Telegram

from .models import PurchaseRequest, RequestHistory, Item
from .forms import PurchaseRequestForm, CustomUserCreationForm


# Вспомогательная функция для отправки уведомлений в Telegram
def send_telegram_notification(msg, request_id=self.object.id, base_url="https://bitps.onrender.com"):
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', None)
    if not token or not chat_id:
        return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown'
    }
    
    # Если передан ID заявки, добавляем кнопку для перехода или просмотра
    if request_id:
        payload['reply_markup'] = {
            'inline_keyboard': [[
                {'text': f"Открыть заявку #{request_id}", 'url': f"http://127.0.0.1:8000/requests/{request_id}/"}
            ]]
        }
    
    try:
        requests.post(url, json=payload, timeout=5)
    except requests.RequestException:
        pass


class CustomLoginView(LoginView):
    template_name = 'purchases/login.html'
    redirect_authenticated_user = True
    def get_success_url(self): return reverse_lazy('request_list')


class RegisterView(CreateView):
    form_class = CustomUserCreationForm
    template_name = 'purchases/register.html'
    success_url = reverse_lazy('login')
    def form_valid(self, form):
        messages.success(self.request, 'Регистрация прошла успешно!')
        return super().form_valid(form)


class CustomLogoutView(LogoutView):
    template_name = 'purchases/logout_confirm.html'
    next_page = reverse_lazy('login')


class RequestListView(LoginRequiredMixin, ListView):
    model = PurchaseRequest
    template_name = 'purchases/request_list.html'
    context_object_name = 'requests'
    paginate_by = 10

    def get_queryset(self):
        if self.request.user.role == 'initiator':
            qs = PurchaseRequest.objects.filter(initiator=self.request.user)
        else:
            qs = PurchaseRequest.objects.all()
            
        status_filter = self.request.GET.get('status')
        search_query = self.request.GET.get('q', '').strip()

        if status_filter:
            qs = qs.filter(status=status_filter)
            
        if search_query:
            if search_query.isdigit():
                qs = qs.filter(Q(id=search_query) | Q(item__name__icontains=search_query))
            else:
                qs = qs.filter(
                    Q(item__name__icontains=search_query) |
                    Q(initiator__username__icontains=search_query) |
                    Q(initiator__first_name__icontains=search_query) |
                    Q(initiator__last_name__icontains=search_query)
                )
                
        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_status'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('q', '')
        context['status_choices'] = PurchaseRequest.STATE_CHOICES
        
        qs = self.get_queryset()
        status_counts = qs.order_by().values('status').annotate(total=Count('id'))
        
        labels = []
        data = []
        status_dict = dict(PurchaseRequest.STATE_CHOICES)
        
        for entry in status_counts:
            labels.append(status_dict.get(entry['status'], entry['status']))
            data.append(entry['total'])
            
        context['chart_labels'] = json.dumps(labels)
        context['chart_data'] = json.dumps(data)
        return context


class RequestCreateView(LoginRequiredMixin, CreateView):
    model = PurchaseRequest
    template_name = 'purchases/request_form.html'
    form_class = PurchaseRequestForm 
    success_url = reverse_lazy('request_list')

    def form_valid(self, form):
        form.instance.initiator = self.request.user
        # Сохраняем объект в базу данных, чтобы получить его ID
        response = super().form_valid(form)
        
        # ОТПРАВКА УВЕДОМЛЕНИЯ О НОВОЙ ЗАЯВКЕ
        user_name = self.request.user.get_full_name() or self.request.user.username
        msg = (
            f"➕ *Создана новая заявка #{self.object.id}*\n\n"
            f"👤 *Инициатор:* {user_name}\n"
            f"📦 *Номенклатура:* {self.object.item.name}\n"
            f"🔢 *Количество:* {self.object.quantity} шт.\n"
            f"📋 *Статус:* {self.object.get_status_display()}"
        )
        send_telegram_notification(msg, request_id=self.object.id)
        
        return response


@login_required
def change_request_status(request, pk, action):
    if request.method == 'POST':
        req = get_object_or_404(PurchaseRequest, pk=pk)
        old_status = req.get_status_display()
        try:
            transition_method = getattr(req, action)
            transition_method()
            req.save()
            
            RequestHistory.objects.create(
                purchase_request=req,
                changed_by=request.user,
                old_status=old_status,
                new_status=req.get_status_display(),
                comment="Статус изменен через веб-интерфейс"
            )
            
            # ОТПРАВКА УВЕДОМЛЕНИЯ ОБ ИЗМЕНЕНИИ СТАТУСА
            modifier_name = request.user.get_full_name() or request.user.username
            msg = (
                f"🔄 *Обновление статуса заявки #{req.id}*\n\n"
                f"📦 *Товар:* {req.item.name}\n"
                f"❌ *Старый статус:* {old_status}\n"
                f"✅ *Новый статус:* {req.get_status_display()}\n"
                f"👤 *Изменил:* {modifier_name}"
            )
            send_telegram_notification(msg, request_id=req.id)
            
            messages.success(request, f'Статус заявки #{req.id} успешно обновлен!')
        except (AttributeError, TransitionNotAllowed):
            messages.error(request, 'Это действие сейчас недоступно.')
    return redirect('request_list')


class ItemListView(LoginRequiredMixin, ListView):
    model = Item
    template_name = 'purchases/catalog_list.html'
    context_object_name = 'items'
    ordering = ['category', 'name']


class ItemCreateView(LoginRequiredMixin, CreateView):
    model = Item
    template_name = 'purchases/item_form.html'
    fields = ['name', 'category', 'estimated_price'] 
    success_url = reverse_lazy('catalog')
    def form_valid(self, form):
        messages.success(self.request, 'Позиция добавлена!')
        return super().form_valid(form)
    

class RequestDetailView(LoginRequiredMixin, DetailView):
    model = PurchaseRequest
    template_name = 'purchases/request_detail.html'
    context_object_name = 'req'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['history'] = self.object.history.all().select_related('changed_by')
        return context


@login_required
def export_requests_excel(request):
    if request.user.role == 'initiator':
        qs = PurchaseRequest.objects.filter(initiator=request.user)
    else:
        qs = PurchaseRequest.objects.all()
        
    status_filter = request.GET.get('status')
    search_query = request.GET.get('q', '').strip()

    if status_filter:
        qs = qs.filter(status=status_filter)
        
    if search_query:
        if search_query.isdigit():
            qs = qs.filter(Q(id=search_query) | Q(item__name__icontains=search_query))
        else:
            qs = qs.filter(
                Q(item__name__icontains=search_query) |
                Q(initiator__username__icontains=search_query) |
                Q(initiator__first_name__icontains=search_query) |
                Q(initiator__last_name__icontains=search_query)
            )
        
    qs = qs.order_by('-created_at')

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="requests_export.xlsx"'

    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = 'Заявки на закупку'

    columns = ['ID', 'Инициатор', 'Товар', 'Категория', 'Количество', 'Статус', 'Дата создания']
    worksheet.append(columns)

    for col_num, column_title in enumerate(columns, 1):
        cell = worksheet.cell(row=1, column=col_num)
        cell.font = openpyxl.styles.Font(bold=True)

    for req in qs:
        created_str = req.created_at.strftime('%d.%m.%Y %H:%M') if req.created_at else ''
        initiator_name = req.initiator.get_full_name() or req.initiator.username
        
        worksheet.append([
            req.id,
            initiator_name,
            req.item.name,
            req.item.category,
            req.quantity,
            req.get_status_display(),
            created_str
        ])

    workbook.save(response)
    return response