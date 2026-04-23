// Escape key: exit fullscreen or close modals
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const container = document.getElementById('chartContainer');
        if (container.classList.contains('fullscreen')) {
            toggleFullscreen();
        } else {
            closeModal();
            cancelPLCForm();
        }
    }
});

// Close modals on overlay click
document.getElementById('modalOverlay').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeModal();
});
document.getElementById('plcFormModal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) cancelPLCForm();
});
document.getElementById('browseModal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeBrowseModal();
});

// Time period selector
document.querySelectorAll('.time-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        selectedMinutes = parseInt(btn.dataset.minutes);
        initTrends();
    });
});

// Boot sequence
document.addEventListener('DOMContentLoaded', async () => {
    loadSavedTheme();
    initChart();
    setTimeout(updateChartColors, 100);

    const isFirstRun = await checkFirstRun();

    if (!isFirstRun) {
        await loadPLCs();

        const hadSavedState = loadVisibleTags();
        if (!hadSavedState) {
            const tags = await fetchTags();
            if (tags) {
                tags.forEach(tag => visibleTagIds.add(tag.id));
                saveVisibleTags();
            }
        }

        await loadTags();
        await initTrends();
    }

    loadStatus();
    setInterval(loadStatus, 1000);
});
