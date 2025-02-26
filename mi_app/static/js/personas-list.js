document.addEventListener('DOMContentLoaded', function() {
  // Variables globales para mantener el estado
  let personasSeleccionadas = [];
  
  // Control de selección múltiple de personas
  const selectAllCheckbox = document.getElementById('selectAllCheckbox');
  const personaCheckboxes = document.querySelectorAll('.persona-checkbox');
  const inscribirMultiplesBtn = document.getElementById('inscribirMultiplesBtn');
  
  // Función para actualizar estado de selección
  function actualizarSeleccion() {
    personasSeleccionadas = [];
    let haySeleccionados = false;
    
    personaCheckboxes.forEach(checkbox => {
      const tr = checkbox.closest('tr');
      if (checkbox.checked) {
        haySeleccionados = true;
        tr.classList.add('row-selected');
        personasSeleccionadas.push({
          id: checkbox.dataset.personaId,
          nombre: tr.dataset.personaNombre
        });
      } else {
        tr.classList.remove('row-selected');
      }
    });
    
    // Mostrar/ocultar botón de acción múltiple
    if (haySeleccionados) {
      inscribirMultiplesBtn.classList.add('active');
    } else {
      inscribirMultiplesBtn.classList.remove('active');
    }
  }
  
  // Event listeners para checkboxes
  if (selectAllCheckbox) {
    selectAllCheckbox.addEventListener('change', function() {
      personaCheckboxes.forEach(checkbox => {
        checkbox.checked = this.checked;
      });
      actualizarSeleccion();
    });
  }
  
  personaCheckboxes.forEach(checkbox => {
    checkbox.addEventListener('change', function() {
      actualizarSeleccion();
      
      // Actualizar estado de "Seleccionar todos"
      if (selectAllCheckbox) {
        const todosSeleccionados = Array.from(personaCheckboxes).every(cb => cb.checked);
        const algunoSeleccionado = Array.from(personaCheckboxes).some(cb => cb.checked);
        
        selectAllCheckbox.checked = todosSeleccionados;
        selectAllCheckbox.indeterminate = algunoSeleccionado && !todosSeleccionados;
      }
    });
  });
  
  // Botón para inscribir múltiples personas
  if (inscribirMultiplesBtn) {
    inscribirMultiplesBtn.addEventListener('click', function() {
      abrirModalInscripcionMultiple();
    });
  }
  
  // Cambio entre pasos del modal
  const btnContinuarConfirmacion = document.getElementById('btnContinuarConfirmacion');
  const btnVolverSeleccion = document.getElementById('btnVolverSeleccion');
  
  if (btnContinuarConfirmacion) {
    btnContinuarConfirmacion.addEventListener('click', function() {
      mostrarPasoConfirmacion();
    });
  }
  
  if (btnVolverSeleccion) {
    btnVolverSeleccion.addEventListener('click', function() {
      const paso1 = document.getElementById('paso1');
      const paso2 = document.getElementById('paso2');
      if (paso1 && paso2) {
        paso1.classList.add('active');
        paso2.classList.remove('active');
      }
    });
  }
  
  // Control del formulario de inscripción
  const inscripcionForm = document.getElementById('inscripcionForm');
  if (inscripcionForm) {
    inscripcionForm.addEventListener('submit', function(event) {
      // Verificar que los campos tengan valores
      const personasIdsInput = document.getElementById('personas_ids');
      const escapadasIdsInput = document.getElementById('escapadas_ids');
      
      if (!personasIdsInput || !personasIdsInput.value || !escapadasIdsInput || !escapadasIdsInput.value) {
        event.preventDefault();
        alert('Error: Falta información necesaria para la inscripción');
        return false;
      }
      
      console.log('Enviando formulario con datos:');
      console.log('Personas:', personasIdsInput.value);
      console.log('Escapadas:', escapadasIdsInput.value);
      console.log('Tipo habitación:', document.getElementById('tipo_habitacion_hidden')?.value);
      
      // No hacemos return false aquí para permitir que el formulario se envíe
    });
  }
  
  // Funciones para filtrado
  const searchInput = document.getElementById('searchInput');
  const escapadaFilter = document.getElementById('escapadaFilter');
  const pagoFilter = document.getElementById('pagoFilter');
  const sinInscripcionFilter = document.getElementById('sinInscripcionFilter');
  const personasTable = document.getElementById('personasTable');
  const resultsCountElement = document.querySelector('.results-count');
  const exportButton = document.querySelector('button[data-action="exportar"]');
  
  // Verifica si existen las filas antes de continuar
  let personasRows = [];
  if (personasTable) {
    personasRows = Array.from(personasTable.querySelectorAll('tbody tr:not(#emptyMessage)'));
  }

  // Función para filtrar las personas
  function filterPersonas() {
    const searchTerm = searchInput?.value?.toLowerCase()?.trim() || '';
    const selectedEscapada = escapadaFilter?.value || '';
    const selectedPago = pagoFilter?.value || '';
    const mostrarSinInscripcion = sinInscripcionFilter?.checked || false;

    let visibleCount = 0;
    let anyVisible = false;

    personasRows.forEach(row => {
      // Datos a filtrar
      const nombre = row.getAttribute('data-nombre')?.toLowerCase() || '';
      const dni = row.getAttribute('data-dni')?.toLowerCase() || '';
      const escapadas = row.getAttribute('data-escapadas') ? row.getAttribute('data-escapadas').split(',') : [];
      const estadoPago = row.getAttribute('data-estado-pago') || '';
      const tieneInscripciones = escapadas.length > 0 && escapadas[0] !== '';

      // Lógica de filtro mejorada para búsqueda
      const searchTerms = searchTerm.split(' ').filter(term => term.length > 0);
      const matchesSearch = searchTerms.length === 0 || 
                           searchTerms.every(term => nombre.includes(term) || dni.includes(term));
      
      // Lógica de filtro mejorada para escapadas
      let matchesEscapada = true;
      if (selectedEscapada) {
        if (mostrarSinInscripcion && !tieneInscripciones) {
          // Si se permite mostrar sin inscripción, las personas sin inscripciones pasan el filtro
          matchesEscapada = true;
        } else {
          // Personas con inscripciones deben coincidir con la escapada seleccionada
          matchesEscapada = escapadas.includes(selectedEscapada);
        }
      }
      
      // Lógica para estado de pago
      let matchesPago = true;
      if (selectedPago) {
        if (!tieneInscripciones) {
          // Personas sin inscripciones no tienen estado de pago
          matchesPago = false;
        } else {
          matchesPago = estadoPago === selectedPago;
        }
      }

      // Aplicar filtro combinado
      const isVisible = matchesSearch && matchesEscapada && matchesPago;
      row.style.display = isVisible ? '' : 'none';
      
      if (isVisible) {
        visibleCount++;
        anyVisible = true;
      }
    });

    // Actualizar contador de resultados
    updateResultsCount(visibleCount, personasRows.length);
    
    // Mostrar mensaje si no hay resultados
    showNoResultsMessage(!anyVisible);
  }

  // Actualizar el contador de resultados
  function updateResultsCount(visibleCount, totalCount) {
    if (resultsCountElement) {
      resultsCountElement.innerHTML = `
        <span class="font-medium">${visibleCount}</span> de 
        <span class="font-medium">${totalCount}</span> personas
      `;
    }
  }

  // Mostrar mensaje cuando no hay resultados
  function showNoResultsMessage(show) {
    // Eliminar mensaje existente si hay
    const existingMessage = document.getElementById('emptyMessage');
    if (existingMessage) {
      existingMessage.remove();
    }
    
    // Si no hay resultados y tenemos filas, mostrar mensaje
    if (show && personasTable && personasRows.length > 0) {
      const tbody = personasTable.querySelector('tbody');
      const newRow = document.createElement('tr');
      newRow.id = 'emptyMessage';
      newRow.className = 'fade-in';
      newRow.innerHTML = `
        <td colspan="6" class="px-6 py-10 text-center">
          <div class="flex flex-col items-center justify-center">
            <div class="bg-gray-100 p-3 rounded-full mb-3">
              <i class="fas fa-search text-gray-400 text-2xl"></i>
            </div>
            <h3 class="text-lg font-medium text-gray-700 mb-2">No se encontraron resultados</h3>
            <p class="text-gray-500 max-w-md mb-4">Modifica los criterios de búsqueda para encontrar más resultados</p>
            <button onclick="resetFilters()" class="px-4 py-2 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 transition">
              <i class="fas fa-redo mr-2"></i>Restablecer filtros
            </button>
          </div>
        </td>
      `;
      tbody.appendChild(newRow);
    }
  }

  // Inicializar listeners para filtros
  if (searchInput) searchInput.addEventListener('input', filterPersonas);
  if (escapadaFilter) escapadaFilter.addEventListener('change', filterPersonas);
  if (pagoFilter) pagoFilter.addEventListener('change', filterPersonas);
  if (sinInscripcionFilter) sinInscripcionFilter.addEventListener('change', filterPersonas);
  if (exportButton) exportButton.addEventListener('click', exportToCSV);

  // Escuchar evento personalizado para filtrar
  document.addEventListener('filterPersonas', filterPersonas);

  // Exportar funciones al objeto window
  window.personasSeleccionadas = personasSeleccionadas;
  window.abrirModalInscripcion = abrirModalInscripcion;
  window.abrirModalInscripcionMultiple = abrirModalInscripcionMultiple;
  window.cerrarModalInscripcion = cerrarModalInscripcion;
  window.mostrarPasoConfirmacion = mostrarPasoConfirmacion;
  window.confirmDelete = confirmDelete;
  window.closeDeleteModal = closeDeleteModal;
  window.resetFilters = resetFilters;
  
  // Aplicar filtros iniciales (por si hay parámetros en URL)
  filterPersonas();
});

