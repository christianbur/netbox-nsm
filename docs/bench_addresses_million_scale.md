# Bench: 200k addresses + 13k rules (COT rulebooks)

Standalone load generator for performance and UI testing. **Not** part of the Setup wizard (except the optional 50k subset via Setup → Address bench).

Policy rules are stored as **Custom Object rows** on a deployed COT rulebook (`nsm_rb_bench_addresses`) with polymorphic `source` / `destination` multiobject fields (addresses **and** address groups) — **not** native `Rulebook` / `Rule` / `RuleObjectItem`.

## Files

| Path | Role |
|------|------|
| `scripts/create_addresses_million_scale.py` | CLI entry point |
| `netbox_nsm/demos/addresses_million_scale.py` | Implementation |
| `netbox_nsm/demos/cot_demo_common.py` | Shared COT helpers |

## Prerequisites

1. Stack running: `cd docker/netbox_dev && docker compose up -d netbox netbox-worker`
2. Plugin mount active: `./netbox-nsm` → `/opt/netbox-nsm` (otherwise rebuild image)
3. NSM setup complete:
   - **Import all types** (Setup §2 — Custom Object Schema: COTs `nsm_address`, `nsm_address_group`, `nsm_service`, `nsm_action`, …; `nsm_config` is written into each type's `comments`)
   - Or: Setup → **Starter demo** (creates default services/actions, etc.)

The script creates rulebook **`nsm_rb_bench_addresses`** if missing (default portable schema with `source` / `destination` polymorphic address fields).

## Data model

All bench objects use the `bench-` prefix (separate from setup demos `demo-*`).

### Address hierarchy

```
2,000 subnets   bench-net-00000 … bench-net-01999   (nsm_address + ipam.Prefix /24)
  └─ up to 200,000 hosts   bench-ip-0000000 …       (nsm_address + ipam.IPAddress /32)
  └─ alias peers           bench-alias-0000000 …    (same IPAM /32, unique COT name;
                                                      comments carry bench_canonical=… + network=…)
  └─ dup-name peers        bench-dup-0000000 …       (overlap bucket only; same IPAM + comments)
  └─ wider parents         bench-net-wide-* /20, bench-net-super-* /16 (overlap bucket blocks)
  └─ 1 group per subnet    bench-grp-00000 …        (nsm_address_group; members = net + hosts)
  └─ overlap groups        bench-grp-ovlp-* …       (adjacent overlap subnets; shared members)
```

IP space: consecutive `/24` blocks in **10.128.0.0/9** (2,000 subnets × 100 hosts).

### Subnet mix (visible in IPA applet and rules)

| Type | Name pattern | IPAM | Role |
|------|--------------|------|------|
| Host | `bench-ip-*` | `/32` | Canonical leaf addresses |
| IPAM host | `bench-host-*` | — | VirtualMachine for overlap showcase leaves (rules 1–20) |
| IPAM interface | `bench-iface-*` | `/32` on VM | Assigned to the same `IPAddress` as the canonical `bench-ip-*` |
| Subnet | `bench-net-*` | `/24` | One per subnet; also group member |
| Wide | `bench-net-wide-*` | `/20` | Parent of 16 `/24` blocks (overlap bucket) |
| Super | `bench-net-super-*` | `/16` | Parent of 256 `/24` blocks (overlap bucket) |

All address types are included in the rule generator address pool (`source` / `destination`).

### Overlap bucket (~7.5% of hosts)

The **first** `overlap_leaves` hosts (and their subnets) form a dedicated overlap subset for duplicate/overlap analysis — without slowing the full 200k run:

| Mechanism | Global | Overlap bucket |
|-----------|--------|----------------|
| Alias stride | every 8th host | every 4th host |
| Dup-name rows | — | every 6th host (`bench-dup-*`, same `network=` in comments) |
| Parent prefixes | — | `/20` + `/16` for covered blocks |
| Overlap groups | — | `bench-grp-ovlp-*` pairs adjacent subnets (net + 5 hosts each) |

Natural containment overlap also exists everywhere: each `/24` contains its `/32` hosts; overlap-bucket `/20`/`/16` parents contain those `/24` subnets.

At **50k** scale: 3,750 overlap leaves across 38 subnets, plus ~3 `/20` and 1 `/16` parent objects.

Region/site containers are not created (address groups only hold `nsm_address` members).

### Policy rules (COT)

Default **13,000** rules in `nsm_rb_bench_addresses`:

- Name: `bench-rule-00001` …
- **Source / destination:** each side gets **1–8** random `nsm_address` refs **and** **1–5** random `nsm_address_group` refs (deterministic seeds), including `bench-grp-ovlp-*` overlap groups
- **Overlap showcase rules (1–20):** both **source** and **destination** address cells are populated (never empty). Each side gets **1–10** combined `nsm_address` + `nsm_address_group` refs (deterministic seed). Every cell includes an overlap bundle (at minimum a `/24` prefix plus a `/32` host from that subnet). Rules 1–5 additionally keep canonical + alias + dup on the same leaf before padding.

| Rules | Pattern (both sides) |
|-------|----------------------|
| `bench-rule-00001` … `00005` | canonical + alias + dup + `/24` (+ padded peers) |
| `bench-rule-00006` … `00010` | host + `/24` (+ `/20` + `/16` on rules 7, 9, 10) |
| `bench-rule-00011` … `00015` | overlap group + member subnets/hosts |
| `bench-rule-00016` … `00020` | host + prefix containment patterns |

**Rules UI cell display:** In **Stack** (lines) mode, multiple objects in one cell render as stacked lines within the **same rule row** — not split across table rows. Empty `-` in `source_addresses` while destination shows objects was a **data** issue (old generator alternated sides); use **Inline** / **Comma** mode for comma-separated pills. All showcase objects for one rule share one COT row.

For rules **1–20**, the generator also creates **VirtualMachine** + **VMInterface** rows (`bench-host-*`, `bench-iface-*`) for showcase leaf indices and assigns the existing `/32` IPAM address to the interface.

Exact object names depend on scale (`overlap_demo_rule_descriptions()` in Django shell; includes `ipam_host` and per-side `source_objects` / `destination_objects`). Open **Security → Rulebooks → Bench Addresses → Rules**, pick rule 1, expand source/destination, and use the cell loupe (IPA).

Rules **21+** use random picks with overlap-bucket bias (~55 %) but still **do not guarantee** co-selected peers in one cell.

Rules are bulk-created; M2M through rows are bulk-inserted in batches of 2,000.

## Run

```bash
cd /home/christian/homelab/docker/netbox_dev
docker compose up -d netbox netbox-worker

# Full run (200k IPAM rows + groups + rules — slow)
docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py

# Smoke test (seconds to a few minutes)
docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py \
  --leaf-count 1000 --rule-count 100

# Rules only (leaves/groups already present; leaf count inferred from DB)
docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py \
  --skip-addresses --rule-count 3250

# Addresses only
docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py \
  --skip-rules

# Remove bench data
docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py \
  --purge
```

Or via Django shell (same logic):

```bash
docker compose exec netbox python /opt/netbox/netbox/manage.py shell
```

```python
from netbox_nsm.demos.addresses_million_scale import create_addresses_million_scale
print(create_addresses_million_scale(leaf_count=1000, rule_count=100))
```

### Setup wizard (50k subset)

Setup → **Address bench (50,000 addresses)** queues `create_addresses_scale_demo_50k` on the RQ worker (same logic, proportional rule count). Requires a running worker container.

### CLI options

| Option | Default | Description |
|--------|---------|-------------|
| `--rulebook-slug` | `nsm_rb_bench_addresses` | Target COT rulebook |
| `--rulebook-id` | — | Legacy: COT by primary key |
| `--leaf-count` | `200000` | Host address count |
| `--rule-count` | `13000` | COT rules |
| `--skip-addresses` | off | Skip IPAM + addresses + groups |
| `--skip-rules` | off | Skip rules |
| `--keep-rules` | off | Do not delete existing `bench-rule-*` |
| `--purge` | off | Delete bench data and exit |

## Runtime / output

| Scale | Order of magnitude |
|-------|-------------------|
| 1,000 leaves + 100 rules | Seconds |
| 200,000 leaves + 2,000 groups | Many minutes (DB, disk, Postgres tuning) |
| 13,000 rules | Minutes (M2M assignments) |

Example output (smoke test):

```text
Rulebook Bench Addresses (nsm_rb_bench_addresses, pk=…): 1,000 leaves, 134 alias addresses, 13 dup-name addresses, 1 /20 + 1 /16 prefixes, 75 overlap leaves (1 subnets), 10 address groups + 0 overlap groups, 50 zones, 100 new rules, … multiobject assignments, 12.34s
```

Rulebook in UI: **Security → Rulebooks → Bench Addresses**.

## Related demos

| Demo | Rulebook | Script |
|------|----------|--------|
| Starter | `nsm_rb_demo` | Setup → Starter demo |
| Address bench 50k | `nsm_rb_bench_addresses` | Setup → Address bench (RQ) |
| Enterprise DC | (manual COT) | `netbox_nsm/demos/enterprise_dc/import.py` — rulebooks skipped |
