# views.py

import csv
import io
import json
import logging
import datetime
import traceback
from decimal import Decimal
from io import TextIOWrapper

from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, F, Q
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.contrib.auth.decorators import login_required

from django.views.decorators.http import require_http_methods
from django.views.generic import (
    ListView, CreateView, DetailView, UpdateView, DeleteView, View,
    FormView, TemplateView
)
import csv
import json
import logging
import datetime
from decimal import Decimal
from io import TextIOWrapper, BytesIO

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction

from .forms import (
    CSVImportForm, EscapadaAlojamientoForm, EscapadaAlojamientoMultipleForm, HabitacionBulkForm, HabitacionForm
)
from .models import (
    Escapada, Alojamiento, Habitacion, Persona, Inscripcion, EscapadaAlojamiento, ReservaHabitacion, TIPO_HABITACION_CHOICES
)
from .utils import (
    validar_csv
)


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

import logging
from django.views.generic import DetailView
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.utils import timezone
from .models import Escapada

logger = logging.getLogger(__name__)

class EscapadaDetailView(DetailView):
    model = Escapada
    template_name = 'escapada/escapada_detail.html'
    context_object_name = 'escapada'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # --- Agrupar habitaciones por alojamiento y por tipo ---
        grouped_rooms = {}
        for ea in self.object.escapadas_alojamiento.all():
            alojamiento = ea.alojamiento
            if alojamiento.pk not in grouped_rooms:
                grouped_rooms[alojamiento.pk] = {
                    'alojamiento': alojamiento,
                    'rooms_by_type': {}
                }
            for room in ea.habitaciones.all():
                # Agrupar por tipo (puedes usar room.capacidad en vez de room.tipo si lo prefieres)
                group_key = room.tipo  # o: group_key = room.capacidad
                if group_key not in grouped_rooms[alojamiento.pk]['rooms_by_type']:
                    grouped_rooms[alojamiento.pk]['rooms_by_type'][group_key] = []
                grouped_rooms[alojamiento.pk]['rooms_by_type'][group_key].append(room)
        context['grouped_rooms'] = grouped_rooms

        # --- Resumen de Habitaciones ---
        total_capacity = 0
        occupancy = 0
        for ea in self.object.escapadas_alojamiento.all():
            for room in ea.habitaciones.all():
                total_capacity += room.capacidad
                occupancy += room.ocupacion_actual()
        context['total_capacity'] = total_capacity
        context['occupancy'] = occupancy
        context['available'] = total_capacity - occupancy

        # --- Paginación de Inscripciones ---
        inscripciones_list = self.object.inscripciones.all().order_by('-fecha_inscripcion')
        paginator = Paginator(inscripciones_list, 10)  # 10 inscripciones por página
        page = self.request.GET.get('page')
        try:
            inscripciones_paginated = paginator.page(page)
        except PageNotAnInteger:
            inscripciones_paginated = paginator.page(1)
        except EmptyPage:
            inscripciones_paginated = paginator.page(paginator.num_pages)
        context['inscripciones_paginated'] = inscripciones_paginated

        return context

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

from django.db.models import Sum, Count, F
from django.views.generic import DetailView
from .models import Alojamiento, Habitacion

class AlojamientoDetailView(DetailView):
    model = Alojamiento
    template_name = 'alojamiento/alojamiento_detail.html'
    context_object_name = 'alojamiento'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        alojamiento = self.object
        
        # Calcular capacidad total sumando las capacidades de todas las habitaciones
        # relacionadas con este alojamiento a través de EscapadaAlojamiento
        habitaciones = Habitacion.objects.filter(
            escapada_alojamiento__alojamiento=alojamiento
        )
        
        capacidad_total = habitaciones.aggregate(
            total_capacity=Sum('capacidad')
        )['total_capacity'] or 0
        
        context['capacidad_total'] = capacidad_total
        
        # Precargar las habitaciones para cada EscapadaAlojamiento
        # para evitar múltiples consultas en la plantilla
        for ea in alojamiento.alojamientos_escapada.all():
            ea.habitaciones_list = ea.habitaciones.all().prefetch_related('persona_set')
        
        return context

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

from django.views.generic import ListView
from django.db.models import Count, Sum, F, Q
from .models import Habitacion, Escapada, Alojamiento
from django.views.generic import DetailView
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from .models import Habitacion, Persona

from django.views.generic import ListView
from .models import Habitacion, Escapada, Alojamiento, ESTADO_HABITACION_CHOICES
from django.db.models import Q, Sum

class HabitacionListView(ListView):
    model = Habitacion
    template_name = 'habitacion/habitacion_list.html'
    context_object_name = 'habitaciones'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['headers'] = ['Escapada', 'Alojamiento', 'Número', 'Capacidad', 
                            'Tipo', 'Ocupación', 'Estado', 'Acciones']
        
        # Añadimos las opciones de estado de habitación al contexto
        context['habitacion'] = {'STATUS_CHOICES': ESTADO_HABITACION_CHOICES}
        
        # Obtener todas las escapadas y alojamientos para los filtros
        context['escapadas'] = Escapada.objects.all()
        context['alojamientos'] = Alojamiento.objects.all()
        
        # Mantener los filtros seleccionados
        context['selected_escapada'] = self.request.GET.get('escapada', '')
        context['selected_alojamiento'] = self.request.GET.get('alojamiento', '')
        context['selected_estado'] = self.request.GET.get('estado', '')
        context['selected_agrupacion'] = self.request.GET.get('agrupacion', 'escapada')
        context['mostrar_estadisticas'] = self.request.GET.get('mostrarEstadisticas', False)
        
        # Obtener estadísticas globales
        if context['mostrar_estadisticas']:
            # Calcular estadísticas generales
            queryset = self.get_queryset()
            context['total_capacidad'] = queryset.aggregate(total=Sum('capacidad'))['total'] or 0
            
            # Contar personas alojadas en estas habitaciones
            total_ocupadas = 0
            for hab in queryset:
                total_ocupadas += hab.ocupacion_actual()
            
            context['total_ocupadas'] = total_ocupadas
            context['habitaciones_disponibles'] = queryset.filter(estado='disponible').count()
            
            if context['total_capacidad'] > 0:
                context['porcentaje_ocupacion'] = round((total_ocupadas / context['total_capacidad']) * 100)
            else:
                context['porcentaje_ocupacion'] = 0
            
            # Si estamos agrupando, agregar estadísticas a cada grupo
            if context['selected_agrupacion'] == 'escapada':
                escapadas = {}
                for hab in queryset:
                    escapada = hab.escapada_alojamiento.escapada
                    if escapada.id not in escapadas:
                        escapadas[escapada.id] = {
                            'capacidad_total': 0,
                            'total_ocupadas': 0,
                            'habitaciones_disponibles': 0
                        }
                    
                    escapadas[escapada.id]['capacidad_total'] += hab.capacidad
                    escapadas[escapada.id]['total_ocupadas'] += hab.ocupacion_actual()
                    if hab.estado == 'disponible':
                        escapadas[escapada.id]['habitaciones_disponibles'] += 1
                
                # Asignar las estadísticas a cada escapada
                for escapada in context['escapadas']:
                    if escapada.id in escapadas:
                        escapada.capacidad_total = escapadas[escapada.id]['capacidad_total']
                        escapada.total_ocupadas = escapadas[escapada.id]['total_ocupadas']
                        escapada.habitaciones_disponibles = escapadas[escapada.id]['habitaciones_disponibles']
            
            elif context['selected_agrupacion'] == 'alojamiento':
                alojamientos = {}
                for hab in queryset:
                    alojamiento = hab.escapada_alojamiento.alojamiento
                    if alojamiento.id not in alojamientos:
                        alojamientos[alojamiento.id] = {
                            'capacidad_total': 0,
                            'total_ocupadas': 0,
                            'habitaciones_disponibles': 0
                        }
                    
                    alojamientos[alojamiento.id]['capacidad_total'] += hab.capacidad
                    alojamientos[alojamiento.id]['total_ocupadas'] += hab.ocupacion_actual()
                    if hab.estado == 'disponible':
                        alojamientos[alojamiento.id]['habitaciones_disponibles'] += 1
                
                # Asignar las estadísticas a cada alojamiento
                for alojamiento in context['alojamientos']:
                    if alojamiento.id in alojamientos:
                        alojamiento.capacidad_total = alojamientos[alojamiento.id]['capacidad_total']
                        alojamiento.total_ocupadas = alojamientos[alojamiento.id]['total_ocupadas']
                        alojamiento.habitaciones_disponibles = alojamientos[alojamiento.id]['habitaciones_disponibles']
        
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.select_related(
            'escapada_alojamiento',
            'escapada_alojamiento__escapada',
            'escapada_alojamiento__alojamiento'
        ).prefetch_related('reservahabitacion_set', 'reservado_por')

        # Aplicar filtros
        escapada_id = self.request.GET.get('escapada')
        alojamiento_id = self.request.GET.get('alojamiento')
        estado = self.request.GET.get('estado')
        search = self.request.GET.get('search')

        if escapada_id:
            queryset = queryset.filter(
                escapada_alojamiento__escapada_id=escapada_id
            )
        if alojamiento_id:
            queryset = queryset.filter(
                escapada_alojamiento__alojamiento_id=alojamiento_id
            )
        if estado:
            queryset = queryset.filter(estado=estado)
            
        # Búsqueda por texto
        if search:
            queryset = queryset.filter(
                Q(numero__icontains=search) |
                Q(escapada_alojamiento__escapada__nombre__icontains=search) |
                Q(escapada_alojamiento__alojamiento__nombre__icontains=search) |
                Q(descripcion__icontains=search)
            )

        return queryset

