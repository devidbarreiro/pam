from django import forms
from .models import EscapadaAlojamiento, Alojamiento, Escapada, Habitacion

class EscapadaAlojamientoForm(forms.ModelForm):
    class Meta:
        model = EscapadaAlojamiento
        fields = ['escapada', 'alojamiento']
        widgets = {
            'escapada': forms.Select(attrs={'class': 'border-gray-300 rounded-md shadow-sm'}),
            'alojamiento': forms.Select(attrs={'class': 'border-gray-300 rounded-md shadow-sm'}),
        }

class EscapadaAlojamientoMultipleForm(forms.Form):
    alojamientos = forms.ModelMultipleChoiceField(
        queryset=Alojamiento.objects.all(),
        widget=forms.CheckboxSelectMultiple,  # También puedes usar forms.SelectMultiple
        label="Seleccione los alojamientos a asociar"
    )
    
class EscapadaForm(forms.ModelForm):
    class Meta:
        model = Escapada
        fields = [
            'id', 
            'nombre',
            'tipo',
            'num_plazas',
            'fecha_ini',
            'fecha_fin',
            'lugar',
            'url_formulario_inscripcion',
            'descripcion',
            'imagen',
            'estado'
        ]
        widgets = {
            'fecha_ini': forms.DateInput(attrs={'type': 'date'}),
            'fecha_fin': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super(EscapadaForm, self).__init__(*args, **kwargs)

        # ID: solo lectura y no requerido
        self.fields['id'].disabled = True
        self.fields['id'].required = False

        # Campos obligatorios
        self.fields['nombre'].required = True
        self.fields['tipo'].required = True
        self.fields['estado'].required = True

        # Hacer opcionales
        self.fields['fecha_ini'].required = False
        self.fields['fecha_fin'].required = False
        self.fields['num_plazas'].required = False
        self.fields['url_formulario_inscripcion'].required = False
        self.fields['descripcion'].required = False
        self.fields['imagen'].required = False

class HabitacionForm(forms.ModelForm):
    class Meta:
        model = Habitacion
        fields = ['capacidad', 'tipo', 'descripcion', 'estado']
        # NOTA: excluimos 'numero' (se asignará automáticamente) y 'escapada_alojamiento' (la asignarás en la vista).

from django.forms import modelformset_factory

HabitacionFormSet = modelformset_factory(
    Habitacion,
    form=HabitacionForm,
    extra=3,           # Número de formularios vacíos adicionales
    can_delete=False   # Permitir o no borrar formularios
)