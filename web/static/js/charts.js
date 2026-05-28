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

function findClosestPoint(data, targetTime) {
    if (!data || data.length === 0) return null;
    
    let low = 0;
    let high = data.length - 1;
    
    while (low < high) {
        const mid = Math.floor((low + high) / 2);
        if (data[mid][0] < targetTime) {
            low = mid + 1;
        } else {
            high = mid;
        }
    }
    
    let closestIdx = low;
    let minDiff = Math.abs(data[low][0] - targetTime);
    
    if (low > 0) {
        const diffPrev = Math.abs(data[low - 1][0] - targetTime);
        if (diffPrev < minDiff) {
            closestIdx = low - 1;
            minDiff = diffPrev;
        }
    }
    
    return {
        point: data[closestIdx],
        diff: minDiff
    };
}

function getChartOption(seriesData = [], yLocked = false) {
    const cs = getComputedStyle(document.documentElement);
    const textPrimary = cs.getPropertyValue('--text-primary').trim() || '#e4e4e7';
    const textSecondary = cs.getPropertyValue('--text-secondary').trim() || '#8b8fa8';
    const border = cs.getPropertyValue('--border').trim() || '#2e3047';
    const bgCard = cs.getPropertyValue('--bg-card').trim() || '#242435';

    // Build dataZoom components based on lock state
    const dataZoom = [
        {
            type: 'inside',
            zoomOnMouseWheel: true,
            moveOnMouseMove: true,
            moveOnMouseWheel: false,
            preventDefaultMouseMove: true,
            xAxisIndex: [0]
        },
        {
            type: 'slider',
            show: true,
            bottom: '10px',
            height: 24,
            textStyle: {
                color: textSecondary,
                fontFamily: 'JetBrains Mono'
            },
            borderColor: border,
            backgroundColor: 'rgba(0,0,0,0.1)',
            dataBackground: {
                lineStyle: { color: border },
                areaStyle: { color: 'rgba(0,0,0,0.05)' }
            },
            selectedDataBackground: {
                lineStyle: { color: '#8b5cf6' },
                areaStyle: { color: 'rgba(139, 92, 246, 0.1)' }
            },
            handleIcon: 'path://M10.7,11.9v-1.3H9.3v1.3c-4.9,0.3-8.8,4.4-8.8,9.4c0,5,3.9,9.1,8.8,9.4v1.3h1.3v-1.3c4.9-0.3,8.8-4.4,8.8-9.4C19.5,16.3,15.6,12.2,10.7,11.9z M13.3,24.4H6.7V23h6.6V24.4z M13.3,19.6H6.7v-1.4h6.6V19.6z',
            handleSize: '100%',
            handleStyle: {
                color: '#fff',
                shadowBlur: 3,
                shadowColor: 'rgba(0, 0, 0, 0.6)',
                shadowOffsetX: 2,
                shadowOffsetY: 2
            },
            xAxisIndex: [0]
        }
    ];

    // If Y axis zoom is unlocked, add Y inside zoom
    if (!yLocked) {
        dataZoom.push({
            type: 'inside',
            yAxisIndex: [0],
            zoomOnMouseWheel: true,
            moveOnMouseMove: true
        });
    }

    return {
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            backgroundColor: bgCard,
            borderColor: border,
            borderWidth: 1,
            textStyle: {
                color: textPrimary,
                fontFamily: 'JetBrains Mono, Courier New, monospace',
                fontSize: 12
            },
            axisPointer: {
                type: 'line',
                lineStyle: {
                    color: '#8b5cf6',
                    width: 1.5,
                    type: 'dashed'
                }
            },
            formatter: function (params) {
                if (!params || params.length === 0) return '';
                const hoveredTime = params[0].value[0];
                const date = new Date(hoveredTime);
                const timeStr = date.toLocaleTimeString([], { hour12: false, fractionSecondDigits: 3 });
                const dateStr = date.toLocaleDateString();
                let html = `<div style="font-weight: bold; margin-bottom: 4px; border-bottom: 1px solid ${border}; padding-bottom: 4px;">📅 ${dateStr} ${timeStr}</div>`;
                
                // Get all series currently rendered in the chart
                const allSeries = chart ? chart.getOption().series : [];
                
                // If chart is not fully initialized, fall back to current parameters
                if (allSeries.length === 0) {
                    params.forEach(item => {
                        const val = item.value[1];
                        html += `
                            <div style="display: flex; justify-content: space-between; gap: 24px; align-items: center; margin-top: 2px;">
                                <span>
                                    <span style="display:inline-block; margin-right:6px; border-radius:50%; width:8px; height:8px; background-color:${item.color};"></span>
                                    ${item.seriesName}
                                </span>
                                <span style="font-family: JetBrains Mono; font-weight: bold; color: ${item.color}">${typeof val === 'number' ? val.toFixed(2) : val}</span>
                            </div>
                        `;
                    });
                    return html;
                }

                allSeries.forEach(s => {
                    const result = findClosestPoint(s.data, hoveredTime);
                    if (result) {
                        const val = result.point[1];
                        const paramItem = params.find(p => p.seriesId === s.id || p.seriesName === s.name);
                        
                        // Find matching color from series configurations
                        let color = '#fff';
                        if (paramItem) {
                            color = paramItem.color;
                        } else if (s.lineStyle && s.lineStyle.color) {
                            color = s.lineStyle.color;
                        } else if (s.itemStyle && s.itemStyle.color) {
                            color = s.itemStyle.color;
                        }
                        
                        // Only show if the closest data point is within 30 seconds to filter out dead/removed tags
                        if (result.diff < 30000) {
                            html += `
                                <div style="display: flex; justify-content: space-between; gap: 24px; align-items: center; margin-top: 2px;">
                                    <span>
                                        <span style="display:inline-block; margin-right:6px; border-radius:50%; width:8px; height:8px; background-color:${color};"></span>
                                        ${s.name}
                                    </span>
                                    <span style="font-family: JetBrains Mono; font-weight: bold; color: ${color}">${typeof val === 'number' ? val.toFixed(2) : val}</span>
                                </div>
                            `;
                        }
                    }
                });
                return html;
            }
        },
        legend: {
            textStyle: {
                color: textPrimary,
                fontFamily: 'Inter, system-ui, sans-serif',
                fontSize: 12
            },
            icon: 'circle',
            padding: [0, 0, 15, 0]
        },
        grid: {
            left: '20px',
            right: '20px',
            bottom: '60px',
            top: '40px',
            containLabel: true
        },
        toolbox: {
            show: true,
            iconStyle: {
                borderColor: textSecondary
            },
            emphasis: {
                iconStyle: {
                    borderColor: '#8b5cf6'
                }
            },
            feature: {
                dataView: { 
                    show: true, 
                    readOnly: true, 
                    title: 'Таблица',
                    lang: ['Просмотр данных', 'Закрыть', 'Обновить'],
                    backgroundColor: bgCard,
                    textColor: textPrimary,
                    buttonColor: '#8b5cf6',
                    buttonTextColor: '#fff'
                },
                saveAsImage: { show: true, title: 'Экспорт PNG' }
            },
            right: '20px',
            top: '0px'
        },
        xAxis: {
            type: 'time',
            splitLine: {
                show: true,
                lineStyle: { color: border, type: 'dashed' }
            },
            axisLine: {
                lineStyle: { color: border }
            },
            axisTick: {
                lineStyle: { color: border }
            },
            axisLabel: {
                color: textSecondary,
                fontFamily: 'JetBrains Mono',
                formatter: function (value) {
                    const date = new Date(value);
                    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
                }
            }
        },
        yAxis: {
            type: 'value',
            scale: true,
            splitLine: {
                show: true,
                lineStyle: { color: border, type: 'dashed' }
            },
            axisLine: {
                show: true,
                lineStyle: { color: border }
            },
            axisLabel: {
                color: textSecondary,
                fontFamily: 'JetBrains Mono'
            }
        },
        dataZoom: dataZoom,
        series: seriesData
    };
}

