# prueba/mi_app/middleware.py
from django.utils import timezone
from mi_app.models import Habitacion

class HabitacionAvailabilityMiddleware:
    """
    Middleware que, cada 5 segundos, recorre las habitaciones
    en estado 'reservada' (con 'reservado_hasta' definido) y 
    llama a 'esta_disponible()' para refrescar su estado.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.last_update = timezone.now()

    def __call__(self, request):
        now = timezone.now()
        if (now - self.last_update).total_seconds() >= 5:
            self.last_update = now
            # Actualizamos solo las habitaciones que están reservadas y tienen fecha de expiración
            habitaciones_reservadas = Habitacion.objects.filter(
                estado='reservada',
                reservado_hasta__isnull=False
            )
            for habitacion in habitaciones_reservadas:
                habitacion.esta_disponible()  # Este método se encarga de actualizar el estado si ya expiró
        response = self.get_response(request)
        return response
