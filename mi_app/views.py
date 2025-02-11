# views.py

from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, View
from .models import Escapada, Alojamiento, Habitacion, Persona, EscapadaAlojamiento, Inscripcion  # Asegúrate de importar EscapadaAlojamiento
from .forms import EscapadaAlojamientoForm, EscapadaAlojamientoMultipleForm, HabitacionFormSet
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import FormView, TemplateView

class HomeView(TemplateView):
    template_name = 'home.html'

# --------------------
# VIEWS PARA ESCAPADA
# --------------------
class EscapadaListView(ListView):
    model = Escapada
    template_name = 'escapada/escapada_list.html'
    context_object_name = 'escapadas'

class EscapadaCreateView(CreateView):
    model = Escapada
    fields = '__all__'
    template_name = 'escapada/escapada_form.html'
    success_url = reverse_lazy('escapada_list')

class EscapadaDetailView(DetailView):
    model = Escapada
    template_name = 'escapada/escapada_detail.html'
    context_object_name = 'escapada'

class EscapadaUpdateView(UpdateView):
    model = Escapada
    fields = '__all__'
    template_name = 'escapada/escapada_form.html'
    success_url = reverse_lazy('escapada_list')

class EscapadaDeleteView(DeleteView):
    model = Escapada
    template_name = 'escapada/escapada_confirm_delete.html'
    success_url = reverse_lazy('escapada_list')

# *** NUEVA VIEW: Selección de alojamientos para una escapada ***
class EscapadaAlojamientoSelectView(DetailView):
    """
    Vista que muestra una Escapada y, a través del modelo intermedio,
    lista los Alojamientos asociados a esa Escapada.
    """
    model = Escapada
    template_name = 'escapada/escapada_alojamiento_select.html'
    context_object_name = 'escapada'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Obtenemos los registros intermedios (cada uno contiene la escapada y el alojamiento)
        context['alojamientos_rel'] = EscapadaAlojamiento.objects.filter(escapada=self.object)
        # Si lo prefieres, también podrías extraer solo los alojamientos:
        context['alojamientos'] = [ea.alojamiento for ea in context['alojamientos_rel']]
        return context

class EscapadaAlojamientoCreateView(CreateView):
    model = EscapadaAlojamiento
    fields = '__all__'
    form_class = EscapadaAlojamientoForm
    template_name = 'escapada/escapada_asociar_alojamiento.html'
    success_url = reverse_lazy('escapada_list')
    
    def get_initial(self):
        initial = super().get_initial()
        escapada_id = self.request.GET.get('escapada')
        if escapada_id:
            # Opcional: verificar que la escapada exista
            escapada = get_object_or_404(Escapada, pk=escapada_id)
            initial['escapada'] = escapada.pk
        return initial

class EscapadaAlojamientoMultipleCreateView(FormView):
    template_name = 'escapada/escapada_asociar_alojamiento_multiple.html'
    form_class = EscapadaAlojamientoMultipleForm
    success_url = reverse_lazy('escapada_list')

    def dispatch(self, request, *args, **kwargs):
        self.escapada = get_object_or_404(Escapada, pk=kwargs.get('pk'))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['escapada'] = self.escapada
        return context

    def form_valid(self, form):
        alojamientos = form.cleaned_data['alojamientos']
        for alojamiento in alojamientos:
            # Crea la asociación si aún no existe
            EscapadaAlojamiento.objects.get_or_create(
                escapada=self.escapada,
                alojamiento=alojamiento
            )
        return super().form_valid(form)

# -----------------------
# VIEWS PARA ALOJAMIENTO
# -----------------------
class AlojamientoListView(ListView):
    model = Alojamiento
    template_name = 'alojamiento/alojamiento_list.html'
    context_object_name = 'alojamientos'

class AlojamientoCreateView(CreateView):
    model = Alojamiento
    fields = '__all__'
    template_name = 'alojamiento/alojamiento_form.html'
    success_url = reverse_lazy('alojamiento_list')

