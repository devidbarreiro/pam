from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Home
    path('', views.HomeView.as_view(), name='home'),

    # URLs para Escapada
    path('escapadas/', views.EscapadaListView.as_view(), name='escapada_list'),
    path('escapadas/nueva/', views.EscapadaCreateView.as_view(), name='escapada_create'),
    path('escapadas/<int:pk>/', views.EscapadaDetailView.as_view(), name='escapada_detail'),
    path('escapadas/<int:pk>/editar/', views.EscapadaUpdateView.as_view(), name='escapada_update'),
    path('escapadas/<int:pk>/eliminar/', views.EscapadaDeleteView.as_view(), name='escapada_delete'),
    # NUEVA URL: Seleccionar alojamientos para una escapada
    path('escapadas/<int:pk>/alojamientos/', views.EscapadaAlojamientoSelectView.as_view(), name='escapada_alojamiento_select'),
    path('escapadas/<int:pk>/asociar-alojamientos/', views.EscapadaAlojamientoMultipleCreateView.as_view(), name='escapada_alojamiento_multiple_create'),
    path('escapadas/<int:pk>/inscripcion/', views.EscapadaInscripcionView.as_view(), name='escapada_inscripcion'),



    # URLs para Alojamiento
    path('alojamientos/', views.AlojamientoListView.as_view(), name='alojamiento_list'),
    path('alojamientos/nuevo/', views.AlojamientoCreateView.as_view(), name='alojamiento_create'),
    path('alojamientos/<int:pk>/', views.AlojamientoDetailView.as_view(), name='alojamiento_detail'),
    path('alojamientos/<int:pk>/editar/', views.AlojamientoUpdateView.as_view(), name='alojamiento_update'),
    path('alojamientos/<int:pk>/eliminar/', views.AlojamientoDeleteView.as_view(), name='alojamiento_delete'),

    # URLs para Habitacion
    path('habitaciones/', views.HabitacionListView.as_view(), name='habitacion_list'),
    path('habitaciones/nueva/', views.HabitacionCreateView.as_view(), name='habitacion_create'),
    path('habitaciones/<int:pk>/', views.HabitacionDetailView.as_view(), name='habitacion_detail'),
    path('habitaciones/<int:pk>/editar/', views.HabitacionUpdateView.as_view(), name='habitacion_update'),
    path('habitaciones/<int:pk>/eliminar/', views.HabitacionDeleteView.as_view(), name='habitacion_delete'),
    # Vista que crea 1 habitación (automática o manual)
    path('habitaciones/crear-para-alojamiento/', views.HabitacionCreateForAlojamientoView.as_view(), name='habitacion_create_for_alojamiento'),
    # Vista que crea varias habitaciones con formset
    path('habitaciones/multiple/<int:ea_id>/', views.HabitacionMultipleCreateView.as_view(), name='habitacion_multiple_create'),

    # Vista que crea varias habitaciones pidiendo cantidad 
    path(
    'habitaciones/crear-variashabs/<int:ea_id>/',
    views.HabitacionMultipleAutoCreateView.as_view(),
    name='habitacion_multiple_auto_create'),

    # URLs para Persona
    path('personas/', views.PersonaListView.as_view(), name='persona_list'),
    path('personas/nueva/', views.PersonaCreateView.as_view(), name='persona_create'),
    path('personas/<int:pk>/', views.PersonaDetailView.as_view(), name='persona_detail'),
    path('personas/<int:pk>/editar/', views.PersonaUpdateView.as_view(), name='persona_update'),
    path('personas/<int:pk>/eliminar/', views.PersonaDeleteView.as_view(), name='persona_delete'),
    
    # Ruta para asociar una Escapada con un Alojamiento
    path('asociar/', views.EscapadaAlojamientoCreateView.as_view(), name='escapada_alojamiento_create'),
    path('escapada-alojamiento/lista/', views.EscapadaAlojamientoListView.as_view(), name='escapada_alojamiento_list'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)