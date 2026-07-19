/**
 * Searchable Picker — combobox replacement for long <select> lists.
 * Usage: <div class="picker" data-picker-name="job_id">
 *          <input type="text" class="picker-search" placeholder="Search...">
 *          <div class="picker-list"></div>
 *        </div>
 * Initialize: new Picker(el, options) where options = [{value, label, meta?}]
 */
(function() {
    'use strict';

    function Picker(container) {
        var self = this;
        var name = container.dataset.pickerName;
        var required = container.hasAttribute('data-picker-required');
        var search = container.querySelector('.picker-search');
        var list = container.querySelector('.picker-list');
        var hidden = document.createElement('input');
        hidden.type = 'hidden';
        hidden.name = name;
        container.appendChild(hidden);

        search.setAttribute('role', 'combobox');
        search.setAttribute('aria-autocomplete', 'list');
        search.setAttribute('aria-expanded', 'false');
        search.setAttribute('aria-controls', name + '-listbox');
        list.id = name + '-listbox';

        var options = [];
        var filtered = [];
        var activeIdx = -1;
        var isOpen = false;

        var source = container.dataset.pickerSource;
        if (source) {
            var srcEl = document.getElementById(source);
            if (srcEl && srcEl.tagName === 'SELECT') {
                Array.from(srcEl.options).forEach(function(opt) {
                    if (opt.value) options.push({value: opt.value, label: opt.textContent, meta: opt.dataset.meta || ''});
                });
                srcEl.remove();
            }
        }
        var jsonOpts = container.dataset.pickerOptions;
        if (jsonOpts) {
            try { options = JSON.parse(jsonOpts); } catch(e) {}
        }

        var preselect = container.dataset.pickerValue;
        if (preselect) {
            var match = options.find(function(o) { return o.value === preselect; });
            if (match) {
                hidden.value = match.value;
                search.value = match.label;
            }
        }

        function render() {
            var html = '';
            filtered.forEach(function(opt, i) {
                var cls = 'picker-option' + (i === activeIdx ? ' picker-option--active' : '');
                var sel = opt.value === hidden.value ? ' picker-option--selected' : '';
                var optId = name + '-opt-' + i;
                html += '<div class="' + cls + sel + '" role="option" id="' + optId + '" data-idx="' + i + '" data-value="' + esc(opt.value) + '"' + (i === activeIdx ? ' aria-selected="true"' : '') + '>';
                html += '<span class="picker-option-label">' + esc(opt.label) + '</span>';
                if (opt.meta) html += '<span class="picker-option-meta">' + esc(opt.meta) + '</span>';
                html += '</div>';
            });
            if (filtered.length === 0) {
                html = '<div class="picker-empty">No results</div>';
            }
            list.innerHTML = html;
            if (activeIdx >= 0) {
                search.setAttribute('aria-activedescendant', name + '-opt-' + activeIdx);
            } else {
                search.removeAttribute('aria-activedescendant');
            }
        }

        function filter(q) {
            var lower = q.toLowerCase();
            filtered = options.filter(function(o) {
                return o.label.toLowerCase().indexOf(lower) >= 0 || (o.meta && o.meta.toLowerCase().indexOf(lower) >= 0);
            });
            activeIdx = -1;
            render();
        }

        function open() {
            if (isOpen) return;
            isOpen = true;
            list.style.display = 'block';
            container.classList.add('picker-open');
            search.setAttribute('aria-expanded', 'true');
            filter(search.value);
        }

        function close() {
            if (!isOpen) return;
            isOpen = false;
            list.style.display = 'none';
            container.classList.remove('picker-open');
            search.setAttribute('aria-expanded', 'false');
            search.removeAttribute('aria-activedescendant');
            activeIdx = -1;
        }

        function select(opt) {
            hidden.value = opt.value;
            search.value = opt.label;
            close();
            hidden.dispatchEvent(new Event('change', {bubbles: true}));
        }

        function scrollActive() {
            var el = list.querySelector('.picker-option--active');
            if (el) el.scrollIntoView({block: 'nearest'});
        }

        search.addEventListener('focus', function() { open(); });
        search.addEventListener('input', function() {
            hidden.value = '';
            filter(search.value);
            if (!isOpen) open();
        });

        search.addEventListener('keydown', function(e) {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (activeIdx < filtered.length - 1) activeIdx++;
                render();
                scrollActive();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (activeIdx > 0) activeIdx--;
                render();
                scrollActive();
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (activeIdx >= 0 && filtered[activeIdx]) {
                    select(filtered[activeIdx]);
                }
            } else if (e.key === 'Escape') {
                close();
                search.blur();
            }
        });

        list.addEventListener('click', function(e) {
            var el = e.target.closest('.picker-option');
            if (!el) return;
            var idx = parseInt(el.dataset.idx);
            if (filtered[idx]) select(filtered[idx]);
        });

        document.addEventListener('click', function(e) {
            if (!container.contains(e.target)) close();
        });

        // Form validation: prevent submit if required and empty
        var form = container.closest('form');
        if (form && required) {
            form.addEventListener('submit', function(e) {
                if (!hidden.value) {
                    e.preventDefault();
                    search.focus();
                    search.setCustomValidity('Please select an option');
                    search.reportValidity();
                }
            });
            search.addEventListener('input', function() { search.setCustomValidity(''); });
        }

        self.setOptions = function(opts) { options = opts; filter(search.value); };
        self.getValue = function() { return hidden.value; };
        self.clear = function() { hidden.value = ''; search.value = ''; };
    }

    function esc(s) {
        if (!s) return '';
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    function init() {
        document.querySelectorAll('[data-picker-name]').forEach(function(el) {
            if (!el._picker) el._picker = new Picker(el);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    window.Picker = Picker;
})();