class AlojamientoDetailView(DetailView):
    model = Alojamiento
    template_name = 'alojamiento/alojamiento_detail.html'
    context_object_name = 'alojamiento'

class AlojamientoUpdateView(UpdateView):
    model = Alojamiento
    fields = '__all__'
    template_name = 'alojamiento/alojamiento_form.html'
    success_url = reverse_lazy('alojamiento_list')

class AlojamientoDeleteView(DeleteView):
    model = Alojamiento
    template_name = 'alojamiento/alojamiento_confirm_delete.html'
    success_url = reverse_lazy('alojamiento_list')

# ---------------------
# VIEWS PARA HABITACION
# ---------------------
class HabitacionListView(ListView):
    model = Habitacion
    template_name = 'habitacion/habitacion_list.html'
    context_object_name = 'habitaciones'

class HabitacionCreateView(CreateView):
    model = Habitacion
    fields = ['numero', 'capacidad', 'tipo', 'descripcion', 'estado']
    template_name = 'habitacion/habitacion_form.html'
    success_url = reverse_lazy('habitacion_list')

    def dispatch(self, request, *args, **kwargs):
        self.alojamiento_id = self.request.GET.get('alojamiento')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if not self.alojamiento_id:
            form.add_error(None, "No se ha proporcionado un alojamiento para la habitación.")
            return self.form_invalid(form)

        alojamiento = get_object_or_404(Alojamiento, pk=self.alojamiento_id)
        # Obtenemos la(s) relación(es) EscapadaAlojamiento para ese Alojamiento
        ea_list = EscapadaAlojamiento.objects.filter(alojamiento=alojamiento)

        if ea_list.count() == 0:
            form.add_error(None, "Este alojamiento no está asociado a ninguna Escapada.")
            return self.form_invalid(form)
        elif ea_list.count() == 1:
            # Si solo hay una, la asignamos automáticamente
            ea = ea_list.first()
            habitacion = form.save(commit=False)
            habitacion.escapada_alojamiento = ea
            # Asigna un numero automático o deja que el usuario lo introduzca
            habitacion.save()
            return super().form_valid(form)
        else:
            # Si hay más de una escapada, el usuario debe elegir manualmente
            form.add_error(None, "Este alojamiento está asociado a varias escapadas. Selecciona la escapada manualmente en 'escapada_alojamiento'.")
            return self.form_invalid(form)

class HabitacionDetailView(DetailView):
    model = Habitacion
    template_name = 'habitacion/habitacion_detail.html'
    context_object_name = 'habitacion'

class HabitacionUpdateView(UpdateView):
    model = Habitacion
    fields = '__all__'
    template_name = 'habitacion/habitacion_form.html'
    success_url = reverse_lazy('habitacion_list')

class HabitacionDeleteView(DeleteView):
    model = Habitacion
    template_name = 'habitacion/habitacion_confirm_delete.html'
    success_url = reverse_lazy('habitacion_list')

