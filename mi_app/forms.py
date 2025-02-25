from django import forms
from .models import EscapadaAlojamiento, Alojamiento, Escapada, TIPO_HABITACION_CHOICES, Habitacion, ESTADO_HABITACION_CHOICES, Persona, Inscripcion

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
        fields = ['escapada_alojamiento', 'numero', 'capacidad', 'tipo', 'estado', 'descripcion']
        widgets = {
            'escapada_alojamiento': forms.Select(
                attrs={'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500'}
            ),
            'numero': forms.TextInput(
                attrs={'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500'}
            ),
            'capacidad': forms.NumberInput(
                attrs={'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500', 'min': 1}
            ),
            'tipo': forms.Select(
                attrs={'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500'},
                choices=TIPO_HABITACION_CHOICES
            ),
            'estado': forms.Select(
                attrs={'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500'},
                choices=ESTADO_HABITACION_CHOICES
            ),
            'descripcion': forms.Textarea(
                attrs={'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500', 'rows': 3}
            ),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Optimize the escapada_alojamiento queryset to show better info
        self.fields['escapada_alojamiento'].queryset = EscapadaAlojamiento.objects.select_related(
            'escapada', 'alojamiento'
        )
        
        # Customize the display format of escapada_alojamiento options
        self.fields['escapada_alojamiento'].label_from_instance = lambda obj: (
            f"{obj.escapada.nombre} - {obj.alojamiento.nombre}"
        )
        
        # Filter escapada_alojamiento by escapada if provided in URL
        escapada_id = None
        if 'instance' in kwargs and kwargs['instance']:
            escapada_id = kwargs['instance'].escapada_alojamiento.escapada_id
            
        if escapada_id:
            self.fields['escapada_alojamiento'].queryset = self.fields['escapada_alojamiento'].queryset.filter(
                escapada_id=escapada_id
            )
            
class HabitacionBulkForm(forms.Form):
    capacidad = forms.IntegerField(
        label="Capacidad", 
        min_value=1, 
        required=True
    )
    # Aunque se muestra el campo, en la view lo recalculamos según la capacidad
    descripcion = forms.CharField(
        label="Descripción",
        required=False,
        widget=forms.Textarea(attrs={'rows': 3})
    )
    numero_de_habitaciones = forms.IntegerField(
        label="N° de Habitaciones a crear",
        min_value=1,
        initial=1
    )

class CSVImportForm(forms.Form):
    """
    Formulario para la importación de personas desde un archivo CSV
    """
    escapada = forms.ModelChoiceField(
        queryset=Escapada.objects.all(),
        required=False,
        empty_label="-- Solo añadir a la base de datos (sin inscripción) --",
        label="Escapada (opcional)",
        help_text="Si seleccionas una escapada, las personas importadas serán inscritas en ella."
    )
    
    csv_file = forms.FileField(
        label="Archivo CSV",
        help_text="El archivo debe estar en formato CSV con codificación UTF-8.",
        widget=forms.FileInput(attrs={'accept': '.csv'})
    )
    
    only_add_to_db = forms.BooleanField(
        required=False,
        initial=False,
        label="Solo añadir a la base de datos",
        help_text="Marca esta opción si quieres añadir las personas a la base de datos sin inscribirlas a la escapada seleccionada."
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Actualizar el queryset de escapadas para mostrar solo las activas
        self.fields['escapada'].queryset = Escapada.objects.all().order_by('-fecha_ini')
                
    def clean(self):
        cleaned_data = super().clean()
        escapada = cleaned_data.get('escapada')
        only_add_to_db = cleaned_data.get('only_add_to_db')
        
        # Si se marca "solo añadir a la BD", la escapada no es necesaria
        if only_add_to_db:
            cleaned_data['escapada'] = None
        
        return cleaned_data
 
class PersonaInscripcionForm(forms.ModelForm):
    """
    Formulario que combina los campos de Persona con algunos campos
    importantes de Inscripcion, para que se puedan editar/crear juntos.
    """
    # Campo para elegir escapada. Si no se selecciona nada,
    # NO se crea la inscripción.
    escapada = forms.ModelChoiceField(
        queryset=Escapada.objects.all(),
        required=False,
        label="Inscribir en Escapada"
    )

    # Campos de Inscripcion
    ha_pagado = forms.BooleanField(required=False, label="¿Ha pagado?")
    a_pagar = forms.DecimalField(
        required=False,
        label="Importe a Pagar",
        min_value=0,
        decimal_places=2,
        max_digits=8,
        initial=0
    )
    pagado = forms.DecimalField(
        required=False,
        label="Importe Pagado",
        min_value=0,
        decimal_places=2,
        max_digits=8,
        initial=0
    )
    pendiente = forms.DecimalField(
        required=False,
        label="Importe Pendiente",
        min_value=0,
        decimal_places=2,
        max_digits=8,
        initial=0
    )
    tipo_habitacion_preferida = forms.CharField(
        required=False,
        label="Tipo Habitación Preferida",
        max_length=20
    )
    # Agrega más campos de Inscripcion si lo deseas

    class Meta:
        model = Persona
        fields = [
            'dni', 'nombre', 'apellidos', 'fecha_nacimiento',
            'correo', 'telefono', 'sexo',
            'es_pringado', 'anio_pringado',
        ]
        # Nota: No incluyo 'id' porque se genera automáticamente.

    def save(self, commit=True):
        """
        1. Crea/Actualiza la Persona.
        2. Si se seleccionó una Escapada, crea/actualiza la Inscripcion
           con los campos que se hayan rellenado.
        """
        persona = super().save(commit=commit)

        escapada = self.cleaned_data.get('escapada')
        if escapada:
            # Preparar datos para Inscripcion
            ins_data = {
                'ha_pagado': self.cleaned_data.get('ha_pagado') or False,
                'a_pagar': self.cleaned_data.get('a_pagar') or 0,
                'pagado': self.cleaned_data.get('pagado') or 0,
                'pendiente': self.cleaned_data.get('pendiente') or 0,
                'tipo_habitacion_preferida': self.cleaned_data.get('tipo_habitacion_preferida') or None
            }

            # Crear/Actualizar la inscripcion:
            Inscripcion.objects.update_or_create(
                persona=persona,
                escapada=escapada,
                defaults=ins_data
            )

        return persona

class PersonaForm(forms.ModelForm):
    # Campo adicional para seleccionar la escapada
    escapada = forms.ModelChoiceField(
        queryset=Escapada.objects.all(),
        required=False,               # Puede ser opcional
        label="Inscribir en Escapada"
    )

    class Meta:
        model = Persona
        fields = ['dni', 'nombre', 'apellidos', 'fecha_nacimiento', 
                  'correo', 'sexo', 'prefijo', 'telefono', 
                  'es_pringado', 'anio_pringado']

    def save(self, commit=True):
        # Sobrescribimos el save para crear la inscripcion si escapada != None
        persona = super().save(commit=commit)

        # Tomar la escapada del cleaned_data
        escapada = self.cleaned_data.get('escapada')

        if escapada:
            # Verificar si ya existe una inscripcion para esa Persona y Escapada
            inscripcion, created = Inscripcion.objects.get_or_create(
                persona=persona,
                escapada=escapada,
                defaults={
                    "ha_pagado": False,  # o lo que proceda
                    "a_pagar": 0,
                    "pagado": 0,
                    "pendiente": 0,
                }
            )
            # Si 'created' es True, hemos creado la inscripcion
            # Si 'created' es False, la inscripcion ya existía

        return persona

