// ============================================
// GENERADOR DE DOCUMENTOS PEI - FASE 3
// Sistema completo con Metas Anuales
// ============================================

// Variables globales
let matrizEstandar = null;
let datosSeleccionados = {
    oei: []
};
let pasoActual = 1;
let draggedElement = null;
let draggedAEIElement = null;
const API_BASE_URL = String(window.PEI_API_BASE_URL || '').replace(/\/+$/, '');

function apiUrl(path) {
    return `${API_BASE_URL}${path}`;
}

// Cargar matriz estándar al iniciar
window.addEventListener('load', async () => {
    await cargarMatrizEstandar();
    restaurarDatosGuardados();
});

// ============================================
// CARGA DE DATOS
// ============================================

async function cargarMatrizEstandar() {
    try {
        const response = await fetch(apiUrl('/matriz_estandar.json'));
        matrizEstandar = await response.json();
        renderizarOEIs();
    } catch (error) {
        console.error('Error al cargar matriz estándar:', error);
        document.getElementById('oeiContainer').innerHTML = `
            <div class="message error">
                ❌ Error al cargar la matriz estándar. Verifica que el archivo matriz_estandar.json esté en la carpeta.
            </div>
        `;
    }
}

// ============================================
// RENDERIZADO DE OEI
// ============================================

function renderizarOEIs() {
    const container = document.getElementById('oeiContainer');
    container.innerHTML = '';

    if (!matrizEstandar || !matrizEstandar.oei) {
        container.innerHTML = '<div class="message error">No se pudo cargar la matriz estándar</div>';
        return;
    }

    matrizEstandar.oei.forEach(oei => {
        const oeiCard = crearOEICard(oei);
        container.appendChild(oeiCard);
    });
}

function crearOEICard(oei) {
    const card = document.createElement('div');
    card.className = 'oei-card';
    card.dataset.codigo = oei.codigo;

    const numIndicadoresOEI = oei.indicadores.length;
    const numAEI = oei.aei.length;
    const numIndicadoresAEI = oei.aei.reduce((sum, aei) => sum + aei.indicadores.length, 0);

    card.innerHTML = `
        <div class="oei-header" onclick="toggleOEI('${oei.codigo}')">
            <input type="checkbox" class="oei-checkbox" id="oei-${oei.codigo}" 
                   onchange="toggleOEISelection('${oei.codigo}')" onclick="event.stopPropagation()">
            <div class="oei-info">
                <div class="oei-code">${oei.codigo}</div>
                <div class="oei-title">${oei.denominacion}</div>
                <div style="margin-top: 6px; font-size: 11px; color: #666;">
                    ${numIndicadoresOEI} ind. OEI • ${numAEI} AEI • ${numIndicadoresAEI} ind. AEI
                </div>
            </div>
            <div class="oei-expand-icon">▼</div>
        </div>
        <div class="oei-details">
            ${crearSeccionIndicadoresOEI(oei)}
            ${crearSeccionAEI(oei)}
        </div>
    `;

    return card;
}

function crearSeccionIndicadoresOEI(oei) {
    let html = '<div class="subsection-title">Indicadores del OEI</div>';
    
    oei.indicadores.forEach((indicador, index) => {
        html += `
            <div class="indicator-item">
                <input type="checkbox" class="indicator-checkbox" 
                       id="ind-oei-${oei.codigo}-${index}"
                       data-oei="${oei.codigo}"
                       data-tipo="oei"
                       data-index="${index}">
                <label for="ind-oei-${oei.codigo}-${index}" class="indicator-text">
                    ${indicador.nombre}
                    <span class="indicator-unit">${indicador.unidad}</span>
                </label>
            </div>
        `;
    });

    return html;
}

function crearSeccionAEI(oei) {
    let html = `<div class="subsection-title" style="margin-top: 15px;">
        Acciones Estratégicas (AEI)
        <span class="counter-badge">${oei.aei.length}</span>
    </div>`;

    oei.aei.forEach(aei => {
        html += `
            <div class="aei-item" data-codigo="${aei.codigo}">
                <input type="checkbox" class="aei-checkbox" 
                       id="aei-${aei.codigo}"
                       data-oei="${oei.codigo}"
                       data-codigo="${aei.codigo}"
                       onchange="toggleAEI('${oei.codigo}', '${aei.codigo}')">
                <div style="flex: 1;">
                    <div class="aei-code">${aei.codigo}</div>
                    <div class="indicator-text">${aei.denominacion}</div>
                    <div class="aei-details" id="aei-details-${aei.codigo}" style="display: none;">
                        ${crearIndicadoresAEI(oei.codigo, aei)}
                    </div>
                </div>
            </div>
        `;
    });

    return html;
}