class HabitacionCreateForAlojamientoView(CreateView):
    model = Habitacion
    fields = ['numero', 'capacidad', 'tipo', 'descripcion', 'estado']
    template_name = 'habitacion/habitacion_form.html'
    success_url = reverse_lazy('habitacion_list')

    def dispatch(self, request, *args, **kwargs):
        """
        Captura el GET parameter 'alojamiento' para filtrar las posibles
        EscapadaAlojamiento a las que se puede asociar.
        """
        self.alojamiento_id = self.request.GET.get('alojamiento')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Opcionalmente, si deseas mostrar en la plantilla las relaciones disponibles:
        if self.alojamiento_id:
            alojamiento = get_object_or_404(Alojamiento, pk=self.alojamiento_id)
            # Este alojamiento puede estar asociado a múltiples escapadas a través de EscapadaAlojamiento
            ea_list = EscapadaAlojamiento.objects.filter(alojamiento=alojamiento)
            context['posibles_escapadas'] = ea_list
            context['alojamiento'] = alojamiento
        return context

    def form_valid(self, form):
        """
        Necesitamos asignar escapada_alojamiento a la nueva Habitación.
        Lo habitual es que el usuario elija en el formulario la EscapadaAlojamiento
        (si hay más de una) o se asigne automáticamente si hay solo una.
        """
        alojamiento_id = self.alojamiento_id
        if not alojamiento_id:
            # Si no llegó el GET param, no podemos asignar la relación.
            form.add_error(None, "No se ha especificado un Alojamiento válido.")
            return self.form_invalid(form)

        alojamiento = get_object_or_404(Alojamiento, pk=alojamiento_id)
        # Obtenemos la relación EA seleccionada (por ejemplo, vía un <select> en el formulario)
        # o asignamos la primera si solo hay una.
        ea_id = self.request.POST.get('escapada_alojamiento_id')
        # Imagina que en el formulario incluiste un campo <select name="escapada_alojamiento_id">
        # con las opciones de ea_list. 

        if not ea_id:
            # Lógica para cuando el usuario no seleccionó nada
            form.add_error(None, "Debe seleccionar la Escapada para la cual se creará la habitación.")
            return self.form_invalid(form)

        ea = get_object_or_404(EscapadaAlojamiento, pk=ea_id, alojamiento=alojamiento)
        
        # Asignamos la relación
        habitacion = form.save(commit=False)
        habitacion.escapada_alojamiento = ea
        habitacion.save()

        return redirect(self.success_url)

class HabitacionMultipleCreateView(View):
    template_name = 'habitacion/habitacion_multiple_form.html'
    
    def get(self, request, ea_id):
        """
        Muestra el formset para crear X habitaciones.
        ea_id se refiere a la PK de EscapadaAlojamiento.
        """
        ea = get_object_or_404(EscapadaAlojamiento, pk=ea_id)
        formset = HabitacionFormSet(queryset=Habitacion.objects.none())  # Formset vacío
        return render(request, self.template_name, {
            'formset': formset,
            'escapada_alojamiento': ea,
        })

    def post(self, request, ea_id):
        """
        Procesa el formset y crea las habitaciones.
        """
        ea = get_object_or_404(EscapadaAlojamiento, pk=ea_id)
        formset = HabitacionFormSet(request.POST, queryset=Habitacion.objects.none())
        
        if formset.is_valid():
            habitaciones = formset.save(commit=False)
            
            for i, hab in enumerate(habitaciones, start=1):
                # Asignar la relación EscapadaAlojamiento
                hab.escapada_alojamiento = ea
                
                # Asignar número automáticamente.
                # Por ejemplo, podrías concatenar el i con la PK de EA, etc.
                hab.numero = f"HAB-{ea.pk}-{i}"
                
                hab.save()
            # Podemos redirigir a la vista de detalle o lista
            return redirect('habitacion_list')
        
        return render(request, self.template_name, {
            'formset': formset,
            'escapada_alojamiento': ea,
        })
     
