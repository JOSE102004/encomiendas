# config/choices.py
from django.db import models


class EstadoGeneral(models.IntegerChoices):
    ACTIVO  = 1, 'Activo'
    DE_BAJA = 9, 'De baja'


class EstadoEnvio(models.TextChoices):
    PENDIENTE   = 'PE', 'Pendiente'
    EN_TRANSITO = 'TR', 'En tránsito'
    EN_DESTINO  = 'DE', 'En destino'
    ENTREGADO   = 'EN', 'Entregado'
    DEVUELTO    = 'DV', 'Devuelto'


class TipoDocumento(models.TextChoices):
    DNI       = 'DNI', 'DNI'
    RUC       = 'RUC', 'RUC'
    PASAPORTE = 'PAS', 'Pasaporte'