# views.py

import csv
import datetime
import io
import json
import logging
import traceback
from decimal import Decimal
from io import BytesIO, TextIOWrapper

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.views.generic import (
    CreateView, DeleteView, DetailView, FormView, ListView,
    TemplateView, UpdateView, View
)
from django.contrib.auth.mixins import LoginRequiredMixin

from .forms import (
    CSVImportForm, EscapadaAlojamientoForm, EscapadaAlojamientoMultipleForm,
    HabitacionBulkForm, HabitacionForm, PersonaForm, PersonaInscripcionForm
)
from .models import (
    Alojamiento, Escapada, EscapadaAlojamiento, Habitacion, Inscripcion,
    Persona, ReservaHabitacion, TIPO_HABITACION_CHOICES, ESTADO_HABITACION_CHOICES
)
import csv
from decimal import Decimal
import datetime
from django.db import transaction
from django.core.exceptions import ValidationError
from typing import Dict, List, Tuple, Any, Optional
import logging
from io import TextIOWrapper
from django.http import JsonResponse


class HomeView(TemplateView, LoginRequiredMixin, UserPassesTestMixin):
    template_name = 'home.html'
    
    def test_func(self):
        # Permitir si el usuario es superuser o su username es uno de los autorizados
        return self.request.user.is_superuser or self.request.user.username in ['gabi', 'david', 'checkin']

# --------------------
# VIEWS PARA ESCAPADA
# --------------------

class EscapadaListView(ListView, LoginRequiredMixin, UserPassesTestMixin):
    model = Escapada
    template_name = 'escapada/escapada_list.html'
    context_object_name = 'escapadas'
    
    def post(self, request, *args, **kwargs):
        escapada_id = request.POST.get('escapada_id')
        if escapada_id:
            try:
                escapada = get_object_or_404(Escapada, id=escapada_id)
                nombre = escapada.nombre
                escapada.delete()
                messages.success(request, f'La escapada "{nombre}" ha sido eliminada correctamente.')
            except Exception as e:
                messages.error(request, f'Error al eliminar la escapada: {str(e)}')
        
        return HttpResponseRedirect(reverse_lazy('escapada_list'))

    def test_func(self):
        # Permitir si el usuario es superuser o su username es uno de los autorizados
        return self.request.user.is_superuser or self.request.user.username in ['gabi', 'david', 'checkin']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Aplicar filtros si existen
        search = self.request.GET.get('search')
        fecha_desde = self.request.GET.get('fecha_desde')
        fecha_hasta = self.request.GET.get('fecha_hasta')
        
        if search:
            queryset = queryset.filter(
                Q(nombre__icontains=search) | Q(lugar__icontains=search)
            )
        
        if fecha_desde:
            queryset = queryset.filter(fecha_ini__gte=fecha_desde)
            
        if fecha_hasta:
            queryset = queryset.filter(fecha_fin__lte=fecha_hasta)
            
        return queryset
class EscapadaCreateView(CreateView):
    model = Escapada
    fields = '__all__'
    template_name = 'escapada/escapada_form.html'
    success_url = reverse_lazy('escapada_list')

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
    paginate_by = 10

    def post(self, request, *args, **kwargs):
        alojamiento_id = request.POST.get('alojamiento_id')
        if alojamiento_id:
            try:
                alojamiento = get_object_or_404(Alojamiento, id=alojamiento_id)
                nombre = alojamiento.nombre
                alojamiento.delete()
                messages.success(request, f'El alojamiento "{nombre}" ha sido eliminado correctamente.')
            except Exception as e:
                messages.error(request, f'Error al eliminar el alojamiento: {str(e)}')
        
        return HttpResponseRedirect(reverse_lazy('alojamiento_list'))

    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.GET.get('q')
        
        if q:
            queryset = queryset.filter(
                Q(nombre__icontains=q) | 
                Q(direccion__icontains=q) |
                Q(telefono__icontains=q)
            )
            
        return queryset

