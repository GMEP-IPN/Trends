function renderPLCItem(plc, isArchived = false) {
    const typeLabel = plc.plc_type === 'allen_bradley' ? 'AB' : 'S7';
    if (isArchived) {
        return `
        <div class="plc-btn" style="opacity: 0.6;">
            <div class="plc-main">
                <div class="plc-name">📦 ${plc.name} <span style="color: var(--text-muted); font-size: 0.7rem;">[${typeLabel}]</span></div>
                <div class="plc-info">${plc.ip_address} • ${plc.tag_count} tags</div>
            </div>
            <div class="plc-actions">
                <button class="plc-action-btn" onclick="event.stopPropagation(); unarchivePLC(${plc.id}, '${plc.name}')" title="Восстановить из архива">📤</button>
                <button class="plc-action-btn delete" onclick="event.stopPropagation(); deletePLC(${plc.id}, '${plc.name}')" title="Delete">🗑️</button>
            </div>
        </div>`;
    }
    const isActive = plc.is_active !== false;
    const inactiveStyle = !isActive ? 'opacity: 0.5;' : '';
    let statusIcon = '⏸️';
    if (isActive) {
        if (plc.connection_status === 'connected') statusIcon = '🟢';
        else if (plc.connection_status === 'disconnected') statusIcon = '🔴';
        else statusIcon = '🟡';
    }
    return `
    <div class="plc-btn ${selectedPlcId === plc.id ? 'active' : ''}" style="${inactiveStyle}" onclick="selectPLC(${plc.id}, '${plc.plc_type || 'siemens_s7'}')">
        <div class="plc-main">
            <div class="plc-name">${statusIcon} ${plc.name} <span style="color: var(--text-muted); font-size: 0.7rem;">[${typeLabel}]</span></div>
            <div class="plc-info">${plc.ip_address} • ${plc.tag_count} tags</div>
        </div>
        <div class="plc-actions">
            <button class="plc-action-btn" onclick="event.stopPropagation(); togglePLC(${plc.id})" title="${isActive ? 'Pause polling' : 'Resume polling'}">${isActive ? '⏸️' : '▶️'}</button>
            <button class="plc-action-btn" onclick="event.stopPropagation(); editPLC(${plc.id}, '${plc.name}', '${plc.plc_type || 'siemens_s7'}', '${plc.ip_address}', ${plc.tcp_port}, ${plc.rack}, ${plc.slot}, ${plc.slot_ab || 0})" title="Edit">✏️</button>
            <button class="plc-action-btn" onclick="event.stopPropagation(); archivePLC(${plc.id}, '${plc.name}')" title="В архив">📦</button>
            <button class="plc-action-btn delete" onclick="event.stopPropagation(); deletePLC(${plc.id}, '${plc.name}')" title="Delete">🗑️</button>
        </div>
    </div>`;
}

async function loadPLCs() {
    try {
        const [activeResp, allResp] = await Promise.all([
            fetch('/api/plcs'),
            fetch('/api/plcs?include_archived=true'),
        ]);
        const activePlcs = await activeResp.json();
        const allPlcs = await allResp.json();
        const archivedPlcs = allPlcs.filter(p => p.is_archived);

        plcsData = activePlcs;

        const plcSelector = document.getElementById('plcSelector');

        if (activePlcs.length === 0 && archivedPlcs.length === 0) {
            plcSelector.innerHTML = '<div style="color: var(--text-muted); font-size: 0.875rem; padding: 0.5rem;">No PLCs</div>';
            return;
        }

        if (selectedPlcId === null && activePlcs.length > 0) {
            selectedPlcId = activePlcs[0].id;
            selectedPlcType = activePlcs[0].plc_type || 'siemens_s7';
        }

        const selectedPLC = activePlcs.find(p => p.id === selectedPlcId);
        if (selectedPLC) selectedPlcType = selectedPLC.plc_type || 'siemens_s7';

        let html = activePlcs.map(plc => renderPLCItem(plc, false)).join('');

        if (archivedPlcs.length > 0) {
            const isOpen = document.getElementById('archiveSection')?.classList.contains('open');
            html += `
            <div class="archive-section" id="archiveSection${isOpen ? ' class="open"' : ''}">
                <div class="archive-toggle" onclick="toggleArchiveSection()">
                    📦 Архив <span class="archive-count">${archivedPlcs.length}</span>
                    <span class="archive-arrow" id="archiveArrow">${isOpen ? '▲' : '▼'}</span>
                </div>
                <div class="archive-list" id="archiveList" style="display: ${isOpen ? 'block' : 'none'};">
                    ${archivedPlcs.map(plc => renderPLCItem(plc, true)).join('')}
                </div>
            </div>`;
        }

        plcSelector.innerHTML = html;
    } catch (error) {
        console.error('Error loading PLCs:', error);
    }
}