function crearIndicadoresAEI(codigoOEI, aei) {
    let html = '<div class="subsection-title" style="font-size: 12px; margin-top: 10px;">Indicadores de la AEI</div>';
    
    aei.indicadores.forEach((indicador, index) => {
        html += `
            <div class="indicator-item">
                <input type="checkbox" class="indicator-checkbox"
                       id="ind-aei-${aei.codigo}-${index}"
                       data-oei="${codigoOEI}"
                       data-aei="${aei.codigo}"
                       data-tipo="aei"
                       data-index="${index}">
                <label for="ind-aei-${aei.codigo}-${index}" class="indicator-text">
                    ${indicador.nombre}
                    <span class="indicator-unit">${indicador.unidad}</span>
                </label>
            </div>
        `;
    });

    return html;
}

// ============================================
// INTERACCIONES OEI
// ============================================

function toggleOEI(codigo) {
    const card = document.querySelector(`[data-codigo="${codigo}"]`);
    card.classList.toggle('expanded');
}

function toggleOEISelection(codigo) {
    const checkbox = document.getElementById(`oei-${codigo}`);
    const card = document.querySelector(`[data-codigo="${codigo}"]`);
    
    if (checkbox.checked) {
        card.classList.add('selected', 'expanded');
        agregarOEIAPrioridad(codigo);
    } else {
        card.classList.remove('selected');
        card.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            if (cb !== checkbox) cb.checked = false;
        });
        eliminarOEIDePrioridad(codigo);
    }
    
    guardarDatos();
}

function toggleAEI(codigoOEI, codigoAEI) {
    const checkbox = document.getElementById(`aei-${codigoAEI}`);
    const details = document.getElementById(`aei-details-${codigoAEI}`);
    const aeiItem = checkbox.closest('.aei-item');
    
    if (checkbox.checked) {
        details.style.display = 'block';
        aeiItem.classList.add('selected');
        actualizarAEIEnPrioridad(codigoOEI);
    } else {
        details.style.display = 'none';
        aeiItem.classList.remove('selected');
        details.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            cb.checked = false;
        });
        actualizarAEIEnPrioridad(codigoOEI);
    }
    
    guardarDatos();
}

// ============================================
// GESTIÓN DE PRIORIDADES - OEI
// ============================================

function agregarOEIAPrioridad(codigo) {
    const oei = matrizEstandar.oei.find(o => o.codigo === codigo);
    if (!oei) return;

    const container = document.getElementById('priorityContainer');
    
    if (container.querySelector('.empty-state')) {
        container.innerHTML = '';
    }

    const priorityItem = crearPriorityItem(oei);
    container.appendChild(priorityItem);

    habilitarDragAndDrop();
    actualizarContadorPrioridad();
}

function crearPriorityItem(oei) {
    const div = document.createElement('div');
    div.className = 'priority-item';
    div.dataset.codigo = oei.codigo;
    div.draggable = true;

    const numIndicadores = obtenerNumeroIndicadoresOEI(oei.codigo);
    const numAEI = obtenerNumeroAEI(oei.codigo);

    div.innerHTML = `
        <div class="priority-number">1</div>
        <button class="remove-btn" onclick="eliminarOEIDePrioridad('${oei.codigo}')" title="Eliminar">✕</button>
        <div class="priority-header">
            <div class="drag-handle">⋮⋮</div>
            <div style="flex: 1;">
                <div class="priority-code">${oei.codigo}</div>
                <div class="priority-title">${oei.denominacion}</div>
                <div class="priority-stats">
                    <div class="priority-stat">📊 ${numIndicadores} indicadores</div>
                    <div class="priority-stat">📋 ${numAEI} AEI</div>
                </div>
            </div>
        </div>
        <button class="expand-aei-btn" onclick="toggleAEIPriority('${oei.codigo}')">
            Ver AEI para priorizar ▼
        </button>
        <div class="aei-priority-list" id="aei-priority-${oei.codigo}">
            ${crearListaAEIPrioridad(oei.codigo)}
        </div>
    `;

    return div;
}

