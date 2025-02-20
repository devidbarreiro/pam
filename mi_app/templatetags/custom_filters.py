from django import template
from collections import defaultdict
from django.forms.boundfield import BoundField

register = template.Library()

@register.filter
def join_escapada_ids(inscripciones):
    return ','.join(str(inscripcion.escapada_id) for inscripcion in inscripciones)



@register.filter(name='add_class')
def add_class(value, arg):
    """
    Adds a CSS class to a form field
    Usage: {{ form.field|add_class:"my-class" }}
    """
    if isinstance(value, BoundField):
        # Get the current class attribute or use an empty string
        current_class = value.field.widget.attrs.get('class', '')
        
        # Combine existing classes with new classes
        if current_class:
            new_classes = f"{current_class} {arg}"
        else:
            new_classes = arg
        
        # Set the new class attribute
        value.field.widget.attrs['class'] = new_classes
    
    return value

@register.filter(name='sub')
def sub(value, arg):
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter(name='plazas_totales')
def plazas_totales(habitaciones):
    try:
        return sum(h.capacidad for h in habitaciones)
    except Exception:
        return 0


@register.filter(name='personas_asignadas')
def personas_asignadas(habitaciones):
    try:
        return sum(h.ocupacion_actual() for h in habitaciones)
    except Exception:
        return 0

@register.filter(name='habitaciones_disponibles')
def habitaciones_disponibles(habitaciones):
    """
    Suma el número de plazas disponibles en cada habitación.
    """
    try:
        return sum(h.plazas_disponibles() for h in habitaciones)
    except Exception:
        return 0
    

@register.filter(name='agrupar_por_tipo')
def agrupar_por_tipo(habitaciones):
    """
    Agrupa un queryset (o lista) de habitaciones por su tipo (usando get_tipo_display)
    y retorna un iterable de tuplas: (tipo, {estadísticas...}).
    """
    grouped = defaultdict(lambda: {'cantidad': 0, 'capacidad_total': 0, 'ocupadas': 0, 'disponibles': 0})
    for habitacion in habitaciones:
        tipo = habitacion.get_tipo_display()  # Si deseas el valor legible, o bien habitacion.tipo si prefieres el código
        grouped[tipo]['cantidad'] += 1
        grouped[tipo]['capacidad_total'] += habitacion.capacidad
        grouped[tipo]['ocupadas'] += habitacion.ocupacion_actual()
        grouped[tipo]['disponibles'] += habitacion.plazas_disponibles()
    # Retorna los items agrupados, por ejemplo, como una lista de tuplas
    return grouped.items()