class HabitacionMultipleAutoCreateView(CreateView):
    """
    Crea varias habitaciones para UN EscapadaAlojamiento concreto (sin select).
    """
    model = Habitacion
    fields = ['capacidad', 'tipo', 'descripcion', 'estado']  # Sin 'numero'
    template_name = 'habitacion/habitacion_multiple_auto_form.html'
    success_url = reverse_lazy('habitacion_list')

    def dispatch(self, request, *args, **kwargs):
        """
        Captura el <int:ea_id> y obtén la instancia de EscapadaAlojamiento.
        """
        self.ea_id = kwargs.get('ea_id')  # Viene de la URL
        self.escapada_alojamiento = get_object_or_404(EscapadaAlojamiento, pk=self.ea_id)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pasamos datos al template para mostrar info de la escapada y el alojamiento
        context['ea'] = self.escapada_alojamiento
        context['alojamiento'] = self.escapada_alojamiento.alojamiento
        return context

    def form_valid(self, form):
        """
        Se crea N habitaciones con numeración consecutiva, 
        sin que el usuario escoja la escapada (la tenemos de self.escapada_alojamiento).
        """
        # 1) Leemos la cantidad de habitaciones y número inicial del POST
        cantidad_str = self.request.POST.get('cantidad_habitaciones', '1')
        numero_inicial_str = self.request.POST.get('numero_inicial', '1')

        try:
            cantidad = int(cantidad_str)
            numero_inicial = int(numero_inicial_str)
        except ValueError:
            form.add_error(None, "Cantidad o Número inicial inválidos. Deben ser enteros.")
            return self.form_invalid(form)

        if cantidad < 1:
            form.add_error(None, "La cantidad de habitaciones debe ser al menos 1.")
            return self.form_invalid(form)

        # 2) Tomamos los datos base (capacidad, tipo, descripcion, estado)
        base_room = form.save(commit=False)
        # No guardamos base_room aún, porque lo usaremos como "plantilla" para N habitaciones

        # 3) Creamos cada una de las N habitaciones
        for i in range(cantidad):
            numero_hab = numero_inicial + i
            nueva = Habitacion(
                escapada_alojamiento=self.escapada_alojamiento,
                numero=str(numero_hab),
                capacidad=base_room.capacidad,
                tipo=base_room.tipo,
                descripcion=base_room.descripcion,
                estado=base_room.estado
            )
            nueva.save()

        return redirect(self.success_url)

   
# -------------------
# VIEWS PARA PERSONA
# -------------------
class PersonaListView(ListView):
    model = Persona
    template_name = 'persona/persona_list.html'
    context_object_name = 'personas'

class PersonaCreateView(CreateView):
    model = Persona
    fields = '__all__'
    template_name = 'persona/persona_form.html'
    success_url = reverse_lazy('persona_list')

class PersonaDetailView(DetailView):
    model = Persona
    template_name = 'persona/persona_detail.html'
    context_object_name = 'persona'

class PersonaUpdateView(UpdateView):
    model = Persona
    fields = '__all__'
    template_name = 'persona/persona_form.html'
    success_url = reverse_lazy('persona_list')

class PersonaDeleteView(DeleteView):
    model = Persona
    template_name = 'persona/persona_confirm_delete.html'
    success_url = reverse_lazy('persona_list')

# -------------------
# VIEWS PARA ESCAPADA_ALOJAMIENTO
# -------------------

class EscapadaAlojamientoListView(TemplateView):
    template_name = 'escapada_alojamiento/escapada_alojamiento_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Recupera todas las escapadas
        context['escapadas'] = Escapada.objects.all()
        return context

from django.utils import timezone
from datetime import timedelta