function crearListaAEIPrioridad(codigoOEI) {
    const aeiSeleccionadas = obtenerAEISeleccionadas(codigoOEI);
    
    if (aeiSeleccionadas.length === 0) {
        return '<div style="text-align: center; padding: 15px; color: #999; font-size: 12px;">No hay AEI seleccionadas aún</div>';
    }

    let html = '<div style="font-size: 12px; font-weight: 600; margin-bottom: 10px; color: #764ba2;">Arrastra para priorizar las AEI:</div>';
    html += '<div class="aei-sortable">';
    
    aeiSeleccionadas.forEach((aei, index) => {
        html += `
            <div class="aei-priority-item" data-codigo="${aei.codigo}" draggable="true">
                <div class="aei-priority-number">${index + 1}</div>
                <div class="aei-priority-code">${aei.codigo}</div>
                <div class="aei-priority-title">${aei.denominacion}</div>
            </div>
        `;
    });
    
    html += '</div>';
    return html;
}

function obtenerAEISeleccionadas(codigoOEI) {
    const oei = matrizEstandar.oei.find(o => o.codigo === codigoOEI);
    if (!oei) return [];

    const aeiSeleccionadas = [];
    oei.aei.forEach(aei => {
        const checkbox = document.getElementById(`aei-${aei.codigo}`);
        if (checkbox && checkbox.checked) {
            aeiSeleccionadas.push(aei);
        }
    });

    return aeiSeleccionadas;
}

function obtenerNumeroIndicadoresOEI(codigoOEI) {
    let count = 0;
    document.querySelectorAll(`input[data-oei="${codigoOEI}"][data-tipo="oei"]:checked`).forEach(() => count++);
    document.querySelectorAll(`input[data-oei="${codigoOEI}"][data-tipo="aei"]:checked`).forEach(() => count++);
    return count;
}

function obtenerNumeroAEI(codigoOEI) {
    return document.querySelectorAll(`input[data-oei="${codigoOEI}"].aei-checkbox:checked`).length;
}

