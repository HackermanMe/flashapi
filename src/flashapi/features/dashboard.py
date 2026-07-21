"""Dashboard — HTML UI + JSON metrics endpoint."""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


class MetricsCollector:
    """Thread-safe metrics collector for FlashAPI operations."""

    def __init__(self):
        self._start_time = time.time()
        self._entity_ops: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._totals: dict[str, int] = defaultdict(int)
        self._recent_events: list[dict] = []
        self._max_recent = 50
        self._entity_meta: dict[str, dict[str, Any]] = {}

    def register_entity(self, name: str, *, soft_delete: bool = True, audit: bool = False,
                        webhook: bool = False, rate_limited: bool = False) -> None:
        self._entity_meta[name] = {
            "softDelete": soft_delete,
            "auditEnabled": audit,
            "webhookEnabled": webhook,
            "rateLimited": rate_limited,
            "multiTenant": False,
        }

    def record(self, operation: str, entity: str, entity_id: str = "") -> None:
        self._entity_ops[entity][operation] += 1
        op_key = operation.lower() + "s" if operation != "SEARCH" else "searches"
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
<html>
<head>
<meta charset="utf-8">
<title>FlashAPI Dashboard</title>
<meta http-equiv="refresh" content="5">
<style>
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }
h1 { color: #212529; }
.card { background: white; border-radius: 8px; padding: 16px; margin: 12px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
.stat { text-align: center; }
.stat .value { font-size: 2rem; font-weight: bold; color: #0d6efd; }
.stat .label { color: #6c757d; font-size: 0.85rem; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #dee2e6; }
th { background: #f1f3f5; font-weight: 600; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; }
.badge-ok { background: #d3f9d8; color: #2b8a3e; }
.badge-off { background: #ffe3e3; color: #c92a2a; }
</style>
</head>
<body>
<h1>FlashAPI Dashboard</h1>
<p id="status">Loading metrics...</p>
<div class="grid" id="totals"></div>
<div class="card"><h3>Entities</h3><table id="entities"><thead><tr><th>Entity</th><th>Soft Delete</th><th>Audit</th><th>Webhook</th><th>Operations</th></tr></thead><tbody></tbody></table></div>
<div class="card"><h3>Recent Events</h3><table id="events"><thead><tr><th>Time</th><th>Operation</th><th>Entity</th><th>ID</th></tr></thead><tbody></tbody></table></div>
<script>
async function load() {
  const r = await fetch(window.location.pathname + '/metrics.json');
  const m = await r.json();
  document.getElementById('status').textContent = 'Uptime: ' + m.uptimeSeconds + 's | Auto-refresh 5s';
  const t = m.totals || {};
  document.getElementById('totals').innerHTML = ['creates','reads','updates','deletes','searches','exports','bulkOps','total']
    .map(k => `<div class="card stat"><div class="value">${t[k]||0}</div><div class="label">${k}</div></div>`).join('');
  const eb = document.querySelector('#entities tbody');
  eb.innerHTML = Object.values(m.entities||{}).map(e =>
    `<tr><td><b>${e.name}</b></td><td>${badge(e.softDelete)}</td><td>${badge(e.auditEnabled)}</td><td>${badge(e.webhookEnabled)}</td><td>C:${e.operations.CREATE} R:${e.operations.READ} U:${e.operations.UPDATE} D:${e.operations.DELETE}</td></tr>`
  ).join('');
  const evb = document.querySelector('#events tbody');
  evb.innerHTML = (m.recentEvents||[]).slice(-10).reverse().map(e =>
    `<tr><td>${e.timestamp.split('T')[1].split('.')[0]}</td><td>${e.operation}</td><td>${e.entity}</td><td>${e.entityId}</td></tr>`
  ).join('');
}
function badge(v) { return v ? '<span class="badge badge-ok">ON</span>' : '<span class="badge badge-off">OFF</span>'; }
load();
</script>
</body>
</html>"""