class HabitacionDetailView(DetailView):
    model = Habitacion
    template_name = 'habitacion/habitacion_detail.html'
    context_object_name = 'habitacion'
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Manejar la acción de desalojar persona
        if request.POST.get('action') == 'desalojar':
            try:
                persona_id = request.POST.get('persona_id')
                persona = Persona.objects.get(id=persona_id)
                
                # Verificar que la persona está en esta habitación
                if persona.habitacion and persona.habitacion.id == self.object.id:
                    persona_nombre = persona.nombre
                    persona.habitacion = None
                    persona.save()
                    
                    # Actualizar el estado de la habitación si ahora está vacía
                    self.actualizar_estado_habitacion()
                    
                    messages.success(request, f"Se ha desalojado a {persona_nombre} de la habitación {self.object.numero}.")
                else:
                    messages.error(request, "Esta persona no se encuentra alojada en esta habitación.")
            except Persona.DoesNotExist:
                messages.error(request, "No se encontró la persona.")
            except Exception as e:
                messages.error(request, f"Error al desalojar: {str(e)}")
                
        return redirect(reverse('habitacion_detail', kwargs={'pk': self.object.pk}))
    
    def actualizar_estado_habitacion(self):
        """Actualiza el estado de la habitación basado en su ocupación"""
        # Si no hay personas, cambia a disponible
        if self.object.persona_set.count() == 0 and self.object.estado == 'ocupada':
            self.object.estado = 'disponible'
            self.object.save()
        # Si hay personas pero no estaba marcada como ocupada, actualiza
        elif self.object.persona_set.count() > 0 and self.object.estado != 'ocupada':
            self.object.estado = 'ocupada'
            self.object.save()

class HabitacionUpdateView(UpdateView):
    model = Habitacion
    fields = '__all__'
    template_name = 'habitacion/habitacion_form.html'
    success_url = reverse_lazy('habitacion_list')

class HabitacionDeleteView(DeleteView):
    model = Habitacion
    template_name = "habitacion/habitacion_confirm_delete.html"
    
    def get_success_url(self):
        # Redirige a la escapada detail con el hash de habitaciones
        escapada_id = self.object.escapada_alojamiento.escapada.pk
        return reverse('escapada_detail', kwargs={'pk': escapada_id}) + '#habitaciones'
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        habitacion_id = self.object.numero or self.object.numero_ficticio
        escapada_id = self.object.escapada_alojamiento.escapada.pk
        
        # Check if there are occupants
        ocupantes_count = self.object.reservahabitacion_set.count()
        if ocupantes_count > 0 and 'force' not in request.POST:
            messages.error(
                request, 
                f"No se puede eliminar la habitación {habitacion_id} porque tiene {ocupantes_count} ocupantes asignados. "
                f"Reasigne o elimine a los ocupantes primero."
            )
            return redirect(reverse('escapada_detail', kwargs={'pk': escapada_id}) + '#habitaciones')
            
        success_url = self.get_success_url()
        self.object.delete()
        messages.success(request, f'Habitación {habitacion_id} eliminada correctamente.')
        return HttpResponseRedirect(success_url)
    
class HabitacionBulkCreateView(View):
    template_name = 'habitacion/habitacion_form.html'

    def get(self, request, ea_id):
        """
        Muestra el formulario en blanco para crear 1 o varias habitaciones.
        """
        ea = get_object_or_404(EscapadaAlojamiento, pk=ea_id)
        form = HabitacionBulkForm()
        return render(request, self.template_name, {
            'form': form,
            'ea': ea
        })

    def post(self, request, ea_id):
        """
        Procesa el formulario y crea las habitaciones.
        """
        ea = get_object_or_404(EscapadaAlojamiento, pk=ea_id)
        form = HabitacionBulkForm(request.POST)

        if form.is_valid():
            capacidad = form.cleaned_data['capacidad']
            n_habs = form.cleaned_data['numero_de_habitaciones']
            descripcion = form.cleaned_data['descripcion']
            # En este caso, ya no se recoge el campo "tipo" del formulario,
            # se asigna automáticamente según la capacidad:
            if capacidad == 1:
                tipo = 'individual'
            elif capacidad == 2:
                tipo = 'doble'
            elif capacidad == 3:
                tipo = 'triple'
            elif capacidad == 4:
                tipo = 'cuadruple'
            elif capacidad == 5:
                tipo = 'quintuple'
            elif capacidad == 6:
                tipo = 'sextuple'
            elif capacidad == 7:
                tipo = 'septuple'
            else:
                tipo = 'individual'  # O puedes definir otra lógica para capacidades mayores

            # Obtener los números reales ingresados, si se envían
            real_numeros = request.POST.getlist('real_numeros[]')
            # Si el usuario no ingresa un número real, usaremos None en lugar de cadena vacía
            if real_numeros:
                real_numeros = [num.strip() if num.strip() != "" else None for num in real_numeros]
            else:
                real_numeros = [None] * n_habs

            habitaciones_creadas = []

            # Calcular el siguiente número secuencial para el número ficticio.
            # Formato: "H" + X + Y + ZZ, donde:
            #   X = id del alojamiento (ea.alojamiento.id)
            #   Y = capacidad de la habitación
            #   ZZ = secuencia de dos dígitos.
            prefijo = f"H{ea.alojamiento.id}{capacidad}"
            # Filtrar las habitaciones ya creadas para este alojamiento y capacidad
            existentes = Habitacion.objects.filter(
                escapada_alojamiento=ea,
                numero_ficticio__startswith=prefijo
            )
            if existentes.exists():
                # Extraer la parte secuencial y obtener el máximo
                try:
                    last_seq = max(
                        int(hab.numero_ficticio[-2:])
                        for hab in existentes
                        if hab.numero_ficticio and hab.numero_ficticio[-2:].isdigit()
                    )
                except ValueError:
                    last_seq = 0
            else:
                last_seq = 0

            # Crear las habitaciones
            for i in range(n_habs):
                secuencia = last_seq + i + 1
                ficticio = f"{prefijo}{secuencia:02d}"
                # Obtener el número real del listado si existe, de lo contrario será None
                if len(real_numeros) == n_habs:
                    real_num = real_numeros[i]
                else:
                    real_num = None

                # Verificar que, si se proporciona un número real, no exista ya para este EA.
                if real_num and Habitacion.objects.filter(escapada_alojamiento=ea, numero=real_num).exists():
                    form.add_error(None, f"La habitación con número real {real_num} ya existe para este alojamiento.")
                    return render(request, self.template_name, {'form': form, 'ea': ea})

                hab = Habitacion.objects.create(
                    escapada_alojamiento=ea,
                    numero=real_num if real_num is not None else None,
                    capacidad=capacidad,
                    tipo=tipo,
                    descripcion=descripcion,
                    estado='disponible',
                    numero_ficticio=ficticio
                )
                habitaciones_creadas.append(hab)

            success_message = f"Se han creado {len(habitaciones_creadas)} habitación(es) correctamente."

            return render(request, self.template_name, {
                'form': HabitacionBulkForm(),  # formulario vacío
                'ea': ea,
                'success_message': success_message
            })

        return render(request, self.template_name, {
            'form': form,
            'ea': ea
        })

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Count, Q

from .models import (
    Habitacion, EscapadaAlojamiento, Escapada, 
    Alojamiento, Persona, ReservaHabitacion,
    TIPO_HABITACION_CHOICES, ESTADO_HABITACION_CHOICES
)
from .forms import HabitacionForm  # You'll need to create this form

@login_required
def habitacion_update(request, pk):
    habitacion = get_object_or_404(Habitacion, pk=pk)
    escapada = habitacion.escapada_alojamiento.escapada
    
    if request.method == 'POST':
        form = HabitacionForm(request.POST, instance=habitacion)
        if form.is_valid():
            form.save()
            messages.success(request, f'Habitación {habitacion.numero or habitacion.numero_ficticio} actualizada correctamente.')
            
            # Redirect back to escapada detail or to a specific tab
            return redirect(f"{reverse('escapada_detail', args=[escapada.pk])}#habitaciones")
    else:
        form = HabitacionForm(instance=habitacion)
    
    context = {
        'form': form,
        'habitacion': habitacion,
        'escapada': escapada,
        'escapada_alojamiento': habitacion.escapada_alojamiento,
        'tipo_habitacion_choices': TIPO_HABITACION_CHOICES,
        'estado_habitacion_choices': ESTADO_HABITACION_CHOICES,
    }
    
    return render(request, 'habitacion/habitacion_update.html', context)

