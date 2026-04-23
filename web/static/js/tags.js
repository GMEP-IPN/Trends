function saveVisibleTags() {
    localStorage.setItem('visibleTagIds', JSON.stringify([...visibleTagIds]));
}

function loadVisibleTags() {
    const saved = localStorage.getItem('visibleTagIds');
    if (saved) {
        try {
            visibleTagIds = new Set(JSON.parse(saved));
            return true;
        } catch (e) {
            console.error('Error loading saved tags:', e);
        }
    }
    return false;
}

function formatTagAddress(tag) {
    if (tag.ab_tag_name) return tag.ab_tag_name;
    const memoryArea = tag.memory_area || 'DB';
    if (memoryArea === 'DB') {
        if (tag.db_number !== null && tag.db_number !== undefined) {
            if (tag.data_type === 'bool') return `DB${tag.db_number}.DBX${tag.start_address}.${tag.bit_number || 0}`;
            return `DB${tag.db_number}.${tag.data_type.toUpperCase()}${tag.start_address}`;
        }
    } else {
        if (tag.start_address !== null && tag.start_address !== undefined) {
            if (tag.data_type === 'bool') return `${memoryArea}${tag.start_address}.${tag.bit_number || 0}`;
            if (memoryArea === 'T' || memoryArea === 'C') return `${memoryArea}${tag.start_address}`;
            const typePrefix = { int: 'W', word: 'W', dint: 'D', dword: 'D', real: 'D' }[tag.data_type] || '';
            return `${memoryArea}${typePrefix}${tag.start_address}`;
        }
    }
    return 'N/A';
}

async function loadTags() {
    try {
        const tags = await fetchTags();
        const tagList = document.getElementById('tagList');
        if (!tagList) return;

        if (!tags || tags.length === 0) {
            tagList.innerHTML = `
                <div style="text-align: center; padding: 2rem; color: var(--text-muted);">
                    <div style="font-size: 2rem; margin-bottom: 0.5rem;">📭</div>
                    <div>No tags</div>
                    <div style="font-size: 0.75rem; margin-top: 0.5rem;">Click + to add</div>
                </div>`;
            return;
        }

        tagList.innerHTML = tags.map((tag, index) => {
            const color = chartColors[index % chartColors.length];
            const isVisible = visibleTagIds.has(tag.id);
            return `
            <div class="tag-item" data-id="${tag.id}">
                <input type="checkbox" class="tag-checkbox"
                       ${isVisible ? 'checked' : ''}
                       onclick="event.stopPropagation(); toggleTagVisibility(${tag.id})"
                       title="Show on chart">
                <span class="tag-color-dot" style="background: ${color.border}; opacity: ${isVisible ? 1 : 0.3}"></span>
                <div class="tag-info" onclick="selectTag(${tag.id}, '${tag.name}')">
                    <div class="tag-name">${tag.name}</div>
                    <div class="tag-meta">${formatTagAddress(tag)}</div>
                </div>
                <div class="tag-value" style="opacity: ${isVisible ? 1 : 0.5}">${tag.latest_value !== null ? tag.latest_value.toFixed(2) : '--'}</div>
                <div class="tag-actions">
                    <button class="tag-action-btn" onclick="event.stopPropagation(); editTag(${tag.id})" title="Edit">✏️</button>
                    <button class="tag-action-btn delete" onclick="deleteTag(event, ${tag.id}, '${tag.name}')" title="Delete">🗑️</button>
                </div>
            </div>`;
        }).join('');

        if (tags.length > 0 && !selectedTagId) selectedTagId = tags[0].id;
    } catch (error) {
        console.error('Error loading tags:', error);
    }
}

async function toggleTagVisibility(tagId) {
    if (visibleTagIds.has(tagId)) {
        visibleTagIds.delete(tagId);
    } else {
        visibleTagIds.add(tagId);
    }
    saveVisibleTags();

    const tagItem = document.querySelector(`.tag-item[data-id="${tagId}"]`);
    if (tagItem) {
        const isVisible = visibleTagIds.has(tagId);
        const checkbox = tagItem.querySelector('.tag-checkbox');
        const colorDot = tagItem.querySelector('.tag-color-dot');
        const valueEl = tagItem.querySelector('.tag-value');
        if (checkbox) checkbox.checked = isVisible;
        if (colorDot) colorDot.style.opacity = isVisible ? 1 : 0.3;
        if (valueEl) valueEl.style.opacity = isVisible ? 1 : 0.5;
    }
    await loadTrendData();
}

async function selectAllTags() {
    const tags = await fetchTags();
    if (tags) {
        tags.forEach(tag => visibleTagIds.add(tag.id));
        saveVisibleTags();
        updateTagCheckboxes();
        await loadTrendData();
    }
}

