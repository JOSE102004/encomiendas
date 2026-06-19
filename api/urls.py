from django.urls import path, include
from rest_framework.routers import DefaultRouter
from envios.viewsets import EncomiendaViewSet
from envios import api_views

router = DefaultRouter()
router.register('encomiendas', EncomiendaViewSet, basename='encomienda')

urlpatterns = [
    path('', include(router.urls)),
    path('clientes/', api_views.ClienteListView.as_view(), name='cliente-list'),
    path('rutas/', api_views.RutaListView.as_view(), name='ruta-list'),
]
