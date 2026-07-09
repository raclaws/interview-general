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

    function initials(name) {
        if (!name) return '?';
        var parts = name.trim().split(/\s+/);
        if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
        return parts[0].substring(0, 2).toUpperCase();
    }

    function nameHash(name) {
        var hash = 0;
        for (var i = 0; i < (name || '').length; i++) {
            hash = ((hash << 5) - hash) + name.charCodeAt(i);
            hash |= 0;
        }
        return Math.abs(hash);
    }

    var AVATAR_COLORS = [
        '#7287fd', '#e64553', '#fe640b', '#df8e1d',
        '#40a02b', '#179299', '#04a5e5', '#8839ef',
        '#ea76cb', '#d20f39', '#209fb5', '#1e66f5'
    ];

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
         * Salary band pill with color coding.
         * @param {string} label - WELL_BELOW/BELOW/MARKET/ABOVE/WELL_ABOVE/NO_INPUT/INSUFFICIENT_DATA
         * @param {number|null} percentile - P0-P100
         * @param {string} [source] - Comparison source text
         */
        band: function(label, percentile, source) {
            if (!label || label === 'NO_INPUT' || label === 'INSUFFICIENT_DATA') {
                return '<td><span class="band-pill band-none">—</span></td>';
            }
            var cls = 'band-' + label.toLowerCase().replace(/_/g, '-');
            var pct = percentile != null ? ' P' + Math.round(percentile) : '';
            var text = label.replace(/_/g, ' ') + pct;
            var title = source ? ' title="' + esc(source) + '"' : '';
            return '<td><span class="band-pill ' + cls + '"' + title + '>' + esc(text) + '</span></td>';
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
         * Person/candidate cell. Initials avatar + two-line text. Flex width.
         * @param {string} name - Person name
         * @param {string} [meta] - Subtitle (email, position, etc.)
         * @param {object} [opts] - { link: '/url' } wraps name in <a>
         */
        person: function(name, meta, opts) {
            var ini = initials(name);
            var color = AVATAR_COLORS[nameHash(name) % AVATAR_COLORS.length];
            var avatar = '<span class="cell-avatar" style="background:' + color + '">' + esc(ini) + '</span>';
            var p = esc(name) || '—';
            if (opts && opts.link) p = '<a href="' + esc(opts.link) + '">' + p + '</a>';
            var html = '<td class="cell-person">' + avatar + '<div><div class="col-primary">' + p + '</div>';
            if (meta) html += '<div class="row-meta">' + esc(meta) + '</div>';
            return html + '</div></td>';
        },

        /**
         * Link/URL cell. Truncated with external icon. Flex width.
         * @param {string} url - Full URL
         * @param {string} [label] - Display label (defaults to truncated URL)
         */
        link: function(url, label) {
            if (!url) return '<td class="row-meta">—</td>';
            var display = label || url.replace(/^https?:\/\//, '').replace(/\/$/, '');
            if (display.length > 40) display = display.substring(0, 37) + '…';
            return '<td class="cell-link"><a href="' + esc(url) + '" target="_blank" rel="noopener" onclick="event.stopPropagation()">' +
                esc(display) + ' <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg></a></td>';
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
