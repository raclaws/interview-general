(function() {
    'use strict';

    var overlay = null;

    function createOverlay() {
        var el = document.createElement('div');
        el.className = 'shortcuts-overlay';
        el.innerHTML = '<div class="shortcuts-overlay-card">' +
            '<h3>Keyboard Shortcuts</h3>' +
            '<table>' +
            '<tr><td><kbd>?</kbd></td><td>Show/hide this help</td></tr>' +
            '<tr><td><kbd>/</kbd></td><td>Focus search</td></tr>' +
            '<tr><td><kbd>j</kbd> / <kbd>↓</kbd></td><td>Move down</td></tr>' +
            '<tr><td><kbd>k</kbd> / <kbd>↑</kbd></td><td>Move up</td></tr>' +
            '<tr><td><kbd>Enter</kbd></td><td>Open focused row</td></tr>' +
            '<tr><td><kbd>n</kbd></td><td>New item</td></tr>' +
            '<tr><td><kbd>c</kbd></td><td>Open comments (peek)</td></tr>' +
            '<tr><td><kbd>Esc</kbd></td><td>Close panel / overlay</td></tr>' +
            '</table>' +
            '<p class="hint">Press <kbd>?</kbd> or <kbd>Esc</kbd> to close</p>' +
            '</div>';
        el.addEventListener('click', function(e) {
            if (e.target === el) toggleOverlay();
        });
        document.body.appendChild(el);
        return el;
    }

    function toggleOverlay() {
        if (!overlay) overlay = createOverlay();
        overlay.style.display = overlay.style.display === 'flex' ? 'none' : 'flex';
    }

    function getRows() {
        var tbody = document.querySelector('[data-sync-table] tbody');
        if (!tbody) return [];
        return Array.from(tbody.querySelectorAll('tr.clickable-row'));
    }

    function getFocusedIndex() {
        var rows = getRows();
        for (var i = 0; i < rows.length; i++) {
            if (rows[i].classList.contains('row-focused')) return i;
        }
        return -1;
    }

    function setFocus(index) {
        var rows = getRows();
        if (!rows.length) return;
        rows.forEach(function(r) { r.classList.remove('row-focused'); });
        var i = Math.max(0, Math.min(index, rows.length - 1));
        rows[i].classList.add('row-focused');
        rows[i].scrollIntoView({ block: 'nearest' });
    }

    document.addEventListener('keydown', function(e) {
        if (['INPUT', 'SELECT', 'TEXTAREA'].indexOf(e.target.tagName) !== -1) return;

        if (e.key === '?') {
            e.preventDefault();
            toggleOverlay();
            return;
        }

        if (e.key === 'Escape') {
            if (overlay && overlay.style.display === 'flex') {
                overlay.style.display = 'none';
                e.preventDefault();
                return;
            }
            var panel = document.getElementById('peek-panel');
            if (panel && panel.classList.contains('peek-open')) {
                panel.classList.remove('peek-open');
                e.preventDefault();
                return;
            }
        }

        if (e.key === '/') {
            var search = document.querySelector('[data-table-search]');
            if (search) { e.preventDefault(); search.focus(); }
            return;
        }

        if (e.key === 'j' || e.key === 'ArrowDown') {
            e.preventDefault();
            var idx = getFocusedIndex();
            setFocus(idx + 1);
            return;
        }

        if (e.key === 'k' || e.key === 'ArrowUp') {
            e.preventDefault();
            var idx = getFocusedIndex();
            setFocus(idx <= 0 ? 0 : idx - 1);
            return;
        }

        if (e.key === 'Enter') {
            var rows = getRows();
            var idx = getFocusedIndex();
            if (idx >= 0 && rows[idx] && rows[idx].dataset.href) {
                e.preventDefault();
                window.location.href = rows[idx].dataset.href;
            }
            return;
        }

        if (e.key === 'n' && !e.ctrlKey && !e.metaKey) {
            var addBtn = document.querySelector('.sync-add-btn');
            if (addBtn) { e.preventDefault(); window.location.href = addBtn.href; }
            return;
        }

        if (e.key === 'c' && !e.ctrlKey && !e.metaKey) {
            var rows = getRows();
            var idx = getFocusedIndex();
            if (idx >= 0 && rows[idx]) {
                var trigger = rows[idx].querySelector('.peek-trigger');
                if (trigger) { e.preventDefault(); trigger.click(); }
            }
            return;
        }
    });
})();