@login_required
def habitacion_create(request):
    escapada_id = request.GET.get('escapada')
    escapada = None
    
    if escapada_id:
        escapada = get_object_or_404(Escapada, pk=escapada_id)
    
    initial_data = {}
    if 'escapada_alojamiento' in request.GET:
        initial_data['escapada_alojamiento'] = request.GET.get('escapada_alojamiento')
        
    if request.method == 'POST':
        form = HabitacionForm(request.POST)
        if form.is_valid():
            habitacion = form.save()
            escapada = habitacion.escapada_alojamiento.escapada
            messages.success(request, f'Habitación creada correctamente.')
            return redirect(f"{reverse('escapada_detail', args=[escapada.pk])}#habitaciones")
    else:
        form = HabitacionForm(initial=initial_data)
    
    context = {
        'form': form,
        'escapada': escapada,
        'tipo_habitacion_choices': TIPO_HABITACION_CHOICES,
        'estado_habitacion_choices': ESTADO_HABITACION_CHOICES,
    }
    
    return render(request, 'habitacion/habitacion_update.html', context)

@login_required
def habitacion_create_for_alojamiento(request, ea_id):
    """
    Create a new room for a specific escapada-alojamiento relationship.
    This is a special route to streamline room creation from the escapada detail page.
    """
    escapada_alojamiento = get_object_or_404(EscapadaAlojamiento, pk=ea_id)
    escapada = escapada_alojamiento.escapada
    
    initial_data = {
        'escapada_alojamiento': ea_id,
    }
    
    if request.method == 'POST':
        form = HabitacionForm(request.POST)
        if form.is_valid():
            habitacion = form.save()
            messages.success(request, f'Habitación creada correctamente para {escapada_alojamiento.alojamiento.nombre}.')
            return redirect(f"{reverse('escapada_detail', args=[escapada.pk])}#habitaciones")
    else:
        form = HabitacionForm(initial=initial_data)
        # Pre-select and disable the escapada_alojamiento field
        form.fields['escapada_alojamiento'].disabled = True
    
    context = {
        'form': form,
        'escapada': escapada,
        'escapada_alojamiento': escapada_alojamiento,
        'tipo_habitacion_choices': TIPO_HABITACION_CHOICES,
        'estado_habitacion_choices': ESTADO_HABITACION_CHOICES,
    }
    
    return render(request, 'habitacion/habitacion_update.html', context)

@login_required
def habitacion_delete(request, pk):
    habitacion = get_object_or_404(Habitacion, pk=pk)
    escapada = habitacion.escapada_alojamiento.escapada
    
    # If it's a GET request and not using JS confirmation, show confirmation page
    if request.method == 'GET' and 'confirm' not in request.GET:
        return render(request, 'habitacion/habitacion_confirm_delete.html', {
            'habitacion': habitacion,
            'escapada': escapada
        })
    
    # Delete on POST or GET with confirmation
    if request.method == 'POST' or 'confirm' in request.GET:
        habitacion_id = habitacion.numero or habitacion.numero_ficticio
        
        # Check if there are occupants
        ocupantes_count = habitacion.reservahabitacion_set.count()
        if ocupantes_count > 0 and 'force' not in request.POST and 'force' not in request.GET:
            messages.error(
                request, 
                f"No se puede eliminar la habitación {habitacion_id} porque tiene {ocupantes_count} ocupantes asignados. "
                f"Reasigne o elimine a los ocupantes primero."
            )
            return redirect(f"{reverse('escapada_detail', args=[escapada.pk])}#habitaciones")
        
        # Proceed with deletion
        habitacion.delete()
        messages.success(request, f'Habitación {habitacion_id} eliminada correctamente.')
        
    return redirect(f"{reverse('escapada_detail', args=[escapada.pk])}#habitaciones")

@login_required
def remove_ocupante(request, habitacion_id, persona_id):
    reserva = get_object_or_404(
        ReservaHabitacion,
        habitacion_id=habitacion_id,
        persona_id=persona_id
    )
    
    escapada = reserva.habitacion.escapada_alojamiento.escapada
    persona_nombre = f"{reserva.persona.nombre} {reserva.persona.apellidos}"
    
    reserva.delete()
    messages.success(
        request, 
        f"{persona_nombre} ha sido removido/a de la habitación correctamente."
    )
    
    # Redirect either to habitacion_update or escapada_detail
    referer = request.META.get('HTTP_REFERER', '')
    if 'habitacion_update' in referer:
        return redirect(reverse('habitacion_update', args=[habitacion_id]))
    return redirect(f"{reverse('escapada_detail', args=[escapada.pk])}#habitaciones")

# API view for JS operations
@login_required
def habitacion_api_detail(request, pk):
    habitacion = get_object_or_404(Habitacion, pk=pk)
    
    data = {
        'id': habitacion.id,
        'numero': habitacion.numero,
        'numero_ficticio': habitacion.numero_ficticio,
        'capacidad': habitacion.capacidad,
        'tipo': habitacion.tipo,
        'estado': habitacion.estado,
        'descripcion': habitacion.descripcion,
        'escapada_alojamiento_id': habitacion.escapada_alojamiento_id,
        'ocupacion_actual': habitacion.ocupacion_actual(),
        'plazas_disponibles': habitacion.plazas_disponibles(),
    }
    
    return JsonResponse(data)

@login_required
def habitacion_api_ocupantes(request, pk):
    habitacion = get_object_or_404(Habitacion, pk=pk)
    
    ocupantes = [{
        'id': reserva.persona.id,
        'nombre': reserva.persona.nombre,
        'apellidos': reserva.persona.apellidos,
        'dni': reserva.persona.dni,
        'es_anfitrion': reserva.es_anfitrion,
    } for reserva in habitacion.reservahabitacion_set.all()]
    
    return JsonResponse({'ocupantes': ocupantes})

@login_required
def asignar_personas_habitacion(request, habitacion_id):
    habitacion = get_object_or_404(Habitacion, pk=habitacion_id)
    escapada = habitacion.escapada_alojamiento.escapada
    
    if request.method == 'POST':
        persona_ids = request.POST.getlist('persona_ids')
        plazas_disponibles = habitacion.plazas_disponibles()
        
        # Limitar a las plazas disponibles
        persona_ids = persona_ids[:plazas_disponibles]
        
        for persona_id in persona_ids:
            persona = get_object_or_404(Persona, pk=persona_id)
            # Crear la reserva si no existe
            ReservaHabitacion.objects.get_or_create(
                persona=persona,
                habitacion=habitacion,
                defaults={'es_anfitrion': False}
            )
        
        if len(persona_ids) > 0:
            messages.success(request, f"Se asignaron {len(persona_ids)} personas a la habitación.")
        
    return redirect('habitacion_update', pk=habitacion_id)

# -------------------
# VIEWS PARA PERSONA
# -------------------

class PersonaListView(ListView):
    model = Persona
    template_name = 'persona/persona_list.html'
    context_object_name = 'personas'
    paginate_by = 12  # Muestra 12 personas por página
    ordering = ['nombre', 'apellidos']  # Ordenamiento por nombre y apellidos
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Prefetch relacionados para optimizar rendimiento
        queryset = queryset.prefetch_related(
            'inscripciones', 'inscripciones__escapada',
            'habitaciones_reservadas', 'habitaciones_reservadas__escapada_alojamiento',
            'habitaciones_reservadas__escapada_alojamiento__alojamiento'
        )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener todas las personas
        todas_personas = Persona.objects.all()
        context['total_personas'] = todas_personas.count()
        
        # Contar personas con pagos completados (al menos una inscripción pagada)
        personas_pagadas = Persona.objects.filter(inscripciones__ha_pagado=True).distinct().count()
        context['personas_pagadas'] = personas_pagadas
        
        # Contar personas con pagos pendientes
        personas_pendientes = Persona.objects.filter(
            inscripciones__ha_pagado=False,
            inscripciones__isnull=False
        ).distinct().count()
        context['personas_pendientes'] = personas_pendientes
        
        # Añadir escapadas para el filtro
        context['escapadas'] = Escapada.objects.all().order_by('-fecha_ini')
        
        # Customizar la paginación
        page_obj = context['page_obj']
        if page_obj.has_other_pages():
            paginator = context['paginator']
            num_pages = paginator.num_pages
            current_page = page_obj.number
            
            # Determinar rango de páginas a mostrar
            if num_pages <= 7:
                # Si hay 7 o menos páginas, mostrar todas
                page_range = range(1, num_pages + 1)
            else:
                # Siempre incluir primera, última y 2 páginas alrededor de la actual
                if current_page <= 4:
                    page_range = list(range(1, 6)) + ['...', num_pages]
                elif current_page >= num_pages - 3:
                    page_range = [1, '...'] + list(range(num_pages - 4, num_pages + 1))
                else:
                    page_range = [1, '...'] + list(range(current_page - 1, current_page + 2)) + ['...', num_pages]
            
            context['page_range'] = page_range
        
        return context

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

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from .models import Persona, Escapada, Inscripcion