class AlojamientoCreateView(CreateView):
    model = Alojamiento
    fields = '__all__'
    template_name = 'alojamiento/alojamiento_form.html'
    success_url = reverse_lazy('alojamiento_list')

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
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        habitacion = self.get_object()
        
        # Obtener personas alojadas a través de ReservaHabitacion
        context['ocupantes'] = ReservaHabitacion.objects.filter(
            habitacion=habitacion
        ).select_related('persona')
        
        # Obtener personas disponibles para asignar (inscritas en la escapada pero sin habitación)
        personas_ya_alojadas = ReservaHabitacion.objects.filter(
            habitacion__escapada_alojamiento=habitacion.escapada_alojamiento
        ).values_list('persona_id', flat=True)
        
        context['personas_disponibles'] = Inscripcion.objects.filter(
            escapada=habitacion.escapada_alojamiento.escapada
        ).exclude(
            persona_id__in=personas_ya_alojadas
        ).select_related('persona')
        
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get('action')
        
        if action == 'asignar':
            self._asignar_persona(request)
        elif action == 'desalojar':
            self._desalojar_persona(request)
            
        return redirect(reverse('habitacion_detail', kwargs={'pk': self.object.pk}))
    
    def _asignar_persona(self, request):
        persona_id = request.POST.get('persona_id')
        try:
            # Verificar que la persona está inscrita en la escapada
            inscripcion = Inscripcion.objects.get(
                persona_id=persona_id,
                escapada=self.object.escapada_alojamiento.escapada
            )
            
            # Verificar capacidad de la habitación
            if self.object.plazas_disponibles() > 0:
                # Crear nueva reserva
                ReservaHabitacion.objects.create(
                    persona_id=persona_id,
                    habitacion=self.object
                )
                
                # Actualizar estado de la habitación
                self.object.estado = 'ocupada'
                self.object.save()
                
                messages.success(request, f"Se ha asignado a {inscripcion.persona.nombre} a la habitación.")
            else:
                messages.error(request, "No hay plazas disponibles en esta habitación.")
                
        except Inscripcion.DoesNotExist:
            messages.error(request, "La persona debe estar inscrita en la escapada para poder asignarle una habitación.")
        except Exception as e:
            messages.error(request, f"Error al asignar persona: {str(e)}")

    def _desalojar_persona(self, request):
        try:
            reserva = ReservaHabitacion.objects.get(
                persona_id=request.POST.get('persona_id'),
                habitacion=self.object
            )
            nombre_persona = reserva.persona.nombre
            reserva.delete()
            
            # Actualizar estado si la habitación queda vacía
            if not ReservaHabitacion.objects.filter(habitacion=self.object).exists():
                self.object.estado = 'disponible'
                self.object.save()
                
            messages.success(request, f"Se ha desalojado a {nombre_persona} de la habitación.")
        except ReservaHabitacion.DoesNotExist:
            messages.error(request, "Esta persona no se encuentra alojada en esta habitación.")
        except Exception as e:
            messages.error(request, f"Error al desalojar: {str(e)}")
            
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
    ordering = ['nombre', 'apellidos']

    def get_queryset(self):
        queryset = super().get_queryset()

        # Excluir registros sin pk
        queryset = queryset.exclude(pk='')

        # Filtro de búsqueda por nombre, apellidos o DNI
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(nombre__icontains=search_query) |
                Q(apellidos__icontains=search_query) |
                Q(dni__icontains=search_query)
            )

        # Filtro por escapada (según la inscripción)
        escapada_id = self.request.GET.get('escapada')
        if escapada_id:
            queryset = queryset.filter(inscripciones__escapada__id=escapada_id)

        # Filtro por estado de pago
        pago_filter = self.request.GET.get('pago')
        if pago_filter:
            if pago_filter == 'pagado':
                queryset = queryset.filter(inscripciones__ha_pagado=True)
            elif pago_filter == 'pendiente':
                queryset = queryset.filter(inscripciones__ha_pagado=False)

        # Prefetch para optimizar consultas y evitar repeticiones
        queryset = queryset.prefetch_related(
            'inscripciones', 'inscripciones__escapada',
            'habitaciones_reservadas', 'habitaciones_reservadas__escapada_alojamiento',
            'habitaciones_reservadas__escapada_alojamiento__alojamiento'
        ).distinct()

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Estadísticas generales (sin aplicar los filtros de búsqueda)
        total_personas = Persona.objects.exclude(pk='').count()
        context['total_personas'] = total_personas

        personas_pagadas = Persona.objects.exclude(pk='').filter(inscripciones__ha_pagado=True).distinct().count()
        context['personas_pagadas'] = personas_pagadas

        personas_pendientes = Persona.objects.exclude(pk='').filter(
            inscripciones__ha_pagado=False,
            inscripciones__isnull=False
        ).distinct().count()
        context['personas_pendientes'] = personas_pendientes

        # Escapadas disponibles para el filtro
        context['escapadas'] = Escapada.objects.all().order_by('-fecha_ini')

        # Mejorar la paginación personalizada
        page_obj = context.get('page_obj')
        if page_obj and page_obj.has_other_pages():
            paginator = context.get('paginator')
            num_pages = paginator.num_pages
            current_page = page_obj.number
            if num_pages <= 7:
                page_range = range(1, num_pages + 1)
            else:
                if current_page <= 4:
                    page_range = list(range(1, 6)) + ['...', num_pages]
                elif current_page >= num_pages - 3:
                    page_range = [1, '...'] + list(range(num_pages - 4, num_pages + 1))
                else:
                    page_range = [1, '...'] + list(range(current_page - 1, current_page + 2)) + ['...', num_pages]
            context['page_range'] = page_range

        # Pasar los parámetros actuales de búsqueda y filtros a la plantilla
        context['query'] = self.request.GET.get('q', '')
        context['escapada_filter'] = self.request.GET.get('escapada', '')
        context['pago_filter'] = self.request.GET.get('pago', '')

        return context

class PersonaCreateView(CreateView):
    model = Persona
    form_class = PersonaInscripcionForm
    template_name = "persona/persona_form.html"
    success_url = reverse_lazy("persona_list")  # Ajusta a tu URL

    def form_valid(self, form):
        response = super().form_valid(form)
        # En form.save() ya se creará la persona e inscripción (si aplica)
        return response

class PersonaDetailView(DetailView):
    model = Persona
    template_name = 'persona/persona_detail.html'
    context_object_name = 'persona'

class PersonaUpdateView(UpdateView):
    model = Persona
    form_class = PersonaInscripcionForm
    template_name = "persona/persona_form.html"
    success_url = reverse_lazy("persona_list")

    def form_valid(self, form):
        return super().form_valid(form)

class PersonaDeleteView(DeleteView):
    model = Persona
    template_name = 'persona/persona_confirm_delete.html'
    success_url = reverse_lazy('persona_list')

@method_decorator(csrf_exempt, name='dispatch')
class InscribirPersonasView(View):
    """
    Vista basada en clase para inscribir una o múltiples personas en una o múltiples escapadas.
    Con decorador CSRF exempt para solucionar problemas de 405 Method Not Allowed.
    """
    
    def get(self, request, *args, **kwargs):
        """Redirige a la lista de personas si se accede por GET"""
        return redirect('persona_list')
        
    def post(self, request, *args, **kwargs):
        """Procesa la inscripción de personas en escapadas"""
        try:
            # Imprimir los datos recibidos para diagnóstico
            print(f"POST data recibida: {request.POST}")
            
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
                if not persona_id.strip():
                    continue
                    
                try:
                    persona = Persona.objects.get(pk=persona_id.strip())
                    
                    for escapada_id in escapadas_ids:
                        if not escapada_id.strip():
                            continue
                            
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
                            print(f"Error: Escapada con ID {escapada_id} no existe")
                        except Exception as e:
                            errores += 1
                            print(f"Error al inscribir: {str(e)}")
                
                except Persona.DoesNotExist:
                    errores += 1
                    print(f"Error: Persona con ID {persona_id} no existe")
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
            
        except Exception as e:
            print(f"Error crítico en InscribirPersonasView: {str(e)}")
            messages.error(request, f"Se produjo un error inesperado: {str(e)}")
            return redirect('persona_list')

logger = logging.getLogger(__name__)

class CSVImportError(Exception):
    """Custom exception for CSV import errors"""
    pass