async function deselectAllTags() {
    visibleTagIds.clear();
    saveVisibleTags();
    updateTagCheckboxes();
    await loadTrendData();
}

function updateTagCheckboxes() {
    document.querySelectorAll('.tag-item').forEach(tagItem => {
        const tagId = parseInt(tagItem.dataset.id);
        const isVisible = visibleTagIds.has(tagId);
        const checkbox = tagItem.querySelector('.tag-checkbox');
        const colorDot = tagItem.querySelector('.tag-color-dot');
        const valueEl = tagItem.querySelector('.tag-value');
        if (checkbox) checkbox.checked = isVisible;
        if (colorDot) colorDot.style.opacity = isVisible ? 1 : 0.3;
        if (valueEl) valueEl.style.opacity = isVisible ? 1 : 0.5;
    });
}

async function selectTag(tagId, tagName) {
    selectedTagId = tagId;
    await loadStatistics();
}

async function initTrends() {
    await loadTrendData();
    await loadStatistics();
    if (updateInterval) clearInterval(updateInterval);
    updateInterval = setInterval(() => {
        loadStatistics();
        refreshLiveData();
    }, 1000);
}

async function loadStatistics() {
    try {
        const tags = await fetchTags();
        if (!tags) return;

        if (tags.length === 0) {
            document.getElementById('statsTableBody').innerHTML = `
                <tr><td colspan="6" style="text-align: center; color: var(--text-muted);">No tags</td></tr>`;
            return;
        }

        const periodText = { 5: '5 min', 15: '15 min', 30: '30 min', 60: '1 hour' };
        document.getElementById('statsPeriod').textContent = `last ${periodText[selectedMinutes] || selectedMinutes + ' min'}`;

        const allStats = await Promise.all(
            tags.map(tag =>
                fetch(`/api/tags/${tag.id}/statistics?minutes=${selectedMinutes}`)
                    .then(r => r.ok ? r.json() : null)
                    .catch(() => null)
            )
        );

        document.getElementById('statsTableBody').innerHTML = tags.map((tag, index) => {
            const stats = allStats[index];
            const color = chartColors[index % chartColors.length];
            return `
                <tr>
                    <td><span class="tag-color" style="background: ${color.border}"></span>${tag.name}</td>
                    <td style="color: var(--accent); font-weight: 600;">${tag.latest_value?.toFixed(2) ?? '--'}</td>
                    <td style="color: var(--accent-secondary);">${stats?.min?.toFixed(2) ?? '--'}</td>
                    <td style="color: var(--warning);">${stats?.max?.toFixed(2) ?? '--'}</td>
                    <td style="color: var(--success);">${stats?.avg?.toFixed(2) ?? '--'}</td>
                    <td style="color: var(--text-muted);">${stats?.count ?? 0}</td>
                </tr>`;
        }).join('');
    } catch (error) {
        console.error('Error loading statistics:', error);
    }
}

function openModal(editMode = false) {
    document.getElementById('modalOverlay').classList.add('active');
    document.getElementById('tagFormTitle').textContent = editMode ? '✏️ Edit Tag' : '➕ Add Tag';
    document.getElementById('tagSubmitBtn').textContent = editMode ? 'Save' : 'Add';
    updateTagFormFields();
    document.getElementById('tagName').focus();
}

function closeModal() {
    document.getElementById('modalOverlay').classList.remove('active');
    document.getElementById('tagForm').reset();
    document.getElementById('tagEditId').value = '';
    document.getElementById('tagFormTitle').textContent = '➕ Add Tag';
    document.getElementById('tagSubmitBtn').textContent = 'Add';
    document.getElementById('bitNumberGroup').style.display = 'none';
    document.getElementById('tagMemoryArea').value = 'DB';
    updateMemoryAreaUI();
}

function updateMemoryAreaUI() {
    const memoryArea = document.getElementById('tagMemoryArea').value;
    document.getElementById('dbNumberGroup').style.display = memoryArea === 'DB' ? 'block' : 'none';
}