# Cambiado de require_POST a require_http_methods para permitir tanto GET como POST
@require_http_methods(["GET", "POST"])
def inscribir_personas(request):
    """
    Vista para inscribir una o múltiples personas en una o múltiples escapadas.
    """
    if request.method != 'POST':
        # Si alguien accede por GET, redirigir a la lista de personas
        return redirect('persona_list')
        
    personas_ids = request.POST.get('personas_ids', '').split(',')
    escapadas_ids = request.POST.get('escapadas_ids', '').split(',')
    tipo_habitacion = request.POST.get('tipo_habitacion', '')
    
    if not personas_ids or not escapadas_ids:
        messages.error(request, 'Debes seleccionar al menos una persona y una escapada.')
        return redirect('persona_list')
    
    # Contadores para el mensaje de resultado
    inscripciones_creadas = 0
    inscripciones_existentes = 0
    errores = 0
    
    for persona_id in personas_ids:
        try:
            persona = Persona.objects.get(pk=persona_id.strip())
            
            for escapada_id in escapadas_ids:
                try:
                    escapada = Escapada.objects.get(pk=int(escapada_id.strip()))
                    
                    # Verificar si ya existe una inscripción
                    inscripcion_existente = Inscripcion.objects.filter(
                        persona=persona,
                        escapada=escapada
                    ).exists()
                    
                    if inscripcion_existente:
                        inscripciones_existentes += 1
                        continue
                    
                    # Crear nueva inscripción
                    Inscripcion.objects.create(
                        persona=persona,
                        escapada=escapada,
                        fecha_inscripcion=timezone.now(),
                        tipo_habitacion_preferida=tipo_habitacion if tipo_habitacion else None,
                        ha_pagado=False,
                        a_pagar=0,
                        pagado=0,
                        pendiente=0
                    )
                    inscripciones_creadas += 1
                    
                    # Actualizar contador de inscritos en la escapada
                    escapada.num_inscritos = Inscripcion.objects.filter(escapada=escapada).count()
                    escapada.save(update_fields=['num_inscritos'])
                    
                except Escapada.DoesNotExist:
                    errores += 1
                except Exception as e:
                    errores += 1
                    print(f"Error al inscribir: {str(e)}")
        
        except Persona.DoesNotExist:
            errores += 1
        except Exception as e:
            errores += 1
            print(f"Error general: {str(e)}")
    
    # Generar mensaje de resultado
    if inscripciones_creadas > 0:
        mensaje = f"Se han creado {inscripciones_creadas} inscripciones correctamente."
        if inscripciones_existentes > 0:
            mensaje += f" {inscripciones_existentes} inscripciones ya existían."
        if errores > 0:
            mensaje += f" No se pudieron procesar {errores} inscripciones debido a errores."
        messages.success(request, mensaje)
    elif inscripciones_existentes > 0:
        mensaje = f"No se han creado nuevas inscripciones. {inscripciones_existentes} inscripciones ya existían."
        if errores > 0:
            mensaje += f" Además, hubo {errores} errores."
        messages.warning(request, mensaje)
    else:
        messages.error(request, f"No se pudo completar ninguna inscripción. Se encontraron {errores} errores.")
    
    return redirect('persona_list')

# Configuración del logger
logger = logging.getLogger(__name__)

def importar_personas(request):
    """Vista para importar personas desde un archivo CSV sin guardar configuraciones de mapeo."""
    escapadas = Escapada.objects.all().order_by('-fecha_ini')
    
    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json'
        if is_ajax:
            try:
                escapada_id = request.POST.get('escapada')
                # Intentamos obtener el CSV desde request.FILES o desde la sesión si ya se almacenó
                csv_file = request.FILES.get('csv_file')
                if not csv_file and 'csv_file_data' in request.session:
                    # Crear un objeto similar a un archivo a partir del contenido almacenado
                    csv_content = request.session['csv_file_data']
                    csv_file = BytesIO(csv_content.encode('utf-8'))
                    csv_file.name = "temp.csv"
                mapping_json = request.POST.get('mapping')
                only_add_to_db = request.POST.get('only_add_to_db') == 'true'
                
                if not csv_file or not mapping_json:
                    return JsonResponse({
                        'success': False,
                        'errors': ['Falta el archivo CSV o la configuración de mapeo.']
                    })
                
                escapada = None
                if escapada_id and not only_add_to_db:
                    try:
                        escapada = Escapada.objects.get(id=escapada_id)
                    except Escapada.DoesNotExist:
                        return JsonResponse({
                            'success': False,
                            'errors': [f'No se encontró la escapada con ID {escapada_id}.']
                        })
                
                try:
                    mapeo = json.loads(mapping_json)
                except json.JSONDecodeError:
                    return JsonResponse({
                        'success': False, 
                        'errors': ['El formato del mapeo es inválido.']
                    })
                
                result = procesar_csv(csv_file, escapada, mapeo, only_add_to_db)
                return JsonResponse(result)
                
            except Exception as e:
                logger.exception(f"Error en importación AJAX: {e}")
                return JsonResponse({
                    'success': False,
                    'errors': [f'Error inesperado: {str(e)}']
                })
        else:
            # Lógica tradicional, similar a la anterior, sin mapeo guardado
            form = CSVImportForm(request.POST, request.FILES)
            if form.is_valid():
                escapada = form.cleaned_data.get('escapada')
                csv_file = request.FILES['csv_file']
                only_add_to_db = form.cleaned_data.get('only_add_to_db', False)
                # Usar un mapeo predeterminado
                mapeo = {
                    "dni": "DNI (si eres europeo) o Pasaporte",
                    "nombre": "Nombre",
                    "apellidos": "Apellidos",
                    "telefono": "Teléfono",
                    "correo": "Correo",
                    "fecha_nacimiento": "Fecha de nacimiento",
                    "sexo": "Sexo",
                    "prefijo": "Prefijo",
                }
                result = procesar_csv(csv_file, escapada, mapeo, only_add_to_db)
                if result['success']:
                    messages.success(request, f"Importación finalizada con éxito. Se importaron {result['total_imported']} personas.")
                else:
                    for error in result['errors']:
                        messages.error(request, error)
                return redirect('importar_personas')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"Error en {field}: {error}")
                return redirect('importar_personas')
    
    # Definir estructura para el frontend sobre los campos disponibles
    campos_persona = [
        {
            'id': 'dni',
            'nombre': 'DNI/Pasaporte',
            'descripcion': 'Identificación única de la persona',
            'tipo': 'texto',
            'requerido': True,
            'ejemplo': '12345678A',
        },
        {
            'id': 'nombre',
            'nombre': 'Nombre',
            'descripcion': 'Nombre de la persona',
            'tipo': 'texto',
            'requerido': True,
            'ejemplo': 'Juan',
        },
        {
            'id': 'apellidos',
            'nombre': 'Apellidos',
            'descripcion': 'Apellidos de la persona',
            'tipo': 'texto',
            'requerido': False,
            'ejemplo': 'Pérez García',
        },
        {
            'id': 'telefono',
            'nombre': 'Teléfono',
            'descripcion': 'Número de teléfono',
            'tipo': 'texto',
            'requerido': False,
            'ejemplo': '612345678',
        },
        {
            'id': 'correo',
            'nombre': 'Correo electrónico',
            'descripcion': 'Email de contacto',
            'tipo': 'email',
            'requerido': False,
            'ejemplo': 'ejemplo@dominio.com',
        },
        {
            'id': 'fecha_nacimiento',
            'nombre': 'Fecha de nacimiento',
            'descripcion': 'Formato: YYYY-MM-DD, DD/MM/YYYY o similar',
            'tipo': 'fecha',
            'requerido': False,
            'ejemplo': '1990-01-15',
        },
        {
            'id': 'sexo',
            'nombre': 'Sexo/Género',
            'descripcion': 'Género de la persona',
            'tipo': 'texto',
            'requerido': False,
            'ejemplo': 'Hombre/Mujer/Otro',
        },
        {
            'id': 'prefijo',
            'nombre': 'Prefijo telefónico',
            'descripcion': 'Prefijo internacional del teléfono',
            'tipo': 'texto',
            'requerido': False,
            'ejemplo': '+34',
        },
        {
            'id': 'a_pagar',
            'nombre': 'Importe a pagar',
            'descripcion': 'Cantidad total a pagar (formato decimal)',
            'tipo': 'decimal',
            'requerido': False,
            'ejemplo': '150.00',
        },
        {
            'id': 'pagado',
            'nombre': 'Importe pagado',
            'descripcion': 'Cantidad ya pagada (formato decimal)',
            'tipo': 'decimal',
            'requerido': False,
            'ejemplo': '75.50',
        },
        {
            'id': 'pendiente',
            'nombre': 'Importe pendiente',
            'descripcion': 'Cantidad pendiente de pago (formato decimal)',
            'tipo': 'decimal',
            'requerido': False,
            'ejemplo': '74.50',
        },
        {
            'id': 'estado',
            'nombre': 'Estado',
            'descripcion': 'Estado de la persona',
            'tipo': 'texto',
            'requerido': False,
            'ejemplo': 'Activo',
        },
        {
            'id': 'es_pringado',
            'nombre': 'Es pringado',
            'descripcion': 'Valores aceptados: sí, no, true, false, 1, 0',
            'tipo': 'booleano',
            'requerido': False,
            'ejemplo': 'sí',
        },
        {
            'id': 'anio_pringado',
            'nombre': 'Año pringado',
            'descripcion': 'Año numérico',
            'tipo': 'entero',
            'requerido': False,
            'ejemplo': '2023',
        },
        {
            'id': 'tipo_alojamiento_deseado',
            'nombre': 'Tipo alojamiento deseado',
            'descripcion': 'Preferencia de tipo de alojamiento',
            'tipo': 'texto',
            'requerido': False,
            'ejemplo': 'Individual',
        },
        {
            'id': 'num_familiares',
            'nombre': 'Número de familiares',
            'descripcion': 'Cantidad de familiares',
            'tipo': 'entero',
            'requerido': False,
            'ejemplo': '2',
        },
        {
            'id': 'es_anfitrion',
            'nombre': 'Es anfitrión',
            'descripcion': 'Valores aceptados: sí, no, true, false, 1, 0',
            'tipo': 'booleano',
            'requerido': False,
            'ejemplo': 'no',
        },
        # Campos específicos para inscripción
        {
            'id': 'ha_pagado',
            'nombre': 'Ha pagado (inscripción)',
            'descripcion': 'Si ha pagado la inscripción completa',
            'tipo': 'booleano',
            'requerido': False,
            'ejemplo': 'sí',
            'inscripcion': True,
        },
        {
            'id': 'tipo_habitacion_preferida',
            'nombre': 'Tipo habitación preferida',
            'descripcion': 'Preferencia de habitación para inscripción',
            'tipo': 'texto',
            'requerido': False,
            'ejemplo': 'doble',
            'inscripcion': True,
        },
        {
            'id': 'importe_pendiente',
            'nombre': 'Importe pendiente (inscripción)',
            'descripcion': 'Cantidad pendiente para la inscripción',
            'tipo': 'decimal',
            'requerido': False,
            'ejemplo': '50.00',
            'inscripcion': True,
        },
        {
            'id': 'es_anfitrion_inscripcion',
            'nombre': 'Es anfitrión (inscripción)',
            'descripcion': 'Si es anfitrión en esta escapada',
            'tipo': 'booleano',
            'requerido': False,
            'ejemplo': 'no',
            'inscripcion': True,
        },
        # Campo especial para nombre completo
        {
            'id': 'nombre_completo',
            'nombre': 'Nombre completo',
            'descripcion': 'Nombre y apellidos juntos (se dividirá automáticamente)',
            'tipo': 'texto',
            'requerido': False,
            'ejemplo': 'Juan Pérez García',
            'especial': True,
        },
    ]
    
    return render(request, 'persona/importar_personas.html', {
        'escapadas': escapadas,
        'campos_persona': campos_persona,
    })

