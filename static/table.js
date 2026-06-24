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
            advancedRules: [],
            showArchived: false
        };

        // Archive toggle config
        var archiveConfig = null;
        if (container.dataset.tableArchive) {
            var parts = container.dataset.tableArchive.split(':');
            archiveConfig = { field: parts[0], values: parts[1].split(',') };
        }

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

        // Custom views
        var viewsData = [];
        if (container.dataset.tableViews) {
            try { viewsData = JSON.parse(container.dataset.tableViews); } catch(e) {}
        }
        var tablePage = container.dataset.tablePage || window.location.pathname;
        var viewPillsRow = null;
        var activeViewId = null;

        if (controls) {
            viewPillsRow = document.createElement('div');
            viewPillsRow.className = 'view-pills';
            controls.parentNode.insertBefore(viewPillsRow, controls.nextSibling);
            // Move filter pills after view pills
            viewPillsRow.parentNode.insertBefore(pillsRow, viewPillsRow.nextSibling);
        }

        function getCurrentState() {
            var state = {};
            if (ctx.advancedRules.length) state.rules = ctx.advancedRules;
            if (sortSelect && sortSelect.value) state.sort = sortSelect.value;
            if (groupSelect && groupSelect.value) state.group = groupSelect.value;
            if (searchInput && searchInput.value) state.search = searchInput.value;
            return JSON.stringify(state);
        }

        function applyViewConfig(configStr) {
            var config = {};
            try { config = JSON.parse(configStr); } catch(e) { return; }
            ctx.advancedRules = config.rules || [];
            syncDropdownFromRules();
            renderPills();
            if (searchInput) searchInput.value = config.search || '';
            if (sortSelect) {
                sortSelect.value = config.sort || '';
                if (config.sort) {
                    var parts = config.sort.split(':');
                    ctx.sortField = parts[0];
                    ctx.sortDir = parts[1] || 'asc';
                    sortSelect.classList.add('sort-active');
                } else {
                    ctx.sortField = null;
                    ctx.sortDir = null;
                    sortSelect.classList.remove('sort-active');
                }
            }
            if (groupSelect) {
                groupSelect.value = config.group || '';
                ctx.groupField = config.group || null;
            }
            applyAll();
        }

        function renderViewPills() {
            if (!viewPillsRow) return;
            viewPillsRow.innerHTML = '';

            var allPill = document.createElement('span');
            allPill.className = 'view-pill' + (activeViewId === null ? ' view-pill--active' : '');
            allPill.textContent = 'All';
            allPill.addEventListener('click', function() {
                activeViewId = null;
                ctx.advancedRules = [];
                syncDropdownFromRules();
                renderPills();
                if (searchInput) searchInput.value = '';
                if (sortSelect) { sortSelect.value = ''; ctx.sortField = null; ctx.sortDir = null; sortSelect.classList.remove('sort-active'); }
                if (groupSelect) { groupSelect.value = ''; ctx.groupField = null; }
                applyAll();
                renderViewPills();
            });
            viewPillsRow.appendChild(allPill);

            viewsData.forEach(function(v) {
                var pill = document.createElement('span');
                pill.className = 'view-pill' + (activeViewId === v.id ? ' view-pill--active' : '');
                pill.dataset.viewId = v.id;
                pill.dataset.viewConfig = v.config;
                pill.innerHTML = v.name + ' <button type="button" class="view-del">×</button>';
                pill.addEventListener('click', function(e) {
                    if (e.target.classList.contains('view-del')) return;
                    activeViewId = v.id;
                    applyViewConfig(v.config);
                    renderViewPills();
                });
                pill.querySelector('.view-del').addEventListener('click', function(e) {
                    e.stopPropagation();
                    fetch('/views/' + v.id, {method: 'DELETE'});
                    viewsData = viewsData.filter(function(x) { return x.id !== v.id; });
                    if (activeViewId === v.id) activeViewId = null;
                    renderViewPills();
                });
                viewPillsRow.appendChild(pill);
            });

            var saveLink = document.createElement('button');
            saveLink.type = 'button';
            saveLink.className = 'view-save-link';
            saveLink.textContent = '+ Save view';
            saveLink.addEventListener('click', function() {
                var name = prompt('View name:');
                if (!name || !name.trim()) return;
                var config = getCurrentState();
                var form = new FormData();
                form.append('page', tablePage);
                form.append('name', name.trim());
                form.append('config', config);
                fetch('/views', {method: 'POST', body: form}).then(function(r) { return r.text(); }).then(function() {
                    viewsData.push({id: Date.now(), name: name.trim(), config: config});
                    activeViewId = viewsData[viewsData.length - 1].id;
                    renderViewPills();
                });
            });
            viewPillsRow.appendChild(saveLink);
        }

        renderViewPills();

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
            if (activeViewId) params.set('view', activeViewId);
            if (ctx.showArchived) params.set('show_all', '1');
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
            // Restore archive toggle
            if (params.has('show_all') && archiveToggle) {
                ctx.showArchived = true;
                archiveToggle.checked = true;
            }
            // Restore view if specified
            if (params.has('view')) {
                var vid = parseInt(params.get('view'));
                var matchedView = viewsData.find(function(v) { return v.id === vid; });
                if (matchedView) {
                    activeViewId = vid;
                    applyViewConfig(matchedView.config);
                    renderViewPills();
                    return;
                }
            }
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

        // Archive toggle UI
        var archiveToggle = null;
        if (archiveConfig && controls) {
            var label = document.createElement('label');
            label.className = 'archive-toggle';
            var checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.checked = false;
            label.appendChild(checkbox);
            label.appendChild(document.createTextNode('Show completed'));
            controls.appendChild(label);
            archiveToggle = checkbox;

            checkbox.addEventListener('change', function() {
                ctx.showArchived = checkbox.checked;
                applyAll();
                if (!checkbox.checked) {
                    ctx.rows.forEach(function(r) { r.classList.remove('row-reveal'); });
                }
            });
        }

        function applyArchiveFilter() {
            if (!archiveConfig) return;
            ctx.rows.forEach(function(row) {
                var val = row.dataset[archiveConfig.field] || '';
                var isArchived = archiveConfig.values.indexOf(val) !== -1;
                if (isArchived && !ctx.showArchived) {
                    row.style.display = 'none';
                    row.classList.remove('row-reveal');
                } else if (isArchived && ctx.showArchived) {
                    row.classList.add('row-reveal');
                }
            });
        }

        // Row count indicator
        var countEl = document.createElement('span');
        countEl.className = 'table-count';
        if (controls) controls.appendChild(countEl);

        function updateCount() {
            var visible = getVisibleRows();
            var total = ctx.rows.length;
            if (archiveConfig && !ctx.showArchived) {
                var activeTotal = ctx.rows.filter(function(r) {
                    return archiveConfig.values.indexOf(r.dataset[archiveConfig.field] || '') === -1;
                }).length;
                var archivedCount = total - activeTotal;
                if (visible.length === activeTotal) {
                    countEl.textContent = visible.length + ' active' + (archivedCount ? ' · ' + total + ' total' : '');
                } else {
                    countEl.textContent = visible.length + ' of ' + activeTotal + ' active · ' + total + ' total';
                }
            } else if (visible.length === total) {
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
            applyArchiveFilter();
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
                if (selected.size > 0) {
                    deselectAll();
                } else if (ctx.focusIndex >= 0) {
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

        // Bulk selection system
        var selected = new Set();
        var lastCheckedIndex = -1;
        var table = container.querySelector('table.table-clean');
        var thead = table ? table.querySelector('thead') : null;
        var selectAllCb = null;
        var bulkBar = document.createElement('div');
        bulkBar.className = 'bulk-bar';
        bulkBar.style.display = 'none';
        if (table) table.parentNode.insertBefore(bulkBar, table);

        if (thead) {
            var headerRow = thead.querySelector('tr');
            if (headerRow) {
                var selectAllTh = document.createElement('th');
                selectAllTh.className = 'col-select';
                selectAllCb = document.createElement('input');
                selectAllCb.type = 'checkbox';
                selectAllTh.appendChild(selectAllCb);
                headerRow.insertBefore(selectAllTh, headerRow.firstChild);

                selectAllCb.addEventListener('change', function() {
                    var visible = getVisibleRows();
                    visible.forEach(function(row) {
                        var cb = row.querySelector('.col-select input');
                        if (selectAllCb.checked) {
                            selected.add(row);
                            row.classList.add('row-selected');
                            if (cb) cb.checked = true;
                        } else {
                            selected.delete(row);
                            row.classList.remove('row-selected');
                            if (cb) cb.checked = false;
                        }
                    });
                    updateBulkBar();
                });
            }
        }

        ctx.rows.forEach(function(row, idx) {
            var td = document.createElement('td');
            td.className = 'col-select';
            var cb = document.createElement('input');
            cb.type = 'checkbox';
            td.appendChild(cb);
            row.insertBefore(td, row.firstChild);

            cb.addEventListener('change', function(e) {
                e.stopPropagation();
                if (cb.checked) {
                    selected.add(row);
                    row.classList.add('row-selected');
                } else {
                    selected.delete(row);
                    row.classList.remove('row-selected');
                }
                lastCheckedIndex = idx;
                updateBulkBar();
            });

            cb.addEventListener('click', function(e) {
                e.stopPropagation();
                if (e.shiftKey && lastCheckedIndex >= 0) {
                    e.preventDefault();
                    if (table) table.classList.add('table-selecting');
                    window.getSelection().removeAllRanges();
                    var start = Math.min(lastCheckedIndex, idx);
                    var end = Math.max(lastCheckedIndex, idx);
                    for (var i = start; i <= end; i++) {
                        selected.add(ctx.rows[i]);
                        ctx.rows[i].classList.add('row-selected');
                        var rcb = ctx.rows[i].querySelector('.col-select input');
                        if (rcb) rcb.checked = true;
                    }
                    lastCheckedIndex = idx;
                    updateBulkBar();
                    setTimeout(function() { if (table) table.classList.remove('table-selecting'); }, 0);
                }
            });

            row.addEventListener('click', function(e) {
                if (e.target.closest('.col-select, a, button, select, input, form')) return;
                if (e.shiftKey && lastCheckedIndex >= 0) {
                    e.preventDefault();
                    if (table) table.classList.add('table-selecting');
                    window.getSelection().removeAllRanges();
                    var start = Math.min(lastCheckedIndex, idx);
                    var end = Math.max(lastCheckedIndex, idx);
                    for (var i = start; i <= end; i++) {
                        selected.add(ctx.rows[i]);
                        ctx.rows[i].classList.add('row-selected');
                        var rcb = ctx.rows[i].querySelector('.col-select input');
                        if (rcb) rcb.checked = true;
                    }
                    lastCheckedIndex = idx;
                    updateBulkBar();
                    setTimeout(function() { if (table) table.classList.remove('table-selecting'); }, 0);
                } else if (e.ctrlKey) {
                    e.preventDefault();
                    toggleRowSelection(row);
                    lastCheckedIndex = idx;
                }
            });
        });

        function toggleRowSelection(row) {
            var cb = row.querySelector('.col-select input');
            if (selected.has(row)) {
                selected.delete(row);
                row.classList.remove('row-selected');
                if (cb) cb.checked = false;
            } else {
                selected.add(row);
                row.classList.add('row-selected');
                if (cb) cb.checked = true;
            }
            updateBulkBar();
        }

        function updateBulkBar() {
            if (selected.size > 0) {
                bulkBar.style.display = 'flex';
                bulkBar.innerHTML = '<span>' + selected.size + ' selected</span>';
                var delBtn = document.createElement('button');
                delBtn.type = 'button';
                delBtn.className = 'bulk-delete-btn';
                delBtn.textContent = 'Delete';
                delBtn.addEventListener('click', bulkDelete);
                bulkBar.appendChild(delBtn);
            } else {
                bulkBar.style.display = 'none';
            }
        }

        function bulkDelete() {
            if (!confirm('Delete ' + selected.size + ' item(s)?')) return;
            var promises = [];
            selected.forEach(function(row) {
                var ctx = row.dataset.ctx;
                if (!ctx) return;
                try {
                    var items = JSON.parse(ctx);
                    var deleteItem = items.find(function(it) { return it.delete; });
                    if (deleteItem) {
                        promises.push(
                            fetch(deleteItem.href, {method: 'POST'}).then(function() {
                                row.remove();
                            })
                        );
                    }
                } catch(err) {}
            });
            Promise.all(promises).then(function() {
                selected.clear();
                updateBulkBar();
                refreshRows();
                updateCount();
            });
        }

        function selectAll() {
            var visible = getVisibleRows();
            visible.forEach(function(row) {
                selected.add(row);
                row.classList.add('row-selected');
                var cb = row.querySelector('.col-select input');
                if (cb) cb.checked = true;
            });
            if (selectAllCb) selectAllCb.checked = true;
            updateBulkBar();
        }

        function deselectAll() {
            selected.forEach(function(row) {
                row.classList.remove('row-selected');
                var cb = row.querySelector('.col-select input');
                if (cb) cb.checked = false;
            });
            selected.clear();
            if (selectAllCb) selectAllCb.checked = false;
            updateBulkBar();
        }

        container.addEventListener('keydown', function(e) {
            if (e.ctrlKey && e.key === 'a') {
                e.preventDefault();
                selectAll();
            }
        });

        document.addEventListener('keydown', function(e) {
            if (e.target.closest('input, textarea, select')) return;
            if (e.ctrlKey && e.key === 'a') {
                e.preventDefault();
                selectAll();
            }
        });

        // Expose toggle for shortcuts.js (x key)
        container._toggleRowSelection = toggleRowSelection;

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
