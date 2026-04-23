function tagsUrl() {
    return selectedPlcId ? `/api/tags?plc_id=${selectedPlcId}` : '/api/tags';
}

async function fetchTags() {
    const r = await fetch(tagsUrl());
    if (!r.ok) return null;
    return r.json();
}