def procesar_csv(csv_file, escapada, mapeo, only_add_to_db=False):
    try:
        # Abrir el archivo CSV usando TextIOWrapper
        # Si csv_file es un objeto InMemoryUploadedFile, se trabaja directamente
        csv_file.seek(0)
        csv_text = TextIOWrapper(csv_file, encoding='utf-8')
        reader = csv.DictReader(csv_text)
        if not reader.fieldnames:
            return {
                'success': False,
                'errors': ['El archivo CSV está vacío o mal formateado.']
            }

        # Verificar que las columnas mapeadas existan en el CSV
        for field_name, column_name in mapeo.items():
            if column_name and column_name not in reader.fieldnames:
                return {
                    'success': False,
                    'errors': [f"La columna '{column_name}' mapeada al campo '{field_name}' no existe en el CSV."]
                }

        # Validar campos obligatorios
        required_fields = ['dni', 'nombre']
        missing_required = [field for field in required_fields if field not in mapeo or not mapeo[field]]
        if missing_required:
            return {
                'success': False,
                'errors': [f"Faltan mapeos para campos obligatorios: {', '.join(missing_required)}"]
            }

        # Cargar todas las filas y validarlas
        all_rows = list(reader)
        validation_errors = []
        warnings = []

        for i, row in enumerate(all_rows, start=1):
            row_errors = validate_row(row, mapeo, i)
            if row_errors:
                validation_errors.extend(row_errors)

        if validation_errors:
            return {
                'success': False,
                'errors': [f"Se encontraron {len(validation_errors)} errores de validación. Ningún dato fue importado."] + validation_errors
            }

        # Seguimiento de importación
        personas_nuevas = 0
        personas_actualizadas = 0
        inscripciones_creadas = 0
        dnis_procesados = set()

        with transaction.atomic():
            for row in all_rows:
                persona_data, inscripcion_data = process_row_data(row, mapeo)
                
                # Evitar duplicados en el mismo CSV
                dni = persona_data.get('dni')
                if dni in dnis_procesados:
                    warnings.append(f"DNI duplicado en el CSV: {dni}. Solo se procesó la primera ocurrencia.")
                    continue
                dnis_procesados.add(dni)
                
                # Actualizar o crear la Persona
                try:
                    persona_obj = Persona.objects.get(dni=dni)
                    for k, v in persona_data.items():
                        if k not in ['dni', 'id'] and v is not None:
                            setattr(persona_obj, k, v)
                    persona_obj.save()
                    personas_actualizadas += 1
                except Persona.DoesNotExist:
                    persona_obj = Persona(**persona_data)
                    persona_obj.save()
                    personas_nuevas += 1

                # Crear la inscripción solo si corresponde
                if escapada and not only_add_to_db:
                    pendiente_val = inscripcion_data.get('pendiente')
                    if pendiente_val is None or Decimal(pendiente_val) <= 0:
                        if not Inscripcion.objects.filter(persona=persona_obj, escapada=escapada).exists():
                            insc_data = {
                                'persona': persona_obj,
                                'escapada': escapada,
                                **inscripcion_data
                            }
                            insc_obj = Inscripcion(**insc_data)
                            insc_obj.save()
                            inscripciones_creadas += 1
                    else:
                        warnings.append(
                            f"La persona {dni} tiene un importe pendiente de {pendiente_val} y no se inscribió."
                        )
        return {
            'success': True,
            'total_imported': personas_nuevas + personas_actualizadas,
            'new_created': personas_nuevas,
            'updated': personas_actualizadas,
            'inscriptions_created': inscripciones_creadas,
            'warnings': warnings
        }
    except Exception as e:
        logger.exception(f"Error procesando CSV: {e}")
        return {
            'success': False,
            'errors': [f"Error procesando el CSV: {str(e)}"]
        }

def process_row_data(row, mapeo):
    """
    Procesa los datos de una fila según el mapeo para crear objetos Persona e Inscripcion.
    """
    persona_data = {}
    inscripcion_data = {}
    
    for field, col_name in mapeo.items():
        if not col_name:
            continue
        value = row.get(col_name, '').strip()
        
        # Campos de inscripción
        if field in ['ha_pagado', 'tipo_habitacion_preferida', 'importe_pendiente', 'es_anfitrion_inscripcion']:
            if field == 'es_anfitrion_inscripcion':
                inscripcion_data['es_anfitrion'] = parse_boolean(value)
            elif field == 'ha_pagado':
                inscripcion_data[field] = parse_boolean(value)
            elif field == 'importe_pendiente' and value:
                try:
                    clean_value = value.replace(',', '.').replace('€', '').replace('$', '').strip()
                    inscripcion_data[field] = Decimal(clean_value) if clean_value else Decimal('0')
                except:
                    inscripcion_data[field] = Decimal('0')
            else:
                inscripcion_data[field] = value or None
            continue
        
        # Caso especial: nombre completo
        if field == 'nombre_completo' and value:
            parts = value.split(' ', 1)
            if not persona_data.get('nombre'):
                persona_data['nombre'] = parts[0]
            if len(parts) > 1 and not persona_data.get('apellidos'):
                persona_data['apellidos'] = parts[1]
            continue
            
        # Procesar según tipo de campo
        if field in ['a_pagar', 'pagado', 'pendiente'] and value:
            try:
                clean_value = value.replace(',', '.').replace('€', '').replace('$', '').strip()
                persona_data[field] = Decimal(clean_value) if clean_value else Decimal('0')
            except:
                persona_data[field] = Decimal('0')
        elif field in ['anio_pringado', 'num_familiares'] and value.isdigit():
            persona_data[field] = int(value)
        elif field == 'fecha_nacimiento' and value:
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"]:
                try:
                    persona_data[field] = datetime.datetime.strptime(value, fmt).date()
                    break
                except ValueError:
                    continue
        elif field in ['es_pringado', 'es_anfitrion']:
            persona_data[field] = parse_boolean(value)
        else:
            persona_data[field] = value or None
    
    return persona_data, inscripcion_data

