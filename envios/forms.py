from django import forms
from .models import Encomienda

class EncomiendaForm(forms.ModelForm):
    class Meta:
        model = Encomienda
        fields = [
            'codigo', 'descripcion', 'peso_kg', 'volumen_cm3', 
            'remitente', 'destinatario', 'ruta', 'empleado_registro',
            'estado', 'costo_envio', 'fecha_entrega_est', 'observaciones'
        ]
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'observaciones': forms.Textarea(attrs={'rows': 2}),
            'fecha_entrega_est': forms.DateInput(attrs={'type': 'date'}),
        }