function eliminarOEIDePrioridad(codigo) {
    const checkbox = document.getElementById(`oei-${codigo}`);
    if (checkbox) {
        checkbox.checked = false;
        toggleOEISelection(codigo);
    }

    const priorityItem = document.querySelector(`.priority-item[data-codigo="${codigo}"]`);
    if (priorityItem) {
        priorityItem.remove();
    }

    actualizarNumerosPrioridad();
    actualizarContadorPrioridad();

    const container = document.getElementById('priorityContainer');
    if (container.children.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📦</div>
                <div class="empty-state-text">
                    Los OEI que selecciones aparecerán aquí.<br>
                    Podrás arrastrarlos para definir su orden de prioridad.
                </div>
            </div>
        `;
    }
}

function actualizarAEIEnPrioridad(codigoOEI) {
    const priorityItem = document.querySelector(`.priority-item[data-codigo="${codigoOEI}"]`);
    if (!priorityItem) return;

    const numIndicadores = obtenerNumeroIndicadoresOEI(codigoOEI);
    const numAEI = obtenerNumeroAEI(codigoOEI);
    
    const stats = priorityItem.querySelector('.priority-stats');
    stats.innerHTML = `
        <div class="priority-stat">📊 ${numIndicadores} indicadores</div>
        <div class="priority-stat">📋 ${numAEI} AEI</div>
    `;

    const aeiList = priorityItem.querySelector('.aei-priority-list');
    if (aeiList && priorityItem.classList.contains('expanded')) {
        aeiList.innerHTML = crearListaAEIPrioridad(codigoOEI);
        habilitarDragAndDropAEI();
    }
}

function toggleAEIPriority(codigoOEI) {
    const priorityItem = document.querySelector(`.priority-item[data-codigo="${codigoOEI}"]`);
    const btn = priorityItem.querySelector('.expand-aei-btn');
    const aeiList = priorityItem.querySelector('.aei-priority-list');
    
    priorityItem.classList.toggle('expanded');
    
    if (priorityItem.classList.contains('expanded')) {
        btn.textContent = 'Ocultar AEI ▲';
        aeiList.innerHTML = crearListaAEIPrioridad(codigoOEI);
        habilitarDragAndDropAEI();
    } else {
        btn.textContent = 'Ver AEI para priorizar ▼';
    }
}

function actualizarNumerosPrioridad() {
    const items = document.querySelectorAll('.priority-item');
    items.forEach((item, index) => {
        const numberBadge = item.querySelector('.priority-number');
        numberBadge.textContent = index + 1;
    });
}

function actualizarContadorPrioridad() {
    const count = document.querySelectorAll('.priority-item').length;
    document.getElementById('priorityCount').textContent = count;
}

// ============================================
// DRAG & DROP - OEI
// ============================================

function habilitarDragAndDrop() {
    const items = document.querySelectorAll('.priority-item');
    
    items.forEach(item => {
        item.addEventListener('dragstart', handleDragStart);
        item.addEventListener('dragover', handleDragOver);
        item.addEventListener('drop', handleDrop);
        item.addEventListener('dragend', handleDragEnd);
        item.addEventListener('dragenter', handleDragEnter);
        item.addEventListener('dragleave', handleDragLeave);
    });
}

function handleDragStart(e) {
    draggedElement = this;
    this.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', this.innerHTML);
}

function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleDragEnter(e) {
    if (this !== draggedElement) {
        this.classList.add('drag-over');
    }
}

function handleDragLeave(e) {
    this.classList.remove('drag-over');
}

function handleDrop(e) {
    if (e.stopPropagation) {
        e.stopPropagation();
    }

    if (draggedElement !== this) {
        const container = document.getElementById('priorityContainer');
        const items = Array.from(container.children);
        const draggedIndex = items.indexOf(draggedElement);
        const targetIndex = items.indexOf(this);

        if (draggedIndex < targetIndex) {
            container.insertBefore(draggedElement, this.nextSibling);
        } else {
            container.insertBefore(draggedElement, this);
        }

        actualizarNumerosPrioridad();
        guardarDatos();
    }

    return false;
}

function handleDragEnd(e) {
    this.classList.remove('dragging');
    
    const items = document.querySelectorAll('.priority-item');
    items.forEach(item => {
        item.classList.remove('drag-over');
    });
}

// ============================================
// DRAG & DROP - AEI
// ============================================

function habilitarDragAndDropAEI() {
    const items = document.querySelectorAll('.aei-priority-item');
    
    items.forEach(item => {
        item.addEventListener('dragstart', handleAEIDragStart);
        item.addEventListener('dragover', handleAEIDragOver);
        item.addEventListener('drop', handleAEIDrop);
        item.addEventListener('dragend', handleAEIDragEnd);
    });
}

function handleAEIDragStart(e) {
    draggedAEIElement = this;
    this.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
}

function handleAEIDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleAEIDrop(e) {
    if (e.stopPropagation) {
        e.stopPropagation();
    }

    if (draggedAEIElement !== this && draggedAEIElement.parentNode === this.parentNode) {
        const container = this.parentNode;
        const items = Array.from(container.children);
        const draggedIndex = items.indexOf(draggedAEIElement);
        const targetIndex = items.indexOf(this);

        if (draggedIndex < targetIndex) {
            container.insertBefore(draggedAEIElement, this.nextSibling);
        } else {
            container.insertBefore(draggedAEIElement, this);
        }

        actualizarNumerosAEI(container);
        guardarDatos();
    }

    return false;
}

function handleAEIDragEnd(e) {
    this.classList.remove('dragging');
}

function actualizarNumerosAEI(container) {
    const items = container.querySelectorAll('.aei-priority-item');
    items.forEach((item, index) => {
        const numberBadge = item.querySelector('.aei-priority-number');
        numberBadge.textContent = index + 1;
    });
}

// ============================================
// FASE 3: RENDERIZADO DE METAS
// ============================================

function renderizarMetasIndicadores() {
    const container = document.getElementById('metasContainer');
    container.innerHTML = '';
    
    const priorityItems = document.querySelectorAll('.priority-item');
    
    if (priorityItems.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📊</div>
                <div class="empty-state-text">
                    No hay indicadores seleccionados.<br>
                    Regresa al Paso 2 para seleccionar OEI/AEI.
                </div>
            </div>
        `;
        return;
    }
    
    priorityItems.forEach((item, index) => {
        const codigoOEI = item.dataset.codigo;
        const oei = matrizEstandar.oei.find(o => o.codigo === codigoOEI);
        
        if (oei) {
            const oeiSection = crearSeccionMetasOEI(oei, index + 1);
            container.appendChild(oeiSection);
        }
    });
}

function crearSeccionMetasOEI(oei, prioridad) {
    const section = document.createElement('div');
    section.className = 'metas-oei-section';
    
    const indicadoresOEI = obtenerIndicadoresOEISeleccionados(oei.codigo);
    const indicadoresAEI = obtenerIndicadoresAEISeleccionados(oei.codigo);
    
    section.innerHTML = `
        <div class="metas-oei-header">
            <div class="metas-oei-priority">Prioridad ${prioridad}</div>
            <div class="metas-oei-title">${oei.codigo}: ${oei.denominacion}</div>
        </div>
        
        <div class="metas-indicadores-container">
            ${indicadoresOEI.length > 0 ? crearMetasIndicadoresOEI(oei, indicadoresOEI) : ''}
            ${indicadoresAEI.length > 0 ? crearMetasIndicadoresAEI(oei, indicadoresAEI) : ''}
        </div>
    `;
    
    return section;
}

