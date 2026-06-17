import uuid  # Импорт для генерации уникального идентификатора
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django_fsm import FSMField, transition

# 1. Расширенная модель пользователя с ролями
class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('initiator', 'Инициатор'),
        ('manager', 'Руководитель'),
        ('purchaser', 'Снабженец'),
    )
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        default='initiator',
        verbose_name='Роль пользователя'
    )

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"

# 2. Справочник номенклатуры (что можно заказывать)
class Item(models.Model):
    name = models.CharField(max_length=255, verbose_name='Наименование')
    sku = models.CharField(max_length=50, unique=True, verbose_name='Артикул', blank=True)
    category = models.CharField(max_length=100, verbose_name='Категория')
    estimated_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='Ориентировочная цена',
        null=True, 
        blank=True
    )

    class Meta:
        verbose_name = 'Номенклатура'
        verbose_name_plural = 'Справочник номенклатуры'

    def save(self, *args, **kwargs):
        if not self.sku:
            self.sku = f"ART-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} [{self.sku}]"

# 3. Главная сущность — Заявка на закупку
class PurchaseRequest(models.Model):
    STATE_CREATED = 'created'
    STATE_PENDING = 'pending_approval'
    STATE_IN_PROGRESS = 'in_progress'
    STATE_AWAITING_DELIVERY = 'awaiting_delivery'
    STATE_COMPLETED = 'completed'
    STATE_REJECTED = 'rejected'

    STATE_CHOICES = (
        (STATE_CREATED, 'Создана'),
        (STATE_PENDING, 'На согласовании'),
        (STATE_IN_PROGRESS, 'В работе'),
        (STATE_AWAITING_DELIVERY, 'Ожидает доставки'),
        (STATE_COMPLETED, 'Выполнена'),
        (STATE_REJECTED, 'Отклонена'),
    )
    
    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='requests',
        verbose_name='Инициатор'
    )
    item = models.ForeignKey(
        Item, 
        on_delete=models.PROTECT, 
        verbose_name='Номенклатура'
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name='Количество')
    justification = models.TextField(verbose_name='Обоснование необходимости')
    
    # --- НОВОЕ ПОЛЕ ДЛЯ ФАЙЛОВ ---
    attached_file = models.FileField(
        upload_to='requests_files/', 
        blank=True, 
        null=True, 
        verbose_name="Прикрепленный документ (счет, ТЗ)"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    status = FSMField(
        default=STATE_CREATED, 
        choices=STATE_CHOICES, 
        verbose_name='Текущий статус'
    )

    class Meta:
        verbose_name = 'Заявка на закупку'
        verbose_name_plural = 'Заявки на закупку'

    @transition(field=status, source=STATE_CREATED, target=STATE_PENDING)
    def submit_for_approval(self):
        pass

    @transition(field=status, source=STATE_PENDING, target=STATE_IN_PROGRESS)
    def approve_request(self):
        pass

    @transition(field=status, source=[STATE_CREATED, STATE_PENDING], target=STATE_REJECTED)
    def reject_request(self):
        pass

    @transition(field=status, source=STATE_IN_PROGRESS, target=STATE_AWAITING_DELIVERY)
    def mark_as_ordered(self):
        pass

    @transition(field=status, source=STATE_AWAITING_DELIVERY, target=STATE_COMPLETED)
    def complete_request(self):
        pass

    def __str__(self):
        return f"Заявка #{self.id} от {self.initiator.username} - {self.get_status_display()}"

# 4. История изменения статусов (Audit Log)
class RequestHistory(models.Model):
    purchase_request = models.ForeignKey(
        PurchaseRequest, 
        on_delete=models.CASCADE, 
        related_name='history',
        verbose_name='Заявка'
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name='Кто изменил'
    )
    old_status = models.CharField(max_length=50, verbose_name='Старый статус')
    new_status = models.CharField(max_length=50, verbose_name='Новый статус')
    comment = models.TextField(blank=True, verbose_name='Комментарий к изменению')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Время изменения')

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Запись истории'
        verbose_name_plural = 'История изменений'

    def __str__(self):
        return f"Изменение заявки #{self.purchase_request.id} ({self.old_status} -> {self.new_status})"