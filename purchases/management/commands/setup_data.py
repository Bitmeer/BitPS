from django.core.management.base import BaseCommand
from purchases.models import CustomUser, Item, PurchaseRequest

class Command(BaseCommand):
    help = 'Автоматическое создание тестовых данных (пользователи, товары, заявки)'

    def handle(self, *args, **kwargs):
        self.stdout.write("Удаление старых данных...")
        PurchaseRequest.objects.all().delete()
        Item.objects.all().delete()
        CustomUser.objects.all().delete()

        self.stdout.write("Создание пользователей...")
        # 1. Суперпользователь (Админ)
        admin = CustomUser.objects.create_superuser(
            username='admin', 
            email='admin@test.com', 
            password='admin',
            first_name='Главный',
            last_name='Админ'
        )

        # 2. Обычные пользователи (Роли)
        initiator = CustomUser.objects.create_user(
            username='ivanov', password='123', role='initiator',
            first_name='Иван', last_name='Иванов (Программист)'
        )
        manager = CustomUser.objects.create_user(
            username='petrov', password='123', role='manager',
            first_name='Петр', last_name='Петров (Тимлид)'
        )
        purchaser = CustomUser.objects.create_user(
            username='sidorov', password='123', role='purchaser',
            first_name='Сидор', last_name='Сидоров (Завхоз)'
        )

        self.stdout.write("Заполнение склада номенклатурой...")
        item1 = Item.objects.create(name='Apple MacBook Pro 14"', sku='MAC-14-M3', category='Ноутбуки', estimated_price=150000.00)
        item2 = Item.objects.create(name='Монитор Dell 27"', sku='DELL-27-4K', category='Периферия', estimated_price=35000.00)
        item3 = Item.objects.create(name='Офисное кресло', sku='CHAIR-01', category='Мебель', estimated_price=12000.00)

        self.stdout.write("Генерация тестовых заявок...")
        # Заявка 1: Только создана
        PurchaseRequest.objects.create(
            initiator=initiator,
            item=item1,
            quantity=1,
            justification='Старый ноутбук не тянет сборку проектов',
            status='created'
        )

        # Заявка 2: Уже в работе у снабженца
        PurchaseRequest.objects.create(
            initiator=initiator,
            item=item2,
            quantity=2,
            justification='Нужны вторые мониторы для отдела разработки',
            status='in_progress'
        )

        self.stdout.write(self.style.SUCCESS('✅ Тестовая база данных успешно сгенерирована!'))
        self.stdout.write(self.style.WARNING('Логин админа: admin | Пароль: admin'))
        self.stdout.write(self.style.WARNING('Логины юзеров: ivanov, petrov, sidorov | Пароль: 123'))