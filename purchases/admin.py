from django.contrib import admin, messages
from django_fsm import TransitionNotAllowed
from .models import CustomUser, Item, PurchaseRequest, RequestHistory

# Базовая регистрация
admin.site.register(CustomUser)
admin.site.register(RequestHistory)

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'category', 'estimated_price')
    search_fields = ('name', 'sku')
    list_filter = ('category',)

@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'item', 'initiator', 'quantity', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('item__name', 'initiator__username')
    
    # Делаем поле status только для чтения, чтобы его нельзя было менять руками
    readonly_fields = ('status',)
    
    # Регистрируем наши кастомные действия
    actions = ['action_submit', 'action_approve', 'action_reject']

    @admin.action(description='➡️ Отправить выбранные на согласование')
    def action_submit(self, request, queryset):
        self._apply_transition(request, queryset, 'submit_for_approval')

    @admin.action(description='✅ Одобрить заявки (В работу)')
    def action_approve(self, request, queryset):
        self._apply_transition(request, queryset, 'approve_request')

    @admin.action(description='❌ Отклонить заявки')
    def action_reject(self, request, queryset):
        self._apply_transition(request, queryset, 'reject_request')

    # Вспомогательная функция, чтобы не дублировать код для каждой кнопки
    # Вспомогательная функция, чтобы не дублировать код для каждой кнопки
    def _apply_transition(self, request, queryset, transition_method_name):
        success_count = 0
        error_count = 0

        for obj in queryset:
            old_status = obj.get_status_display()  # Запоминаем старый статус до изменений (в красивом виде)
            
            try:
                # Получаем нужный метод (например, obj.approve_request) и вызываем его
                method = getattr(obj, transition_method_name)
                method()  
                obj.save() # Сохраняем новый статус в базу

                # --- НОВЫЙ КОД: Записываем историю ---
                RequestHistory.objects.create(
                    purchase_request=obj,
                    changed_by=request.user, # Мы знаем, кто нажал кнопку в админке!
                    old_status=old_status,
                    new_status=obj.get_status_display(), # Записываем новый красивый статус
                    comment="Статус изменен через панель администратора"
                )
                # -------------------------------------

                success_count += 1
            except TransitionNotAllowed:
                # Если FSM блокирует переход
                error_count += 1

        # Показываем красивые уведомления в админке
        if success_count > 0:
            self.message_user(request, f'Успешно обновлено заявок: {success_count}', messages.SUCCESS)
        if error_count > 0:
            self.message_user(request, f'Не удалось обновить {error_count} заявок (недопустимый текущий статус)', messages.ERROR)