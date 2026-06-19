# clientes/models.py
from django.db import models
from config.choices import EstadoGeneral, TipoDocumento
from envios.querysets import ClienteQuerySet


class Cliente(models.Model):
    objects = ClienteQuerySet.as_manager()
    tipo_doc = models.CharField(
        max_length=3,
        choices=TipoDocumento.choices,
        default=TipoDocumento.DNI
    )
    nro_doc   = models.CharField(max_length=15, unique=True)
    nombres   = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    telefono  = models.CharField(max_length=15, blank=True, null=True)
    email     = models.EmailField(blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    estado    = models.IntegerField(
        choices=EstadoGeneral.choices,
        default=EstadoGeneral.ACTIVO
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)

    # ── Properties ────────────────────────────────────
    @property
    def nombre_completo(self):
        return f'{self.apellidos}, {self.nombres}'

    @property
    def esta_activo(self):
        return self.estado == EstadoGeneral.ACTIVO

    @property
    def total_encomiendas_enviadas(self):
        return self.envios_como_remitente.count()

    def __str__(self):
        return f'{self.nro_doc} - {self.apellidos}, {self.nombres}'

    class Meta:
        db_table            = 'clientes'
        verbose_name        = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering            = ['apellidos', 'nombres']