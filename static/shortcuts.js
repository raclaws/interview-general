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
            '<tr><td><kbd>Backspace</kbd></td><td>Go back</td></tr>' +
            '<tr><td><kbd>/</kbd></td><td>Focus search</td></tr>' +
            '<tr><td><kbd>j</kbd> / <kbd>↓</kbd></td><td>Move down</td></tr>' +
            '<tr><td><kbd>k</kbd> / <kbd>↑</kbd></td><td>Move up</td></tr>' +
            '<tr><td><kbd>Shift+J</kbd> / <kbd>Shift+↓</kbd></td><td>Select + move down</td></tr>' +
            '<tr><td><kbd>Shift+K</kbd> / <kbd>Shift+↑</kbd></td><td>Select + move up</td></tr>' +
            '<tr><td><kbd>Ctrl+A</kbd></td><td>Select all rows</td></tr>' +
            '<tr><td><kbd>Enter</kbd></td><td>Open focused row</td></tr>' +
            '<tr><td><kbd>n</kbd></td><td>New item</td></tr>' +
            '<tr><td><kbd>c</kbd></td><td>Open comments (peek)</td></tr>' +
            '<tr><td><kbd>Esc</kbd></td><td>Close / clear selection</td></tr>' +
            '<tr><td><kbd>Ctrl+Z</kbd></td><td>Undo last delete</td></tr>' +
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

    function isEditing(e) {
        var tag = e.target.tagName;
        if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return true;
        if (e.target.isContentEditable) return true;
        return false;
    }

    function isListPage() {
        return !!document.querySelector('[data-sync-table]');
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

    // --- Bulk selection helpers ---

    var shiftAnchor = -1;

    function toggleRowSelect(row) {
        var cb = row.querySelector('.bulk-cb');
        if (!cb) return;
        cb.click();
    }

    function selectRow(row) {
        var cb = row.querySelector('.bulk-cb');
        if (!cb || cb.checked) return;
        cb.click();
    }

    function deselectRow(row) {
        var cb = row.querySelector('.bulk-cb');
        if (!cb || !cb.checked) return;
        cb.click();
    }

    function selectAllRows() {
        var rows = getRows();
        rows.forEach(function(row) {
            var cb = row.querySelector('.bulk-cb');
            if (cb && !cb.checked) cb.click();
        });
    }

    function clearSelection() {
        var rows = getRows();
        var hadSelection = false;
        rows.forEach(function(row) {
            var cb = row.querySelector('.bulk-cb');
            if (cb && cb.checked) {
                hadSelection = true;
                cb.click();
            }
        });
        shiftAnchor = -1;
        return hadSelection;
    }

    function hasSelection() {
        var rows = getRows();
        for (var i = 0; i < rows.length; i++) {
            var cb = rows[i].querySelector('.bulk-cb');
            if (cb && cb.checked) return true;
        }
        return false;
    }

    // --- Main keydown handler ---

    document.addEventListener('keydown', function(e) {
        if (isEditing(e)) return;

        // ? — toggle help
        if (e.key === '?') {
            e.preventDefault();
            toggleOverlay();
            return;
        }

        // Backspace — navigate back
        if (e.key === 'Backspace') {
            e.preventDefault();
            history.back();
            return;
        }

        // Escape — close overlay, or clear selection, or defocus
        if (e.key === 'Escape') {
            if (overlay && overlay.style.display === 'flex') {
                overlay.style.display = 'none';
                e.preventDefault();
                return;
            }
            if (isListPage() && hasSelection()) {
                clearSelection();
                e.preventDefault();
                return;
            }
            return;
        }

        // Ctrl+A — select all (list pages only)
        if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
            if (!isListPage()) return;
            e.preventDefault();
            selectAllRows();
            return;
        }

        // / — focus search (no modifiers)
        if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey) {
            var search = document.querySelector('[data-table-search]');
            if (search) { e.preventDefault(); search.focus(); }
            return;
        }

        // List-page-only shortcuts below
        if (!isListPage()) return;

        // Ctrl+Shift+J / Ctrl+Shift+↓ — select all from anchor to end
        if ((e.key === 'J' || (e.key === 'ArrowDown' && e.shiftKey)) && (e.ctrlKey || e.metaKey) && !e.altKey) {
            e.preventDefault(); e.stopImmediatePropagation();
            var rows = getRows();
            var idx = getFocusedIndex();
            if (idx < 0) idx = 0;
            if (shiftAnchor < 0) shiftAnchor = idx;
            for (var i = shiftAnchor; i < rows.length; i++) selectRow(rows[i]);
            setFocus(rows.length - 1);
            return;
        }

        // Ctrl+Shift+K / Ctrl+Shift+↑ — select all from anchor to start
        if ((e.key === 'K' || (e.key === 'ArrowUp' && e.shiftKey)) && (e.ctrlKey || e.metaKey) && !e.altKey) {
            e.preventDefault(); e.stopImmediatePropagation();
            var rows = getRows();
            var idx = getFocusedIndex();
            if (idx < 0) idx = 0;
            if (shiftAnchor < 0) shiftAnchor = idx;
            for (var i = shiftAnchor; i >= 0; i--) selectRow(rows[i]);
            setFocus(0);
            return;
        }

        // Shift+J / Shift+↓ — extend selection down (anchor-based)
        if ((e.key === 'J' || (e.key === 'ArrowDown' && e.shiftKey)) && !e.ctrlKey && !e.metaKey && !e.altKey) {
            e.preventDefault(); e.stopImmediatePropagation();
            var rows = getRows();
            var idx = getFocusedIndex();
            if (idx < 0) {
                setFocus(0);
                shiftAnchor = 0;
                selectRow(rows[0]);
                return;
            }
            if (shiftAnchor < 0) { shiftAnchor = idx; selectRow(rows[idx]); }
            var next = Math.min(idx + 1, rows.length - 1);
            // Moving away from anchor: select next row
            // Moving back toward anchor: deselect current row
            if ((idx >= shiftAnchor && next > idx) || next === idx) {
                selectRow(rows[next]);
            } else {
                deselectRow(rows[idx]);
            }
            setFocus(next);
            return;
        }

        // Shift+K / Shift+↑ — extend selection up (anchor-based)
        if ((e.key === 'K' || (e.key === 'ArrowUp' && e.shiftKey)) && !e.ctrlKey && !e.metaKey && !e.altKey) {
            e.preventDefault(); e.stopImmediatePropagation();
            var rows = getRows();
            var idx = getFocusedIndex();
            if (idx < 0) {
                var last = rows.length - 1;
                setFocus(last);
                shiftAnchor = last;
                selectRow(rows[last]);
                return;
            }
            if (shiftAnchor < 0) { shiftAnchor = idx; selectRow(rows[idx]); }
            var prev = Math.max(idx - 1, 0);
            // Moving away from anchor: select prev row
            // Moving back toward anchor: deselect current row
            if ((idx <= shiftAnchor && prev < idx) || prev === idx) {
                selectRow(rows[prev]);
            } else {
                deselectRow(rows[idx]);
            }
            setFocus(prev);
            return;
        }

        // j / ↓ — move down (no modifiers)
        if (e.key === 'j' || (e.key === 'ArrowDown' && !e.shiftKey)) {
            if (e.key === 'j' && (e.ctrlKey || e.metaKey || e.altKey)) return;
            e.preventDefault();
            shiftAnchor = -1;
            var idx = getFocusedIndex();
            setFocus(idx + 1);
            return;
        }

        // k / ↑ — move up (no modifiers)
        if (e.key === 'k' || (e.key === 'ArrowUp' && !e.shiftKey)) {
            if (e.key === 'k' && (e.ctrlKey || e.metaKey || e.altKey)) return;
            e.preventDefault();
            shiftAnchor = -1;
            var idx = getFocusedIndex();
            setFocus(idx <= 0 ? 0 : idx - 1);
            return;
        }

        // Enter — navigate to focused row
        if (e.key === 'Enter') {
            var rows = getRows();
            var idx = getFocusedIndex();
            if (idx >= 0 && rows[idx] && rows[idx].dataset.href) {
                e.preventDefault();
                window.location.href = rows[idx].dataset.href;
            }
            return;
        }

        // n — new item
        if (e.key === 'n' && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey) {
            var addBtn = document.querySelector('.sync-add-btn');
            if (addBtn) { e.preventDefault(); window.location.href = addBtn.href; }
            return;
        }

        // c — open comments/peek
        if (e.key === 'c' && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey) {
            var rows = getRows();
            var idx = getFocusedIndex();
            if (idx >= 0 && rows[idx]) {
                var trigger = rows[idx].querySelector('.peek-trigger');
                if (trigger) { e.preventDefault(); trigger.click(); }
            }
            return;
        }

        // x — toggle select on focused row
        if (e.key === 'x' && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey) {
            var rows = getRows();
            var idx = getFocusedIndex();
            if (idx >= 0 && rows[idx]) {
                e.preventDefault();
                toggleRowSelect(rows[idx]);
            }
            return;
        }
    });
})();
