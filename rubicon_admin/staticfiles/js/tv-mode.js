/**
 * Режим ТВ: крупные шрифты, без верхнего меню, на весь экран.
 * Состояние сохраняется в localStorage.
 */
(function () {
    'use strict';

    const STORAGE_KEY = 'rubicon_tv_mode';
    const root = document.documentElement;

    function isTvMode() {
        return root.classList.contains('tv-mode');
    }

    function getFullscreenTarget() {
        const page = document.body.dataset.page;
        if (page === 'dashboard') {
            return document.getElementById('dashboardShell');
        }
        if (page === 'map') {
            return document.querySelector('.map-container') || document.documentElement;
        }
        if (page === 'schedule') {
            return document.getElementById('scheduleShell');
        }
        if (page === 'operators') {
            return document.getElementById('operatorsShell');
        }
        return null;
    }

    function enterFullscreen() {
        if (document.body.dataset.page === 'operators') {
            return;
        }
        const el = getFullscreenTarget();
        if (!el) return;
        const req = el.requestFullscreen || el.webkitRequestFullscreen;
        if (req && !document.fullscreenElement) {
            Promise.resolve(req.call(el)).catch(function () {});
        }
    }

    function exitFullscreen() {
        if (!document.fullscreenElement) return;
        const exit = document.exitFullscreen || document.webkitExitFullscreen;
        if (exit) {
            Promise.resolve(exit.call(document)).catch(function () {});
        }
    }

    function updateButton(btn) {
        if (!btn) return;
        const on = isTvMode();
        btn.setAttribute('aria-pressed', on ? 'true' : 'false');
        const label = btn.querySelector('.tv-mode-btn__label');
        if (label) {
            label.textContent = on ? 'Обычный экран' : 'Режим ТВ';
        } else {
            btn.textContent = on ? '📺 Обычный' : '📺 ТВ';
        }
        btn.title = on
            ? 'Вернуть обычное отображение'
            : 'Крупный интерфейс для телевизора (скрыть меню, на весь экран)';
    }

    function syncDashboardContentDisplay() {
        if (document.body.dataset.page !== 'dashboard') return;
        const el = document.getElementById('dashboardContent');
        if (!el || el.style.display === 'none') return;
        el.style.display = isTvMode() ? 'grid' : 'block';
    }

    function syncOperatorsTvScroll(enabled) {
        if (document.body.dataset.page !== 'operators') {
            return;
        }
        if (!enabled) {
            if (typeof window.stopOperatorsTvScroll === 'function') {
                window.stopOperatorsTvScroll();
            }
            return;
        }
        if (typeof window.setupOperatorsTvScroll === 'function') {
            window.setupOperatorsTvScroll(true);
        }
    }

    function setTvMode(enabled, options) {
        options = options || {};
        var requestFullscreen = options.fullscreen !== false;

        root.classList.toggle('tv-mode', enabled);
        try {
            localStorage.setItem(STORAGE_KEY, enabled ? '1' : '0');
        } catch (e) {
            /* ignore */
        }
        document.querySelectorAll('.tv-mode-btn').forEach(updateButton);
        syncDashboardContentDisplay();
        if (enabled && requestFullscreen) {
            enterFullscreen();
        } else if (!enabled) {
            exitFullscreen();
        }
        window.dispatchEvent(new CustomEvent('rubicon-tv-mode', { detail: { enabled: enabled } }));
        syncOperatorsTvScroll(enabled);
    }

    function toggleTvMode() {
        setTvMode(!isTvMode(), { fullscreen: true });
    }

    function bindButton(btn) {
        if (!btn || btn.dataset.tvBound === '1') return;
        btn.dataset.tvBound = '1';
        btn.addEventListener('click', toggleTvMode);
        updateButton(btn);
    }

    function init() {
        document.querySelectorAll('.tv-mode-btn').forEach(bindButton);
        let saved = false;
        try {
            saved = localStorage.getItem(STORAGE_KEY) === '1';
        } catch (e) {
            saved = false;
        }
        if (saved) {
            setTvMode(true, { fullscreen: false });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    window.RubiconTvMode = {
        enable: function () { setTvMode(true, { fullscreen: false }); },
        disable: function () { setTvMode(false); },
        toggle: toggleTvMode,
        isActive: isTvMode,
        syncDashboardContentDisplay: syncDashboardContentDisplay,
    };
})();