def parse_boolean(value):
    """
    Convierte un valor en booleano considerando formatos comunes.
    """
    if not value:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        value = value.strip().lower()
        return value in ['sí', 'si', 'true', '1', 'yes', 'y', 'verdadero']
    return bool(value)

def validate_row(row, mapeo, row_index):
    """
    Valida una fila del CSV según el mapeo establecido.
    """
    errors = []
    dni_col = mapeo.get('dni')
    nombre_col = mapeo.get('nombre')
    nombre_completo_col = mapeo.get('nombre_completo')
    
    if not dni_col or not row.get(dni_col, '').strip():
        errors.append(f"Fila {row_index}: Falta el DNI/Pasaporte (campo obligatorio).")
    
    if not nombre_col or not row.get(nombre_col, '').strip():
        if not nombre_completo_col or not row.get(nombre_completo_col, '').strip():
            errors.append(f"Fila {row_index}: Falta el Nombre (obligatorio directamente o a través de 'Nombre completo').")
    
    for field, col_name in mapeo.items():
        if not col_name or not row.get(col_name, '').strip():
            continue
        value = row.get(col_name, '').strip()
        if field in ['a_pagar', 'pagado', 'pendiente', 'importe_pendiente']:
            try:
                clean_value = value.replace(',', '.').replace('€', '').replace('$', '').strip()
                if clean_value:
                    Decimal(clean_value)
            except:
                errors.append(f"Fila {row_index}: El campo '{field}' debe ser un número decimal válido. Valor actual: '{value}'")
        elif field in ['anio_pringado', 'num_familiares']:
            if value and not value.isdigit():
                errors.append(f"Fila {row_index}: El campo '{field}' debe ser un número entero. Valor actual: '{value}'")
        elif field == 'fecha_nacimiento' and value:
            is_valid_date = False
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"]:
                try:
                    datetime.datetime.strptime(value, fmt)
                    is_valid_date = True
                    break
                except ValueError:
                    continue
            if not is_valid_date:
                errors.append(f"Fila {row_index}: El campo 'fecha_nacimiento' tiene un formato inválido. Valor actual: '{value}'")
    return errors