function initChart() {
    const container = document.getElementById('trendChart');
    if (!container) return;
    
    chart = echarts.init(container);
    
    // Set initial configuration
    const option = getChartOption([], yAxisLocked);
    chart.setOption(option);
    
    // Listen to datazoom events to fetch more history when scrolling left
    chart.on('datazoom', onChartNavigate);
    
    // Resize chart automatically when container size changes
    window.addEventListener('resize', () => {
        if (chart) chart.resize();
    });
}

function resetZoom() {
    if (chart) {
        chart.setOption({
            dataZoom: [
                { start: 0, end: 100 },
                { start: 0, end: 100 }
            ]
        });
    }
}

function toggleYLock() {
    yAxisLocked = !yAxisLocked;
    
    const btn = document.getElementById('yLockBtn');
    if (btn) {
        btn.classList.toggle('active', yAxisLocked);
        btn.title = yAxisLocked ? 'Y locked (click to unlock)' : 'Lock Y axis';
    }

    updateChartOptions();
}

function toggleFullscreen() {
    const container = document.getElementById('chartContainer');
    const btn = document.getElementById('fullscreenBtn');
    if (!container || !btn) return;
    
    container.classList.toggle('fullscreen');
    if (container.classList.contains('fullscreen')) {
        btn.textContent = '✕';
        btn.title = 'Exit fullscreen';
    } else {
        btn.textContent = '⛶';
        btn.title = 'Fullscreen';
    }
    setTimeout(() => {
        if (chart) chart.resize();
    }, 100);
}

function toggleTheme() {
    const html = document.documentElement;
    const icon = document.getElementById('themeIcon');
    if (!html || !icon) return;

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
    updateChartOptions();
}

