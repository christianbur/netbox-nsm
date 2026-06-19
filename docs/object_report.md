# Daily Object Report

The object report is a scheduled background job that audits the NSM address
layer (`nsm_address` / `nsm_address_group` Custom Objects and their IPAM links)
once per day. The latest result is viewable and a fresh run can be started
manually from the menu.

**Menu:** NSM → **Configuration → Object Report**
(`plugins:netbox_nsm:object_report`)

**URL:** `/plugins/netbox-nsm/object-report/`

## What it checks

| Key | Check | How it is computed |
|-----|-------|--------------------|
| `status_mismatch` | NSM address `status` differs from the status mapped from its linked IPAM object | Streams the address table per IPAM content type with `.iterator()`, resolves IPAM statuses in bounded `pk__in` batches, maps via the Object Builder `status_map`, buckets by `(expected, actual)` pair. |
| `ipam_duplicates` | More than one NSM address points at the same IPAM resource | Pure DB `values('address_content_type_id', 'address_object_id').annotate(Count('id')).filter(c__gt=1)`. ContentType / model-class lookups are cached per content type so sampling does not re-query. |
| `ipam_orphans` | NSM address objects with **no** IPAM reference at all | Iterates only the rows whose polymorphic IPAM link is empty (`address_object_id__isnull=True`) — the small non-linked tail of the table. Intentional literal-network objects (e.g. `0.0.0.0/0` stored as `nsm_config` in `comments`) are detected via `get_network_literal` and excluded (reported separately as `literal_skipped`). |
| `multi_group` | An NSM address is a member of more than one address group | Pure DB aggregation on the group membership through-table: `values(member).annotate(Count(group, distinct=True)).filter(c__gt=1)`. Sample objects are resolved in a single batched query (no per-sample lookup). |
| `empty_groups` | Address groups with no members | Set difference between all group pks and the distinct group pks present in the membership through-table. |
| `single_member_groups` | Address groups that wrap exactly one member | Through-table aggregation `values(group).annotate(Count(member, distinct=True)).filter(c=1)`. Flags redundant single-address groups. |
| `similar_groups` | Address groups with highly overlapping membership (duplicate / redundancy) | Loads group membership from the through-table only (group-level, not per-address scan). Member identity is IPAM `content_type_id` + `object_id` when linked, else address pk. Groups with ≥ 3 members are compared via an inverted member index (member → groups); pairs are reported when they share ≥ 3 members and both groups have 3–4 members, or when `overlap / min(size) ≥ 0.75`. Breakdown buckets by Jaccard score; samples list group pairs. Names/URLs are resolved only for the sampled pairs. |
| `deprecated` | Deprecated NSM address / group objects | `filter(status='deprecated')` count + capped sample. |

## Export (TOML)

The **Checks** card has an **Export TOML** button
(`btn btn-sm btn-outline-secondary` + `mdi mdi-download`) that downloads the
full last run as a structured TOML document
(`format = "netbox-nsm-object-report-v1"`).

- **Server-side**, not a DOM scrape: the report is already a structured payload
  on `Job.data`, so the export reproduces *every* check — including the grouped
  breakdown buckets and the structured detail samples that the collapsible
  sample rows render — without re-running any analysis. This is more complete
  and robust than scraping the rendered (and partly collapsed) table, and keeps
  the format consistent with the rulebook-rules TOML export.
- The endpoint is the report view itself with `?export=toml`
  (`/plugins/netbox-nsm/object-report/?export=toml`); it enforces the same
  `VIEW_CUSTOM_OBJECT_TYPE` permission and returns
  `Content-Type: application/toml` as an attachment
  (`nsm_object_report_<timestamp>.toml`). When no run exists yet it redirects
  back with an info message.
- A tiny hand-rolled writer (`object_report/toml_export.py`) is used so the
  plugin does not depend on a third-party TOML writer being installed; values
  are escaped the same way as the JS rules export.

Document shape:

```toml
format = "netbox-nsm-object-report-v1"
plugin_version = "…"
generated_at = "…"
exported_at = "…"
findings_total = 12

[totals]
addresses = 57000
ipam_linked = 50000
groups = 480

[[checks]]
key = "ipam_duplicates"
title = "Multiple address objects per IPAM resource"
enabled = true
findings = 3
excess_objects = 3

[[checks.breakdown]]
label = "ipaddress"
count = 3

[[checks.samples]]
name = "1.2.3.4/32"
ipam_type = "ipaddress"
address_count = 2
```

## Scaling to > 1,000,000 objects

The analysis is **aggregated, never materialized**:

- Duplicate and multi-group checks are single grouped DB queries — no Python
  loop over the full table, no N+1.
- The status check streams rows with `.iterator(chunk_size=…)` and resolves IPAM
  statuses in bounded `pk__in` batches, so memory stays flat.
- Each check persists only **counts**, **grouped breakdowns**, and a **capped
  list of samples** (`DEFAULT_SAMPLE_LIMIT`, default 500). The stored JSON and the
  rendered HTML never contain the full object set — the cap is a fixed upper
  bound independent of how many objects exist.

## Sample pagination

Each check's collapsible sample list is **paginated client-side** in
`SAMPLE_PAGE_SIZE` (50) steps. The full *stored* sample set (up to
`DEFAULT_SAMPLE_LIMIT`) is rendered into the DOM once and the paginator
(`plugin_assets/js/object_report_samples.js`) shows one page at a time with
**Previous / Next** buttons and a `start–end of total` status line.

- **Client-side, not server-side**, because the bounded sample set is already
  in `Job.data`; paging this way needs no extra requests and cannot re-trigger
  any analysis. Re-running a check per page would be expensive and most checks
  cannot cheaply `OFFSET`. The server-side cap (`DEFAULT_SAMPLE_LIMIT`) keeps
  this safe regardless of total object count.
- If a check has more findings than the stored cap, the pager shows
  `… of <stored> (of <total> total)` so it is clear that only the first
  `DEFAULT_SAMPLE_LIMIT` are browsable.

## Job mechanism (NetBox 4.5/4.6)

`ObjectReportJob` (`netbox_nsm/object_report/jobs.py`) is a NetBox `JobRunner` registered
with the native scheduler:

```python
@system_job(interval=JobIntervalChoices.INTERVAL_DAILY)  # 1440 minutes
class ObjectReportJob(JobRunner):
    class Meta:
        name = "NSM Object Report"
    def run(self, *args, **kwargs):
        report = build_object_report()
        self.job.data = report
        self.job.save(update_fields=["data"])
```

- The `@system_job` decorator registers the class in `registry['system_jobs']`.
  The plugin imports the module in `SecurityConfig.ready()` so the decorator runs.
- At RQ-worker startup, NetBox's `rqworker` command calls `enqueue_once()` for
  every registered system job (idempotent daily schedule). `JobRunner.handle()`
  re-schedules the next run after each execution.
- **Manual run:** the view calls `ObjectReportJob.enqueue(user=…)` for an
  immediate one-off run (independent of the recurring schedule). Requires a
  running RQ worker.

### Backward compatibility

Existing `Job` rows created before the rename used the name `"NSM Audit Report"`.
Lookups (`get_latest_object_report_job`, `get_pending_object_report_job`) match
both the current name and the legacy name so stored reports keep displaying.
New runs are registered under `"NSM Object Report"`.

## Persistence

The report payload is stored on the run's `Job.data` (JSONField). The viewer
reads the most recent **completed** job via `get_latest_object_report_job()`, so
display never recomputes. No extra model or migration is required; retention
follows NetBox's normal `Job` housekeeping.

## Reuse from REST / scripts

The analysis is plain Python and safe to call anywhere:

```python
from netbox_nsm.object_report.object_report import build_object_report
report = build_object_report(sample_limit=50)
```

```bash
docker compose exec netbox python manage.py shell -c \
  "from netbox_nsm.object_report.object_report import build_object_report; print(build_object_report()['findings_total'])"
```

[← docs](README.md)