async function editTag(tagId) {
    try {
        const tags = await fetchTags();
        if (!tags) return;
        const tag = tags.find(t => t.id === tagId);
        if (!tag) { showToast('Tag not found', 'error'); return; }

        document.getElementById('tagEditId').value = tag.id;
        document.getElementById('tagName').value = tag.name;
        document.getElementById('tagDescription').value = tag.description || '';
        document.getElementById('tagDataType').value = tag.data_type;
        document.getElementById('tagPollInterval').value = tag.poll_interval_ms;

        const memoryArea = tag.memory_area || 'DB';
        document.getElementById('tagMemoryArea').value = memoryArea;
        updateMemoryAreaUI();

        if (memoryArea === 'DB' && tag.db_number !== null && tag.db_number !== undefined) {
            document.getElementById('tagDbNumber').value = tag.db_number;
        }
        if (tag.start_address !== null && tag.start_address !== undefined) {
            document.getElementById('tagAddress').value = tag.start_address;
        }
        document.getElementById('tagBitNumber').value = tag.bit_number || 0;
        if (tag.ab_tag_name) document.getElementById('tagABName').value = tag.ab_tag_name;

        updateDataSize();
        openModal(true);
    } catch (error) {
        console.error('Error loading tag:', error);
        showToast('Error loading tag', 'error');
    }
}

function updateDataSize() {
    const isBool = document.getElementById('tagDataType').value === 'bool';
    document.getElementById('bitNumberGroup').style.display = isBool ? 'block' : 'none';
    if (!isBool) document.getElementById('tagBitNumber').value = '0';
}

async function submitTag(event) {
    event.preventDefault();
    const editId = document.getElementById('tagEditId').value;
    const isEditMode = !!editId;

    if (!selectedPlcId && !isEditMode) { showToast('Please select a PLC first', 'error'); return; }

    const data = {
        name: document.getElementById('tagName').value,
        description: document.getElementById('tagDescription').value,
        data_type: document.getElementById('tagDataType').value,
        poll_interval_ms: parseInt(document.getElementById('tagPollInterval').value)
    };
    if (!isEditMode) data.plc_id = selectedPlcId;

    if (selectedPlcType === 'allen_bradley') {
        data.ab_tag_name = document.getElementById('tagABName').value;
        if (!data.ab_tag_name && !isEditMode) { showToast('Please enter AB tag name', 'error'); return; }
    } else {
        const memoryArea = document.getElementById('tagMemoryArea').value;
        const dbNumber = document.getElementById('tagDbNumber').value;
        const startAddress = document.getElementById('tagAddress').value;
        data.memory_area = memoryArea;
        if (memoryArea === 'DB' && dbNumber) data.db_number = parseInt(dbNumber);
        if (startAddress !== '') data.start_address = parseInt(startAddress);
        data.bit_number = parseInt(document.getElementById('tagBitNumber').value) || 0;
        if (!isEditMode) {
            if (memoryArea === 'DB' && !data.db_number) { showToast('Please enter DB number', 'error'); return; }
            if (isNaN(data.start_address)) { showToast('Please enter address', 'error'); return; }
        }
    }

    try {
        const url = isEditMode ? `/api/tags/${editId}` : '/api/tags';
        const method = isEditMode ? 'PUT' : 'POST';
        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            const result = await response.json();
            showToast(isEditMode ? `Tag "${data.name}" updated` : `Tag "${result.name}" added`, 'success');
            if (!isEditMode) visibleTagIds.add(result.id);
            closeModal();
            await loadTags();
            await initTrends();
        } else {
            const error = await response.json();
            showToast(error.detail || (isEditMode ? 'Error updating tag' : 'Error creating tag'), 'error');
        }
    } catch (error) {
        showToast('Network error', 'error');
    }
}

async function deleteTag(event, tagId, tagName) {
    event.stopPropagation();
    if (!confirm(`Delete tag "${tagName}"?`)) return;
    try {
        const response = await fetch(`/api/tags/${tagId}`, { method: 'DELETE' });
        if (response.ok) {
            showToast(`Tag "${tagName}" deleted`, 'success');
            if (selectedTagId === tagId) selectedTagId = null;
            await loadTags();
            await initTrends();
        } else {
            showToast('Delete error', 'error');
        }
    } catch (error) {
        showToast('Network error', 'error');
    }
}

async function deleteTagWithRestart(event, tagId, tagName) {
    event.stopPropagation();
    if (!confirm(`Delete tag "${tagName}"?`)) return;
    try {
        const response = await fetch(`/api/tags/${tagId}`, { method: 'DELETE' });
        if (response.ok) {
            showToast(`Tag "${tagName}" deleted`, 'success');
            if (selectedTagId === tagId) selectedTagId = null;
            loadTags();
        } else {
            showToast('Delete error', 'error');
        }
    } catch (error) {
        showToast('Network error', 'error');
    }
}

function updateTagFormFields() {
    const s7TagFields = document.getElementById('s7TagFields');
    const abTagFields = document.getElementById('abTagFields');
    if (selectedPlcType === 'allen_bradley') {
        s7TagFields.style.display = 'none';
        abTagFields.style.display = 'block';
    } else {
        s7TagFields.style.display = 'block';
        abTagFields.style.display = 'none';
    }
}