// Funciones para el modal de inscripción
function abrirModalInscripcion(personaId, personaNombre) {
  window.personasSeleccionadas = [{id: personaId, nombre: personaNombre}];
  const nombresPersonasElement = document.getElementById('nombresPersonas');
  const inscripcionModalElement = document.getElementById('inscripcionModal');
  const paso1Element = document.getElementById('paso1');
  const paso2Element = document.getElementById('paso2');
  const tipoHabitacionSelect = document.getElementById('tipo-habitacion');
  
  if (nombresPersonasElement) nombresPersonasElement.textContent = personaNombre;
  if (inscripcionModalElement) inscripcionModalElement.classList.remove('hidden');
  if (paso1Element) paso1Element.classList.add('active');
  if (paso2Element) paso2Element.classList.remove('active');
  
  // Limpiar selecciones previas
  document.querySelectorAll('.escapada-checkbox').forEach(cb => cb.checked = false);
  if (tipoHabitacionSelect) tipoHabitacionSelect.value = '';
}

function abrirModalInscripcionMultiple() {
  if (!window.personasSeleccionadas || window.personasSeleccionadas.length === 0) {
    alert('No hay personas seleccionadas');
    return;
  }
  
  const nombres = window.personasSeleccionadas.map(p => p.nombre).join(', ');
  const nombresPersonasElement = document.getElementById('nombresPersonas');
  const inscripcionModalElement = document.getElementById('inscripcionModal');
  const paso1Element = document.getElementById('paso1');
  const paso2Element = document.getElementById('paso2');
  const tipoHabitacionSelect = document.getElementById('tipo-habitacion');
  
  if (nombresPersonasElement) nombresPersonasElement.textContent = nombres;
  if (inscripcionModalElement) inscripcionModalElement.classList.remove('hidden');
  if (paso1Element) paso1Element.classList.add('active');
  if (paso2Element) paso2Element.classList.remove('active');
  
  // Limpiar selecciones previas
  document.querySelectorAll('.escapada-checkbox').forEach(cb => cb.checked = false);
  if (tipoHabitacionSelect) tipoHabitacionSelect.value = '';
}