function toggleArchiveSection() {
    const list = document.getElementById('archiveList');
    const arrow = document.getElementById('archiveArrow');
    if (!list) return;
    const isOpen = list.style.display !== 'none';
    list.style.display = isOpen ? 'none' : 'block';
    if (arrow) arrow.textContent = isOpen ? '▼' : '▲';
}

function updatePLCFormFields() {
    const plcType = document.getElementById('plcType').value;
    const s7Fields = document.getElementById('s7Fields');
    const abFields = document.getElementById('abFields');
    const portInput = document.getElementById('plcPort');
    const portHint = document.getElementById('plcPortHint');
    if (plcType === 'allen_bradley') {
        s7Fields.style.display = 'none';
        abFields.style.display = 'flex';
        portInput.value = '44818';
        portHint.textContent = 'EtherNet/IP: 44818';
    } else {
        s7Fields.style.display = 'flex';
        abFields.style.display = 'none';
        portInput.value = '102';
        portHint.textContent = 'S7: 102, Sim: 2000';
    }
}

async function selectPLC(plcId, plcType = 'siemens_s7') {
    selectedPlcId = plcId;
    selectedPlcType = plcType;
    selectedTagId = null;
    await loadPLCs();
    await loadTags();
    await initTrends();
}

function showPLCForm(editMode = false) {
    document.getElementById('plcFormModal').classList.add('active');
    document.getElementById('plcFormTitle').textContent = editMode ? '✏️ Edit PLC' : '➕ Add PLC';
    document.getElementById('plcSubmitBtn').textContent = editMode ? 'Save' : 'Add';
    if (!editMode) {
        document.getElementById('plcForm').reset();
        document.getElementById('plcEditId').value = '';
        document.getElementById('plcType').value = 'siemens_s7';
        document.getElementById('plcPort').value = '102';
        document.getElementById('plcRack').value = '0';
        document.getElementById('plcSlot').value = '1';
        document.getElementById('plcSlotAB').value = '0';
        updatePLCFormFields();
    }
    document.getElementById('plcName').focus();
}

function cancelPLCForm() {
    document.getElementById('plcForm').reset();
    document.getElementById('plcEditId').value = '';
    document.getElementById('plcType').value = 'siemens_s7';
    updatePLCFormFields();
    document.getElementById('plcFormModal').classList.remove('active');
}

function editPLC(id, name, plcType, ip, port, rack = 0, slot = 1, slotAB = 0) {
    document.getElementById('plcEditId').value = id;
    document.getElementById('plcType').value = plcType || 'siemens_s7';
    document.getElementById('plcName').value = name;
    document.getElementById('plcIP').value = ip;
    document.getElementById('plcPort').value = port;
    document.getElementById('plcRack').value = rack;
    document.getElementById('plcSlot').value = slot;
    document.getElementById('plcSlotAB').value = slotAB;
    updatePLCFormFields();
    showPLCForm(true);
}

async function submitPLC(event) {
    event.preventDefault();
    const editId = document.getElementById('plcEditId').value;
    const plcType = document.getElementById('plcType').value;
    const data = {
        name: document.getElementById('plcName').value,
        plc_type: plcType,
        ip_address: document.getElementById('plcIP').value,
        tcp_port: parseInt(document.getElementById('plcPort').value),
        rack: parseInt(document.getElementById('plcRack').value),
        slot: parseInt(document.getElementById('plcSlot').value),
        slot_ab: parseInt(document.getElementById('plcSlotAB').value)
    };

    try {
        const url = editId ? `/api/plcs/${editId}` : '/api/plcs';
        const method = editId ? 'PUT' : 'POST';
        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            document.getElementById('welcomeScreen').style.display = 'none';
            const typeLabel = plcType === 'allen_bradley' ? 'Allen-Bradley' : 'Siemens S7';
            showToast(`PLC "${data.name}" (${typeLabel}) ${editId ? 'updated' : 'added'}`, 'success');
            cancelPLCForm();
            await loadPLCs();
            await loadTags();
            await initTrends();
        } else {
            const error = await response.json();
            showToast(error.detail || 'Save error', 'error');
        }
    } catch (error) {
        showToast('Network error', 'error');
    }
}

