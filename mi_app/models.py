from django.db import models
from django.utils import timezone
import datetime
import uuid
from django.core.exceptions import ValidationError

# -----------------------------
# 1. ESCAPADA Y ALOJAMIENTO
# -----------------------------

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
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=50, choices=TIPO_ESCAPADA_CHOICES)
    num_plazas = models.PositiveIntegerField(blank=True, null=True)
    num_inscritos = models.PositiveIntegerField(default=0, blank=True, null=True)
    fecha_ini = models.DateField(blank=True, null=True)
    fecha_fin = models.DateField(blank=True, null=True)
    lugar = models.CharField(max_length=200, blank=True, null=True)
    url_formulario_inscripcion = models.URLField(blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    imagen = models.ImageField(upload_to='escapadas/', blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_ESCAPADA_CHOICES, default='cerrada')

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'escapada'

TIPO_ALOJAMIENTO_CHOICES = [
    ('hotel', 'Hotel'),
    ('hostal', 'Hostal'),
    ('casa_rural', 'Casa Rural'),
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
    
    class Meta:
        db_table = 'alojamiento'


class EscapadaAlojamiento(models.Model):
    escapada = models.ForeignKey(Escapada, on_delete=models.CASCADE, related_name="escapadas_alojamiento")
    alojamiento = models.ForeignKey(Alojamiento, on_delete=models.CASCADE, related_name="alojamientos_escapada")

    class Meta:
        db_table = 'escapadaalojamiento'
        unique_together = ("escapada", "alojamiento")

    def __str__(self):
        return f"{self.escapada} - {self.alojamiento}"


# -------------------------------------------------------
# 2. HABITACION: ahora con codigo_interno y numero_ficticio
# -------------------------------------------------------

TIPO_HABITACION_CHOICES = [
    ('individual', 'Individual'),
    ('doble', 'Doble'),
    ('triple', 'Triple'),
    ('cuadruple', 'Cuádruple'),
    ('quintuple', 'Quíntuple'),
    ('sextuple', 'Sextuple'),
    ('septuple', 'Septuple'),
]

ESTADO_HABITACION_CHOICES = [
    ('disponible', 'Disponible'),
    ('ocupada', 'Ocupada'),
    ('reservada', 'Reservada'),
    ('bloqueada', 'Bloqueada'),
]

class Habitacion(models.Model):
    # AutoField 'id' se crea solo (pk)
    
    # Campo "numero_ficticio" por necesidades específicas
    numero_ficticio = models.CharField(max_length=50, blank=True, null=True)

    escapada_alojamiento = models.ForeignKey(
        'EscapadaAlojamiento',
        on_delete=models.CASCADE,
        related_name="habitaciones"
    )
    numero = models.CharField(max_length=20, blank=True, null=True)  # Identificador o número de habitación "oficial"
    capacidad = models.PositiveIntegerField()
    tipo = models.CharField(max_length=50, choices=TIPO_HABITACION_CHOICES, default='individual')
    descripcion = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_HABITACION_CHOICES, default='disponible')
    
    
    # Opcional: reserva temporal
    reservado_por = models.ForeignKey('Persona', on_delete=models.SET_NULL, null=True, blank=True, related_name="habitaciones_reservadas")
    reservado_hasta = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        # Si no se ha asignado aún el numero_ficticio
        if not self.numero_ficticio:
            # Supongamos que 'ea_id' es el identificador de la asignación de alojamiento (o una porción del mismo)
            # Y 'capacidad' es la capacidad de la habitación
            # Y 'n' es el número secuencial, calculado en función del total de habitaciones ya creadas para esa asignación
            n = self.escapada_alojamiento.habitaciones.count() + 1
            self.numero_ficticio = f"H{self.escapada_alojamiento.alojamiento.pk}{self.capacidad}{n:02d}"
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'habitacion'
        unique_together = ('escapada_alojamiento', 'numero')

    def __str__(self):
        return f"Habitación {self.numero} ({self.escapada_alojamiento})"
    
    def esta_disponible(self):
        if self.estado == 'ocupada':
            return False
            
        # Si está reservada, verificar si la reserva expiró
        if self.estado == 'reservada' and self.reservado_hasta:
            if timezone.now() > self.reservado_hasta:
                self.estado = 'disponible'
                self.reservado_por = None
                self.reservado_hasta = None
                self.save()
                return True
            return False
                
        return self.estado == 'disponible'

    
    def reservar_temporalmente(self, persona, minutos=15):
        """Reserva temporalmente la habitación."""
        if not self.esta_disponible():
            return False
        self.estado = 'reservada'
        self.reservado_por = persona
        self.reservado_hasta = timezone.now() + datetime.timedelta(minutes=minutos)
        self.save()
        return True

    
    @property
    def ocupantes(self):
        return [reserva.persona for reserva in self.reservahabitacion_set.all()]

    
    def ocupacion_actual(self):
        """Retorna el número de personas asignadas a esta habitación (según la tabla intermedia)."""
        return self.reservahabitacion_set.count()
    
    def plazas_disponibles(self):
        return self.capacidad - self.ocupacion_actual()

# ----------------------------------
# 3. PERSONA (sin FK a habitacion)
# ----------------------------------

class Persona(models.Model):
    """
    Ejemplo de persona con 'dni' como campo único
    y 'id' personalizado.
    """
    id = models.CharField(primary_key=True, max_length=50, unique=True)
    dni = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=150, null=True)
    
    fecha_nacimiento = models.DateField(blank=True, null=True)
    correo = models.EmailField(blank=True, null=True)
    sexo = models.CharField(max_length=20, blank=True, null=True)
    prefijo = models.CharField(max_length=20, blank=True, null=True)
    telefono = models.CharField(max_length=20, null=True)
    es_pringado = models.BooleanField(default=False)
    anio_pringado = models.PositiveIntegerField(blank=True, null=True)
    
    
    # Eliminamos los FK directos a Alojamiento y Habitacion.
    # alojamiento = ...
    # habitacion = ...


    def __str__(self):
        return f"{self.id} - {self.nombre} {self.apellidos}"
    
    class Meta:
        db_table = 'persona'

    def save(self, *args, **kwargs):
        """Genera el 'id' si no existe (basado en dni o en la lógica NI...)."""
        if not self.id:
            self.assign_id()
        super().save(*args, **kwargs)

    def assign_id(self):
        if self.dni and len(self.dni) > 5:
            self.id = self.dni.strip().upper()
        else:
            self.id = self._build_custom_id()

    def _build_custom_id(self):
        prefix = "NI"
        aa = (self.nombre[:2] if self.nombre else "").upper().ljust(2, 'X')
        bb = (self.apellidos[:2] if self.apellidos else "").upper().ljust(2, 'X')
        phone_digits = (self.telefono or "")[-4:].rjust(4, '0')
        if self.fecha_nacimiento:
            year = self.fecha_nacimiento.year
            yyy = (year % 100) + 19
        else:
            yyy = 0
        return f"{prefix}{aa}{bb}{phone_digits}{yyy}"