function cerrarModalInscripcion() {
  const inscripcionModalElement = document.getElementById('inscripcionModal');
  if (inscripcionModalElement) inscripcionModalElement.classList.add('hidden');
}

function mostrarPasoConfirmacion() {
  // Verificar que al menos una escapada esté seleccionada
  const escapadasSeleccionadas = Array.from(document.querySelectorAll('.escapada-checkbox:checked'));
  if (escapadasSeleccionadas.length === 0) {
    alert('Debes seleccionar al menos una escapada');
    return;
  }
  
  // Mostrar resumen de personas
  const listaPersonas = document.getElementById('lista-personas-confirmacion');
  if (listaPersonas) {
    listaPersonas.innerHTML = '';
    window.personasSeleccionadas.forEach(persona => {
      const li = document.createElement('li');
      li.className = 'py-1';
      li.innerHTML = `<i class="fas fa-user text-blue-600 mr-2"></i>${persona.nombre}`;
      listaPersonas.appendChild(li);
    });
  }
  
  // Mostrar resumen de escapadas
  const listaEscapadas = document.getElementById('lista-escapadas-confirmacion');
  const escapadasIds = [];
  if (listaEscapadas) {
    listaEscapadas.innerHTML = '';
    escapadasSeleccionadas.forEach(checkbox => {
      const label = checkbox.nextElementSibling.textContent.trim();
      const li = document.createElement('li');
      li.className = 'py-1';
      li.innerHTML = `<i class="fas fa-mountain text-green-600 mr-2"></i>${label}`;
      listaEscapadas.appendChild(li);
      escapadasIds.push(checkbox.value);
    });
  }
  
  // Mostrar preferencia de habitación
  const tipoHabitacion = document.getElementById('tipo-habitacion')?.value || '';
  const preferenciaDiv = document.getElementById('preferencia-habitacion-confirmacion');
  if (preferenciaDiv) {
    if (tipoHabitacion) {
      preferenciaDiv.innerHTML = `<i class="fas fa-bed text-gray-600 mr-2"></i>Preferencia de habitación: <strong>${tipoHabitacion}</strong>`;
    } else {
      preferenciaDiv.innerHTML = `<i class="fas fa-bed text-gray-600 mr-2"></i>Sin preferencia de habitación específica`;
    }
  }
  
  // Preparar datos para el formulario
  const personasIdsInput = document.getElementById('personas_ids');
  const escapadasIdsInput = document.getElementById('escapadas_ids');
  const tipoHabitacionInput = document.getElementById('tipo_habitacion_hidden');
  
  if (personasIdsInput) personasIdsInput.value = window.personasSeleccionadas.map(p => p.id).join(',');
  if (escapadasIdsInput) escapadasIdsInput.value = escapadasIds.join(',');
  if (tipoHabitacionInput) tipoHabitacionInput.value = tipoHabitacion;
  
  // Cambiar al paso de confirmación
  const paso1Element = document.getElementById('paso1');
  const paso2Element = document.getElementById('paso2');
  if (paso1Element) paso1Element.classList.remove('active');
  if (paso2Element) paso2Element.classList.add('active');
}

