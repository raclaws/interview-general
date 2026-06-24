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
            '<tr><td><kbd>Enter</kbd></td><td>Open focused item</td></tr>' +
            '<tr><td><kbd>c</kbd></td><td>Create new item</td></tr>' +
            '<tr><td><kbd>e</kbd></td><td>Edit focused item</td></tr>' +
            '<tr><td><kbd>Delete</kbd></td><td>Delete focused item</td></tr>' +
            '<tr><td><kbd>Esc</kbd></td><td>Close / go back</td></tr>' +
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

    function getFocusedRow() {
        return document.querySelector('.row-focused');
    }

    document.addEventListener('keydown', function(e) {
        if (['INPUT', 'SELECT', 'TEXTAREA'].indexOf(e.target.tagName) !== -1) return;

        // ? — toggle help
        if (e.key === '?') {
            e.preventDefault();
            toggleOverlay();
            return;
        }

        // Escape — close overlay first
        if (e.key === 'Escape') {
            if (overlay && overlay.style.display === 'flex') {
                overlay.style.display = 'none';
                e.preventDefault();
                return;
            }
        }

        // c — create new item (not with Ctrl/Meta — that's copy)
        if (e.key === 'c' && !e.ctrlKey && !e.metaKey) {
            var container = document.querySelector('[data-shortcut-new]');
            if (container) {
                e.preventDefault();
                window.location.href = container.dataset.shortcutNew;
            }
            return;
        }

        // x — toggle selection on focused row
        if (e.key === 'x') {
            var row = getFocusedRow();
            if (row) {
                var tableContainer = row.closest('[data-table]');
                if (tableContainer && tableContainer._toggleRowSelection) {
                    e.preventDefault();
                    tableContainer._toggleRowSelection(row);
                }
            }
            return;
        }

        // e — edit focused row
        if (e.key === 'e') {
            var row = getFocusedRow();
            if (row && row.dataset.href) {
                e.preventDefault();
                window.location.href = row.dataset.href + '/edit';
            }
            return;
        }

        // Delete/Backspace — delete focused row
        if (e.key === 'Delete' || e.key === 'Backspace') {
            var row = getFocusedRow();
            if (!row) return;
            var ctx = row.dataset.ctx;
            if (!ctx) return;
            try {
                var items = JSON.parse(ctx);
                var deleteItem = items.find(function(it) { return it.delete; });
                if (deleteItem && confirm(deleteItem.confirm || 'Delete this item?')) {
                    e.preventDefault();
                    var form = document.createElement('form');
                    form.method = 'POST';
                    form.action = deleteItem.href;
                    form.style.display = 'none';
                    form.setAttribute('hx-post', deleteItem.href);
                    form.setAttribute('hx-swap', 'none');
                    form.setAttribute('data-ctx-delete', '');
                    document.body.appendChild(form);
                    if (window.htmx) {
                        htmx.process(form);
                        htmx.trigger(form, 'submit');
                    } else {
                        form.submit();
                    }
                }
            } catch(err) {}
            return;
        }
    });
})();
