from django import forms
from .models import Ruta
from config.choices import EstadoGeneral


class RutaForm(forms.ModelForm):
    class Meta:
        model = Ruta
        fields = ['codigo', 'origen', 'destino', 'descripcion', 'precio_base', 'dias_entrega', 'estado']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'precio_base': forms.NumberInput(attrs={'step': '0.01'}),
        }
        labels = {
            'codigo': 'Código de ruta',
            'origen': 'Ciudad de origen',
            'destino': 'Ciudad de destino',
            'precio_base': 'Precio base (S/)',
            'dias_entrega': 'Días estimados de entrega',
        }