@require_http_methods(["POST"])
def inspeccionar_csv(request):
    """API para obtener una vista previa del CSV sin importarlo y almacenar su contenido en sesión"""
    try:
        if not request.FILES.get('csv_file'):
            return JsonResponse({'error': 'No se proporcionó ningún archivo'}, status=400)
            
        csv_file = request.FILES['csv_file']
        # Almacenar el contenido del CSV en sesión (útil para pasos posteriores)
        request.session['csv_file_data'] = csv_file.read().decode('utf-8')
        csv_file.seek(0)
        
        csv_text = TextIOWrapper(csv_file.file, encoding='utf-8')
        reader = csv.DictReader(csv_text)
        columns = reader.fieldnames if reader.fieldnames else []
        preview_rows = []
        for i, row in enumerate(reader):
            if i >= 5:
                break
            preview_rows.append(row)
        
        return JsonResponse({
            'success': True,
            'columns': columns,
            'preview_rows': preview_rows,
            'total_columns': len(columns) if columns else 0,
            'sample_rows': len(preview_rows)
        })
    except Exception as e:
        logger.error(f"Error inspeccionando CSV: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


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


class EscapadaAlojamientoDetailView(DetailView):
    model = EscapadaAlojamiento
    template_name = 'escapada_alojamiento/escapada_alojamiento_detail.html'
    context_object_name = 'ea'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Obtener las habitaciones asociadas ordenadas por número
        habitaciones = self.object.habitaciones.all().order_by('numero')
        # Calcular estadísticas de habitaciones
        total_capacity = sum(hab.capacidad for hab in habitaciones)
        occupancy = sum(hab.ocupacion_actual() for hab in habitaciones)
        available = total_capacity - occupancy
        context['habitaciones'] = habitaciones
        context['total_capacity'] = total_capacity
        context['occupancy'] = occupancy
        context['available'] = available
        return context

class EscapadaAlojamientoDeleteView(DeleteView):
    model = EscapadaAlojamiento
    template_name = 'escapada_alojamiento/escapada_alojamiento_confirm_delete.html'
    
    def get_success_url(self):
        # Redirigir al detalle de la escapada luego de eliminar la asignación.
        # Se asume que el objeto "EscapadaAlojamiento" tiene una referencia a la escapada (self.object.escapada)
        return reverse_lazy('escapada_detail', kwargs={'pk': self.object.escapada.pk})


class EscapadaInscripcionView(View):
    template_name = 'escapada/inscripcion_escapada.html'
    
    def get(self, request, pk):
        escapada = get_object_or_404(Escapada, pk=pk)
        
        # Reiniciar la sesión si se pasa ?reset=true
        if request.GET.get('reset') == 'true':
            for key in ['inscripcion_token', 'persona_dni', 'inscripcion_step', 
                        'capacidad_seleccionada', 'habitacion_seleccionada']:
                request.session.pop(key, None)
            return render(request, self.template_name, {'escapada': escapada})
        
        # Si se envía un parámetro de capacidad, actualizamos la sesión
        capacidad_param = request.GET.get('capacidad')
        if capacidad_param:
            try:
                capacidad_int = int(capacidad_param)
                request.session['capacidad_seleccionada'] = capacidad_int
                # Si ya estamos en el paso de elegir habitación, actualizamos el step
                request.session['inscripcion_step'] = 'elegir_habitacion'
            except ValueError:
                pass  # O manejar el error si el valor no es un entero válido

        # Resto de la lógica: si hay token de sesión, mostrar el paso correspondiente
        session_token = request.session.get('inscripcion_token')
        if session_token:
            persona_dni = request.session.get('persona_dni')
            step = request.session.get('inscripcion_step')
            try:
                persona = Persona.objects.get(dni=persona_dni)
                if step == 'elegir_capacidad':
                    return self._show_capacidad_selection(request, escapada, persona)
                elif step == 'elegir_habitacion':
                    capacidad = request.session.get('capacidad_seleccionada')
                    return self._show_habitaciones(request, escapada, persona, capacidad)
                elif step == 'agregar_companeros':
                    habitacion_id = request.session.get('habitacion_seleccionada')
                    try:
                        habitacion = Habitacion.objects.get(id=habitacion_id)
                        return self._show_companeros_form(request, escapada, persona, habitacion)
                    except Habitacion.DoesNotExist:
                        messages.error(request, "La habitación seleccionada ya no está disponible.")
                        request.session.pop('inscripcion_token', None)
            except Persona.DoesNotExist:
                messages.error(request, "Ha ocurrido un error en tu sesión. Por favor, inténtalo nuevamente.")
                request.session.pop('inscripcion_token', None)

        # Vista inicial: formulario de DNI
        return render(request, self.template_name, {'escapada': escapada})

    def post(self, request, pk):
        """Procesa los diferentes formularios según el paso"""
        escapada = get_object_or_404(Escapada, pk=pk)
        
        # Verificar qué acción se está realizando
        if 'verificar_dni' in request.POST:
            return self._procesar_verificacion_dni(request, escapada)
        elif 'seleccionar_capacidad' in request.POST:
            return self._procesar_seleccion_capacidad(request, escapada)
        elif 'seleccionar_habitacion' in request.POST:
            return self._procesar_seleccion_habitacion(request, escapada)
        elif 'confirmar_companeros' in request.POST:
            return self._procesar_confirmacion_companeros(request, escapada)
        elif 'reservar_habitacion' in request.POST:
            return self._procesar_reserva_temporal(request, escapada)
        else:
            messages.error(request, "Acción no reconocida")
            return redirect('escapada_inscripcion', pk=escapada.pk)
    
    def _procesar_verificacion_dni(self, request, escapada):
        """Procesa la verificación inicial del DNI"""
        dni = request.POST.get('dni', '').upper().strip()
        
        try:
            persona = Persona.objects.get(dni=dni)
            
            # Verificar si la persona está inscrita en esta escapada
            try:
                inscripcion = Inscripcion.objects.get(persona=persona, escapada=escapada)
                
                # Si el importe pendiente es mayor que 0, se muestra el mensaje de pago pendiente.
                if inscripcion.pendiente > 0:
                    return render(request, self.template_name, {
                        'escapada': escapada,
                        'persona': persona,
                        'inscripcion': inscripcion,
                        'pendiente_pago': True  # Variable para usar en la plantilla
                    })
                
                # Si pendiente <= 0, se permite continuar con la inscripción.
                request.session['inscripcion_token'] = f"{persona.pk}_{escapada.pk}_{timezone.now().timestamp()}"
                request.session['persona_dni'] = persona.dni
                request.session['inscripcion_step'] = 'elegir_capacidad'
                
                # Limpiar sesiones anteriores
                for key in ['capacidad_seleccionada', 'habitacion_seleccionada']:
                    if key in request.session:
                        del request.session[key]
                
                return self._show_capacidad_selection(request, escapada, persona)
                
            except Inscripcion.DoesNotExist:
                return render(request, self.template_name, {
                    'escapada': escapada,
                    'persona': persona,
                    'no_inscrito': True
                })
                
        except Persona.DoesNotExist:
            messages.error(request, "No encontramos ninguna persona registrada con ese DNI.")
            return redirect('escapada_inscripcion', pk=escapada.pk)

    def _show_capacidad_selection(self, request, escapada, persona):
        """Muestra el formulario de selección de capacidad"""
        # Obtener las capacidades disponibles en esta escapada
        capacidades_disponibles = (
            Habitacion.objects
            .filter(escapada_alojamiento__escapada=escapada)
            .values_list('capacidad', flat=True)
            .distinct()
            .order_by('capacidad')
        )

        
        return render(request, self.template_name, {
            'escapada': escapada,
            'persona': persona,
            'mostrar_selector_capacidad': True,
            'capacidades_disponibles': capacidades_disponibles
        })
    
    def _procesar_seleccion_capacidad(self, request, escapada):
        """Procesa la selección de capacidad de habitación"""
        dni = request.session.get('persona_dni')
        capacidad = request.POST.get('capacidad')
        sorprendeme = request.POST.get('sorprendeme') == 'on'
        
        if not dni:
            messages.error(request, "Ha ocurrido un error en tu sesión. Por favor, inténtalo nuevamente.")
            return redirect('escapada_inscripcion', pk=escapada.pk)
        
        try:
            persona = Persona.objects.get(dni=dni)
            
            if sorprendeme:
                # Lógica para seleccionar una habitación automáticamente
                habitacion = self._seleccionar_habitacion_automatica(escapada)
                if habitacion:
                    request.session['habitacion_seleccionada'] = habitacion.pk
                    request.session['inscripcion_step'] = 'agregar_companeros'
                    return self._show_companeros_form(request, escapada, persona, habitacion)
                else:
                    messages.error(request, "No pudimos encontrar una habitación disponible. Por favor, selecciona una manualmente.")
                    return self._show_capacidad_selection(request, escapada, persona)
            else:
                # Guardar capacidad seleccionada y continuar
                try:
                    capacidad = int(capacidad)
                    request.session['capacidad_seleccionada'] = capacidad
                    request.session['inscripcion_step'] = 'elegir_habitacion'
                    return self._show_habitaciones(request, escapada, persona, capacidad)
                except (ValueError, TypeError):
                    messages.error(request, "Por favor, selecciona una capacidad válida.")
                    return self._show_capacidad_selection(request, escapada, persona)
                
        except Persona.DoesNotExist:
            messages.error(request, "Ha ocurrido un error en tu sesión. Por favor, inténtalo nuevamente.")
            return redirect('escapada_inscripcion', pk=escapada.pk)
    
    def _seleccionar_habitacion_automatica(self, escapada):
        """Selecciona automáticamente una habitación priorizando las más ocupadas"""
        # Obtener habitaciones disponibles y con al menos una persona
        habitaciones_parciales = (
            Habitacion.objects
            .filter(escapada_alojamiento__escapada=escapada)
            .filter(estado='disponible')
            .annotate(num_personas=Count('reservahabitacion'))
            .filter(num_personas__gt=0, num_personas__lt=F('capacidad'))
            .order_by('-num_personas')
        )
        
        if habitaciones_parciales.exists():
            return habitaciones_parciales.first()
        
        # Si no hay parcialmente ocupadas, cualquier disponible
        habitaciones_disponibles = (
            Habitacion.objects
            .filter(escapada_alojamiento__escapada=escapada)
            .filter(estado='disponible')
            .order_by('?')  # Aleatorio
        )
        
        if habitaciones_disponibles.exists():
            return habitaciones_disponibles.first()
            
        return None
    
    def _show_habitaciones(self, request, escapada, persona, capacidad):
        """Muestra las habitaciones disponibles con la capacidad seleccionada"""
        # Mapeo de capacidades a nombres legibles
        CAPACIDAD_NOMBRES = {
            1: 'Individual',
            2: 'Doble',
            3: 'Triple',
            4: 'Cuádruple',
            5: 'Quintuple',
            6: 'Sextuple',
            7: 'Septuple'
        }

        # Optional: Handle invalid capacity from URL
        try:
            capacidad = int(capacidad)
            # Validar que la capacidad esté dentro de un rango razonable
            if capacidad < 1 or capacidad > 7:
                raise ValueError("Capacidad fuera de rango")
        except (ValueError, TypeError):
            messages.error(request, "Capacidad no válida. Selecciona una capacidad correcta.")
            return self._show_capacidad_selection(request, escapada, persona)
        
        # Obtener todas las capacidades disponibles
        todas_capacidades = (
            Habitacion.objects
            .filter(escapada_alojamiento__escapada=escapada)
            .filter(
                Q(estado='disponible') | 
                Q(estado='reservada', reservado_hasta__lt=timezone.now())
            )
            .values_list('capacidad', flat=True)
            .distinct()
            .order_by('capacidad')
        )

        habitaciones_capacidad = (
            Habitacion.objects
            .filter(escapada_alojamiento__escapada=escapada, capacidad=capacidad)
            .filter(
                Q(estado='disponible') | 
                Q(estado='reservada', reservado_hasta__lt=timezone.now())
            )
            .annotate(ocupacion_actual=Count('reservahabitacion'))
            .filter(ocupacion_actual__lt=F('capacidad'))
        )


        
        # Agrupar habitaciones por alojamiento
        habitaciones_por_alojamiento = {}
        for habitacion in habitaciones_capacidad:
            alojamiento = habitacion.escapada_alojamiento.alojamiento
            if alojamiento.id not in habitaciones_por_alojamiento:
                habitaciones_por_alojamiento[alojamiento.id] = {
                    'alojamiento': alojamiento,
                    'habitaciones': []
                }
            habitaciones_por_alojamiento[alojamiento.id]['habitaciones'].append(habitacion)
        
        return render(request, self.template_name, {
            'escapada': escapada,
            'persona': persona,
            'capacidad_seleccionada': capacidad,
            'capacidad_nombre': CAPACIDAD_NOMBRES.get(capacidad, f"{capacidad} personas"),
            'todas_capacidades': todas_capacidades,
            'habitaciones_por_alojamiento': habitaciones_por_alojamiento.values(),
            'mostrar_habitaciones': True
        })

    def _show_capacidad_selection(self, request, escapada, persona):
        """Muestra el formulario de selección de capacidad"""
        # Mapeo de capacidades a nombres legibles
        CAPACIDAD_NOMBRES = {
            1: 'Individual',
            2: 'Doble',
            3: 'Triple',
            4: 'Cuádruple',
            5: 'Quintuple',
            6: 'Sextuple',
            7: 'Septuple'
        }

        # Obtener las capacidades disponibles en esta escapada
        capacidades_disponibles = (
            Habitacion.objects
            .filter(escapada_alojamiento__escapada=escapada)
            .filter(
                Q(estado='disponible') | 
                Q(estado='reservada', reservado_hasta__lt=timezone.now())
            )
            .values_list('capacidad', flat=True)
            .distinct()
            .order_by('capacidad')
        )
        
        # Transformar capacidades con sus nombres legibles
        capacidades_con_nombres = [
            {
                'valor': cap, 
                'nombre': CAPACIDAD_NOMBRES.get(cap, f"{cap} personas")
            } 
            for cap in capacidades_disponibles
        ]
        
        return render(request, self.template_name, {
            'escapada': escapada,
            'persona': persona,
            'mostrar_selector_capacidad': True,
            'capacidades_disponibles': capacidades_con_nombres
        })
    def _procesar_seleccion_habitacion(self, request, escapada):
        """Procesa la selección de una habitación específica"""
        dni = request.session.get('persona_dni')
        habitacion_id = request.POST.get('habitacion_id')
        
        if not dni or not habitacion_id:
            messages.error(request, "Información incompleta. Por favor, inténtalo nuevamente.")
            return redirect('escapada_inscripcion', pk=escapada.pk)
        
        try:
            persona = Persona.objects.get(dni=dni)
            habitacion = Habitacion.objects.get(id=habitacion_id)
            
            # Verificar que la habitación pertenezca a esta escapada
            if habitacion.escapada_alojamiento.escapada_id != escapada.id:
                messages.error(request, "La habitación seleccionada no pertenece a esta escapada.")
                return redirect('escapada_inscripcion', pk=escapada.pk)
            
            # Verificar disponibilidad
            if not habitacion.esta_disponible() or habitacion.plazas_disponibles() <= 0:
                messages.error(request, "La habitación seleccionada ya no está disponible.")
                capacidad = request.session.get('capacidad_seleccionada')
                return self._show_habitaciones(request, escapada, persona, capacidad)
            
            # Guardar habitación seleccionada
            request.session['habitacion_seleccionada'] = habitacion.id
            request.session['inscripcion_step'] = 'agregar_companeros'
            
            return self._show_companeros_form(request, escapada, persona, habitacion)
                
        except (Persona.DoesNotExist, Habitacion.DoesNotExist):
            messages.error(request, "Ha ocurrido un error. Por favor, inténtalo nuevamente.")
            return redirect('escapada_inscripcion', pk=escapada.pk)
    
    def _show_companeros_form(self, request, escapada, persona, habitacion):
        # Verificar si la habitación está reservada por otro
        if (habitacion.estado == 'reservada' and 
            habitacion.reservado_por and 
            habitacion.reservado_por.id != persona.id and
            habitacion.reservado_hasta and 
            habitacion.reservado_hasta > timezone.now()):
            messages.error(request, "La habitación ha sido reservada por otra persona. Por favor, selecciona otra habitación.")
            capacidad = request.session.get('capacidad_seleccionada')
            return self._show_habitaciones(request, escapada, persona, capacidad)
        
        # Calcular plazas totales y ocupadas
        plazas_totales = habitacion.capacidad
        # Usamos la propiedad 'ocupantes' (ya definida en el modelo) que incluye al anfitrión
        ocupantes = habitacion.ocupantes  
        # Calculamos cuántos compañeros ya hay (excluyendo al anfitrión)
        compañeros_actuales = [p for p in ocupantes if p.dni != persona.dni]
        
        # El número máximo de compañeros permitidos es (capacidad - 1)
        available_companion_slots = max(0, habitacion.capacidad - 1 - len(compañeros_actuales))
        
        # Nota: Si la habitación es individual, available_companion_slots será 0.
        
        return render(request, self.template_name, {
            'escapada': escapada,
            'persona': persona,
            'habitacion': habitacion,
            'plazas_disponibles': habitacion.capacidad - len(ocupantes),  # si aún te interesa usar este dato
            'plazas_companeros': available_companion_slots,  # NUEVO: cupos para compañeros
            'puede_reservar': habitacion.estado != 'reservada' or (habitacion.reservado_por and habitacion.reservado_por.id == persona.id),
            'expiracion_reserva': habitacion.reservado_hasta if (habitacion.reservado_por and habitacion.reservado_por.id == persona.dni) else None,
            'ocupantes_actuales': ocupantes,
            'mostrar_form_companeros': True
        })
    
    def _procesar_reserva_temporal(self, request, escapada):
        """Procesa la reserva temporal de una habitación"""
        dni = request.session.get('persona_dni')
        habitacion_id = request.session.get('habitacion_seleccionada')
        
        if not dni or not habitacion_id:
            messages.error(request, "Ha ocurrido un error en tu sesión. Por favor, inténtalo nuevamente.")
            return redirect('escapada_inscripcion', pk=escapada.pk)
        
        try:
            persona = Persona.objects.get(dni=dni)
            habitacion = Habitacion.objects.get(id=habitacion_id)
            
            # Realizar la reserva temporal
            if habitacion.reservar_temporalmente(persona):
                # Actualizar información de la persona como anfitrión
                inscripcion = Inscripcion.objects.get(persona=persona, escapada=escapada)
                inscripcion.es_anfitrion = True
                inscripcion.save()
                
                persona.es_anfitrion = True
                persona.save()
                
                messages.success(request, f"Has reservado la habitación por 15 minutos. Ahora puedes agregar a tus compañeros.")
                return self._show_companeros_form(request, escapada, persona, habitacion)
            else:
                messages.error(request, "No se pudo reservar la habitación. Es posible que ya no esté disponible.")
                capacidad = request.session.get('capacidad_seleccionada')
                return self._show_habitaciones(request, escapada, persona, capacidad)
                
        except (Persona.DoesNotExist, Habitacion.DoesNotExist, Inscripcion.DoesNotExist):
            messages.error(request, "Ha ocurrido un error en tu sesión. Por favor, inténtalo nuevamente.")
            return redirect('escapada_inscripcion', pk=escapada.pk)
    
    def _procesar_confirmacion_companeros(self, request, escapada):
        """Procesa la confirmación final con compañeros"""
        dni_anfitrion = request.session.get('persona_dni')
        habitacion_id = request.session.get('habitacion_seleccionada')
        dnis_companeros = request.POST.getlist('dni_companero')
        
        if not dni_anfitrion or not habitacion_id:
            messages.error(request, "Ha ocurrido un error en tu sesión. Por favor, inténtalo nuevamente.")
            return redirect('escapada_inscripcion', pk=escapada.pk)
        
        try:
            anfitrion = Persona.objects.get(dni=dni_anfitrion)
            habitacion = Habitacion.objects.get(id=habitacion_id)
            
            # Verificar disponibilidad
            plazas_disponibles = habitacion.plazas_disponibles()
            if plazas_disponibles <= 0:
                messages.error(request, "La habitación ya no tiene plazas disponibles.")
                return redirect('escapada_inscripcion', pk=escapada.pk)
            
            # Verificar que la habitación no esté reservada por otra persona
            if (habitacion.estado == 'reservada' and 
                habitacion.reservado_por and 
                habitacion.reservado_por.id != anfitrion.id and
                habitacion.reservado_hasta and 
                habitacion.reservado_hasta > timezone.now()):
                messages.error(request, "La habitación ha sido reservada por otra persona. Por favor, selecciona otra habitación.")
                capacidad = request.session.get('capacidad_seleccionada')
                return self._show_habitaciones(request, escapada, anfitrion, capacidad)
            
            # Verificar DNIs de compañeros
            companeros_validos = []
            dnis_invalidos = []

            # Verificar si el anfitrión ya tiene asignada la habitación
            if not ReservaHabitacion.objects.filter(persona=anfitrion, habitacion=habitacion).exists():
                # Asigna la habitación creando una reserva
                ReservaHabitacion.objects.create(persona=anfitrion, habitacion=habitacion)

            
            # Luego procesar compañeros
            for dni in dnis_companeros:
                if not dni.strip():
                    continue
                    
                try:
                    companero = Persona.objects.get(dni=dni.strip().upper())
                    
                    # Verificar inscripción y pago
                    try:
                        inscripcion = Inscripcion.objects.get(persona=companero, escapada=escapada)
                        if inscripcion.ha_pagado:
                            companeros_validos.append(companero)
                        else:
                            dnis_invalidos.append({
                                'dni': dni,
                                'motivo': f"{companero.nombre} no ha completado el pago."
                            })
                    except Inscripcion.DoesNotExist:
                        dnis_invalidos.append({
                            'dni': dni,
                            'motivo': f"{companero.nombre} no está inscrito en esta escapada."
                        })
                        
                except Persona.DoesNotExist:
                    dnis_invalidos.append({
                        'dni': dni,
                        'motivo': "Persona no encontrada en el sistema."
                    })
            
            # Si hay DNIs inválidos, mostrar errores
            if dnis_invalidos:
                return render(request, self.template_name, {
                    'escapada': escapada,
                    'persona': anfitrion,
                    'habitacion': habitacion,
                    'dnis_invalidos': dnis_invalidos,
                    'companeros_validos': companeros_validos,
                    'plazas_disponibles': plazas_disponibles,
                    'ocupantes_actuales': habitacion.persona_set.all(),
                    'mostrar_form_companeros': True
                })
            
            # Asignar compañeros a la habitación
            for companero in companeros_validos:
                companero.asignar_habitacion(habitacion)
            
            # Finalizar reserva si existe
            if habitacion.estado == 'reservada' and habitacion.reservado_por and habitacion.reservado_por.id == anfitrion.id:
                habitacion.estado = 'ocupada' if habitacion.plazas_disponibles() == 0 else 'disponible'
                habitacion.reservado_por = None
                habitacion.reservado_hasta = None
                habitacion.save()
            
            # Limpiar sesión
            del request.session['inscripcion_token']
            del request.session['persona_dni']
            del request.session['inscripcion_step']
            
            for key in ['capacidad_seleccionada', 'habitacion_seleccionada']:
                if key in request.session:
                    del request.session[key]
            
            # Mensaje de éxito
            messages.success(
                request, 
                f"¡Asignación completa! Te has registrado junto con {len(companeros_validos)} "
                f"compañeros en la habitación {habitacion.numero}."
            )
            
            # Redirigir a la página de confirmación
            return render(request, self.template_name, {
                'escapada': escapada,
                'confirmacion_final': True,
                'habitacion': habitacion,
                'anfitrion': anfitrion,
                'companeros': companeros_validos
            })
                
        except (Persona.DoesNotExist, Habitacion.DoesNotExist):
            messages.error(request, "Ha ocurrido un error en tu sesión. Por favor, inténtalo nuevamente.")
            return redirect('escapada_inscripcion', pk=escapada.pk)
        