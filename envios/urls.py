from django.urls import path
from . import views
from . import views_async

urlpatterns = [
    path('', views.home, name='home'),
    path('encomiendas/', views.encomienda_list, name='encomienda_list'),
    path('encomiendas/<int:pk>/', views.encomienda_detail, name='encomienda_detail'),
    path('encomiendas/nueva/', views.encomienda_create, name='encomienda_create'),
    path('encomiendas/<int:pk>/editar/', views.encomienda_edit, name='encomienda_edit'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/stats/', views_async.dashboard_stats_async, name='dashboard_stats_async'),
    path('api/v1/encomiendas/<int:pk>/estado/', views_async.cambiar_estado_vista, name='encomienda_cambiar_estado_async'),
]