function updateChartOptions() {
    if (!chart) return;
    const option = chart.getOption();
    const currentSeries = option.series || [];
    const newOption = getChartOption(currentSeries, yAxisLocked);
    chart.setOption(newOption, { notMerge: true });
}

function loadSavedTheme() {
    const savedTheme = localStorage.getItem('theme');
    const icon = document.getElementById('themeIcon');
    if (savedTheme === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
        if (icon) icon.textContent = '☀️';
    }
}

function onChartNavigate() {
    if (isFetchingHistory || !loadedFrom || !chart) return;
    
    const option = chart.getOption();
    if (!option.dataZoom || option.dataZoom.length === 0) return;
    
    const dz = option.dataZoom[0];
    const startValue = dz.startValue;
    const endValue = dz.endValue;
    
    if (startValue && endValue) {
        const visibleRange = endValue - startValue;
        // Fetch more historical data if the user pans within 30% of the loaded left boundary
        if (startValue - loadedFrom.getTime() < visibleRange * 0.3) {
            fetchMoreHistory();
        }
    }
}

async function fetchMoreHistory() {
    if (isFetchingHistory || !loadedFrom || !chart) return;
    const option = chart.getOption();
    if (!option.series || option.series.length === 0) return;
    
    isFetchingHistory = true;

    const chunkMs = selectedMinutes * 60 * 1000;
    const toTime = loadedFrom;
    const fromTime = new Date(toTime.getTime() - chunkMs);

    try {
        const base = selectedPlcId ? `/api/trends?plc_id=${selectedPlcId}&` : '/api/trends?';
        const url = `${base}from_time=${fromTime.getTime()}&to_time=${toTime.getTime()}`;
        const resp = await fetch(url);
        if (!resp.ok) return;
        const trends = await resp.json();

        let anyData = false;
        const series = option.series;
        
        trends.forEach(trend => {
            const s = series.find(d => d.tagId === trend.tag_id);
            if (s && trend.data.length > 0) {
                const newPoints = trend.data.map(p => [new Date(p.timestamp).getTime(), p.value]);
                s.data = [...newPoints, ...s.data];
                anyData = true;
            }
        });

        if (anyData) {
            loadedFrom = fromTime;
            
            // Capture current zoom range (absolute values) to prevent viewport jumps
            const startValue = option.dataZoom[0].startValue;
            const endValue = option.dataZoom[0].endValue;
            
            chart.setOption({ 
                series: series,
                dataZoom: [
                    { startValue: startValue, endValue: endValue },
                    { startValue: startValue, endValue: endValue }
                ]
            });
        } else {
            // No more data available, stop polling
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
        
        const seriesData = visibleTrends.map((trend) => {
            const originalIndex = trends.findIndex(t => t.tag_id === trend.tag_id);
            const color = chartColors[originalIndex % chartColors.length];
            return {
                name: trend.tag_name,
                tagId: trend.tag_id,
                type: 'line',
                symbol: 'none',
                sampling: 'lttb',
                lineStyle: {
                    width: 2,
                    color: color.border
                },
                itemStyle: {
                    color: color.border
                },
                data: trend.data.map(point => [new Date(point.timestamp).getTime(), point.value])
            };
        });

        const option = getChartOption(seriesData, yAxisLocked);
        chart.setOption(option, { notMerge: true });

        // Focus zoom window on the last loaded range
        const now = Date.now();
        const startValue = now - selectedMinutes * 60 * 1000;
        chart.setOption({
            dataZoom: [
                { startValue: startValue, endValue: now },
                { startValue: startValue, endValue: now }
            ]
        });

        const visibleCount = visibleTrends.length;
        const totalCount = trends.length;
        const titleEl = document.getElementById('chartTitle');
        if (titleEl) {
            titleEl.textContent = totalCount > 0 ? `Trends (${visibleCount}/${totalCount} tags)` : 'No data';
        }
    } catch (error) {
        console.error('Error loading trend data:', error);
    }
}

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
    const option = chart.getOption();
    const series = option.series || [];
    if (series.length === 0) return;
    
    const cutoffTime = Date.now() - selectedMinutes * 60 * 1000;
    let updated = false;

    series.forEach((s) => {
        const tag = tags.find(t => t.id === s.tagId || t.name === s.name);
        if (tag && tag.latest_value !== null && tag.latest_time) {
            const newTime = new Date(tag.latest_time).getTime();
            const newVal = tag.latest_value;
            const currentData = s.data || [];
            
            if (currentData.length > 0) {
                const lastPoint = currentData[currentData.length - 1];
                if (newTime > lastPoint[0]) {
                    currentData.push([newTime, newVal]);
                    s.data = currentData.filter(point => point[0] >= cutoffTime);
                    updated = true;
                }
            } else {
                currentData.push([newTime, newVal]);
                s.data = currentData;
                updated = true;
            }
        }
    });

    if (updated) {
        chart.setOption({ series: series });
    }
}
