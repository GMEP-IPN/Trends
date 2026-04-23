function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.className = 'toast ' + type;
    document.getElementById('toastIcon').textContent = type === 'success' ? '✅' : '❌';
    document.getElementById('toastMessage').textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
}

async function loadStatus() {
    try {
        const response = await fetch('/api/status');
        const status = await response.json();

        const versionBadge = document.getElementById('versionBadge');
        if (status.version && versionBadge) versionBadge.textContent = `v${status.version}`;

        const dot = document.getElementById('statusDot');
        const text = document.getElementById('statusText');
        const banner = document.getElementById('connectionBanner');
        const bannerText = document.getElementById('bannerText');

        dot.className = 'status-dot';

        const plcErrors = status.plc_errors || {};
        let errorPLCs = Object.keys(plcErrors);

        if (errorPLCs.length === 0) {
            try {
                const plcResponse = await fetch('/api/plcs');
                if (plcResponse.ok) {
                    const plcs = await plcResponse.json();
                    errorPLCs = plcs.filter(p => p.is_active && p.connection_status === 'disconnected').map(p => p.name);
                }
            } catch (e) { /* ignore */ }
        }

        if (errorPLCs.length > 0) {
            dot.classList.add('disconnected');
            text.textContent = 'Error';
            banner.classList.add('show');
            banner.style.background = 'var(--danger)';
            bannerText.textContent = `🔴 Error: ${errorPLCs.join(', ')}`;
        } else if (status.connection_status === 'connected') {
            text.textContent = 'Connected';
            banner.classList.remove('show');
            banner.style.background = '';
        } else if (status.connection_status === 'disconnected') {
            dot.classList.add('disconnected');
            text.textContent = 'Disconnected';
            banner.classList.add('show');
            banner.style.background = 'var(--danger)';
            bannerText.textContent = '⚠️ No PLC connection';
        } else if (status.connection_status === 'stopped') {
            dot.classList.add('stopped');
            text.textContent = 'Stopped';
            banner.classList.add('show');
            banner.style.background = 'var(--text-muted)';
            bannerText.textContent = '⏸️ Collector stopped';
        } else {
            dot.classList.add('stopped');
            text.textContent = 'Unknown';
        }

        return status;
    } catch (error) {
        console.error('Error loading status:', error);
        document.getElementById('statusDot').className = 'status-dot stopped';
        document.getElementById('statusText').textContent = 'Error';
        return null;
    }
}

async function checkFirstRun() {
    try {
        const response = await fetch('/api/plcs');
        const plcs = await response.json();
        if (plcs.length === 0) {
            document.getElementById('welcomeScreen').style.display = 'flex';
            return true;
        }
        return false;
    } catch (error) {
        console.error('Error checking PLCs:', error);
        return false;
    }
}

function startSetup() {
    document.getElementById('welcomeScreen').style.display = 'none';
    showPLCForm();
}