class CSVValidator:
    """Handles CSV validation logic"""
    
    @staticmethod
    def validate_required_fields(mapeo: Dict[str, str], fieldnames: List[str]) -> List[str]:
        """Validate that all required mapped fields exist in CSV"""
        errors = []
        for field_name, column_name in mapeo.items():
            if column_name and column_name not in fieldnames:
                errors.append(f"La columna '{column_name}' mapeada al campo '{field_name}' no existe en el CSV.")
        return errors

    @staticmethod
    def validate_mandatory_fields(mapeo: Dict[str, str]) -> List[str]:
        """Validate that mandatory fields are mapped"""
        required_fields = ['dni', 'nombre']
        missing = [field for field in required_fields if field not in mapeo or not mapeo[field]]
        return [f"Faltan mapeos para campos obligatorios: {', '.join(missing)}"] if missing else []

    @staticmethod
    def validate_row_data(row: Dict[str, str], mapeo: Dict[str, str], row_index: int) -> List[str]:
        """Validate individual row data"""
        errors = []
        
        # Validate mandatory fields
        dni_col = mapeo.get('dni')
        nombre_col = mapeo.get('nombre')
        nombre_completo_col = mapeo.get('nombre_completo')
        
        if not dni_col or not row.get(dni_col, '').strip():
            errors.append(f"Fila {row_index}: Falta el DNI/Pasaporte (campo obligatorio).")
        
        if (not nombre_col or not row.get(nombre_col, '').strip()) and \
           (not nombre_completo_col or not row.get(nombre_completo_col, '').strip()):
            errors.append(f"Fila {row_index}: Falta el Nombre (obligatorio directamente o a través de 'Nombre completo').")

        # Validate data types
        for field, col_name in mapeo.items():
            if not col_name or not row.get(col_name, '').strip():
                continue
                
            value = row.get(col_name, '').strip()
            
            # Validate decimal fields
            if field in ['a_pagar', 'pagado', 'pendiente', 'importe_pendiente']:
                try:
                    clean_value = value.replace(',', '.').replace('€', '').replace('$', '').strip()
                    if clean_value:
                        Decimal(clean_value)
                except:
                    errors.append(
                        f"Fila {row_index}: El campo '{field}' debe ser un número decimal válido. "
                        f"Valor actual: '{value}'"
                    )
            
            # Validate integer fields
            elif field in ['anio_pringado', 'num_familiares']:
                if value:
                    try:
                        # Intentar convertir a float primero y luego a int
                        float_value = float(value)
                        int_value = int(float_value)
                        # Verificar que el float y el int son iguales (no hay decimales)
                        if float_value == int_value:
                            continue
                        errors.append(
                            f"Fila {row_index}: El campo '{field}' debe ser un número entero. "
                            f"Valor actual: '{value}'"
                        )
                    except ValueError:
                        pass
            
            # Validate date fields
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
                    errors.append(
                        f"Fila {row_index}: El campo 'fecha_nacimiento' tiene un formato inválido. "
                        f"Valor actual: '{value}'"
                    )
        
        return errors

