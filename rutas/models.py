# rutas/models.py
from django.db import models
from config.choices import EstadoGeneral
from envios.querysets import RutaQuerySet


class Ruta(models.Model):
    objects = RutaQuerySet.as_manager()
    codigo       = models.CharField(max_length=10, unique=True)
    origen       = models.CharField(max_length=100)
    destino      = models.CharField(max_length=100)
    descripcion  = models.TextField(blank=True, null=True)
    precio_base  = models.DecimalField(max_digits=10, decimal_places=2)
    dias_entrega = models.PositiveIntegerField(default=1)
    estado       = models.IntegerField(
        choices=EstadoGeneral.choices,
        default=EstadoGeneral.ACTIVO
    )

    def __str__(self):
        return f'{self.codigo}: {self.origen} → {self.destino}'

    class Meta:
        db_table            = 'rutas'
        verbose_name        = 'Ruta'
        verbose_name_plural = 'Rutas'
        ordering            = ['origen', 'destino']