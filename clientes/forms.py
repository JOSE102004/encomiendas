from django import forms
from .models import Cliente
from envios.validators import validar_nro_doc_dni
from config.choices import TipoDocumento


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'tipo_doc', 'nro_doc', 'nombres', 'apellidos',
            'telefono', 'email', 'direccion', 'estado',
        ]
        widgets = {
            'direccion': forms.Textarea(attrs={'rows': 3}),
            'nro_doc': forms.TextInput(attrs={'placeholder': 'Ej: 12345678'}),
            'telefono': forms.TextInput(attrs={'placeholder': 'Ej: 999888777'}),
        }

    def clean_nro_doc(self):
        nro = self.cleaned_data.get('nro_doc')
        tipo = self.cleaned_data.get('tipo_doc')
        if tipo == TipoDocumento.DNI:
            validar_nro_doc_dni(nro)
        return nro
