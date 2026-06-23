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
            groupField: null,
            focusIndex: -1,
            advancedRules: []
        };

        function refreshRows() {
            ctx.rows = Array.from(tbody.querySelectorAll('tr:not(.empty-row):not(.group-header)'));
        }
        refreshRows();

        var searchInput = container.querySelector('[data-table-search]');
        var filters = Array.from(container.querySelectorAll('[data-table-filter]'));
        var sortSelect = container.querySelector('[data-table-sort]');
        var groupSelect = container.querySelector('[data-table-groupby]');
        var controls = container.querySelector('.table-controls');

        // Advanced filter field config
        var fieldsConfig = null;
        if (container.dataset.tableFields) {
            try { fieldsConfig = JSON.parse(container.dataset.tableFields); } catch(e) {}
        }

        // Filter pills container
        var pillsRow = document.createElement('div');
        pillsRow.className = 'filter-pills';
        if (controls) controls.parentNode.insertBefore(pillsRow, controls.nextSibling);

        // "+ Filter" button and popover
        var filterWrap = null;
        if (fieldsConfig && controls) {
            filterWrap = document.createElement('span');
            filterWrap.style.position = 'relative';
            filterWrap.style.display = 'inline-block';

            var addBtn = document.createElement('button');
            addBtn.type = 'button';
            addBtn.className = 'filter-add-btn';
            addBtn.textContent = '+ Filter';
            filterWrap.appendChild(addBtn);

            var popover = document.createElement('div');
            popover.className = 'filter-popover';
            popover.style.display = 'none';

            var fieldSel = document.createElement('select');
            fieldSel.innerHTML = '<option value="">Field</option>' +
                fieldsConfig.map(function(f) { return '<option value="' + f.key + '">' + f.label + '</option>'; }).join('');
            popover.appendChild(fieldSel);

            var opSel = document.createElement('select');
            opSel.innerHTML = '<option value="">Op</option>';
            popover.appendChild(opSel);

            var valInput = document.createElement('input');
            valInput.type = 'text';
            valInput.placeholder = 'Value';
            valInput.style.width = '100px';
            popover.appendChild(valInput);

            var valSel = document.createElement('select');
            valSel.style.display = 'none';
            popover.appendChild(valSel);

            var addRuleBtn = document.createElement('button');
            addRuleBtn.type = 'button';
            addRuleBtn.textContent = 'Add';
            popover.appendChild(addRuleBtn);

            filterWrap.appendChild(popover);
            controls.appendChild(filterWrap);

            var opsForType = {
                'select': [
                    {value: 'is', label: 'is'},
                    {value: 'is_not', label: 'is not'},
                    {value: 'in', label: 'in'}
                ],
                'date': [
                    {value: 'is', label: 'is'},
                    {value: 'gte', label: 'on or after'},
                    {value: 'lte', label: 'on or before'}
                ],
                'text': [
                    {value: 'contains', label: 'contains'},
                    {value: 'not_contains', label: 'does not contain'}
                ]
            };

            fieldSel.addEventListener('change', function() {
                var cfg = fieldsConfig.find(function(f) { return f.key === fieldSel.value; });
                if (!cfg) { opSel.innerHTML = '<option value="">Op</option>'; return; }
                var ops = opsForType[cfg.type] || opsForType['text'];
                opSel.innerHTML = ops.map(function(o) { return '<option value="' + o.value + '">' + o.label + '</option>'; }).join('');
                if (cfg.type === 'select' && cfg.options) {
                    valSel.innerHTML = cfg.options.map(function(o) { return '<option value="' + o + '">' + o.replace(/_/g, ' ') + '</option>'; }).join('');
                    valSel.style.display = '';
                    valInput.style.display = 'none';
                } else {
                    valSel.style.display = 'none';
                    valInput.style.display = '';
                    valInput.type = cfg.type === 'date' ? 'date' : 'text';
                }
            });

            addBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                popover.style.display = popover.style.display === 'none' ? 'flex' : 'none';
            });

            addRuleBtn.addEventListener('click', function() {
                var field = fieldSel.value;
                var op = opSel.value;
                var cfg = fieldsConfig.find(function(f) { return f.key === field; });
                if (!field || !op) return;
                var value = (cfg && cfg.type === 'select' && cfg.options) ? valSel.value : valInput.value;
                if (!value) return;
                ctx.advancedRules.push({field: field, op: op, value: value});
                renderPills();
                syncDropdownFromRules();
                applyAll();
                popover.style.display = 'none';
                fieldSel.value = '';
                opSel.innerHTML = '<option value="">Op</option>';
                valInput.value = '';
            });

            document.addEventListener('click', function(e) {
                if (!filterWrap.contains(e.target)) popover.style.display = 'none';
            });
        }

        function renderPills() {
            pillsRow.innerHTML = '';
            ctx.advancedRules.forEach(function(rule, i) {
                var cfg = fieldsConfig ? fieldsConfig.find(function(f) { return f.key === rule.field; }) : null;
                var label = cfg ? cfg.label : rule.field;
                var opLabel = rule.op.replace(/_/g, ' ');
                var pill = document.createElement('span');
                pill.className = 'filter-pill';
                pill.innerHTML = '<span>' + label + ' ' + opLabel + ' ' + rule.value.replace(/_/g, ' ') + '</span>';
                var closeBtn = document.createElement('button');
                closeBtn.type = 'button';
                closeBtn.textContent = '×';
                closeBtn.addEventListener('click', function() {
                    ctx.advancedRules.splice(i, 1);
                    renderPills();
                    syncDropdownFromRules();
                    applyAll();
                });
                pill.appendChild(closeBtn);
                pillsRow.appendChild(pill);
            });
        }

        function syncDropdownFromRules() {
            filters.forEach(function(sel) {
                var field = sel.dataset.tableFilter;
                var rule = ctx.advancedRules.find(function(r) { return r.field === field && r.op === 'is'; });
                sel.value = rule ? rule.value : '';
            });
        }

        function syncRulesFromDropdown(sel) {
            var field = sel.dataset.tableFilter;
            var value = sel.value;
            var idx = -1;
            ctx.advancedRules.forEach(function(r, i) { if (r.field === field) idx = i; });
            if (value) {
                var rule = {field: field, op: 'is', value: value};
                if (idx >= 0) ctx.advancedRules[idx] = rule;
                else ctx.advancedRules.push(rule);
            } else {
                if (idx >= 0) ctx.advancedRules.splice(idx, 1);
            }
            renderPills();
        }

        // URL param sync
        function syncToURL() {
            var params = new URLSearchParams();
            if (searchInput && searchInput.value) params.set('search', searchInput.value);
            ctx.advancedRules.forEach(function(rule) {
                params.append('af', rule.field + ':' + rule.op + ':' + rule.value);
            });
            if (sortSelect && sortSelect.value) params.set('sort', sortSelect.value);
            if (groupSelect && groupSelect.value) params.set('group', groupSelect.value);
            var qs = params.toString();
            var url = window.location.pathname + (qs ? '?' + qs : '');
            history.replaceState(null, '', url);
        }

        function restoreFromURL() {
            var params = new URLSearchParams(window.location.search);
            if (searchInput && params.has('search')) {
                searchInput.value = params.get('search');
            }
            // Restore advanced rules
            ctx.advancedRules = [];
            params.getAll('af').forEach(function(raw) {
                var parts = raw.split(':');
                if (parts.length >= 3) {
                    ctx.advancedRules.push({field: parts[0], op: parts[1], value: parts.slice(2).join(':')});
                }
            });
            // Legacy f_ params (from CLA-66) — convert to rules
            filters.forEach(function(sel) {
                var key = 'f_' + sel.dataset.tableFilter;
                if (params.has(key) && !ctx.advancedRules.some(function(r) { return r.field === sel.dataset.tableFilter; })) {
                    var val = params.get(key);
                    var opt = sel.querySelector('option[value="' + CSS.escape(val) + '"]');
                    if (opt) {
                        ctx.advancedRules.push({field: sel.dataset.tableFilter, op: 'is', value: val});
                    }
                }
            });
            syncDropdownFromRules();
            renderPills();
            if (sortSelect && params.has('sort')) {
                var sortVal = params.get('sort');
                var opt = sortSelect.querySelector('option[value="' + CSS.escape(sortVal) + '"]');
                if (opt) {
                    sortSelect.value = sortVal;
                    var parts = sortVal.split(':');
                    ctx.sortField = parts[0];
                    ctx.sortDir = parts[1] || 'asc';
                    sortSelect.classList.add('sort-active');
                }
            }
            if (groupSelect && params.has('group')) {
                var groupVal = params.get('group');
                var opt = groupSelect.querySelector('option[value="' + CSS.escape(groupVal) + '"]');
                if (opt) {
                    groupSelect.value = groupVal;
                    ctx.groupField = groupVal;
                }
            }
        }

        window.addEventListener('popstate', function() {
            restoreFromURL();
            applyAll();
        });

        // Row count indicator
        var countEl = document.createElement('span');
        countEl.className = 'table-count';
        if (controls) controls.appendChild(countEl);

        function updateCount() {
            var visible = getVisibleRows();
            var total = ctx.rows.length;
            if (visible.length === total) {
                countEl.textContent = total + ' item' + (total !== 1 ? 's' : '');
            } else {
                countEl.textContent = visible.length + ' of ' + total;
            }
        }

        function getVisibleRows() {
            return ctx.rows.filter(function(r) { return r.style.display !== 'none'; });
        }

        function setFocus(index) {
            var visible = getVisibleRows();
            ctx.rows.forEach(function(r) { r.classList.remove('row-focused'); });
            if (index < 0 || index >= visible.length) { ctx.focusIndex = -1; return; }
            ctx.focusIndex = index;
            visible[index].classList.add('row-focused');
            visible[index].scrollIntoView({ block: 'nearest' });
        }

        function applyAll() {
            filterRows(ctx, searchInput);
            sortRows(ctx);
            groupRows(ctx);
            updateCount();
            var visible = getVisibleRows();
            if (ctx.focusIndex >= visible.length) setFocus(visible.length - 1);
            else if (ctx.focusIndex >= 0 && !visible[ctx.focusIndex]) setFocus(0);
            syncToURL();
        }

        if (searchInput) {
            searchInput.addEventListener('input', debounce(applyAll, 150));
        }

        filters.forEach(function(sel) {
            sel.addEventListener('change', function() {
                syncRulesFromDropdown(sel);
                applyAll();
            });
        });

        if (sortSelect) {
            sortSelect.addEventListener('change', function() {
                var val = sortSelect.value;
                if (!val) {
                    ctx.sortField = null;
                    ctx.sortDir = null;
                    sortSelect.classList.remove('sort-active');
                } else {
                    var parts = val.split(':');
                    ctx.sortField = parts[0];
                    ctx.sortDir = parts[1] || 'asc';
                    sortSelect.classList.add('sort-active');
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

        document.addEventListener('keydown', function(e) {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') {
                if (e.key === 'Escape') {
                    e.target.blur();
                    e.preventDefault();
                }
                return;
            }

            var ctxMenu = document.getElementById('ctx-menu');
            if (e.key === 'Escape' && ctxMenu && ctxMenu.style.display === 'block') {
                ctxMenu.style.display = 'none';
                e.preventDefault();
                return;
            }

            if (e.key === '/' && searchInput) {
                e.preventDefault();
                searchInput.focus();
                return;
            }

            var visible = getVisibleRows();
            if (!visible.length) return;

            if (e.key === 'ArrowDown' || e.key === 'j') {
                e.preventDefault();
                setFocus(ctx.focusIndex < visible.length - 1 ? ctx.focusIndex + 1 : 0);
            } else if (e.key === 'ArrowUp' || e.key === 'k') {
                e.preventDefault();
                setFocus(ctx.focusIndex > 0 ? ctx.focusIndex - 1 : visible.length - 1);
            } else if (e.key === 'Enter' && ctx.focusIndex >= 0) {
                e.preventDefault();
                var row = visible[ctx.focusIndex];
                if (row && row.dataset.href) window.location.href = row.dataset.href;
            } else if (e.key === 'Escape') {
                if (ctx.focusIndex >= 0) {
                    setFocus(-1);
                } else {
                    history.back();
                }
            } else if (e.key === 'Home') {
                e.preventDefault();
                setFocus(0);
            } else if (e.key === 'End') {
                e.preventDefault();
                setFocus(visible.length - 1);
            }
        });

        // Restore state from URL params and apply
        restoreFromURL();
        updateCount();
        applyAll();

        container.addEventListener('table:refresh', applyAll);
    }

    function matchRule(rule, rowVal) {
        var rv = (rowVal || '').toLowerCase();
        var v = rule.value.toLowerCase();
        switch (rule.op) {
            case 'is': return rv === v;
            case 'is_not': return rv !== v;
            case 'in':
                var vals = rule.value.split(',').map(function(s) { return s.trim().toLowerCase(); });
                return vals.indexOf(rv) !== -1;
            case 'contains': return rv.indexOf(v) !== -1;
            case 'not_contains': return rv.indexOf(v) === -1;
            case 'gte': return rv >= v;
            case 'lte': return rv <= v;
            default: return true;
        }
    }

    function filterRows(ctx, searchInput) {
        var query = searchInput ? searchInput.value.toLowerCase() : '';

        ctx.rows.forEach(function(row) {
            var matchSearch = !query || (row.dataset.search || '').indexOf(query) !== -1;

            var matchAdvanced = ctx.advancedRules.every(function(rule) {
                var rowVal = row.dataset[rule.field] || '';
                return matchRule(rule, rowVal);
            });

            row.style.display = (matchSearch && matchAdvanced) ? '' : 'none';
        });

        highlightSearch(ctx, query);
    }

    function highlightSearch(ctx, query) {
        ctx.rows.forEach(function(row) {
            var cells = row.querySelectorAll('td');
            cells.forEach(function(cell) {
                cell.querySelectorAll('mark.search-hl').forEach(function(m) {
                    m.replaceWith(m.textContent);
                });
            });
            if (!query || row.style.display === 'none') return;
            cells.forEach(function(cell) {
                highlightText(cell, query);
            });
        });
    }

    function highlightText(el, query) {
        var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
        var nodes = [];
        while (walker.nextNode()) nodes.push(walker.currentNode);
        nodes.forEach(function(node) {
            var text = node.textContent;
            var lower = text.toLowerCase();
            var idx = lower.indexOf(query);
            if (idx === -1) return;
            var before = text.slice(0, idx);
            var match = text.slice(idx, idx + query.length);
            var after = text.slice(idx + query.length);
            var frag = document.createDocumentFragment();
            if (before) frag.appendChild(document.createTextNode(before));
            var mark = document.createElement('mark');
            mark.className = 'search-hl';
            mark.textContent = match;
            frag.appendChild(mark);
            if (after) frag.appendChild(document.createTextNode(after));
            node.parentNode.replaceChild(frag, node);
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

            ctx.tbody.appendChild(headerRow);
            groups[label].forEach(function(row) {
                ctx.tbody.appendChild(row);
            });
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
