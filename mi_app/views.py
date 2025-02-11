# views.py

from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, View
from .models import Escapada, Alojamiento, Habitacion, Persona, EscapadaAlojamiento  # Asegúrate de importar EscapadaAlojamiento
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

# views.py
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
