# models.py

from django.db import models

TIPO_ESCAPADA_CHOICES = [
    ('universitarios', 'Universitarios'),
    ('profesionales', 'Profesionales'),
    ('senior', 'Senior'),
]

ESTADO_ESCAPADA_CHOICES = [
    ('abierta', 'Abierta'),
    ('cerrada', 'Cerrada'),
    ('cancelada', 'Cancelada'),
]

class Escapada(models.Model):
    # Declaramos explícitamente el campo 'id'
    id = models.AutoField(primary_key=True)

    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=50, choices=TIPO_ESCAPADA_CHOICES)
    num_plazas = models.PositiveIntegerField(blank=True, null=True)
    num_inscritos = models.PositiveIntegerField(default=0, blank=True, null=True)  # No requerido
    fecha_ini = models.DateField(blank=True, null=True)
    fecha_fin = models.DateField(blank=True, null=True)
    lugar = models.CharField(max_length=200, blank=True, null=True)
    url_formulario_inscripcion = models.URLField(blank=True, null=True)  # No requerido
    descripcion = models.TextField(blank=True, null=True)                # No requerido
    imagen = models.ImageField(upload_to='escapadas/', blank=True, null=True)  # No requerido
    estado = models.CharField(max_length=20, choices=ESTADO_ESCAPADA_CHOICES, default='cerrada')  # Valor por defecto

    def __str__(self):
        return self.nombre


# --- Alojamiento ---
TIPO_ALOJAMIENTO_CHOICES = [
    ('hotel', 'Hotel'),
    ('hostal', 'Hostal'),
    ('casa_rural', 'Casa Rural'),
    # Otros tipos según se necesite
]

class Alojamiento(models.Model):
    nombre = models.CharField(max_length=200)
    direccion = models.TextField()
    telefono = models.CharField(max_length=20)
    correo = models.EmailField()
    num_habitaciones = models.PositiveIntegerField()
    tipo_alojamiento = models.CharField(max_length=50, choices=TIPO_ALOJAMIENTO_CHOICES, default='hotel')
    imagen = models.ImageField(upload_to='alojamientos/', blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    horario_checkin = models.TimeField(blank=True, null=True)
    horario_checkout = models.TimeField(blank=True, null=True)

    def __str__(self):
        return self.nombre

# --- Relación N:M entre Escapada y Alojamiento (tabla intermedia) ---
class EscapadaAlojamiento(models.Model):
    escapada = models.ForeignKey(Escapada, on_delete=models.CASCADE, related_name="escapadas_alojamiento")
    alojamiento = models.ForeignKey(Alojamiento, on_delete=models.CASCADE, related_name="alojamientos_escapada")

    class Meta:
        unique_together = ("escapada", "alojamiento")

    def __str__(self):
        return f"{self.escapada} - {self.alojamiento}"

# --- Habitacion: dependiente de la combinación Escapada-Alojamiento ---
TIPO_HABITACION_CHOICES = [
    ('individual', 'Individual'),
    ('doble', 'Doble'),
    ('suite', 'Suite'),
]

ESTADO_HABITACION_CHOICES = [
    ('disponible', 'Disponible'),
    ('ocupada', 'Ocupada'),
    ('reservada', 'Reservada'),
]

class Habitacion(models.Model):
    # La habitación se crea para una asociación concreta de Escapada y Alojamiento.
    escapada_alojamiento = models.ForeignKey(
        EscapadaAlojamiento,
        on_delete=models.CASCADE,
        related_name="habitaciones"
    )
    numero = models.CharField(max_length=20)  # Identificador o número de habitación
    capacidad = models.PositiveIntegerField()
    tipo = models.CharField(max_length=50, choices=TIPO_HABITACION_CHOICES, default='individual')
    descripcion = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_HABITACION_CHOICES, default='disponible')
    
    class Meta:
        # Evita que se repita el número de habitación en la misma asociación.
        unique_together = ('escapada_alojamiento', 'numero')
    
    def __str__(self):
        return f"Habitación {self.numero} ({self.escapada_alojamiento})"

# --- Persona: usuarios inscritos que seleccionan una habitación ---
class Persona(models.Model):
    dni = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=100)
    email = models.EmailField()
    telefono = models.CharField(max_length=20, blank=True, null=True)
    # El alojamiento puede asignarse previamente (por ejemplo, mediante importación de datos)
    alojamiento = models.ForeignKey(Alojamiento, on_delete=models.SET_NULL, null=True, blank=True)
    # La habitación seleccionada; cada persona puede estar en una única habitación.
    habitacion = models.ForeignKey(Habitacion, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.nombre} ({self.dni})"