// Funciones para el modal de eliminación
function confirmDelete(url) {
  const deleteModal = document.getElementById('deleteModal');
  const deleteForm = document.getElementById('deleteForm');
  
  if (deleteModal) deleteModal.classList.remove('hidden');
  if (deleteForm) deleteForm.action = url;
}

function closeDeleteModal() {
  const deleteModal = document.getElementById('deleteModal');
  if (deleteModal) deleteModal.classList.add('hidden');
}

// Función para exportar a CSV
function exportToCSV() {
  const personasTable = document.getElementById('personasTable');
  if (!personasTable) return;
  
  const personasRows = Array.from(personasTable.querySelectorAll('tbody tr:not(#emptyMessage)'));
  // Obtener sólo filas visibles
  const visibleRows = personasRows.filter(row => row.style.display !== 'none');
  
  if (visibleRows.length === 0) {
    alert('No hay datos para exportar. Ajusta los filtros para mostrar resultados.');
    return;
  }
  
  // Encabezados para el CSV
  const headers = ['ID/DNI', 'Nombre', 'Apellidos', 'Email', 'Teléfono', 'Escapadas', 'Estado Pago', 'Alojamiento'];
  const csvContent = [headers.join(',')];

  // Extraer datos de cada fila visible
  visibleRows.forEach(row => {
    try {
      // Extraer datos cuidadosamente para evitar errores
      const dniElement = row.querySelector('td:nth-child(2) .text-gray-500');
      const nombreElement = row.querySelector('td:nth-child(2) .font-medium');
      
      // Dividir el nombre completo si es posible
      let nombre = '', apellidos = '';
      if (nombreElement) {
        const nombreCompleto = nombreElement.textContent.trim().split(' ');
        if (nombreCompleto.length > 1) {
          nombre = nombreCompleto[0];
          apellidos = nombreCompleto.slice(1).join(' ');
        } else {
          nombre = nombreCompleto[0] || '';
        }
      }
      
      const dni = dniElement ? dniElement.textContent.trim() : '';
      const email = row.querySelector('td:nth-child(3) a[href^="mailto:"]')?.textContent.trim() || '';
      const telefono = row.querySelector('td:nth-child(3) a[href^="tel:"]')?.textContent.trim() || '';
      
      // Recopilar información de escapadas
      const escapadasElements = Array.from(row.querySelectorAll('td:nth-child(4) .text-gray-900'));
      const escapadas = escapadasElements.map(el => el.textContent.trim()).join(' | ');
      
      // Estados de pago
      const estadosPagoElements = Array.from(row.querySelectorAll('td:nth-child(4) .badge-pill'));
      const estadosPago = estadosPagoElements.map(el => el.textContent.trim()).join(' | ');
      
      // Información de alojamiento
      const alojamientoElements = Array.from(row.querySelectorAll('td:nth-child(5) .text-gray-900'));
      const alojamiento = alojamientoElements.map(el => {
        const habitacion = el.closest('div').querySelector('.pill-badge')?.textContent.trim() || '';
        return `${el.textContent.trim()} - ${habitacion}`;
      }).join(' | ');

      // Escapar posibles comillas en campos
      const rowData = [
        `"${dni}"`,
        `"${nombre}"`,
        `"${apellidos}"`,
        `"${email}"`,
        `"${telefono}"`,
        `"${escapadas}"`,
        `"${estadosPago}"`,
        `"${alojamiento}"`
      ];

      csvContent.push(rowData.join(','));
    } catch (error) {
      console.error('Error al procesar fila para CSV:', error);
    }
  });

  // Crear y descargar el archivo CSV
  const csvString = csvContent.join('\n');
  const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  const timestamp = new Date().toISOString().split('T')[0];

  link.setAttribute('href', url);
  link.setAttribute('download', `personas_exportadas_${timestamp}.csv`);
  link.style.visibility = 'hidden';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// Función para restablecer filtros
function resetFilters() {
  const searchInput = document.getElementById('searchInput');
  const escapadaFilter = document.getElementById('escapadaFilter');
  const pagoFilter = document.getElementById('pagoFilter');
  const sinInscripcionFilter = document.getElementById('sinInscripcionFilter');
  
  if (searchInput) searchInput.value = '';
  if (escapadaFilter) escapadaFilter.value = '';
  if (pagoFilter) pagoFilter.value = '';
  if (sinInscripcionFilter) sinInscripcionFilter.checked = false;
  
  // Forzar el evento de cambio para que se aplique el filtrado
  const event = new CustomEvent('filterPersonas');
  document.dispatchEvent(event);
  
  // También podemos llamar directamente a la función
  const personasRows = Array.from(document.querySelectorAll('#personasTable tbody tr:not(#emptyMessage)'));
  personasRows.forEach(row => {
    row.style.display = '';
  });
  
  // Actualizar contador
  const resultsCountElement = document.querySelector('.results-count');
  if (resultsCountElement) {
    resultsCountElement.innerHTML = `
      <span class="font-medium">${personasRows.length}</span> de 
      <span class="font-medium">${personasRows.length}</span> personas
    `;
  }
}