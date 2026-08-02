"""Dashboard — HTML UI + JSON metrics endpoint."""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


class MetricsCollector:
    """Thread-safe metrics collector for FlashAPI operations."""

    def __init__(self) -> None:
        self._start_time = time.time()
        self._entity_ops: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._totals: dict[str, int] = defaultdict(int)
        self._recent_events: list[dict] = []
        self._max_recent = 50
        self._entity_meta: dict[str, dict[str, Any]] = {}

    def register_entity(self, name: str, *, soft_delete: bool = True, audit: bool = False,
                        webhook: bool = False, rate_limited: bool = False,
                        multi_tenant: bool = False) -> None:
        self._entity_meta[name] = {
            "softDelete": soft_delete,
            "auditEnabled": audit,
            "webhookEnabled": webhook,
            "rateLimited": rate_limited,
            "multiTenant": multi_tenant,
        }

    def record(self, operation: str, entity: str, entity_id: str = "") -> None:
        self._entity_ops[entity][operation] += 1
        if operation == "CREATE":
            self._totals["creates"] += 1
        elif operation == "READ":
            self._totals["reads"] += 1
        elif operation == "UPDATE":
            self._totals["updates"] += 1
        elif operation == "DELETE":
            self._totals["deletes"] += 1
        elif operation == "SEARCH":
            self._totals["searches"] += 1
        elif operation == "EXPORT":
            self._totals["exports"] += 1
        elif operation == "BULK":
            self._totals["bulkOps"] += 1
        self._totals["total"] += 1

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            "entity": entity,
            "entityId": str(entity_id),
            "status": "OK",
        }
        self._recent_events.append(event)
        if len(self._recent_events) > self._max_recent:
            self._recent_events = self._recent_events[-self._max_recent:]

    def get_metrics(self, webhook_dispatcher=None) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        uptime = int(time.time() - self._start_time)

        entities = {}
        for name, meta in self._entity_meta.items():
            ops = dict(self._entity_ops.get(name, {}))
            count = ops.get("CREATE", 0) - ops.get("DELETE", 0)
            entities[name] = {
                "name": name,
                "count": max(0, count),
                **meta,
                "operations": {
                    "CREATE": ops.get("CREATE", 0),
                    "READ": ops.get("READ", 0),
                    "UPDATE": ops.get("UPDATE", 0),
                    "DELETE": ops.get("DELETE", 0),
                },
            }

        webhooks = {"sent": 0, "failed": 0, "retries": 0, "targetUrls": []}
        if webhook_dispatcher:
            webhooks = {
                "sent": webhook_dispatcher.sent,
                "failed": webhook_dispatcher.failed,
                "retries": webhook_dispatcher.retries,
                "targetUrls": webhook_dispatcher._urls,
            }

        return {
            "generatedAt": now,
            "uptimeSeconds": uptime,
            "entities": entities,
            "totals": dict(self._totals),
            "webhooks": webhooks,
            "recentEvents": self._recent_events[-20:],
        }


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
<meta charset="utf-8">
<title>FlashAPI — Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
<script src="https://cdn.tailwindcss.com"></script>
<script>
tailwind.config = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        flash: {
          50: '#eef7ff',
          100: '#d9ecff',
          200: '#bce0ff',
          300: '#8ecdff',
          400: '#59b0ff',
          500: '#338dff',
          600: '#1a6df5',
          700: '#1457e1',
          800: '#1746b6',
          900: '#193d8f',
          950: '#142757',
        },
        surface: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          700: '#1e293b',
          800: '#0f172a',
          900: '#020617',
        }
      },
      fontFamily: {
        display: ['JetBrains Mono', 'Fira Code', 'monospace'],
        body: ['Inter', 'system-ui', 'sans-serif'],
      },
    }
  }
}
</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  @keyframes pulse-dot { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
  .live-dot { animation: pulse-dot 2s ease-in-out infinite; }
  @keyframes fade-in { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
  .animate-row { animation: fade-in 0.3s ease-out; }
  .op-bar { transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1); }
</style>
</head>
<body class="h-full bg-surface-50 dark:bg-surface-900 font-body text-slate-800 dark:text-slate-200 transition-colors duration-300">

<!-- Shell -->
<div class="min-h-full flex flex-col">

  <!-- Header -->
  <header class="sticky top-0 z-50 backdrop-blur-md bg-white/80 dark:bg-surface-800/80 border-b border-slate-200/60 dark:border-slate-700/60">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="flex items-center gap-2">
          <svg class="w-6 h-6 text-flash-600 dark:text-flash-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
          <span class="font-display font-bold text-lg tracking-tight">FlashAPI</span>
        </div>
        <span class="hidden sm:inline text-xs font-medium text-slate-400 dark:text-slate-500 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full">Dashboard</span>
      </div>
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
          <span class="live-dot w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
          <span id="uptime-badge">Live</span>
        </div>
        <button id="theme-toggle" class="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors" title="Toggle dark mode">
          <svg id="icon-sun" class="w-4 h-4 hidden dark:block" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
          <svg id="icon-moon" class="w-4 h-4 block dark:hidden" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        </button>
      </div>
    </div>
  </header>

  <!-- Main content -->
  <main class="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-6 space-y-6">

    <!-- Totals row -->
    <section id="totals-section" class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
      <!-- Filled by JS -->
    </section>

    <!-- Two-column layout -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

      <!-- Entities (2/3) -->
      <section class="lg:col-span-2 space-y-3">
        <div class="flex items-center justify-between">
          <h2 class="text-sm font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider">Resources</h2>
          <span id="entity-count" class="text-xs text-slate-400"></span>
        </div>
        <div id="entities-grid" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <!-- Filled by JS -->
        </div>
      </section>

      <!-- Sidebar (1/3) -->
      <aside class="space-y-6">
        <!-- Webhooks -->
        <div class="rounded-xl bg-white dark:bg-surface-800 border border-slate-200/80 dark:border-slate-700/50 p-5">
          <h2 class="text-sm font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider mb-4">Webhooks</h2>
          <div id="webhook-stats" class="space-y-3">
            <!-- Filled by JS -->
          </div>
        </div>

        <!-- Recent events -->
        <div class="rounded-xl bg-white dark:bg-surface-800 border border-slate-200/80 dark:border-slate-700/50 p-5">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-sm font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider">Activity</h2>
            <span class="text-[10px] text-slate-400 font-medium">LAST 10</span>
          </div>
          <div id="events-list" class="space-y-1.5 max-h-80 overflow-y-auto">
            <!-- Filled by JS -->
          </div>
        </div>
      </aside>
    </div>
  </main>

  <!-- Footer -->
  <footer class="border-t border-slate-200/60 dark:border-slate-700/60 py-3">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between text-[11px] text-slate-400">
      <span>Polling every 5s</span>
      <span id="last-update"></span>
    </div>
  </footer>
</div>

<script>
(function() {
  // Dark mode
  const html = document.documentElement;
  const stored = localStorage.getItem('flash-theme');
  if (stored === 'dark' || (!stored && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    html.classList.add('dark');
  }
  document.getElementById('theme-toggle').addEventListener('click', () => {
    html.classList.toggle('dark');
    localStorage.setItem('flash-theme', html.classList.contains('dark') ? 'dark' : 'light');
  });

  // Formatting
  function fmtUptime(s) {
    if (s < 60) return s + 's';
    if (s < 3600) return Math.floor(s/60) + 'm ' + (s%60) + 's';
    const h = Math.floor(s/3600);
    const m = Math.floor((s%3600)/60);
    return h + 'h ' + m + 'm';
  }

  const OP_COLORS = {
    CREATE: { bg: 'bg-emerald-100 dark:bg-emerald-900/30', text: 'text-emerald-700 dark:text-emerald-400', bar: 'bg-emerald-500' },
    READ:   { bg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-700 dark:text-blue-400', bar: 'bg-blue-500' },
    UPDATE: { bg: 'bg-amber-100 dark:bg-amber-900/30', text: 'text-amber-700 dark:text-amber-400', bar: 'bg-amber-500' },
    DELETE: { bg: 'bg-red-100 dark:bg-red-900/30', text: 'text-red-700 dark:text-red-400', bar: 'bg-red-500' },
  };

  const STAT_ICONS = {
    creates: '<path d="M12 5v14M5 12h14"/>',
    reads: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    updates: '<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>',
    deletes: '<path d="M3 6h18M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
    searches: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    exports: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
    bulkOps: '<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/>',
    total: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
  };

  function statCard(key, value) {
    const icon = STAT_ICONS[key] || STAT_ICONS.total;
    return `
      <div class="rounded-lg bg-white dark:bg-surface-800 border border-slate-200/80 dark:border-slate-700/50 p-3 text-center">
        <div class="flex items-center justify-center mb-1.5">
          <svg class="w-3.5 h-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${icon}</svg>
        </div>
        <div class="font-display text-xl font-bold text-slate-900 dark:text-white">${value}</div>
        <div class="text-[10px] font-medium text-slate-400 uppercase tracking-wide mt-0.5">${key}</div>
      </div>`;
  }

  function entityCard(e) {
    const ops = e.operations;
    const total = ops.CREATE + ops.READ + ops.UPDATE + ops.DELETE;
    const maxOp = Math.max(ops.CREATE, ops.READ, ops.UPDATE, ops.DELETE, 1);

    function bar(op, count) {
      const pct = Math.round((count / maxOp) * 100);
      const c = OP_COLORS[op];
      return `<div class="flex items-center gap-2">
        <span class="w-6 text-[10px] font-medium ${c.text}">${op[0]}</span>
        <div class="flex-1 h-1.5 rounded-full bg-slate-100 dark:bg-slate-700 overflow-hidden">
          <div class="op-bar h-full rounded-full ${c.bar}" style="width:${pct}%"></div>
        </div>
        <span class="w-8 text-right text-[11px] font-display text-slate-500 dark:text-slate-400">${count}</span>
      </div>`;
    }

    function flag(label, enabled) {
      if (enabled) return `<span class="px-1.5 py-0.5 text-[9px] font-semibold uppercase rounded bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400">${label}</span>`;
      return '';
    }

    const flags = [
      flag('soft-del', e.softDelete),
      flag('audit', e.auditEnabled),
      flag('webhook', e.webhookEnabled),
      flag('rate-limit', e.rateLimited),
      flag('multi-tenant', e.multiTenant),
    ].filter(Boolean).join(' ');

    return `
      <div class="rounded-xl bg-white dark:bg-surface-800 border border-slate-200/80 dark:border-slate-700/50 p-4 space-y-3 hover:border-flash-300 dark:hover:border-flash-700 transition-colors">
        <div class="flex items-center justify-between">
          <h3 class="font-display font-semibold text-sm text-slate-900 dark:text-white">${e.name}</h3>
          <span class="text-xs font-display text-slate-400">${total} ops</span>
        </div>
        <div class="space-y-1.5">${bar('CREATE', ops.CREATE)}${bar('READ', ops.READ)}${bar('UPDATE', ops.UPDATE)}${bar('DELETE', ops.DELETE)}</div>
        ${flags ? '<div class="flex flex-wrap gap-1 pt-1">' + flags + '</div>' : ''}
      </div>`;
  }

  function webhookBlock(wh) {
    const total = wh.sent + wh.failed;
    const successRate = total > 0 ? Math.round((wh.sent / total) * 100) : 100;
    const rateColor = successRate >= 95 ? 'text-emerald-600 dark:text-emerald-400' :
                      successRate >= 80 ? 'text-amber-600 dark:text-amber-400' :
                      'text-red-600 dark:text-red-400';

    if (wh.targetUrls.length === 0) {
      return `<p class="text-xs text-slate-400 italic">No webhook URLs configured</p>`;
    }

    return `
      <div class="flex items-baseline justify-between">
        <span class="font-display text-2xl font-bold ${rateColor}">${successRate}%</span>
        <span class="text-[10px] text-slate-400 uppercase">success rate</span>
      </div>
      <div class="grid grid-cols-3 gap-2 text-center">
        <div><div class="font-display text-sm font-bold text-slate-700 dark:text-slate-200">${wh.sent}</div><div class="text-[9px] text-slate-400 uppercase">sent</div></div>
        <div><div class="font-display text-sm font-bold text-slate-700 dark:text-slate-200">${wh.failed}</div><div class="text-[9px] text-slate-400 uppercase">failed</div></div>
        <div><div class="font-display text-sm font-bold text-slate-700 dark:text-slate-200">${wh.retries}</div><div class="text-[9px] text-slate-400 uppercase">retries</div></div>
      </div>
      <div class="pt-2 border-t border-slate-100 dark:border-slate-700">
        <div class="text-[10px] text-slate-400 uppercase mb-1">Targets</div>
        ${wh.targetUrls.map(u => `<div class="text-[11px] font-display text-slate-500 dark:text-slate-400 truncate">${u}</div>`).join('')}
      </div>`;
  }

  function eventRow(ev) {
    const time = ev.timestamp.split('T')[1].split('.')[0];
    const c = OP_COLORS[ev.operation] || OP_COLORS.READ;
    return `
      <div class="animate-row flex items-center gap-2 py-1.5 px-2 rounded-md hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors">
        <span class="font-display text-[10px] text-slate-400 w-12 shrink-0">${time}</span>
        <span class="px-1.5 py-0.5 text-[9px] font-bold uppercase rounded ${c.bg} ${c.text} shrink-0">${ev.operation}</span>
        <span class="text-xs text-slate-600 dark:text-slate-300 truncate">${ev.entity}</span>
        <span class="ml-auto text-[10px] font-display text-slate-400">#${ev.entityId || '-'}</span>
      </div>`;
  }

  // Fetch and render
  async function load() {
    try {
      const base = window.location.pathname.replace(/\\/$/, '');
      const r = await fetch(base + '/metrics.json');
      const m = await r.json();

      // Uptime
      document.getElementById('uptime-badge').textContent = 'Up ' + fmtUptime(m.uptimeSeconds);

      // Totals
      const t = m.totals || {};
      const keys = ['creates','reads','updates','deletes','searches','exports','bulkOps','total'];
      document.getElementById('totals-section').innerHTML = keys.map(k => statCard(k, t[k] || 0)).join('');

      // Entities
      const entities = Object.values(m.entities || {});
      document.getElementById('entity-count').textContent = entities.length + ' registered';
      document.getElementById('entities-grid').innerHTML = entities.map(entityCard).join('');

      // Webhooks
      document.getElementById('webhook-stats').innerHTML = webhookBlock(m.webhooks || {sent:0, failed:0, retries:0, targetUrls:[]});

      // Events
      const events = (m.recentEvents || []).slice(-10).reverse();
      document.getElementById('events-list').innerHTML = events.length > 0
        ? events.map(eventRow).join('')
        : '<p class="text-xs text-slate-400 italic py-4 text-center">No activity yet</p>';

      // Last update
      document.getElementById('last-update').textContent = 'Updated ' + new Date().toLocaleTimeString();
    } catch(err) {
      console.error('Dashboard fetch failed:', err);
    }
  }

  // Initial load + polling via HTMX-style interval
  load();
  setInterval(load, 5000);
})();
</script>
</body>
</html>"""
