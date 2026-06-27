/**
 * Cell render vocabulary for sync-list tables.
 * Each function returns an HTML string for a <td>.
 * Designed for composition inside renderRow functions
 * and future migration to declarative column-type config.
 */
var C = (function() {
    function esc(s) {
        if (!s) return '';
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    function formatDate(iso) {
        if (!iso) return '';
        return new Date(iso).toLocaleDateString();
    }

    function stageClass(val) {
        return val ? ' data-stage="' + esc(val) + '"' : '';
    }

    return {
        /**
         * Two-line text cell (identity column). Flex width.
         * @param {string} primary - Bold first line
         * @param {string} [meta] - Muted second line
         * @param {object} [opts] - { link: '/url' } wraps primary in <a>
         */
        text: function(primary, meta, opts) {
            var p = esc(primary) || '—';
            if (opts && opts.link) p = '<a href="' + esc(opts.link) + '">' + p + '</a>';
            var html = '<td><div class="col-primary">' + p + '</div>';
            if (meta) html += '<div class="row-meta">' + esc(meta) + '</div>';
            return html + '</td>';
        },

        /**
         * Read-only badge (computed/status). Fixed width.
         * @param {string} value - Badge text
         * @param {string} [variant] - CSS class suffix (defaults to value)
         */
        badge: function(value, variant) {
            if (!value) return '<td></td>';
            var v = variant || value;
            var label = value.replace(/_/g, ' ').replace(/\b\w/g, function(c){return c.toUpperCase();});
            return '<td><span class="badge badge-' + esc(v) + '">' + esc(label) + '</span></td>';
        },

        /**
         * Mutable inline select (badge-select). Fixed width.
         * Includes hx-disinherit, stopPropagation, and push-url=false.
         * @param {string} value - Current selected value
         * @param {string[]} options - All possible values
         * @param {string} endpoint - POST URL for changes
         * @param {object} [opts] - { swap: 'outerHTML', trigger: 'change' }
         */
        select: function(value, options, endpoint, opts) {
            opts = opts || {};
            var optHtml = options.map(function(s) {
                var sel = s === value ? ' selected' : '';
                var label = s.replace(/_/g, ' ').replace(/\b\w/g, function(c){return c.toUpperCase();});
                return '<option value="' + esc(s) + '"' + sel + '>' + label + '</option>';
            }).join('');
            return '<td hx-disinherit="*"><select name="' + (opts.name || 'stage') + '" class="inline-select"' +
                stageClass(value) +
                ' hx-post="' + esc(endpoint) + '"' +
                ' hx-target="this" hx-swap="' + (opts.swap || 'outerHTML') + '"' +
                ' hx-push-url="false" hx-trigger="' + (opts.trigger || 'change') + '"' +
                ' onclick="event.stopPropagation()">' + optHtml + '</select></td>';
        },

        /**
         * Multiple read-only badges with +N overflow. Fixed width.
         * @param {string[]} values - All badge values
         * @param {number} [max] - Max visible (default 3)
         */
        multiBadge: function(values, max) {
            if (!values || !values.length) return '<td>—</td>';
            max = max || 3;
            var visible = values.slice(0, max);
            var html = visible.map(function(s) {
                return '<span class="badge badge-' + esc(s) + '">' + s.replace(/_/g, ' ') + '</span>';
            }).join(' ');
            if (values.length > max) {
                html += ' <span class="badge badge-overflow">+' + (values.length - max) + '</span>';
            }
            return '<td class="cell-multi-badge">' + html + '</td>';
        },

        /**
         * Ratio/progress cell. Fixed width, right-aligned.
         * @param {number} n - Numerator
         * @param {number} total - Denominator
         * @param {string} [label] - Optional suffix label
         */
        ratio: function(n, total, label) {
            var text = (n || 0) + '/' + (total || 0);
            if (label) text += ' ' + label;
            return '<td class="cell-ratio">' + text + '</td>';
        },

        /**
         * Date cell. Fixed width, right-aligned, muted.
         * @param {string} iso - ISO date string
         * @param {string} [prefix] - Optional label prefix (e.g. "Due:")
         */
        date: function(iso, prefix) {
            var d = formatDate(iso);
            var text = prefix ? prefix + ' ' + d : d;
            return '<td class="cell-date row-meta">' + text + '</td>';
        },

        /**
         * Compound metadata cell. Joins parts with ' · '.
         * @param {string[]} parts - Values to join (falsy filtered out)
         */
        compound: function(parts) {
            var filtered = parts.filter(Boolean);
            if (!filtered.length) return '<td class="row-meta">—</td>';
            return '<td class="row-meta">' + filtered.map(esc).join(' · ') + '</td>';
        },

        /**
         * Action/peek trigger cell. Fixed width.
         * @param {string} entityType - e.g. 'pipeline', 'candidate'
         * @param {string|number} entityId - Entity ID
         * @param {number} [count] - Comment count
         */
        action: function(entityType, entityId, count) {
            return '<td class="peek-trigger" onclick="event.stopPropagation(); openPeek(\'' +
                esc(entityType) + '\', ' + entityId + ')">' +
                '<span class="peek-icon">' + (count || '') +
                ' <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>' +
                '</span></td>';
        },

        /**
         * Raw HTML cell (escape hatch for non-standard content).
         * @param {string} html - Pre-built HTML
         * @param {string} [cls] - Additional class
         */
        raw: function(html, cls) {
            return '<td' + (cls ? ' class="' + cls + '"' : '') + '>' + (html || '') + '</td>';
        }
    };
})();