# ----------------------------------
# 4. INSCRIPCION
# ----------------------------------

class Inscripcion(models.Model):
    persona = models.ForeignKey(Persona, on_delete=models.CASCADE, related_name='inscripciones')
    escapada = models.ForeignKey(Escapada, on_delete=models.CASCADE, related_name='inscripciones')
    
    ha_pagado = models.BooleanField(default=False)
    tipo_habitacion_preferida = models.CharField(max_length=20, blank=True, null=True)
    fecha_inscripcion = models.DateTimeField(blank=True, null=True, default=timezone.now)
    importe_pendiente = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    estado = models.CharField(max_length=50, blank=True, null=True) # pasar a clase Inscripción

    a_pagar = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    pagado = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    pendiente = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    tipo_alojamiento_deseado = models.CharField(max_length=100, blank=True, null=True)
    num_familiares = models.PositiveIntegerField(blank=True, null=True)
    
    # Campos para check-in
    fecha_checkin = models.DateTimeField(null=True, blank=True)
    checkin_completado = models.BooleanField(default=False)

    def tiene_habitacion_asignada(self):
        """Verifica si la persona tiene una habitación asignada para esta escapada."""
        return ReservaHabitacion.objects.filter(
            persona=self.persona,
            habitacion__escapada_alojamiento__escapada=self.escapada
        ).exists()

    def realizar_checkin(self):
        """Realiza el check-in de la inscripción."""
        if not self.tiene_habitacion_asignada():
            raise ValidationError("No se puede realizar el check-in. La persona no tiene habitación asignada.")
            
        if not self.checkin_completado:
            self.fecha_checkin = timezone.now()
            self.checkin_completado = True
            self.save()
            
    def cancelar_checkin(self):
        """Cancela el check-in de la inscripción."""
        if self.checkin_completado:
            self.fecha_checkin = None
            self.checkin_completado = False
            self.save()
   
    def save(self, *args, **kwargs):
        # Actualizar ha_pagado basado en la condición
        self.ha_pagado = (self.a_pagar - self.pagado) <= 0
        
        # Llamar al método save() original
        super().save(*args, **kwargs) 
    
    def __str__(self):
        return f"{self.persona} - {self.escapada}"

    class Meta:
        db_table = 'inscripcion'

# ----------------------------------
# 5. TABLA INTERMEDIA:
#    Persona <--> Habitacion
# ----------------------------------

class ReservaHabitacion(models.Model):
    """
    Relación muchos-a-muchos entre Persona y Habitacion.
    Permite asignar a cada persona las habitaciones que quiera,
    pero no más de 1 habitación en la misma escapada_alojamiento.
    """
    persona = models.ForeignKey(Persona, on_delete=models.CASCADE)
    habitacion = models.ForeignKey(Habitacion, on_delete=models.CASCADE)
    
    es_anfitrion = models.BooleanField(default=False)

    # Fecha/hora de asignación, u otros campos que desees
    fecha_reserva = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.persona} -> {self.habitacion}"

    def clean(self):
        """
        Validación para impedir que una persona tenga dos Habitaciones distintas
        en el mismo escapada_alojamiento.
        """
        from django.core.exceptions import ValidationError
        
        # El escapada_alojamiento de la habitación en cuestión:
        ea = self.habitacion.escapada_alojamiento
        
        # Buscar si la persona ya tiene otra ReservaHabitacion con *otro* habitacion
        # que apunte al mismo escapada_alojamiento:
        ya_existe = (
            ReservaHabitacion.objects
            .filter(persona=self.persona)
            .exclude(pk=self.pk)  # excluir la propia
            .filter(habitacion__escapada_alojamiento=ea)
            .exists()
        )
        if ya_existe:
            raise ValidationError("Esta persona ya tiene una habitación en este escapada_alojamiento.")

    class Meta:
        db_table = 'reservahabitacion'
        unique_together = ('persona', 'habitacion')
    