function obtenerIndicadoresOEISeleccionados(codigoOEI) {
    const oei = matrizEstandar.oei.find(o => o.codigo === codigoOEI);
    if (!oei) return [];
    
    const indicadores = [];
    oei.indicadores.forEach((indicador, index) => {
        const checkbox = document.getElementById(`ind-oei-${codigoOEI}-${index}`);
        if (checkbox && checkbox.checked) {
            indicadores.push({
                id: `ind-oei-${codigoOEI}-${index}`,
                nombre: indicador.nombre,
                unidad: indicador.unidad,
                tipo: 'OEI'
            });
        }
    });
    
    return indicadores;
}

function obtenerIndicadoresAEISeleccionados(codigoOEI) {
    const oei = matrizEstandar.oei.find(o => o.codigo === codigoOEI);
    if (!oei) return [];
    
    const indicadores = [];
    oei.aei.forEach(aei => {
        const aeiCheckbox = document.getElementById(`aei-${aei.codigo}`);
        if (aeiCheckbox && aeiCheckbox.checked) {
            aei.indicadores.forEach((indicador, index) => {
                const checkbox = document.getElementById(`ind-aei-${aei.codigo}-${index}`);
                if (checkbox && checkbox.checked) {
                    indicadores.push({
                        id: `ind-aei-${aei.codigo}-${index}`,
                        nombre: indicador.nombre,
                        unidad: indicador.unidad,
                        tipo: 'AEI',
                        codigoAEI: aei.codigo,
                        denominacionAEI: aei.denominacion
                    });
                }
            });
        }
    });
    
    return indicadores;
}

function crearMetasIndicadoresOEI(oei, indicadores) {
    let html = '<div class="metas-tipo-header">📊 Indicadores del OEI</div>';
    
    indicadores.forEach(indicador => {
        html += crearFormularioMeta(indicador);
    });
    
    return html;
}

function crearMetasIndicadoresAEI(oei, indicadores) {
    let html = '<div class="metas-tipo-header">📋 Indicadores de las AEI</div>';
    
    const porAEI = {};
    indicadores.forEach(ind => {
        if (!porAEI[ind.codigoAEI]) {
            porAEI[ind.codigoAEI] = {
                denominacion: ind.denominacionAEI,
                indicadores: []
            };
        }
        porAEI[ind.codigoAEI].indicadores.push(ind);
    });
    
    Object.keys(porAEI).forEach(codigoAEI => {
        const aei = porAEI[codigoAEI];
        html += `<div class="metas-aei-subtitle">${codigoAEI}: ${aei.denominacion}</div>`;
        aei.indicadores.forEach(indicador => {
            html += crearFormularioMeta(indicador);
        });
    });
    
    return html;
}

function crearFormularioMeta(indicador) {
    const savedData = JSON.parse(localStorage.getItem('peiFormData') || '{}');
    const metas = savedData.metas || {};
    const metaData = metas[indicador.id] || {};
    
    return `
        <div class="meta-card">
            <div class="meta-header">
                <span class="meta-icon">📊</span>
                <div class="meta-info">
                    <div class="meta-nombre">${indicador.nombre}</div>
                    <div class="meta-unidad">Unidad: ${indicador.unidad}</div>
                </div>
            </div>
            
            <div class="meta-form-grid">
                <div class="meta-field">
                    <label>Año Base *</label>
                    <input type="number" 
                           id="${indicador.id}-año_base"
                           class="meta-input"
                           placeholder="2025"
                           min="2020" max="2027"
                           value="${metaData.año_base || ''}"
                           oninput="guardarMeta('${indicador.id}', 'año_base', this.value)"
                           required>
                </div>
                
                <div class="meta-field">
                    <label>Valor Base *</label>
                    <input type="number" 
                           id="${indicador.id}-valor_base"
                           class="meta-input"
                           placeholder="0"
                           min="0" step="0.01"
                           value="${metaData.valor_base || ''}"
                           oninput="guardarMeta('${indicador.id}', 'valor_base', this.value)"
                           required>
                </div>
            </div>
            
            <div class="meta-años-grid">
                ${(() => {
                    const periodoStr = savedData.periodo_pei || '';
                    const aniosMatch = periodoStr.match(/\d{4}/g);
                    const anios = (aniosMatch && aniosMatch.length >= 2)
                        ? Array.from({length: parseInt(aniosMatch[1]) - parseInt(aniosMatch[0]) + 1}, (_, i) => parseInt(aniosMatch[0]) + i)
                        : [2026, 2027, 2028, 2029, 2030];
                    return anios.map(anio => `
                        <div class="meta-field">
                            <label>Meta ${anio} *</label>
                            <input type="number" 
                                   id="${indicador.id}-meta_${anio}"
                                   class="meta-input"
                                   placeholder="0"
                                   min="0" step="0.01"
                                   value="${metaData['meta_' + anio] || ''}"
                                   oninput="guardarMeta('${indicador.id}', 'meta_${anio}', this.value)"
                                   required>
                        </div>
                    `).join('');
                })()}
            </div>
        </div>
    `;
}

