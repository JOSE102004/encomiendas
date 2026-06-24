from django.urls import path
from . import views

urlpatterns = [
    path('', views.ruta_list, name='ruta_list'),
    path('nueva/', views.ruta_create, name='ruta_create'),
    path('<int:pk>/', views.ruta_detail, name='ruta_detail'),
    path('<int:pk>/editar/', views.ruta_edit, name='ruta_edit'),
    path('<int:pk>/eliminar/', views.ruta_delete, name='ruta_delete'),
]
