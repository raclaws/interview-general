(function() {
    'use strict';

    function debounce(fn, ms) {
        var timer;
        return function() {
            clearTimeout(timer);
            timer = setTimeout(fn, ms);
        };
    }

    function initTable(container) {
        var tbody = container.querySelector('table.table-clean tbody');
        if (!tbody) return;

        var ctx = {
            container: container,
            tbody: tbody,
            rows: [],
            sortField: null,
            sortDir: null,
            groupField: null
        };

        function refreshRows() {
            ctx.rows = Array.from(tbody.querySelectorAll('tr:not(.empty-row):not(.group-header)'));
        }
        refreshRows();

        var searchInput = container.querySelector('[data-table-search]');
        var filters = Array.from(container.querySelectorAll('[data-table-filter]'));
        var sortSelect = container.querySelector('[data-table-sort]');
        var groupSelect = container.querySelector('[data-table-groupby]');

        function applyAll() {
            filterRows(ctx, searchInput, filters);
            sortRows(ctx);
            groupRows(ctx);
        }

        if (searchInput) {
            searchInput.addEventListener('input', debounce(applyAll, 150));
        }

        filters.forEach(function(sel) {
            sel.addEventListener('change', applyAll);
        });

        if (sortSelect) {
            sortSelect.addEventListener('change', function() {
                var val = sortSelect.value;
                if (!val) {
                    ctx.sortField = null;
                    ctx.sortDir = null;
                } else {
                    var parts = val.split(':');
                    ctx.sortField = parts[0];
                    ctx.sortDir = parts[1] || 'asc';
                }
                applyAll();
            });
        }

        if (groupSelect) {
            groupSelect.addEventListener('change', function() {
                ctx.groupField = groupSelect.value || null;
                applyAll();
            });
        }
    }

    function filterRows(ctx, searchInput, filters) {
        var query = searchInput ? searchInput.value.toLowerCase() : '';

        ctx.rows.forEach(function(row) {
            var matchSearch = !query || (row.dataset.search || '').indexOf(query) !== -1;

            var matchFilters = filters.every(function(sel) {
                var field = sel.dataset.tableFilter;
                var value = sel.value;
                if (!value) return true;
                var rowVal = row.dataset[field] || '';
                if (sel.dataset.filterMode === 'contains') {
                    return rowVal.indexOf(value) !== -1;
                }
                return rowVal === value;
            });

            row.style.display = (matchSearch && matchFilters) ? '' : 'none';
        });
    }

    function sortRows(ctx) {
        if (!ctx.sortField) return;

        var visible = ctx.rows.filter(function(r) { return r.style.display !== 'none'; });
        var field = ctx.sortField;
        var dir = ctx.sortDir === 'desc' ? -1 : 1;

        var sortType = 'string';
        var sortSelect = ctx.container.querySelector('[data-table-sort]');
        if (sortSelect) {
            var opt = sortSelect.querySelector('option[value="' + field + ':' + ctx.sortDir + '"]');
            if (opt && opt.dataset.sortType) sortType = opt.dataset.sortType;
        }

        visible.sort(function(a, b) {
            var av = a.dataset[field] || '';
            var bv = b.dataset[field] || '';
            if (sortType === 'number') {
                return (parseFloat(av) - parseFloat(bv)) * dir;
            }
            if (sortType === 'date') {
                return (new Date(av) - new Date(bv)) * dir;
            }
            return av.localeCompare(bv) * dir;
        });

        visible.forEach(function(row) {
            ctx.tbody.appendChild(row);
        });
    }

    function groupRows(ctx) {
        ctx.tbody.querySelectorAll('.group-header').forEach(function(el) {
            el.remove();
        });

        if (!ctx.groupField) return;

        ctx.tbody.style.opacity = '0.7';

        var visible = ctx.rows.filter(function(r) { return r.style.display !== 'none'; });
        var field = ctx.groupField;
        var groups = {};
        var order = [];

        visible.forEach(function(row) {
            var val = row.dataset[field] || '—';
            if (!groups[val]) {
                groups[val] = [];
                order.push(val);
            }
            groups[val].push(row);
        });

        var colCount = visible.length > 0 ? visible[0].children.length : 1;

        order.forEach(function(label) {
            var headerRow = document.createElement('tr');
            headerRow.className = 'group-header';
            var td = document.createElement('td');
            td.setAttribute('colspan', colCount);
            td.innerHTML = label.replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); }) +
                ' <span class="group-count">(' + groups[label].length + ')</span>';
            headerRow.appendChild(td);

            var firstRow = groups[label][0];
            ctx.tbody.insertBefore(headerRow, firstRow);
        });

        requestAnimationFrame(function() {
            ctx.tbody.style.opacity = '';
        });
    }

    document.addEventListener('DOMContentLoaded', function() {
        var containers = document.querySelectorAll('[data-table]');
        containers.forEach(initTable);
    });
})();