// ============================================
// FASE 3: GESTIÓN DE METAS
// ============================================

function guardarMeta(indicadorId, campo, valor) {
    const savedData = JSON.parse(localStorage.getItem('peiFormData') || '{}');
    
    if (!savedData.metas) {
        savedData.metas = {};
    }
    
    if (!savedData.metas[indicadorId]) {
        savedData.metas[indicadorId] = {};
    }
    
    savedData.metas[indicadorId][campo] = valor !== '' ? parseFloat(valor) : '';
    
    localStorage.setItem('peiFormData', JSON.stringify(savedData));
}

function validarMetasYContinuar() {
    const metaInputs = document.querySelectorAll('.meta-input');
    const alert = document.getElementById('selectionAlert');
    
    let hayVacios = false;
    metaInputs.forEach(input => {
        if (input.value === '' || input.value === null) {
            hayVacios = true;
            input.style.borderColor = '#dc3545';
        } else {
            input.style.borderColor = '#e0e0e0';
        }
    });
    
    if (hayVacios) {
        if (alert) {
            alert.innerHTML = '⚠️ Por favor, completa todas las metas antes de continuar. Los campos en rojo están vacíos.';
            alert.classList.add('show');
            alert.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        return;
    }
    
    if (alert) {
        alert.classList.remove('show');
    }
    
    actualizarResumenFinal();
    siguientePaso(4);
}

// ============================================
// NAVEGACIÓN
// ============================================

function siguientePaso(paso) {
    document.querySelectorAll('.form-step').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
    
    for (let i = 1; i < paso; i++) {
        document.querySelector(`[data-step="${i}"].step`).classList.add('completed');
    }
    
    document.querySelector(`.form-step[data-step="${paso}"]`).classList.add('active');
    document.querySelector(`.step[data-step="${paso}"]`).classList.add('active');
    
    pasoActual = paso;
    
    if (paso === 3) {
        renderizarMetasIndicadores();
    }
    
    window.scrollTo({ top: 0, behavior: 'smooth' });
    guardarDatos();
}

function validarYContinuarAMetas() {
    const oeiSeleccionados = document.querySelectorAll('.oei-checkbox:checked');
    const alert = document.getElementById('selectionAlert');
    
    if (oeiSeleccionados.length === 0) {
        alert.classList.add('show');
        alert.textContent = '⚠️ Debes seleccionar al menos 1 OEI con sus indicadores y AEI antes de continuar.';
        return;
    }
    
    let valido = true;
    oeiSeleccionados.forEach(oeiCheckbox => {
        const codigo = oeiCheckbox.id.replace('oei-', '');
        const card = document.querySelector(`[data-codigo="${codigo}"]`);
        const indicadoresOEI = card.querySelectorAll('input[data-tipo="oei"]:checked');
        const aeiSeleccionadas = card.querySelectorAll('.aei-checkbox:checked');
        
        if (indicadoresOEI.length === 0 || aeiSeleccionadas.length === 0) {
            valido = false;
        }
    });
    
    if (!valido) {
        alert.innerHTML = '⚠️ Cada OEI seleccionado debe tener al menos 1 indicador y 1 AEI con sus indicadores.';
        alert.classList.add('show');
        return;
    }
    
    alert.classList.remove('show');
    siguientePaso(3);
}

function actualizarResumenFinal() {
    const oeiCount = document.querySelectorAll('.oei-checkbox:checked').length;
    const aeiCount = document.querySelectorAll('.aei-checkbox:checked').length;
    const indCount = document.querySelectorAll('.indicator-checkbox:checked').length;
    
    const savedData = JSON.parse(localStorage.getItem('peiFormData') || '{}');
    const metasCount = savedData.metas ? Object.keys(savedData.metas).length : 0;
    
    document.getElementById('resumenOEI').textContent = `${oeiCount} OEI seleccionados`;
    document.getElementById('resumenAEI').textContent = `${aeiCount} AEI seleccionadas`;
    document.getElementById('resumenIndicadores').textContent = `${indCount} indicadores totales`;
    
    const resumenMetasElement = document.getElementById('resumenMetas');
    if (resumenMetasElement) {
        resumenMetasElement.textContent = `${metasCount} indicadores con metas definidas`;
    }
}

// ============================================
// PERSISTENCIA
// ============================================

function guardarDatos() {
    const formData = new FormData(document.getElementById('peiForm'));
    const data = {};
    formData.forEach((value, key) => {
        data[key] = value;
    });
    
    data.selecciones = {
        oei: Array.from(document.querySelectorAll('.oei-checkbox:checked')).map(cb => cb.id),
        indicadoresOEI: Array.from(document.querySelectorAll('input[data-tipo="oei"]:checked')).map(cb => cb.id),
        aei: Array.from(document.querySelectorAll('.aei-checkbox:checked')).map(cb => cb.id),
        indicadoresAEI: Array.from(document.querySelectorAll('input[data-tipo="aei"]:checked')).map(cb => cb.id)
    };

    const priorityItems = document.querySelectorAll('.priority-item');
    data.prioridades = {
        oei: Array.from(priorityItems).map(item => item.dataset.codigo),
        aei: {}
    };

    priorityItems.forEach(item => {
        const codigoOEI = item.dataset.codigo;
        const aeiItems = item.querySelectorAll('.aei-priority-item');
        data.prioridades.aei[codigoOEI] = Array.from(aeiItems).map(aei => aei.dataset.codigo);
    });
    
    const savedData = JSON.parse(localStorage.getItem('peiFormData') || '{}');
    if (savedData.metas) {
        data.metas = savedData.metas;
    }
    
    localStorage.setItem('peiFormData', JSON.stringify(data));
}

function restaurarDatosGuardados() {
    const savedData = localStorage.getItem('peiFormData');
    if (!savedData) return;
    
    try {
        const data = JSON.parse(savedData);
        
        Object.keys(data).forEach(key => {
            if (key !== 'selecciones' && key !== 'prioridades' && key !== 'metas') {
                const field = document.getElementById(key);
                if (field) field.value = data[key];
            }
        });
        
        if (data.selecciones) {
            setTimeout(() => {
                data.selecciones.oei?.forEach(id => {
                    const cb = document.getElementById(id);
                    if (cb) {
                        cb.checked = true;
                        toggleOEISelection(id.replace('oei-', ''));
                    }
                });
                
                data.selecciones.indicadoresOEI?.forEach(id => {
                    const cb = document.getElementById(id);
                    if (cb) cb.checked = true;
                });
                
                data.selecciones.aei?.forEach(id => {
                    const cb = document.getElementById(id);
                    if (cb) {
                        cb.checked = true;
                        const codigo = id.replace('aei-', '');
                        const details = document.getElementById(`aei-details-${codigo}`);
                        if (details) details.style.display = 'block';
                    }
                });
                
                data.selecciones.indicadoresAEI?.forEach(id => {
                    const cb = document.getElementById(id);
                    if (cb) cb.checked = true;
                });

                if (data.prioridades) {
                    restaurarPrioridades(data.prioridades);
                }
            }, 500);
        }
    } catch (error) {
        console.error('Error al restaurar datos:', error);
    }
}

function restaurarPrioridades(prioridades) {
    const container = document.getElementById('priorityContainer');
    
    if (prioridades.oei && prioridades.oei.length > 0) {
        const items = Array.from(container.querySelectorAll('.priority-item'));
        
        prioridades.oei.forEach((codigo, index) => {
            const item = items.find(i => i.dataset.codigo === codigo);
            if (item) {
                container.appendChild(item);
            }
        });

        actualizarNumerosPrioridad();
    }

    if (prioridades.aei) {
        Object.keys(prioridades.aei).forEach(codigoOEI => {
            const aeiList = document.getElementById(`aei-priority-${codigoOEI}`);
            if (aeiList) {
                const sortable = aeiList.querySelector('.aei-sortable');
                if (sortable) {
                    const aeiItems = Array.from(sortable.querySelectorAll('.aei-priority-item'));
                    prioridades.aei[codigoOEI].forEach(codigoAEI => {
                        const item = aeiItems.find(i => i.dataset.codigo === codigoAEI);
                        if (item) {
                            sortable.appendChild(item);
                        }
                    });
                    actualizarNumerosAEI(sortable);
                }
            }
        });
    }
}

function limpiarFormulario() {
    if (confirm('¿Estás seguro de que deseas limpiar todos los datos? Esta acción no se puede deshacer.')) {
        localStorage.removeItem('peiFormData');
        location.reload();
    }
}

// Auto-guardar al escribir
document.getElementById('peiForm').addEventListener('input', guardarDatos);
document.getElementById('peiForm').addEventListener('change', guardarDatos);

// Manejar envío del formulario (Paso 4)
document.getElementById('peiForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const btnGenerar = document.getElementById('btnGenerar');
    const loading = document.getElementById('loading');
    const message = document.getElementById('message');
    
    // Deshabilitar botón y mostrar loading
    btnGenerar.disabled = true;
    loading.classList.add('active');
    message.style.display = 'none';
    
    try {
        // Obtener todos los datos del localStorage
        const savedData = JSON.parse(localStorage.getItem('peiFormData') || '{}');

    // === CÓDIGO SALVAVIDAS PARA PRIORIDADES ===
        if (!savedData.prioridades) {
            savedData.prioridades = { oei: [], aei: {} };
        }

        // 1. Auto-llenar prioridades OEI si están vacías
        if (!savedData.prioridades.oei || savedData.prioridades.oei.length === 0) {
            if (savedData.selecciones && savedData.selecciones.oei) {
                savedData.prioridades.oei = savedData.selecciones.oei.map(id => id.replace('oei-', ''));
            }
        }

        // 2. Auto-llenar prioridades AEI agrupándolas por su OEI padre
        if (savedData.selecciones && savedData.selecciones.aei) {
            if (!savedData.prioridades.aei) savedData.prioridades.aei = {};
            
            savedData.selecciones.aei.forEach(aeiId => {
                const codigoAei = aeiId.replace('aei-', ''); // Ej: AEI.01.01
                const match = codigoAei.match(/^AEI\.(\d{2})/);
                if (match) {
                    const codigoOei = `OEI.${match[1]}`; // Ej: OEI.01
                    
                    // Aseguramos que exista el array para este OEI
                    if (!savedData.prioridades.aei[codigoOei]) {
                        savedData.prioridades.aei[codigoOei] = [];
                    }
                    // Agregamos la AEI si por alguna razón no estaba en la lista de prioridades
                    if (!savedData.prioridades.aei[codigoOei].includes(codigoAei)) {
                        savedData.prioridades.aei[codigoOei].push(codigoAei);
                    }
                }
            });
        }

        // Validar que hay datos
        if (!savedData.codigo_ue || !savedData.nombre_municipio) {
            throw new Error('Faltan datos básicos. Por favor completa el Paso 1.');
        }
        
        if (!savedData.selecciones || !savedData.selecciones.oei || savedData.selecciones.oei.length === 0) {
            throw new Error('No hay OEI seleccionados. Por favor completa el Paso 2.');
        }
        
        if (!savedData.metas || Object.keys(savedData.metas).length === 0) {
            throw new Error('No hay metas definidas. Por favor completa el Paso 3.');
        }
        
        console.log('Enviando datos al servidor...', savedData);
        
        // Enviar datos al servidor
        const response = await fetch(apiUrl('/generar'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(savedData)
        });

        const text = await response.text();
        let result;
        try {
            result = JSON.parse(text);
        } catch {
            throw new Error(`Respuesta inesperada del servidor (HTTP ${response.status}). Cuerpo: ${text.substring(0, 400)}`);
        }
        
        loading.classList.remove('active');
        
        if (!response.ok || !result.success) {
            let errorMsg = result.error || `Error HTTP ${response.status} al generar el documento`;
            
            // Extraer y formatear los detalles exactos de la validación del backend
            if (result.details && result.details.length > 0) {
                const detalles = result.details.map(d => d.message).join("<br>• ");
                errorMsg += `<br><br><span style="color: #dc3545;"><strong>Detalles a corregir:</strong></span><br>• ${detalles}`;
            }
            
            throw new Error(errorMsg);
        }

        // Mostrar mensaje de éxito
        message.className = 'message success';
        message.innerHTML = `
            <strong>✅ ${result.message || '¡Documento generado exitosamente!'}</strong><br><br>
            <strong>📄 Archivo generado:</strong> ${result.file}<br><br>
            <a href="${apiUrl(`/downloads/${encodeURIComponent(result.file)}`)}" download class="download-link">
                📥 Descargar Documento
            </a>
            <br><br>
            <small>El documento se ha generado en la carpeta del servidor.</small>
        `;
        
    } catch (error) {
        loading.classList.remove('active');
        message.className = 'message error';
        message.innerHTML = `
            <strong>❌ Error al generar el documento</strong><br><br>
            ${error.message}<br><br>
            <small>Por favor verifica que todos los pasos estén completos y vuelve a intentar.</small>
        `;
        console.error('Error:', error);
    } finally {
        btnGenerar.disabled = false;
    }
});