class EscapadaInscripcionView(TemplateView):
    template_name = 'escapada/inscripcion_escapada.html'

    def dispatch(self, request, *args, **kwargs):
        self.escapada_id = kwargs.get('pk')
        self.escapada = get_object_or_404(Escapada, pk=self.escapada_id)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['escapada'] = self.escapada
        return context

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        
        dni = request.POST.get('dni')
        asignar = request.POST.get('asignar_habitacion')
        habitacion_id = request.POST.get('habitacion_id')

        if asignar == 'true' and habitacion_id:
            # Paso 3: El usuario ya eligió una habitación.
            return self.asignar_habitacion(request, context, dni, habitacion_id)
        else:
            # Paso 1 y 2: El usuario recién ingresó su DNI (o repite).
            return self.verificar_dni(request, context, dni)

    def verificar_dni(self, request, context, dni):
        if not dni:
            context['error_message'] = "Por favor, ingresa tu DNI."
            return self.render_to_response(context)

        # Buscamos la persona por dni
        try:
            persona = Persona.objects.get(dni=dni)
        except Persona.DoesNotExist:
            context['error_message'] = "No se encontró ninguna persona con ese DNI."
            return self.render_to_response(context)

        # Verificamos si está inscrita y ha pagado en esta escapada
        try:
            inscripcion = Inscripcion.objects.get(persona=persona, escapada=self.escapada)
        except Inscripcion.DoesNotExist:
            context['error_message'] = "No estás inscrito en esta escapada."
            return self.render_to_response(context)

        if not inscripcion.ha_pagado:
            context['error_message'] = "Tu pago no está registrado. Contacta a la organización."
            return self.render_to_response(context)

        # Obtenemos las habitaciones disponibles (misma lógica que antes)    
        ea_list = EscapadaAlojamiento.objects.filter(escapada=self.escapada)

        habitaciones_disponibles = []

        for ea in ea_list:
            # Habitaciones libres en este EA
            habs_libres = ea.habitaciones.filter(estado='disponible')
            habitaciones_disponibles.extend(habs_libres)

        # --> AGREGAMOS la habitación actual del usuario si pertenece a esta escapada
        if persona.habitacion:
            escapada_de_habitacion_actual = persona.habitacion.escapada_alojamiento.escapada
            if escapada_de_habitacion_actual == self.escapada:
                # Añadimos la habitación actual a la lista, si no está ya
                if persona.habitacion not in habitaciones_disponibles:
                    habitaciones_disponibles.append(persona.habitacion)

        if not habitaciones_disponibles:
            context['error_message'] = "No hay habitaciones disponibles en esta escapada."
            return self.render_to_response(context)

        context['persona'] = persona
        context['habitaciones_disponibles'] = habitaciones_disponibles
        return self.render_to_response(context)


    def asignar_habitacion(self, request, context, dni, habitacion_id):
        try:
            persona = Persona.objects.get(dni=dni)
        except Persona.DoesNotExist:
            context['error_message'] = "Error interno: Persona no encontrada."
            return self.render_to_response(context)

        try:
            habitacion = Habitacion.objects.get(pk=habitacion_id)
        except Habitacion.DoesNotExist:
            context['error_message'] = "La habitación seleccionada no existe."
            return self.render_to_response(context)

        # 1) Verificar si la Persona ya tiene una habitación en ESTA escapada
        #    (es decir, si su habitacion pertenece a la misma escapada_alojamiento.escapada).
        habitacion_actual = persona.habitacion
        ya_tiene_habitacion_en_esta_escapada = False

        if habitacion_actual:
            escapada_actual_de_la_persona = habitacion_actual.escapada_alojamiento.escapada
            if escapada_actual_de_la_persona == self.escapada:
                ya_tiene_habitacion_en_esta_escapada = True

        # 2) Si ya tenía habitación, verificar si podemos cambiarla
        if ya_tiene_habitacion_en_esta_escapada:
            # Chequeamos la fecha de inicio y si faltan más de 3 días
            fecha_ini = self.escapada.fecha_ini
            if fecha_ini:
                # Calculamos la diferencia con la fecha actual
                dias_restantes = (fecha_ini - timezone.now().date()).days
                if dias_restantes < 3:
                    # No permitir cambio
                    context['error_message'] = (
                        "Faltan menos de 3 días para el inicio de la escapada; no puedes cambiar de habitación."
                    )
                    return self.render_to_response(context)
                # Si faltan 3 o más días, se permite el cambio
            # Si no hay fecha_ini, se permite cambiar siempre

        # 3) Proceder con la asignación
        #    - Marcar la anterior habitación como 'disponible' si queremos “liberarla”
        #      o depende de tu lógica de “ocupada” vs “reservada”.
        #    - Asignar la nueva habitación
        if habitacion_actual and habitacion_actual != habitacion:
            # Liberar la habitación anterior (opcional, según tu lógica)
            habitacion_actual.estado = 'disponible'
            habitacion_actual.save()

        # Marcar la nueva habitación como ocupada
        habitacion.estado = 'ocupada'
        habitacion.save()

        # Asignar la nueva habitación a la persona
        persona.habitacion = habitacion
        persona.save()

        context['success_message'] = f"Habitación {habitacion.numero} asignada correctamente."
        return self.render_to_response(context)

