from django.contrib import admin
from .models import Ruta

@admin.register(Ruta)
class RutaAdmin(admin.ModelAdmin):
    list_display  = ('codigo', 'origen', 'destino', 'precio_base', 'dias_entrega', 'estado')
    list_filter   = ('estado',)
    search_fields = ('codigo', 'origen', 'destino')