function showRestartBanner() {
    const banner = document.getElementById('connectionBanner');
    banner.classList.add('show');
    banner.style.background = 'var(--warning)';
    document.getElementById('bannerText').innerHTML = '⚠️ Config changed <button onclick="restartCollector()">Restart</button>';
}

async function restartCollector() {
    try {
        const response = await fetch('/api/collector/restart', { method: 'POST' });
        if (response.ok) {
            showToast('Collector restarting...', 'success');
            setTimeout(() => {
                document.getElementById('connectionBanner').classList.remove('show');
                loadStatus();
                loadTags();
            }, 2000);
        } else {
            showToast('Restart error', 'error');
        }
    } catch (error) {
        showToast('Network error', 'error');
    }
}

async function togglePLC(id) {
    try {
        const response = await fetch(`/api/plcs/${id}/toggle`, { method: 'PUT' });
        if (response.ok) {
            const result = await response.json();
            showToast(result.message, 'success');
            await new Promise(resolve => setTimeout(resolve, 1500));
            await loadPLCs();
            await loadStatus();
        } else {
            showToast('Toggle error', 'error');
        }
    } catch (error) {
        showToast('Network error', 'error');
    }
}

async function deletePLC(id, name) {
    if (!confirm(`Delete PLC "${name}" and all its tags?`)) return;
    try {
        const response = await fetch(`/api/plcs/${id}`, { method: 'DELETE' });
        if (response.ok) {
            showToast(`PLC "${name}" deleted`, 'success');
            await loadPLCs();
            await loadTags();
            await initTrends();
        } else {
            showToast('Delete error', 'error');
        }
    } catch (error) {
        showToast('Network error', 'error');
    }
}

async function browsePLC() {
    if (!selectedPlcId) { showToast('Please select a PLC first', 'error'); return; }

    document.getElementById('browseModal').classList.add('active');
    document.getElementById('browseContent').innerHTML = `
        <div style="text-align: center; padding: 2rem; color: var(--text-muted);">
            <div>⏳ Connecting to PLC...</div>
        </div>`;

    try {
        const response = await fetch(`/api/plcs/${selectedPlcId}/browse`);
        if (!response.ok) {
            const error = await response.json();
            document.getElementById('browseContent').innerHTML = `
                <div style="text-align: center; padding: 2rem; color: var(--danger);">
                    ❌ ${error.detail || 'Browse failed'}
                </div>`;
            return;
        }
        renderBrowseResults(await response.json());
    } catch (error) {
        document.getElementById('browseContent').innerHTML = `
            <div style="text-align: center; padding: 2rem; color: var(--danger);">
                ❌ Network error: ${error.message}
            </div>`;
    }
}

