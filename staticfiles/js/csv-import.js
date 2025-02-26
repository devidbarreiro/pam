/**
 * CSV Import Form - Main JavaScript Controller
 * Handles the multi-step import process, field mapping, validation, and form submission
 */
document.addEventListener('DOMContentLoaded', function() {
    // ============================
    // 1. ELEMENTOS CORE
    // ============================
    const importForm = document.getElementById('importForm');
    const stepContainers = document.querySelectorAll('.step-content');
    const stepIndicators = document.querySelectorAll('.step');
    const progressBar = document.getElementById('progressBar');
    const alertContainer = document.getElementById('alertContainer');

    // Elementos para selección de archivo
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('csv_file');
    const browseButton = document.getElementById('browseButton');
    const removeFileBtn = document.getElementById('removeFile');
    const selectedFileName = document.getElementById('selectedFileName');
    const fileSize = document.getElementById('fileSize');
    const fileDropMessage = document.querySelector('.file-drop-message');

    // Botones de navegación entre pasos
    const btnAnalyze = document.getElementById('btnAnalyze');
    const btnToMapping = document.getElementById('btnToMapping');
    const btnValidateMapping = document.getElementById('btnValidateMapping');
    const btnImport = document.getElementById('btnImport');
    const prevStepButtons = document.querySelectorAll('.prev-step');

    // Elementos relacionados con el mapeo
    const fieldsContainer = document.getElementById('fieldsContainer');
    const mappingContainer = document.getElementById('mappingContainer');
    const searchField = document.getElementById('searchField');
    const clearSearchBtn = document.getElementById('clearSearch');
    const filterButtons = document.querySelectorAll('.filter-btn');
    // Eliminamos elementos relacionados con configuraciones guardadas
    const mappingProgressBar = document.getElementById('mappingProgress');
    const mappedCountDisplay = document.getElementById('mappedCount');
    const totalFieldsDisplay = document.getElementById('totalFields');
    const validationErrorsContainer = document.getElementById('validationErrors');
    const errorsList = document.getElementById('errorsList');

    // Elementos de la vista previa
    const previewTableHead = document.getElementById('previewTableHead');
    const previewTableBody = document.getElementById('previewTableBody');
    const columnCountDisplay = document.getElementById('columnCount');

    // Elementos de resumen
    const summaryFileName = document.getElementById('summaryFileName');
    const summaryEscapada = document.getElementById('summaryEscapada');
    const summaryMappedFields = document.getElementById('summaryMappedFields');
    const summaryImportMode = document.getElementById('summaryImportMode');
    const summaryMappingTable = document.getElementById('summaryMappingTable');

    // Elementos del formulario
    const escapadaSelect = document.getElementById('escapada');
    const onlyAddToDbCheckbox = document.getElementById('only_add_to_db');
    const mappingHiddenInput = document.getElementById('mapping');

    // ============================
    // 2. VARIABLES DE ESTADO
    // ============================
    let currentStep = 1;
    let csvColumns = [];
    let previewData = [];
    let fieldMappings = {};
    let activeField = null;
    let requiredFields = ['dni', 'nombre']; // Campos obligatorios

    // Inicialización: mostrar el número total de campos
    totalFieldsDisplay.textContent = document.querySelectorAll('.field-item').length;
    updateMappingStats();

    // ============================
    // 3. MANEJO DEL CHECKBOX "Solo añadir a la BD"
    // ============================
    function updateEscapadaState() {
        if (onlyAddToDbCheckbox.checked) {
            escapadaSelect.disabled = true;
            escapadaSelect.parentElement.classList.add('opacity-50');
        } else {
            escapadaSelect.disabled = false;
            escapadaSelect.parentElement.classList.remove('opacity-50');
        }
    }
    updateEscapadaState();
    onlyAddToDbCheckbox.addEventListener('change', updateEscapadaState);

    // ============================
    // 4. MANEJO DE ARCHIVOS
    // ============================
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('border-primary'), false);
    });
    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('border-primary'), false);
    });
    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleFiles(files);
        }
    });
    browseButton.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFiles(e.target.files);
        }
    });
    removeFileBtn.addEventListener('click', () => {
        fileInput.value = '';
        if (fileDropMessage) fileDropMessage.classList.remove('hidden');
        const selectedFileElem = document.querySelector('.selected-file');
        if (selectedFileElem) selectedFileElem.classList.add('hidden');
        btnAnalyze.disabled = true;
    });
    function handleFiles(files) {
        if (files.length === 0) return;
        const file = files[0];
        if (file.type !== 'text/csv' && !file.name.endsWith('.csv')) {
            showAlert('error', 'El archivo debe ser de tipo CSV.');
            return;
        }
        // Actualizar el nombre del archivo en el elemento "selectedFile"
        const selectedFileDiv = document.getElementById('selectedFile');
        if (selectedFileDiv) {
            selectedFileDiv.textContent = file.name;
        }
        // También se pueden actualizar otros elementos, por ejemplo, si se usa "selectedFileName":
        if (selectedFileName) {
            selectedFileName.textContent = file.name;
        }
        fileSize.textContent = formatFileSize(file.size);
        if (fileDropMessage) fileDropMessage.classList.add('hidden');
        const selectedFileElem = document.querySelector('.selected-file');
        if (selectedFileElem) selectedFileElem.classList.remove('hidden');
        btnAnalyze.disabled = false;
    }    
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // ============================
    // 5. GESTIÓN DE PASOS
    // ============================
    function goToStep(step) {
        stepContainers.forEach(container => container.style.display = 'none');
        stepIndicators.forEach((indicator, index) => {
            const stepNum = index + 1;
            if (stepNum < step) {
                indicator.classList.remove('active');
                indicator.classList.add('completed');
            } else if (stepNum === step) {
                indicator.classList.add('active');
                indicator.classList.remove('completed');
            } else {
                indicator.classList.remove('active', 'completed');
            }
        });
        document.getElementById(`step${step}`).style.display = 'block';
        if (progressBar) {
            const progress = ((step - 1) / (stepIndicators.length - 1)) * 100;
            progressBar.style.width = `${progress}%`;
        }
        currentStep = step;
        window.scrollTo(0, 0);
    }
    prevStepButtons.forEach(button => {
        button.addEventListener('click', () => goToStep(currentStep - 1));
    });

    // ============================
    // 6. ANÁLISIS DEL CSV
    // ============================
    btnAnalyze.addEventListener('click', analyzeCSV);
    function analyzeCSV() {
        console.log("Iniciando análisis del CSV");
        if (!fileInput.files || fileInput.files.length === 0) {
            showAlert('error', 'Por favor, seleccione un archivo CSV.');
            return;
        }
        const spinner = btnAnalyze.querySelector('.spinner');
        const buttonText = btnAnalyze.querySelector('.button-text');
        buttonText.textContent = 'Analizando...';
        spinner.classList.remove('hidden');
        btnAnalyze.disabled = true;
        const formData = new FormData();
        formData.append('csv_file', fileInput.files[0]);
        formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);
        // Usamos una URL absoluta para evitar duplicados: inicia con "/"
        fetch('/importar-personas/inspeccionar_csv/', {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(response => {
            console.log("Respuesta recibida, status", response.status);
            return response.json();
        })
        .then(data => {
            console.log("Datos de inspección:", data);
            spinner.classList.add('hidden');
            buttonText.textContent = 'Continuar y analizar CSV';
            btnAnalyze.disabled = false;
            if (data.success) {
                csvColumns = data.columns || [];
                previewData = data.preview_rows || [];
                columnCountDisplay.textContent = csvColumns.length;
                generatePreviewTable();
                goToStep(2);
            } else {
                showAlert('error', data.error || 'Error al analizar el CSV.');
                console.error("Error en análisis CSV:", data.error);
            }
        })
        .catch(error => {
            spinner.classList.add('hidden');
            buttonText.textContent = 'Continuar y analizar CSV';
            btnAnalyze.disabled = false;
            console.error("Error en fetch:", error);
            showAlert('error', 'Error al conectar con el servidor: ' + error.message);
        });
    }
    function generatePreviewTable() {
        previewTableHead.innerHTML = '';
        previewTableBody.innerHTML = '';
        const headerRow = document.createElement('tr');
        csvColumns.forEach(column => {
            const th = document.createElement('th');
            th.textContent = column;
            headerRow.appendChild(th);
        });
        previewTableHead.appendChild(headerRow);
        previewData.forEach(row => {
            const tableRow = document.createElement('tr');
            csvColumns.forEach(column => {
                const td = document.createElement('td');
                td.textContent = row[column] || '';
                tableRow.appendChild(td);
            });
            previewTableBody.appendChild(tableRow);
        });
    }

    // ============================
    // 7. PREPARACIÓN DEL MAPEO
    // ============================
    btnToMapping.addEventListener('click', () => {
        goToStep(3);
        initializeMappingInterface();
    });
    function initializeMappingInterface() {
        const fieldItems = document.querySelectorAll('.field-item');
        fieldItems.forEach(item => {
            item.addEventListener('click', () => {
                if (activeField) {
                    document.querySelector(`[data-field-id="${activeField}"]`).classList.remove('active');
                }
                item.classList.add('active');
                activeField = item.dataset.fieldId;
                generateMappingInterface(activeField);
            });
            if (fieldMappings[item.dataset.fieldId]) {
                updateFieldStatus(item.dataset.fieldId, true);
            } else if (item.dataset.required === 'true') {
                item.classList.add('missing-required');
            }
        });
    }
    
    function generateMappingInterface(fieldId) {
        console.log(`Generating mapping interface for field: ${fieldId}`);
        console.log('Current mappings:', fieldMappings);
        const fieldElement = document.querySelector(`[data-field-id="${fieldId}"]`);
        if (!fieldElement) {
            console.error(`No se encontró el elemento para el campo ${fieldId}`);
            return;
        }
        // Usamos 'h4' ya que en la plantilla se utiliza ese tag para el nombre del campo
        const fieldName = fieldElement.querySelector('h4').textContent.replace(' *', '');
        mappingContainer.innerHTML = '';
        const mappingContent = document.createElement('div');
        mappingContent.className = 'mapping-form p-4 border rounded';
        mappingContent.innerHTML = `
            <h5 class="text-lg font-semibold mb-4">${fieldName}</h5>
            <div class="mb-4">
                <label for="map_${fieldId}" class="block text-sm font-medium text-gray-700 mb-2">
                    Seleccione la columna del CSV:
                </label>
                <select id="map_${fieldId}" data-field-id="${fieldId}" class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500">
                    <option value="">-- No mapear este campo --</option>
                    ${csvColumns.map(column => `<option value="${column}" ${fieldMappings[fieldId] === column ? 'selected' : ''}>${column}</option>`).join('')}
                </select>
            </div>
            <button type="button" id="clearMappingBtn_${fieldId}" class="mb-4 px-3 py-1 bg-red-500 text-white rounded-md hover:bg-red-600 transition-colors">
                Deseleccionar
            </button>
            <div>
                <h6 class="text-sm font-medium text-gray-700 mb-2">Vista previa:</h6>
                <div class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Columna CSV</th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ejemplo</th>
                            </tr>
                        </thead>
                        <tbody id="previewValues_${fieldId}" class="bg-white divide-y divide-gray-200">
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        mappingContainer.appendChild(mappingContent);
        // Configurar evento en el select
        const mappingSelect = document.getElementById(`map_${fieldId}`);
        mappingSelect.addEventListener('change', () => {
            const selectedColumn = mappingSelect.value;
            if (selectedColumn) {
                fieldMappings[fieldId] = selectedColumn;
                updateFieldStatus(fieldId, true);
            } else {
                delete fieldMappings[fieldId];
                updateFieldStatus(fieldId, false);
            }
            updateMappingPreview(fieldId, selectedColumn);
            updateMappingStats();
        });
        // Configurar evento en el botón "Deseleccionar"
        const clearMappingBtn = document.getElementById(`clearMappingBtn_${fieldId}`);
        clearMappingBtn.addEventListener('click', () => {
            mappingSelect.value = "";
            delete fieldMappings[fieldId];
            updateFieldStatus(fieldId, false);
            updateMappingPreview(fieldId, "");
            updateMappingStats();
        });
        updateMappingPreview(fieldId, fieldMappings[fieldId]);

        const select = mappingContainer.querySelector('select');
        select.addEventListener('change', (e) => {
            const selectedColumn = e.target.value;
            console.log(`Mapping updated for ${fieldId}:`, selectedColumn);
            
            if (selectedColumn) {
                fieldMappings[fieldId] = selectedColumn;
                console.log('Updated mappings:', fieldMappings);
                updateFieldStatus(fieldId, true);
            } else {
                delete fieldMappings[fieldId];
                console.log('Mapping removed for', fieldId);
                console.log('Updated mappings:', fieldMappings);
                updateFieldStatus(fieldId, false);
            }
            updateMappingPreview(fieldId, selectedColumn);
            updateMappingStats();
        });
    }
    
    
    function updateFieldStatus(fieldId, isMapped) {
        const fieldElement = document.querySelector(`[data-field-id="${fieldId}"]`);
        if (!fieldElement) return;
        const statusIndicator = fieldElement.querySelector('.field-status-indicator');
        if (isMapped) {
            fieldElement.classList.add('mapped');
            fieldElement.classList.remove('missing-required');
            statusIndicator.innerHTML = '✓';
        } else {
            fieldElement.classList.remove('mapped');
            if (fieldElement.dataset.required === 'true') {
                fieldElement.classList.add('missing-required');
                statusIndicator.innerHTML = '!';
            } else {
                statusIndicator.innerHTML = '⭘';
            }
        }
    }
    
    function validateAndContinue() {
        const errors = [];
        requiredFields.forEach(field => {
            const fieldElement = document.querySelector(`[data-field-id="${field}"]`);
            if (!fieldElement) return;
            // Usamos 'h4' en lugar de 'h6'
            const fieldName = fieldElement.querySelector('h4').textContent.replace(' *', '');
            if (!fieldMappings[field]) {
                errors.push(`El campo obligatorio "${fieldName}" no ha sido mapeado.`);
            }
        });
        if (errors.length > 0) {
            errorsList.innerHTML = '';
            errors.forEach(err => {
                const li = document.createElement('li');
                li.textContent = err;
                li.className = 'mb-1';
                errorsList.appendChild(li);
            });
            validationErrorsContainer.classList.remove('hidden');
            validationErrorsContainer.scrollIntoView({ behavior: 'smooth' });
            return;
        }
        validationErrorsContainer.classList.add('hidden');
        updateSummary();
        goToStep(4);
    }
    
    function updateSummary() {
        // Actualiza el nombre del archivo
        summaryFileName.textContent = (fileInput.files && fileInput.files[0] && fileInput.files[0].name) ? fileInput.files[0].name : 'No seleccionado';
      
        // Actualiza la escapada seleccionada
        if (escapadaSelect && escapadaSelect.options && escapadaSelect.selectedIndex >= 0) {
          const escapadaOption = escapadaSelect.options[escapadaSelect.selectedIndex];
          if (escapadaSelect.value && !onlyAddToDbCheckbox.checked) {
            summaryEscapada.textContent = escapadaOption.text;
          } else {
            summaryEscapada.textContent = 'No seleccionada (solo importación)';
          }
        } else {
          summaryEscapada.textContent = 'No seleccionada (solo importación)';
        }
      
        // Actualiza el resumen del mapeo
        summaryMappedFields.textContent = `${Object.keys(fieldMappings).length} de ${document.querySelectorAll('.field-item').length}`;
        summaryImportMode.textContent = onlyAddToDbCheckbox.checked ? 'Solo añadir a la base de datos' : (escapadaSelect.value ? 'Añadir e inscribir en escapada' : 'Solo añadir a la base de datos');
      
        // Limpiar la tabla de resumen del mapeo
        summaryMappingTable.innerHTML = '';
      
        // Recorrer cada campo mapeado
        for (const [fieldId, columnName] of Object.entries(fieldMappings)) {
          const fieldElement = document.querySelector(`[data-field-id="${fieldId}"]`);
          if (!fieldElement) {
            console.warn(`No se encontró el campo con id ${fieldId}. Se omitirá del resumen.`);
            continue; // Opción: saltar este campo
          }
          // Intentamos obtener el nombre del campo usando el h4; si no existe, usamos el id
          const fieldNameElem = fieldElement.querySelector('h4');
          const fieldName = fieldNameElem ? fieldNameElem.textContent.replace(' *', '') : fieldId;
          const row = document.createElement('tr');
          row.innerHTML = `<td>${fieldName}</td><td>${columnName}</td>`;
          summaryMappingTable.appendChild(row);
        }
    }
      
      
    
    function updateMappingPreview(fieldId, columnName) {
        const previewContainer = document.getElementById(`previewValues_${fieldId}`);
        previewContainer.innerHTML = '';
        if (!columnName) {
            const row = document.createElement('tr');
            row.innerHTML = `<td colspan="2" class="text-center text-muted">
                                  <i class="fas fa-exclamation-circle me-2"></i>
                                  No se ha seleccionado ninguna columna
                              </td>`;
            previewContainer.appendChild(row);
            return;
        }
        for (let i = 0; i < Math.min(previewData.length, 3); i++) {
            const row = document.createElement('tr');
            const value = previewData[i][columnName] || '';
            row.innerHTML = `<td>${columnName}</td>
                             <td><code>${value}</code></td>`;
            previewContainer.appendChild(row);
        }
    }
    
    function updateFieldStatus(fieldId, isMapped) {
        const fieldElement = document.querySelector(`[data-field-id="${fieldId}"]`);
        if (!fieldElement) return;
        const statusIndicator = fieldElement.querySelector('.field-status-indicator');
        const deselectBtn = fieldElement.querySelector('.deselect-btn');
        
        if (isMapped) {
          fieldElement.classList.add('mapped');
          fieldElement.classList.remove('missing-required');
          statusIndicator.innerHTML = '✓';
          if (deselectBtn) {
            deselectBtn.classList.remove('hidden');
          }
        } else {
          fieldElement.classList.remove('mapped');
          if (fieldElement.dataset.required === 'true') {
            fieldElement.classList.add('missing-required');
            statusIndicator.innerHTML = '!';
          } else {
            statusIndicator.innerHTML = '⭘';
          }
          if (deselectBtn) {
            deselectBtn.classList.add('hidden');
          }
        }
      }
      

    function updateMappingStats() {
        const totalMapped = Object.keys(fieldMappings).length;
        mappedCountDisplay.textContent = totalMapped;
        const totalRequired = requiredFields.length;
        const mappedRequired = requiredFields.filter(field => fieldMappings[field]).length;
        let progressPercentage = 0;
        if (mappedRequired === totalRequired) {
            progressPercentage = (totalMapped / document.querySelectorAll('.field-item').length) * 100;
        } else {
            progressPercentage = (mappedRequired / totalRequired) * 100;
        }
        mappingProgressBar.style.width = `${progressPercentage}%`;
    }

    // ============================
    // 8. BÚSQUEDA Y FILTRADO DE CAMPOS
    // ============================
    searchField.addEventListener('input', filterFields);
    clearSearchBtn.addEventListener('click', () => {
        searchField.value = '';
        filterFields();
    });
    function filterFields() {
        const searchTerm = searchField.value.toLowerCase();
        const fieldItems = document.querySelectorAll('.field-item');
        fieldItems.forEach(item => {
            const fieldName = item.querySelector('h6').textContent.toLowerCase();
            if (fieldName.includes(searchTerm)) {
                item.style.display = 'block';
            } else {
                item.style.display = 'none';
            }
        });
    }
    filterButtons.forEach(button => {
        button.addEventListener('click', () => {
            filterButtons.forEach(btn => {
                btn.classList.remove('bg-blue-50', 'text-blue-700');
            });
            button.classList.add('bg-blue-50', 'text-blue-700');
            const filter = button.dataset.filter;
            applyFieldFilter(filter);
        });
    });
    function applyFieldFilter(filter) {
        const fieldItems = document.querySelectorAll('.field-item');
        fieldItems.forEach(item => {
            switch(filter) {
                case 'all':
                    item.style.display = 'block';
                    break;
                case 'required':
                    item.style.display = item.dataset.required === 'true' ? 'block' : 'none';
                    break;
                case 'inscripcion':
                    item.style.display = item.dataset.inscripcion === 'true' ? 'block' : 'none';
                    break;
                case 'mapped':
                    item.style.display = item.classList.contains('mapped') ? 'block' : 'none';
                    break;
            }
        });
    }

    // ============================
    // 9. VALIDACIÓN Y RESUMEN
    // ============================
    btnValidateMapping.addEventListener('click', validateAndContinue);
    function validateAndContinue() {
        const validationResult = validateMapping();
        if (validationResult.valid) {
            validationErrorsContainer.classList.add('hidden');
            updateSummary();
            goToStep(4);
        } else {
            errorsList.innerHTML = '';
            validationResult.errors.forEach(error => {
                const li = document.createElement('li');
                li.textContent = error;
                li.className = 'mb-1';
                errorsList.appendChild(li);
            });
            validationErrorsContainer.classList.remove('hidden');
            validationErrorsContainer.scrollIntoView({ behavior: 'smooth' });
        }
    }
    function validateAndContinue() {
        const errors = [];
        requiredFields.forEach(field => {
            if (!fieldMappings[field]) {
                const fieldElement = document.querySelector(`[data-field-id="${field}"]`);
                const fieldName = fieldElement.querySelector('h6').textContent.replace(' *', '');
                errors.push(`El campo obligatorio "${fieldName}" no ha sido mapeado.`);
            }
        });
        if (errors.length > 0) {
            errorsList.innerHTML = '';
            errors.forEach(err => {
                const li = document.createElement('li');
                li.textContent = err;
                li.className = 'mb-1';
                errorsList.appendChild(li);
            });
            validationErrorsContainer.classList.remove('hidden');
            validationErrorsContainer.scrollIntoView({ behavior: 'smooth' });
            return;
        }
        validationErrorsContainer.classList.add('hidden');
        updateSummary();
        goToStep(4);
    }
    function updateSummary() {
        // Actualiza el nombre del archivo
        summaryFileName.textContent = (fileInput.files && fileInput.files[0] && fileInput.files[0].name) || 'No seleccionado';
        
        // Actualiza la escapada seleccionada
        if (escapadaSelect && escapadaSelect.options && escapadaSelect.selectedIndex >= 0) {
          const escapadaOption = escapadaSelect.options[escapadaSelect.selectedIndex];
          summaryEscapada.textContent = (escapadaSelect.value && !onlyAddToDbCheckbox.checked && escapadaOption) 
            ? escapadaOption.text 
            : 'No seleccionada (solo importación)';
        } else {
          summaryEscapada.textContent = 'No seleccionada (solo importación)';
        }
        
        // Actualiza el mapeo
        const totalFields = document.querySelectorAll('.field-item').length;
        summaryMappedFields.textContent = `${Object.keys(fieldMappings).length} de ${totalFields}`;
        summaryImportMode.textContent = onlyAddToDbCheckbox.checked 
          ? 'Solo añadir a la base de datos' 
          : (escapadaSelect.value ? 'Añadir e inscribir en escapada' : 'Solo añadir a la base de datos');
        
        summaryMappingTable.innerHTML = '';
        for (const [fieldId, columnName] of Object.entries(fieldMappings)) {
          const fieldElement = document.querySelector(`[data-field-id="${fieldId}"]`);
          if (!fieldElement) {
            console.warn(`No se encontró el elemento para el campo ${fieldId}`);
            continue;
          }
          // Usamos h4 según la plantilla; si no existe, se usa el fieldId como fallback
          const fieldNameElem = fieldElement.querySelector('h4');
          const fieldName = fieldNameElem ? fieldNameElem.textContent.replace(' *', '') : fieldId;
          const row = document.createElement('tr');
          row.innerHTML = `<td>${fieldName}</td><td>${columnName}</td>`;
          summaryMappingTable.appendChild(row);
        }
      }
      

    // ============================
// 10. IMPORTACIÓN FINAL
// ============================
btnImport.addEventListener('click', startImport);

function startImport() {
    console.log('Iniciando importación...');
    console.log('Field Mappings:', fieldMappings);
    
    // Preparar datos
    mappingInput.value = JSON.stringify(fieldMappings);
    
    // UI Elements
    const spinner = btnImport.querySelector('svg.animate-spin');
    const buttonText = btnImport.querySelector('.button-text');
    
    // Update UI
    if (spinner) spinner.classList.remove('hidden');
    buttonText.textContent = 'Importando...';
    btnImport.disabled = true;

    // Crear y verificar FormData
    const formData = new FormData(importForm);
    console.log('FormData entries:');
    for (let [key, value] of formData.entries()) {
        console.log(key, value);
    }

    // Enviar petición
    fetch(importForm.action, {
        method: 'POST',
        body: formData,
        headers: { 
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        console.log('Response status:', response.status);
        return response.json();
    })
    .then(data => {
        console.log('Response data:', data);
        
        // Restaurar UI
        if (spinner) spinner.classList.add('hidden');
        buttonText.innerHTML = '<i class="fas fa-upload mr-2"></i> Iniciar importación';
        btnImport.disabled = false;

        if (data.success) {
            showImportSuccess(data);
        } else {
            showImportErrors(data.errors);
        }
    })
    .catch(error => {
        console.error('Error en la importación:', error);
        
        // Restaurar UI
        if (spinner) spinner.classList.add('hidden');
        buttonText.innerHTML = '<i class="fas fa-upload mr-2"></i> Iniciar importación';
        btnImport.disabled = false;
        
        showAlert('error', 'Error al conectar con el servidor: ' + error.message);
    });
}

function showImportSuccess(data) {
    console.log('Mostrando resultados exitosos:', data);
    
    const successHTML = `
        <div class="bg-green-50 border-l-4 border-green-500 p-4 mb-4">
            <div class="flex">
                <div class="flex-shrink-0">
                    <svg class="h-5 w-5 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                    </svg>
                </div>
                <div class="ml-3">
                    <h3 class="text-lg font-medium text-green-800">Importación completada con éxito</h3>
                    <div class="mt-2 text-sm text-green-700">
                        <ul class="list-disc pl-5 space-y-1">
                            <li>${data.new_created} nuevas personas creadas</li>
                            <li>${data.updated} personas actualizadas</li>
                            ${data.inscriptions_created ? `<li>${data.inscriptions_created} inscripciones creadas</li>` : ''}
                        </ul>
                    </div>
                </div>
            </div>
        </div>
        <div class="flex justify-center space-x-4 mt-6">
            <a href="/personas/" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                <i class="fas fa-users mr-2"></i>Ver personas
            </a>
            <a href="/importar-personas/" class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700">
                <i class="fas fa-file-upload mr-2"></i>Nueva importación
            </a>
        </div>
    `;

    importForm.innerHTML = successHTML;
}

function showImportErrors(errors) {
    console.log('Mostrando errores:', errors);
    
    let errorList = '';
    if (Array.isArray(errors)) {
        errorList = errors.map(error => `<li class="mb-1">${error}</li>`).join('');
    } else {
        errorList = `<li class="mb-1">${errors || 'Error desconocido'}</li>`;
    }

    const errorHTML = `
        <div class="bg-red-50 border-l-4 border-red-500 p-4 mb-4">
            <div class="flex">
                <div class="flex-shrink-0">
                    <svg class="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
                    </svg>
                </div>
                <div class="ml-3">
                    <h3 class="text-lg font-medium text-red-800">Error en la importación</h3>
                    <div class="mt-2 text-sm text-red-700">
                        <ul class="list-disc pl-5">
                            ${errorList}
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    `;

    showAlert('error', errorHTML, false);
    window.scrollTo(0, 0);
}

    // ============================
    // 11. UTILIDADES GENERALES
    // ============================
    function showAlert(type, message, autoClose = true) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.setAttribute('role', 'alert');
        if (message.includes('<') && message.includes('>')) {
            alertDiv.innerHTML = message;
        } else {
            alertDiv.textContent = message;
        }
        if (!message.includes('btn-close')) {
            const closeButton = document.createElement('button');
            closeButton.className = 'btn-close';
            closeButton.setAttribute('type', 'button');
            closeButton.setAttribute('data-bs-dismiss', 'alert');
            closeButton.setAttribute('aria-label', 'Cerrar');
            closeButton.innerHTML = '<i class="fas fa-times"></i>';
            alertDiv.appendChild(closeButton);
        }
        alertContainer.prepend(alertDiv);
        if (autoClose && (type === 'info' || type === 'success')) {
            setTimeout(() => {
                alertDiv.classList.remove('show');
                setTimeout(() => alertDiv.remove(), 150);
            }, 5000);
        }
    }
});