class DataProcessor:
    """Handles data processing and transformation"""
    
    # Campos que pertenecen al modelo Inscripcion
    INSCRIPCION_FIELDS = {
        'ha_pagado',
        'tipo_habitacion_preferida',
        'importe_pendiente',
        'a_pagar',
        'pagado',
        'pendiente',
        'tipo_alojamiento_deseado',
        'num_familiares',
        'es_anfitrion_inscripcion'
    }

    # Campos que pertenecen al modelo Persona
    PERSONA_FIELDS = {
        'dni',
        'nombre',
        'apellidos',
        'fecha_nacimiento',
        'correo',
        'estado',
        'sexo',
        'prefijo',
        'telefono',
        'es_pringado',
        'anio_pringado'
    }

    @staticmethod
    def parse_boolean(value: Any) -> bool:
        """Convert various input formats to boolean"""
        if not value:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            value = value.strip().lower()
            return value in ['sí', 'si', 'true', '1', 'yes', 'y', 'verdadero']
        return bool(value)

    @staticmethod
    def parse_decimal(value: str) -> Optional[Decimal]:
        """Parse decimal values with error handling"""
        if not value:
            return Decimal('0')
        try:
            clean_value = value.replace(',', '.').replace('€', '').replace('$', '').strip()
            return Decimal(clean_value) if clean_value else Decimal('0')
        except:
            return Decimal('0')

    @staticmethod
    def parse_date(value: str) -> Optional[datetime.date]:
        """Parse date values with multiple format support"""
        if not value:
            return None
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"]:
            try:
                return datetime.datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None

    @classmethod
    def process_row(cls, row: Dict[str, str], mapeo: Dict[str, str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Process a single row of data according to mapping"""
        persona_data = {}
        inscripcion_data = {}
        
        for field, col_name in mapeo.items():
            if not col_name:
                continue
            
            value = row.get(col_name, '').strip()
            
            # Caso especial: nombre completo
            if field == 'nombre_completo' and value:
                parts = value.split(' ', 1)
                if not persona_data.get('nombre'):
                    persona_data['nombre'] = parts[0]
                if len(parts) > 1 and not persona_data.get('apellidos'):
                    persona_data['apellidos'] = parts[1]
                continue

            # Determinar si el campo pertenece a Inscripcion o Persona
            if field in cls.INSCRIPCION_FIELDS:
                if field in ['ha_pagado', 'es_anfitrion_inscripcion']:
                    inscripcion_data[field.replace('_inscripcion', '')] = cls.parse_boolean(value)
                elif field in ['importe_pendiente', 'a_pagar', 'pagado', 'pendiente']:
                    inscripcion_data[field] = cls.parse_decimal(value)
                elif field in ['num_familiares']:
                    inscripcion_data[field] = int(value) if value.isdigit() else None
                else:
                    inscripcion_data[field] = value or None
            elif field in cls.PERSONA_FIELDS:
                if field == 'fecha_nacimiento':
                    persona_data[field] = cls.parse_date(value)
                elif field in ['es_pringado', 'es_anfitrion']:
                    persona_data[field] = cls.parse_boolean(value)
                elif field == 'anio_pringado':
                    persona_data[field] = int(value) if value.isdigit() else None
                else:
                    persona_data[field] = value or None

        return persona_data, inscripcion_data

class CSVImporter:
    """Main class for handling CSV imports"""
    
    def __init__(self, csv_file, escapada=None, mapeo=None, only_add_to_db=False):
        self.csv_file = csv_file
        self.escapada = escapada
        self.mapeo = mapeo or {}
        self.only_add_to_db = only_add_to_db
        self.validator = CSVValidator()
        self.processor = DataProcessor()
        self.warnings = []
        self.dnis_procesados = set()
        logger.info(f"""
        Inicializando importador:
        - Archivo: {csv_file.name if csv_file else 'No file'}
        - Escapada: {escapada}
        - Mapeo: {mapeo}
        - Solo BD: {only_add_to_db}
        """)

    def validate_csv(self, reader) -> List[str]:
        """Validate CSV structure and content"""
        logger.info("Iniciando validación del CSV")
        errors = []
        
        if not reader.fieldnames:
            logger.error("CSV sin encabezados")
            errors.append('El archivo CSV está vacío o mal formateado.')
            return errors
        
        logger.info(f"Columnas encontradas: {reader.fieldnames}")
        
        # Validate required fields
        field_errors = self.validator.validate_required_fields(self.mapeo, reader.fieldnames)
        if field_errors:
            logger.error(f"Errores en campos requeridos: {field_errors}")
            errors.extend(field_errors)
        
        # Validate mandatory fields
        mandatory_errors = self.validator.validate_mandatory_fields(self.mapeo)
        if mandatory_errors:
            logger.error(f"Errores en campos obligatorios: {mandatory_errors}")
            errors.extend(mandatory_errors)
        
        return errors

    def process_rows(self, reader) -> Tuple[int, int, int]:
        """Process all rows in the CSV"""
        logger.info("Iniciando procesamiento de filas")
        personas_nuevas = 0
        personas_actualizadas = 0
        inscripciones_creadas = 0
        
        for i, row in enumerate(reader, 1):
            logger.info(f"Procesando fila {i}")
            
            # Skip duplicates
            dni = row.get(self.mapeo.get('dni', ''), '').strip()
            if dni in self.dnis_procesados:
                logger.warning(f"DNI duplicado encontrado: {dni}")
                self.warnings.append(f"DNI duplicado en el CSV: {dni}. Solo se procesó la primera ocurrencia.")
                continue
            
            self.dnis_procesados.add(dni)
            logger.info(f"Procesando DNI: {dni}")
            
            try:
                persona_data, inscripcion_data = self.processor.process_row(row, self.mapeo)
                logger.debug(f"""
                Datos procesados para DNI {dni}:
                - Persona: {persona_data}
                - Inscripción: {inscripcion_data}
                """)
                
                # Create or update person
                persona_obj = self.create_or_update_person(persona_data)
                if persona_obj.id not in self.dnis_procesados:
                    if persona_obj._state.adding:
                        personas_nuevas += 1
                        logger.info(f"Nueva persona creada: {dni}")
                    else:
                        personas_actualizadas += 1
                        logger.info(f"Persona actualizada: {dni}")
                
                # Create inscription if needed
                if self.escapada and not self.only_add_to_db:
                    logger.info(f"Intentando crear inscripción para {dni}")
                    created = self.create_inscription(persona_obj, inscripcion_data)
                    if created:
                        inscripciones_creadas += 1
                        logger.info(f"Inscripción creada para {dni}")
                    else:
                        logger.info(f"No se creó inscripción para {dni}")
                    
            except Exception as e:
                logger.error(f"Error processing row for DNI {dni}: {str(e)}", exc_info=True)
                self.warnings.append(f"Error al procesar DNI {dni}: {str(e)}")
                
        logger.info(f"""
        Resultados del procesamiento:
        - Personas nuevas: {personas_nuevas}
        - Personas actualizadas: {personas_actualizadas}
        - Inscripciones creadas: {inscripciones_creadas}
        """)
        return personas_nuevas, personas_actualizadas, inscripciones_creadas

    @transaction.atomic
    def create_or_update_person(self, persona_data):
        """Create or update a person record"""
        dni = persona_data.get('dni')
        logger.info(f"Creando/actualizando persona con DNI: {dni}")
        logger.debug(f"Datos de persona: {persona_data}")
        
        try:
            persona = Persona.objects.get(dni=dni)
            logger.info(f"Persona encontrada: {dni}, actualizando...")
            for k, v in persona_data.items():
                if k not in ['dni', 'id'] and v is not None:
                    setattr(persona, k, v)
            persona.save()
            logger.info(f"Persona actualizada: {dni}")
        except Persona.DoesNotExist:
            logger.info(f"Persona no encontrada: {dni}, creando nueva...")
            persona = Persona.objects.create(**persona_data)
            logger.info(f"Nueva persona creada: {dni}")
        
        return persona

    def create_inscription(self, persona, inscripcion_data) -> bool:
        """Create inscription if conditions are met"""
        logger.info(f"Intentando crear inscripción para persona: {persona.dni}")
        logger.debug(f"Datos de inscripción: {inscripcion_data}")
        
        pendiente = inscripcion_data.get('pendiente', Decimal('0'))
        
        if pendiente and pendiente > 0:
            logger.warning(f"La persona {persona.dni} tiene importe pendiente: {pendiente}")
            self.warnings.append(
                f"La persona {persona.dni} tiene un importe pendiente de {pendiente} y no se inscribió."
            )
            return False
            
        if not Inscripcion.objects.filter(persona=persona, escapada=self.escapada).exists():
            logger.info(f"Creando nueva inscripción para {persona.dni}")
            try:
                Inscripcion.objects.create(
                    persona=persona,
                    escapada=self.escapada,
                    **inscripcion_data
                )
                logger.info(f"Inscripción creada para {persona.dni}")
                return True
            except Exception as e:
                logger.error(f"Error al crear inscripción para {persona.dni}: {e}", exc_info=True)
                self.warnings.append(f"Error al crear inscripción para {persona.dni}: {e}")
                return False
        else:
            logger.info(f"La persona {persona.dni} ya tiene una inscripción para esta escapada")
            return False

    def import_data(self) -> Dict[str, Any]:
        """Main method to handle the import process"""
        logger.info("Iniciando importación de datos")
        try:
            # Prepare CSV reader
            self.csv_file.seek(0)
            csv_text = TextIOWrapper(self.csv_file, encoding='utf-8')
            reader = csv.DictReader(csv_text)
            
            # Validate CSV structure
            validation_errors = self.validate_csv(reader)
            if validation_errors:
                logger.error(f"Errores de validación: {validation_errors}")
                return {
                    'success': False,
                    'errors': validation_errors
                }
            
            # Validate row data
            all_rows = list(reader)
            logger.info(f"Total de filas a procesar: {len(all_rows)}")
            
            row_errors = []
            for i, row in enumerate(all_rows, start=1):
                errors = self.validator.validate_row_data(row, self.mapeo, i)
                if errors:
                    logger.error(f"Errores en fila {i}: {errors}")
                    row_errors.extend(errors)
            
            if row_errors:
                logger.error(f"Se encontraron {len(row_errors)} errores de validación")
                return {
                    'success': False,
                    'errors': [f"Se encontraron {len(row_errors)} errores de validación:"] + row_errors
                }
            
            # Process data
            logger.info("Iniciando procesamiento de filas")
            personas_nuevas, personas_actualizadas, inscripciones_creadas = self.process_rows(all_rows)
            
            result = {
                'success': True,
                'total_imported': personas_nuevas + personas_actualizadas,
                'new_created': personas_nuevas,
                'updated': personas_actualizadas,
                'inscriptions_created': inscripciones_creadas,
                'warnings': self.warnings
            }
            logger.info(f"Importación completada: {result}")
            return result
            
        except Exception as e:
            logger.exception(f"Error en la importación: {str(e)}")
            return {
                'success': False,
                'errors': [f"Error en la importación: {str(e)}"]
            }
            
def importar_personas(request):
    """View for handling person imports"""
    if request.method != 'POST':
        return render(request, 'persona/importar_personas.html', {
            'escapadas': Escapada.objects.all().order_by('-fecha_ini'),
            'campos_persona': get_campos_persona()
        })

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if not is_ajax:
        return handle_traditional_import(request)

    try:
        # Get parameters
        escapada_id = request.POST.get('escapada')
        csv_file = request.FILES.get('csv_file')
        mapping_json = request.POST.get('mapping')
        only_add_to_db = request.POST.get('only_add_to_db') == 'true'

        # Try to get CSV from session if not in request
        if not csv_file and 'csv_file_data' in request.session:
            csv_content = request.session['csv_file_data']
            csv_file = BytesIO(csv_content.encode('utf-8'))
            csv_file.name = "temp.csv"

        # Validate basic requirements
        if not csv_file or not mapping_json:
            return JsonResponse({
                'success': False,
                'errors': ['Falta el archivo CSV o la configuración de mapeo.']
            })

        # Parse mapping
        try:
            mapeo = json.loads(mapping_json)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'errors': ['El formato del mapeo es inválido.']
            })

        # Get escapada if needed
        escapada = None
        if escapada_id and not only_add_to_db:
            try:
                escapada = Escapada.objects.get(id=escapada_id)
            except Escapada.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'errors': [f'No se encontró la escapada con ID {escapada_id}.']
                })

        # Initialize importer and process data
        importer = CSVImporter(
            csv_file=csv_file,
            escapada=escapada,
            mapeo=mapeo,
            only_add_to_db=only_add_to_db
        )
        
        result = importer.import_data()
        return JsonResponse(result)

    except Exception as e:
        logger.exception(f"Error en importación AJAX: {e}")
        return JsonResponse({
            'success': False,
            'errors': [f'Error inesperado: {str(e)}']
        })

def handle_traditional_import(request):
    """Handle traditional (non-AJAX) form submission"""
    form = CSVImportForm(request.POST, request.FILES)
    if not form.is_valid():
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"Error en {field}: {error}")
        return redirect('importar_personas')

    # Get form data
    escapada = form.cleaned_data.get('escapada')
    csv_file = request.FILES['csv_file']
    only_add_to_db = form.cleaned_data.get('only_add_to_db', False)

    # Use default mapping for traditional import
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

    # Initialize importer and process data
    importer = CSVImporter(
        csv_file=csv_file,
        escapada=escapada,
        mapeo=mapeo,
        only_add_to_db=only_add_to_db
    )
    
    result = importer.import_data()
    
    if result['success']:
        messages.success(
            request,
            f"Importación finalizada con éxito. "
            f"Se importaron {result['total_imported']} personas."
        )
        for warning in result.get('warnings', []):
            messages.warning(request, warning)
    else:
        for error in result['errors']:
            messages.error(request, error)

    return redirect('importar_personas')

def get_campos_persona() -> List[Dict[str, Any]]:
    """Return the structure of available person fields for the frontend"""
    return [
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
            'inscripcion': True,
        },
        {
            'id': 'pagado',
            'nombre': 'Importe pagado',
            'descripcion': 'Cantidad ya pagada (formato decimal)',
            'tipo': 'decimal',
            'requerido': False,
            'ejemplo': '75.50',
            'inscripcion': True,
        },
        {
            'id': 'pendiente',
            'nombre': 'Importe pendiente',
            'descripcion': 'Cantidad pendiente de pago (formato decimal)',
            'tipo': 'decimal',
            'requerido': False,
            'ejemplo': '74.50',
            'inscripcion': True,
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
            'inscripcion': True,
        },
        {
            'id': 'num_familiares',
            'nombre': 'Número de familiares',
            'descripcion': 'Cantidad de familiares',
            'tipo': 'entero',
            'requerido': False,
            'ejemplo': '2',
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
    ]

def inspeccionar_csv(request):
    """API endpoint for previewing CSV content without importing"""
    try:
        if not request.FILES.get('csv_file'):
            return JsonResponse({
                'error': 'No se proporcionó ningún archivo'
            }, status=400)
            
        csv_file = request.FILES['csv_file']
        
        # Store CSV content in session for later use
        request.session['csv_file_data'] = csv_file.read().decode('utf-8')
        csv_file.seek(0)
        
        # Preview CSV content
        csv_text = TextIOWrapper(csv_file.file, encoding='utf-8')
        reader = csv.DictReader(csv_text)
        
        preview_data = {
            'success': True,
            'columns': reader.fieldnames or [],
            'preview_rows': [],
            'total_columns': len(reader.fieldnames) if reader.fieldnames else 0,
            'sample_rows': 0
        }
        
        # Get preview rows (limited to 5)
        for i, row in enumerate(reader):
            if i >= 5:
                break
            preview_data['preview_rows'].append(row)
            preview_data['sample_rows'] += 1
            
        return JsonResponse(preview_data)
        
    except Exception as e:
        logger.error(f"Error inspeccionando CSV: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': str(e)
        }, status=500)
        
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
                pass

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
                        habitacion.esta_disponible()
                        return self._show_companeros_form(request, escapada, persona, habitacion)
                    except Habitacion.DoesNotExist:
                        messages.error(request, "La habitación seleccionada ya no está disponible.")
                        request.session.pop('inscripcion_token', None)
            except Persona.DoesNotExist:
                messages.error(request, "Ha ocurrido un error en tu sesión. Por favor, inténtalo nuevamente.")
                request.session.pop('inscripcion_token', None)

        # Vista inicial: formulario de DNI
        return render(request, self.template_name, {'escapada': escapada})
    
    def _procesar_cancelacion_reserva(self, request, escapada):
        dni = request.session.get('persona_dni', request.POST.get('dni'))
        habitacion_id = request.POST.get('habitacion_id')
        
        if not dni or not habitacion_id:
            messages.error(request, "Datos incompletos para cancelar la reserva.")
            return redirect('escapada_inscripcion', pk=escapada.pk)
        
        try:
            persona = Persona.objects.get(dni=dni)
            habitacion = Habitacion.objects.get(id=habitacion_id)
            habitacion.esta_disponible()
            
            # Si la reserva es temporal y la persona es quien la realizó:
            if habitacion.estado == 'reservada' and habitacion.reservado_por and habitacion.reservado_por.id == persona.id:
                habitacion.estado = 'disponible'
                habitacion.reservado_por = None
                habitacion.reservado_hasta = None
                habitacion.save()
                messages.success(request, "Tu reserva temporal ha sido cancelada correctamente.")
            
            # Si la persona tiene una asignación permanente:
            reserva = ReservaHabitacion.objects.filter(persona=persona, habitacion=habitacion).first()
            if reserva:
                reserva.delete()
                # Actualizamos el estado de la habitación si ya no hay ocupantes
                if habitacion.ocupacion_actual() == 0:
                    habitacion.estado = 'disponible'
                    habitacion.save()
                messages.success(request, "Tu asignación de habitación ha sido cancelada correctamente.")
            
            return redirect('escapada_inscripcion', pk=escapada.pk)
                    
        except (Persona.DoesNotExist, Habitacion.DoesNotExist):
            messages.error(request, "No se pudo encontrar la reserva especificada.")
            return redirect('escapada_inscripcion', pk=escapada.pk)

    def post(self, request, pk):
        """Procesa los diferentes formularios según el paso"""
        escapada = get_object_or_404(Escapada, pk=pk)
        
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
        elif 'cancelar_reserva' in request.POST:
            return self._procesar_cancelacion_reserva(request, escapada)
        else:
            messages.error(request, "Acción no reconocida")
            return redirect('escapada_inscripcion', pk=escapada.pk)
    
    def _procesar_verificacion_dni(self, request, escapada):
        """Procesa la verificación inicial del DNI"""
        dni = request.POST.get('dni', '').upper().strip()
        
        try:
            persona = Persona.objects.get(dni=dni)
            
            # Verificar si la persona ya tiene una habitación asignada
            reserva_habitacion = ReservaHabitacion.objects.filter(
                persona=persona,
                habitacion__escapada_alojamiento__escapada_id=escapada.pk
            ).first()
            
            if reserva_habitacion:
                habitacion = reserva_habitacion.habitacion
                companeros = ReservaHabitacion.objects.filter(
                    habitacion=habitacion
                ).exclude(persona=persona).select_related('persona')
                plazas_ocupadas = habitacion.ocupacion_actual()
                plazas_disponibles = habitacion.capacidad - plazas_ocupadas
                return render(request, self.template_name, {
                    'escapada': escapada,
                    'persona': persona,
                    'habitacion': habitacion,
                    'reserva': reserva_habitacion,
                    'companeros': companeros,
                    'plazas_disponibles': plazas_disponibles,
                    'mostrar_reserva_actual': True
                })
            
            # Verificar si tiene una reserva temporal activa
            habitacion_reservada = Habitacion.objects.filter(
                reservado_por=persona,
                escapada_alojamiento__escapada_id=escapada.pk,
                estado='reservada',
                reservado_hasta__gt=timezone.now()
            ).first()
            
            if habitacion_reservada:
                ocupantes = habitacion_reservada.ocupantes
                plazas_disponibles = habitacion_reservada.capacidad - len(ocupantes)
                return render(request, self.template_name, {
                    'escapada': escapada,
                    'persona': persona,
                    'habitacion': habitacion_reservada,
                    'ocupantes_actuales': ocupantes,
                    'plazas_disponibles': plazas_disponibles,
                    'expiracion_reserva': habitacion_reservada.reservado_hasta,
                    'mostrar_form_companeros': True,
                    'puede_reservar': False
                })
            
            # Procesar inscripción normal
            try:
                inscripcion = Inscripcion.objects.get(persona=persona, escapada=escapada)
                
                # AÑADIDO: Comprobar el campo tipo_alojamiento_deseado
                if inscripcion.tipo_alojamiento_deseado:
                    tipo = inscripcion.tipo_alojamiento_deseado.lower()
                    if "sin alojamiento" in tipo:
                        messages.info(request, "Sin alojamiento: No es necesario seleccionar habitación.")
                        return render(request, self.template_name, {
                            'escapada': escapada,
                            'persona': persona,
                            'sin_alojamiento': True
                        })
                    elif "familia" in tipo:
                        messages.info(request, "No te preocupes familia, nosotros nos ocupamos de reservarte la mejor habitación 😉")
                        return render(request, self.template_name, {
                            'escapada': escapada,
                            'persona': persona,
                            'familia': True
                        })
                
                if inscripcion.pendiente > 0:
                    return render(request, self.template_name, {
                        'escapada': escapada,
                        'persona': persona,
                        'inscripcion': inscripcion,
                        'pendiente_pago': True
                    })
                
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
                Q(estado='disponible') | Q(estado='reservada')
            )
            .values_list('capacidad', flat=True)
            .distinct()
            .order_by('capacidad')
        )

        habitaciones_capacidad = (
            Habitacion.objects
            .filter(escapada_alojamiento__escapada=escapada, capacidad=capacidad)
            .filter( Q(estado='disponible') | Q(estado='reservada') )
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
            habitacion.esta_disponible()
            
            # Verificar que la habitación pertenezca a esta escapada
            if habitacion.escapada_alojamiento.escapada_id != escapada.id:
                messages.error(request, "La habitación seleccionada no pertenece a esta escapada.")
                return redirect('escapada_inscripcion', pk=escapada.pk)
            
            # Verificar disponibilidad
            if not habitacion.esta_disponible() or habitacion.plazas_disponibles() <= 0:
                messages.error(request, "La habitación seleccionada ya no está disponible.")
                capacidad = request.session.get('capacidad_seleccionada')
                return self._show_habitaciones(request, escapada, persona, capacidad)
            
            # MODIFICACIÓN: Reservar automáticamente la habitación por 3 minutos
            if habitacion.reservar_temporalmente(persona, minutos=3):
                # La reserva se realizó con éxito
                messages.info(request, "Habitación reservada automáticamente por 3 minutos. Completa tu inscripción antes de que expire.")
            else:
                # La reserva no se pudo realizar
                messages.warning(request, "No se pudo reservar la habitación temporalmente, pero puedes continuar con el proceso.")
            
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
            habitacion.esta_disponible()

            # Llamada al método que reserva la habitación por 15 minutos.
            if habitacion.reservar_temporalmente(persona):
                # Opcional: Actualiza la inscripción para marcar al usuario como anfitrión
                inscripcion = Inscripcion.objects.get(persona=persona, escapada=escapada)
                inscripcion.es_anfitrion = True
                inscripcion.save()

                persona.es_anfitrion = True
                persona.save()

                messages.success(request, "Has reservado la habitación por 15 minutos. Ahora puedes agregar a tus compañeros.")
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
        desde_reserva_actual = request.POST.get('desde_reserva_actual') == 'true'
        
        if not dni_anfitrion:
            messages.error(request, "Ha ocurrido un error en tu sesión. Por favor, inténtalo nuevamente.")
            return redirect('escapada_inscripcion', pk=escapada.pk)
        
        try:
            anfitrion = Persona.objects.get(dni=dni_anfitrion)
            
            # Si viene desde la vista de reserva actual, usamos el habitacion_id del POST
            if desde_reserva_actual:
                habitacion_id = request.POST.get('habitacion_id')
            
            if not habitacion_id:
                messages.error(request, "No se especificó una habitación. Por favor, selecciona una habitación.")
                return redirect('escapada_inscripcion', pk=escapada.pk)
                
            habitacion = Habitacion.objects.get(id=habitacion_id)
            
            # Verificar disponibilidad - ahora consideramos si ya tiene reserva
            reserva_existente = ReservaHabitacion.objects.filter(persona=anfitrion, habitacion=habitacion).exists()
            
            # Obtenemos todos los ocupantes actuales de la habitación
            ocupantes_actuales = []
            for reserva in ReservaHabitacion.objects.filter(habitacion=habitacion):
                ocupantes_actuales.append(reserva.persona)
                
            # Calculamos plazas disponibles considerando a los ocupantes actuales
            plazas_disponibles = habitacion.capacidad - len(ocupantes_actuales)
            
            # Si el anfitrión no está entre los ocupantes, hay que contar su plaza también
            if anfitrion not in ocupantes_actuales and not reserva_existente:
                plazas_disponibles -= 1
                
            if plazas_disponibles < 0:
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
            
            # Filtrar DNIs vacíos y duplicados
            dnis_companeros = [dni.strip().upper() for dni in dnis_companeros if dni.strip()]
            dnis_companeros = list(filter(None, dnis_companeros))  # Eliminar valores vacíos
            
            # Verificar si hay suficientes plazas para los compañeros
            if len(dnis_companeros) > plazas_disponibles:
                messages.error(request, f"Solo hay {plazas_disponibles} plazas disponibles, pero intentaste añadir {len(dnis_companeros)} compañeros.")
                return self._show_companeros_form(request, escapada, anfitrion, habitacion)
                
            # Verificar DNIs de compañeros
            for dni in dnis_companeros:
                try:
                    companero = Persona.objects.get(dni=dni)
                    
                    # Comprobar que no sea el anfitrión
                    if companero.dni == anfitrion.dni:
                        dnis_invalidos.append({
                            'dni': dni,
                            'motivo': "No puedes añadirte a ti mismo como compañero."
                        })
                        continue
                        
                    # Verificar que no tenga ya otra habitación asignada en esta escapada
                    otra_habitacion = ReservaHabitacion.objects.filter(
                        persona=companero,
                        habitacion__escapada_alojamiento__escapada=escapada
                    ).exclude(habitacion=habitacion).first()
                    
                    if otra_habitacion:
                        dnis_invalidos.append({
                            'dni': dni,
                            'motivo': f"{companero.nombre} ya tiene asignada otra habitación en esta escapada."
                        })
                        continue
                    
                    # Verificar que el compañero ya no esté en esta habitación
                    if ReservaHabitacion.objects.filter(persona=companero, habitacion=habitacion).exists():
                        dnis_invalidos.append({
                            'dni': dni,
                            'motivo': f"{companero.nombre} ya está asignado a esta habitación."
                        })
                        continue
                    
                    # Verificar inscripción y pago
                    try:
                        inscripcion = Inscripcion.objects.get(persona=companero, escapada=escapada)
                        if inscripcion.pendiente <= 0:  # Asumiendo que pendiente=0 significa ha_pagado
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
            
            # Si hay DNIs inválidos, mostrar errores y volver al formulario
            if dnis_invalidos:
                return self._show_companeros_form(request, escapada, anfitrion, habitacion, dnis_invalidos)
            
            # Verificar de nuevo que no haya habido cambios en la disponibilidad
            if len(companeros_validos) > plazas_disponibles:
                messages.error(request, "La disponibilidad de la habitación ha cambiado. Por favor, intenta nuevamente.")
                return self._show_habitaciones(request, escapada, anfitrion, habitacion.capacidad)
            
            # Asignar anfitrión a la habitación si aún no tiene reserva
            if not reserva_existente:
                ReservaHabitacion.objects.create(
                    persona=anfitrion, 
                    habitacion=habitacion, 
                    es_anfitrion=True
                )
            
            # Asignar compañeros a la habitación
            for companero in companeros_validos:
                ReservaHabitacion.objects.create(
                    persona=companero,
                    habitacion=habitacion,
                    es_anfitrion=False
                )
            
            # Actualizar estado de la habitación
            ocupacion_actual = ReservaHabitacion.objects.filter(habitacion=habitacion).count()
            if ocupacion_actual >= habitacion.capacidad:
                habitacion.estado = 'ocupada'
            else:
                # Si estaba reservada por anfitrión, ahora será disponible (pero con ocupantes)
                if habitacion.estado == 'reservada' and habitacion.reservado_por and habitacion.reservado_por.id == anfitrion.id:
                    habitacion.estado = 'disponible'
                    habitacion.reservado_por = None
                    habitacion.reservado_hasta = None
            
            habitacion.save()
            
            # Limpiar sesión si no viene desde una reserva actual
            if not desde_reserva_actual:
                for key in ['inscripcion_token', 'persona_dni', 'inscripcion_step', 
                            'capacidad_seleccionada', 'habitacion_seleccionada']:
                    request.session.pop(key, None)
                    
                # Mensaje de éxito
                mensaje = "¡Asignación completa! "
                if len(companeros_validos) > 0:
                    mensaje += f"Has añadido {len(companeros_validos)} compañero{'s' if len(companeros_validos) > 1 else ''} a la habitación."
                else:
                    mensaje += "Te has registrado en la habitación correctamente."
                    
                messages.success(request, mensaje)
                
                # Redirigir a la página de confirmación
                return render(request, self.template_name, {
                    'escapada': escapada,
                    'confirmacion_final': True,
                    'habitacion': habitacion,
                    'anfitrion': anfitrion,
                    'companeros': ReservaHabitacion.objects.filter(habitacion=habitacion).exclude(persona=anfitrion).select_related('persona')
                })
            else:
                # Si viene desde una reserva actual, redirigimos a la misma vista con los datos actualizados
                messages.success(request, f"Has añadido {len(companeros_validos)} compañero{'s' if len(companeros_validos) > 1 else ''} a tu habitación.")
                return redirect('escapada_inscripcion', pk=escapada.pk)
                    
        except (Persona.DoesNotExist, Habitacion.DoesNotExist) as e:
            messages.error(request, f"Ha ocurrido un error en tu sesión. {str(e)}")
            return redirect('escapada_inscripcion', pk=escapada.pk)

    def _show_companeros_form(self, request, escapada, persona, habitacion, dnis_invalidos=None):
        """Muestra el formulario para añadir compañeros"""
        # Verificar si la habitación está reservada por otro
        if (habitacion.estado == 'reservada' and 
            habitacion.reservado_por and 
            habitacion.reservado_por.id != persona.id and
            habitacion.reservado_hasta and 
            habitacion.reservado_hasta > timezone.now()):
            messages.error(request, "La habitación ha sido reservada por otra persona. Por favor, selecciona otra habitación.")
            capacidad = request.session.get('capacidad_seleccionada', habitacion.capacidad)
            return self._show_habitaciones(request, escapada, persona, capacidad)
        
        # Obtener las reservas existentes para esta habitación
        reservas = ReservaHabitacion.objects.filter(habitacion=habitacion).select_related('persona')
        ocupantes = [reserva.persona for reserva in reservas]
        
        # Verificar si el usuario actual ya tiene una reserva
        tiene_reserva = persona in ocupantes
        
        # Calcular plazas disponibles
        plazas_disponibles = habitacion.capacidad - len(ocupantes)
        
        # Si el usuario no tiene reserva, se restará su plaza de las disponibles
        plazas_companeros = plazas_disponibles
        if not tiene_reserva:
            plazas_companeros -= 1
        
        # Asegurarse de que no haya valores negativos
        plazas_companeros = max(0, plazas_companeros)
        
        # Verificar si puede reservar (si no está reservada o si él es quien la reservó)
        puede_reservar = habitacion.estado != 'reservada' or (
            habitacion.reservado_por and habitacion.reservado_por.id == persona.id
        )
        
        # Verificar si tiene reserva temporal activa
        expiracion_reserva = None
        if habitacion.estado == 'reservada' and habitacion.reservado_por and habitacion.reservado_por.id == persona.id:
            expiracion_reserva = habitacion.reservado_hasta
        
        return render(request, self.template_name, {
            'escapada': escapada,
            'persona': persona,
            'habitacion': habitacion,
            'plazas_disponibles': plazas_disponibles,
            'plazas_companeros': plazas_companeros,
            'puede_reservar': puede_reservar,
            'expiracion_reserva': expiracion_reserva,
            'dnis_invalidos': dnis_invalidos,
            'mostrar_form_companeros': True
        })
    
@require_POST
def reservar_habitacion_ajax(request):
    # Se espera que en POST se envíen: habitacion_id y, opcionalmente, el DNI de la persona.
    habitacion_id = request.POST.get('habitacion_id')
    dni = request.POST.get('dni')
    if not habitacion_id or not dni:
        return JsonResponse({'error': 'Información incompleta'}, status=400)
    try:
        persona = Persona.objects.get(dni=dni)
        habitacion = Habitacion.objects.get(id=habitacion_id)
        habitacion.esta_disponible()
    except (Persona.DoesNotExist, Habitacion.DoesNotExist):
        return JsonResponse({'error': 'Datos no encontrados'}, status=404)
    
    # Verificamos disponibilidad
    if not habitacion.esta_disponible():
        return JsonResponse({'error': 'La habitación ya no está disponible'}, status=400)
    
    # Realizamos la reserva temporal (15 minutos)
    habitacion.estado = 'reservada'
    habitacion.reservado_por = persona
    habitacion.reservado_hasta = timezone.now() + datetime.timedelta(minutes=15)
    habitacion.save()
    
    # Calculamos el tiempo restante (en segundos)
    tiempo_restante = int((habitacion.reservado_hasta - timezone.now()).total_seconds())
    return JsonResponse({
        'success': True,
        'tiempo_restante': tiempo_restante,
        'reservado_hasta': habitacion.reservado_hasta.isoformat()
    })

class CheckinListView(View):  # Quitamos LoginRequiredMixin
    template_name = 'escapada/checkin_list.html'
    
    def get(self, request, escapada_id):
        escapada = get_object_or_404(Escapada, pk=escapada_id)
        
        # Obtener búsqueda
        query = request.GET.get('q', '').strip()
        
        # Base queryset de inscripciones
        inscripciones = Inscripcion.objects.filter(escapada=escapada)\
            .select_related('persona')\
            .prefetch_related(
                'persona__reservahabitacion_set',
                'persona__reservahabitacion_set__habitacion',
                'persona__reservahabitacion_set__habitacion__escapada_alojamiento',
                'persona__reservahabitacion_set__habitacion__escapada_alojamiento__alojamiento'
            )
        
        # Aplicar filtro de búsqueda si existe
        if query:
            inscripciones = inscripciones.filter(
                Q(persona__dni__icontains=query) |
                Q(persona__nombre__icontains=query) |
                Q(persona__apellidos__icontains=query)
            )
        
        # Filtros de estado
        estado = request.GET.get('estado')
        if estado == 'pendiente':
            inscripciones = inscripciones.filter(checkin_completado=False)
        elif estado == 'completado':
            inscripciones = inscripciones.filter(checkin_completado=True)
        
        # Estadísticas
        total_inscritos = inscripciones.count()
        checkin_completado = inscripciones.filter(checkin_completado=True).count()
        pendientes_checkin = total_inscritos - checkin_completado
        
        context = {
            'escapada': escapada,
            'inscripciones': inscripciones,
            'query': query,
            'estado': estado,
            'total_inscritos': total_inscritos,
            'checkin_completado': checkin_completado,
            'pendientes_checkin': pendientes_checkin,
        }
        
        # Obtener habitaciones disponibles y tipos
        habitaciones_disponibles = []
        for ea in escapada.escapadas_alojamiento.all():
            habitaciones = ea.habitaciones.all()
            for hab in habitaciones:
                if hab.plazas_disponibles() > 0:
                    habitaciones_disponibles.append(hab)

        # Ordenar por tipo
        habitaciones_disponibles.sort(key=lambda x: x.tipo)

        # Obtener lista de tipos de habitación
        tipos_habitacion = [
            (tipo, nombre) for tipo, nombre in TIPO_HABITACION_CHOICES
            if any(h.tipo == tipo for h in habitaciones_disponibles)
        ]

        context.update({
            'habitaciones_disponibles': habitaciones_disponibles,
            'tipos_habitacion': tipos_habitacion,
        })
        
        return render(request, self.template_name, context)

def realizar_checkin(request, pk):  # Quitamos el decorador @login_required
    inscripcion = get_object_or_404(Inscripcion, pk=pk)
    if request.method == 'POST':
        try:
            inscripcion.realizar_checkin()
            messages.success(request, f"Check-in realizado correctamente para {inscripcion.persona.nombre}")
        except Exception as e:
            messages.error(request, f"Error al realizar el check-in: {str(e)}")
    
    return redirect('checkin_list', escapada_id=inscripcion.escapada.id)

def cancelar_checkin(request, pk):  # Quitamos el decorador @login_required
    inscripcion = get_object_or_404(Inscripcion, pk=pk)
    if request.method == 'POST':
        try:
            inscripcion.cancelar_checkin()
            messages.success(request, f"Check-in cancelado para {inscripcion.persona.nombre}")
        except Exception as e:
            messages.error(request, f"Error al cancelar el check-in: {str(e)}")
    
    return redirect('checkin_list', escapada_id=inscripcion.escapada.id)

@require_POST
def asignar_habitacion_checkin(request):
    inscripcion_id = request.POST.get('inscripcion_id')
    habitacion_id = request.POST.get('habitacion_id')
    
    try:
        inscripcion = Inscripcion.objects.get(pk=inscripcion_id)
        habitacion = Habitacion.objects.get(pk=habitacion_id)
        habitacion.esta_disponible()
        
        # Crear la reserva de habitación
        ReservaHabitacion.objects.create(
            persona=inscripcion.persona,
            habitacion=habitacion,
            es_anfitrion=False
        )
        
        messages.success(request, f'Habitación asignada correctamente a {inscripcion.persona.nombre}')
        
    except (Inscripcion.DoesNotExist, Habitacion.DoesNotExist):
        messages.error(request, 'Error al asignar la habitación. Datos no válidos.')
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Error inesperado: {str(e)}')
    
    return redirect('checkin_list', escapada_id=inscripcion.escapada.id)