function renderBrowseResults(data) {
    let html = `
        <div style="margin-bottom: 1rem;">
            <strong>${data.plc_name}</strong> - Connected ✅
            <span style="color: var(--text-muted); font-size: 0.85rem; margin-left: 0.5rem;">
                (${data.plc_type === 'allen_bradley' ? 'Allen-Bradley' : 'Siemens S7'})
            </span>
        </div>`;

    if (data.plc_type === 'allen_bradley' && data.tags && data.tags.length > 0) {
        html += `
            <div style="margin-bottom: 0.5rem; display: flex; justify-content: space-between; align-items: center;">
                <div style="font-weight: 500;">Tags (${data.tag_count})</div>
                <input type="text" id="browseTagFilter" placeholder="Filter tags..."
                       style="padding: 0.25rem 0.5rem; border-radius: 4px; border: 1px solid var(--border);
                              background: var(--bg-card); color: var(--text); font-size: 0.85rem; width: 150px;"
                       oninput="filterBrowseTags()">
            </div>
            <div id="browseTagList" style="display: flex; flex-direction: column; gap: 0.25rem; max-height: 300px; overflow-y: auto;">`;

        for (const tag of data.tags) {
            const dimStr = tag.dim > 0 ? `[${tag.dimensions ? tag.dimensions.join('][') : tag.dim}]` : '';
            html += `
                <div class="browse-tag-item" data-name="${tag.tag_name.toLowerCase()}"
                     style="display: flex; justify-content: space-between; align-items: center;
                            padding: 0.5rem; background: var(--bg-card); border-radius: 6px; font-size: 0.85rem;">
                    <div style="overflow: hidden;">
                        <div style="font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;"
                             title="${tag.tag_name}">${tag.tag_name}${dimStr}</div>
                        <div style="font-size: 0.75rem; color: var(--text-muted);">${tag.data_type_name || tag.data_type}</div>
                    </div>
                    <button class="btn btn-primary" style="padding: 0.25rem 0.5rem; font-size: 0.75rem; flex-shrink: 0;"
                            onclick="addABTagFromBrowse('${tag.tag_name.replace(/'/g, "\\'")}')">+ Add</button>
                </div>`;
        }
        html += `</div>`;
        window.browseTagsData = data.tags;

    } else if (data.blocks) {
        html += `
            <div style="margin-bottom: 1rem; padding: 0.75rem; background: var(--bg-card); border-radius: 8px;">
                <div style="font-weight: 500; margin-bottom: 0.5rem;">Block Summary</div>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem; font-size: 0.85rem;">
                    <div>OB: ${data.blocks.OB}</div>
                    <div>FB: ${data.blocks.FB}</div>
                    <div>FC: ${data.blocks.FC}</div>
                    <div>DB: ${data.blocks.DB}</div>
                </div>
            </div>`;

        if (data.data_blocks && data.data_blocks.length > 0) {
            html += `
                <div style="margin-bottom: 1rem;">
                    <div style="font-weight: 500; margin-bottom: 0.5rem;">Data Blocks</div>
                    <div style="display: flex; flex-direction: column; gap: 0.25rem;">`;
            for (const db of data.data_blocks) {
                html += `
                    <div style="display: flex; justify-content: space-between; align-items: center;
                                padding: 0.5rem; background: var(--bg-card); border-radius: 6px; font-size: 0.85rem;">
                        <span><strong>DB${db.db_number}</strong> - ${db.size} bytes</span>
                        <button class="btn btn-primary" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;"
                                onclick="addTagFromBrowse('DB', ${db.db_number})">+ Add Tag</button>
                    </div>`;
            }
            html += `</div></div>`;
        }

        if (data.memory_areas && data.memory_areas.length > 0) {
            const areaNames = { I: 'Inputs', Q: 'Outputs', M: 'Markers', T: 'Timers', C: 'Counters' };
            html += `
                <div style="margin-bottom: 1rem;">
                    <div style="font-weight: 500; margin-bottom: 0.5rem;">Memory Areas</div>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">`;
            for (const area of data.memory_areas) {
                html += `
                    <button class="btn btn-secondary" style="padding: 0.5rem 1rem; font-size: 0.85rem;"
                            onclick="addTagFromBrowse('${area}', null)">
                        ${area} (${areaNames[area]})
                    </button>`;
            }
            html += `</div></div>`;
        }
    }

    document.getElementById('browseContent').innerHTML = html;
}

function filterBrowseTags() {
    const filter = document.getElementById('browseTagFilter').value.toLowerCase();
    document.querySelectorAll('.browse-tag-item').forEach(item => {
        item.style.display = item.dataset.name.includes(filter) ? 'flex' : 'none';
    });
}

function addABTagFromBrowse(tagName) {
    closeBrowseModal();
    openModal();
    document.getElementById('tagABName').value = tagName;
    document.getElementById('tagName').value = tagName.split('.').pop();
}

function addTagFromBrowse(memoryArea, dbNumber) {
    closeBrowseModal();
    openModal();
    document.getElementById('tagMemoryArea').value = memoryArea;
    updateMemoryAreaUI();
    if (dbNumber !== null) document.getElementById('tagDbNumber').value = dbNumber;
}

function closeBrowseModal() {
    document.getElementById('browseModal').classList.remove('active');
}

async function archivePLC(id, name) {
    if (!confirm(`Убрать ПЛК "${name}" в архив?\nОпрос будет остановлен, теги скрыты из основного вида.`)) return;
    try {
        const response = await fetch(`/api/plcs/${id}/archive`, { method: 'PUT' });
        if (response.ok) {
            if (selectedPlcId === id) {
                selectedPlcId = null;
                selectedTagId = null;
            }
            showToast(`ПЛК "${name}" убран в архив`, 'success');
            await loadPLCs();
            await loadTags();
            await initTrends();
        } else {
            showToast('Ошибка архивирования', 'error');
        }
    } catch (error) {
        showToast('Network error', 'error');
    }
}

async function unarchivePLC(id, name) {
    try {
        const response = await fetch(`/api/plcs/${id}/unarchive`, { method: 'PUT' });
        if (response.ok) {
            showToast(`ПЛК "${name}" восстановлен из архива`, 'success');
            await loadPLCs();
            await loadTags();
            await initTrends();
        } else {
            showToast('Ошибка восстановления', 'error');
        }
    } catch (error) {
        showToast('Network error', 'error');
    }
}
