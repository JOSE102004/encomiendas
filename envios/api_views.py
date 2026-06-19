from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from clientes.models import Cliente
from rutas.models import Ruta
from .serializers import ClienteSerializer, RutaSerializer
from api.pagination import ClientePagination
from drf_spectacular.utils import extend_schema

# ── Clientes: solo lectura ───────────────────────────────────────
@extend_schema(
    summary='Listar clientes activos',
    description='Devuelve todos los clientes con estado Activo, paginados de 20 en 20.',
    tags=['Clientes'],
)
class ClienteListView(generics.ListAPIView):
    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ClientePagination

    def get_queryset(self):
        return Cliente.objects.activos()

# ── Rutas: solo lectura ──────────────────────────────────────────
@extend_schema(
    summary='Listar rutas activas',
    description='Devuelve todas las rutas con estado Activo. Sin paginacion.',
    tags=['Rutas'],
)
class RutaListView(generics.ListAPIView):
    serializer_class = RutaSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return Ruta.objects.activas()

