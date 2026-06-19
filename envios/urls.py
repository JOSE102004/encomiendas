from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('encomiendas/', views.encomienda_list, name='encomienda_list'),
    path('encomiendas/<int:pk>/', views.encomienda_detail, name='encomienda_detail'),
    path('encomiendas/nueva/', views.encomienda_create, name='encomienda_create'),
    path('encomiendas/<int:pk>/editar/', views.encomienda_edit, name='encomienda_edit'),
    path('dashboard/', views.dashboard, name='dashboard'),
]
