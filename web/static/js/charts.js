const chartColors = [
    { border: '#8b5cf6', bg: 'rgba(139, 92, 246, 0.1)' },
    { border: '#06b6d4', bg: 'rgba(6, 182, 212, 0.1)' },
    { border: '#00d4aa', bg: 'rgba(0, 212, 170, 0.1)' },
    { border: '#f59e0b', bg: 'rgba(245, 158, 11, 0.1)' },
    { border: '#ef4444', bg: 'rgba(239, 68, 68, 0.1)' },
    { border: '#22c55e', bg: 'rgba(34, 197, 94, 0.1)' },
    { border: '#3b82f6', bg: 'rgba(59, 130, 246, 0.1)' },
    { border: '#ec4899', bg: 'rgba(236, 72, 153, 0.1)' },
    { border: '#eab308', bg: 'rgba(234, 179, 8, 0.1)' },
    { border: '#f97316', bg: 'rgba(249, 115, 22, 0.1)' },
];

const chartConfig = {
    type: 'line',
    data: { datasets: [] },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' },
        plugins: {
            legend: {
                display: true,
                position: 'top',
                labels: {
                    color: getComputedStyle(document.documentElement).getPropertyValue('--text-primary').trim() || '#e4e4e7',
                    font: { family: 'Inter', size: 12 },
                    usePointStyle: true,
                    pointStyle: 'circle',
                    padding: 20
                }
            },
            tooltip: {
                backgroundColor: '#242435',
                titleColor: '#e2e4f0',
                bodyColor: '#e2e4f0',
                bodyFont: { family: 'JetBrains Mono', size: 12 },
                borderColor: '#2e3047',
                borderWidth: 1,
                padding: 12,
                displayColors: true,
                callbacks: {
                    label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)}`
                }
            },
            zoom: {
                pan: { enabled: true, mode: 'xy', onPanComplete: onChartNavigate },
                zoom: {
                    wheel: { enabled: true },
                    pinch: { enabled: true },
                    mode: 'x',
                    onZoomComplete: onChartNavigate,
                }
            }
        },
        scales: {
            x: {
                type: 'time',
                time: { displayFormats: { minute: 'HH:mm', hour: 'HH:mm' } },
                grid: { color: '#2e3047', drawBorder: false },
                ticks: { color: '#8b8fa8', font: { family: 'JetBrains Mono' } }
            },
            y: {
                grid: { color: '#2e3047', drawBorder: false },
                ticks: { color: '#8b8fa8', font: { family: 'JetBrains Mono' } }
            }
        }
    }
};

function initChart() {
    const ctx = document.getElementById('trendChart').getContext('2d');
    chart = new Chart(ctx, chartConfig);
}

function resetZoom() {
    if (chart) chart.resetZoom();
}

function toggleYLock() {
    yAxisLocked = !yAxisLocked;
    chart.options.plugins.zoom.pan.mode = yAxisLocked ? 'x' : 'xy';
    chart.update('none');

    const btn = document.getElementById('yLockBtn');
    btn.classList.toggle('active', yAxisLocked);
    btn.title = yAxisLocked ? 'Y locked (click to unlock)' : 'Lock Y axis';
}

function toggleFullscreen() {
    const container = document.getElementById('chartContainer');
    const btn = document.getElementById('fullscreenBtn');
    container.classList.toggle('fullscreen');
    if (container.classList.contains('fullscreen')) {
        btn.textContent = '✕';
        btn.title = 'Exit fullscreen';
    } else {
        btn.textContent = '⛶';
        btn.title = 'Fullscreen';
    }
    setTimeout(() => chart.resize(), 100);
}

function toggleTheme() {
    const html = document.documentElement;
    const icon = document.getElementById('themeIcon');
    if (html.getAttribute('data-theme') === 'light') {
        html.removeAttribute('data-theme');
        icon.textContent = '🌙';
        localStorage.setItem('theme', 'dark');
    } else {
        html.setAttribute('data-theme', 'light');
        icon.textContent = '☀️';
        localStorage.setItem('theme', 'light');
    }
    updateChartColors();
}

function updateChartColors() {
    if (!chart) return;
    const cs = getComputedStyle(document.documentElement);
    const textPrimary  = cs.getPropertyValue('--text-primary').trim();
    const textSecondary = cs.getPropertyValue('--text-secondary').trim();
    const border = cs.getPropertyValue('--border').trim();
    const bgCard = cs.getPropertyValue('--bg-card').trim();
    chart.options.scales.x.grid.color = border;
    chart.options.scales.y.grid.color = border;
    chart.options.scales.x.ticks.color = textSecondary;
    chart.options.scales.y.ticks.color = textSecondary;
    chart.options.plugins.legend.labels.color = textPrimary;
    chart.options.plugins.tooltip.backgroundColor = bgCard;
    chart.options.plugins.tooltip.titleColor = textPrimary;
    chart.options.plugins.tooltip.bodyColor = textPrimary;
    chart.options.plugins.tooltip.borderColor = border;
    chart.update('none');
}

function loadSavedTheme() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
        document.getElementById('themeIcon').textContent = '☀️';
    }
}

function onChartNavigate() {
    if (isFetchingHistory || !loadedFrom || !chart) return;
    const xMin = chart.scales.x.min;
    const xMax = chart.scales.x.max;
    const visibleRange = xMax - xMin;
    // Дозагружаем когда левый край экрана приблизился к границе загруженных данных
    if (xMin - loadedFrom.getTime() < visibleRange * 0.5) {
        fetchMoreHistory();
    }
}

async function fetchMoreHistory() {
    if (isFetchingHistory || !loadedFrom || chart.data.datasets.length === 0) return;
    isFetchingHistory = true;

    const chunkMs = selectedMinutes * 60 * 1000;
    const toTime = loadedFrom;
    const fromTime = new Date(toTime.getTime() - chunkMs);

    try {
        const base = selectedPlcId ? `/api/trends?plc_id=${selectedPlcId}` : '/api/trends';
        const url = `${base}&from_time=${fromTime.toISOString()}&to_time=${toTime.toISOString()}`;
        const resp = await fetch(url);
        if (!resp.ok) return;
        const trends = await resp.json();

        let anyData = false;
        trends.forEach(trend => {
            const dataset = chart.data.datasets.find(d => d.tagId === trend.tag_id);
            if (dataset && trend.data.length > 0) {
                const newPoints = trend.data.map(p => ({ x: new Date(p.timestamp), y: p.value }));
                dataset.data = [...newPoints, ...dataset.data];
                anyData = true;
            }
        });

        if (anyData) {
            loadedFrom = fromTime;
            chart.update('none');
        } else {
            // Данных больше нет — дальше не грузим
            loadedFrom = null;
        }
    } finally {
        isFetchingHistory = false;
    }
}

async function loadTrendData() {
    try {
        const url = selectedPlcId
            ? `/api/trends?plc_id=${selectedPlcId}&minutes=${selectedMinutes}`
            : `/api/trends?minutes=${selectedMinutes}`;
        const response = await fetch(url);
        if (!response.ok) return;
        const trends = await response.json();
        tagsData = trends;

        loadedFrom = new Date(Date.now() - selectedMinutes * 60 * 1000);
        isFetchingHistory = false;

        const visibleTrends = trends.filter(t => visibleTagIds.has(t.tag_id));
        chart.data.datasets = visibleTrends.map((trend) => {
            const originalIndex = trends.findIndex(t => t.tag_id === trend.tag_id);
            const color = chartColors[originalIndex % chartColors.length];
            return {
                label: trend.tag_name,
                tagId: trend.tag_id,
                data: trend.data.map(point => ({ x: new Date(point.timestamp), y: point.value })),
                borderColor: color.border,
                backgroundColor: color.bg,
                borderWidth: 2,
                fill: false,
                tension: 0,
                pointRadius: 0,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: color.border,
                pointHoverBorderColor: '#fff',
                pointHoverBorderWidth: 2,
                spanGaps: false
            };
        });
        chart.resetZoom();
        chart.update('none');

        const visibleCount = visibleTrends.length;
        const totalCount = trends.length;
        document.getElementById('chartTitle').textContent =
            totalCount > 0 ? `Trends (${visibleCount}/${totalCount} tags)` : 'No data';
    } catch (error) {
        console.error('Error loading trend data:', error);
    }
}

// Deduplicated live update: one fetch per tick for both chart and sidebar values
async function refreshLiveData() {
    if (!chart) return;
    const tags = await fetchTags();
    if (!tags) return;

    // Update sidebar values
    tags.forEach(tag => {
        const tagItem = document.querySelector(`.tag-item[data-id="${tag.id}"]`);
        if (tagItem) {
            const valueEl = tagItem.querySelector('.tag-value');
            if (valueEl) valueEl.textContent = tag.latest_value !== null ? tag.latest_value.toFixed(2) : '--';
        }
    });

    // Add live points to chart
    if (chart.data.datasets.length === 0) return;
    const cutoffTime = new Date();
    cutoffTime.setMinutes(cutoffTime.getMinutes() - selectedMinutes);

    chart.data.datasets.forEach((dataset) => {
        const tag = tags.find(t => t.id === dataset.tagId || t.name === dataset.label);
        if (tag && tag.latest_value !== null && tag.latest_time) {
            const newPoint = { x: new Date(tag.latest_time), y: tag.latest_value };
            const currentData = dataset.data;
            if (currentData.length > 0) {
                const lastPoint = currentData[currentData.length - 1];
                if (newPoint.x > lastPoint.x) {
                    currentData.push(newPoint);
                    dataset.data = currentData.filter(point => point.x >= cutoffTime);
                }
            }
        }
    });
    chart.update('none');
}
