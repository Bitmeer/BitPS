from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('', views.RequestListView.as_view(), name='request_list'),
    path('request/<int:pk>/', views.RequestDetailView.as_view(), name='request_detail'),
    path('create/', views.RequestCreateView.as_view(), name='request_create'),
    path('request/<int:pk>/transition/<str:action>/', views.change_request_status, name='change_status'),
    
    # Новые маршруты для каталога
    path('catalog/', views.ItemListView.as_view(), name='catalog'),
    path('catalog/add/', views.ItemCreateView.as_view(), name='item_create'),
    
    # ЭКСПОРТ В EXCEL
    path('export/', views.export_requests_excel, name='export_requests_excel'),
]