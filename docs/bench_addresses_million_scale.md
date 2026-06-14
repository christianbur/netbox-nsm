# Bench: 200k addresses + 13k rules (COT rulebooks)

Standalone load generator for performance and UI testing. **Not** part of the Setup wizard.

Policy rules are stored as **Custom Object rows** on a deployed COT rulebook (`nsm_rb_bench_addresses`) with `source_addresses` / `destination_addresses` multiobject fields — **not** native `Rulebook` / `Rule` / `RuleObjectItem`.

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
   - **Import all types** (COTs: `nsm_address`, `nsm_service`, `nsm_action`, …)
   - **Create all TypeConfigs**
   - Or: Setup → **Starter demo** (creates default services/actions, etc.)

The script creates rulebook **`nsm_rb_bench_addresses`** if missing (template 0002 — addresses only).

## Data model

All bench objects use the `bench-` prefix (separate from setup demos `demo-*`).

### Address hierarchy (simplified for COT)

The old self-reference via `nsm_addresses.group` is gone. Instead:

```
2,000 subnets   bench-net-00000 … bench-net-01999   (nsm_address + ipam.Prefix /24)
  └─ up to 200,000 hosts   bench-ip-0000000 …       (nsm_address + ipam.IPAddress /32 + prefix FK)
```

IP space: consecutive `/24` blocks in **10.128.0.0/9** (2,000 subnets × 100 hosts).

Region/site containers (`bench-reg-*`, `bench-site-*`) are not created in the COT model (address groups only hold `nsm_address` members, no nested groups).

### Policy rules (COT)

Default **13,000** rules in `nsm_rb_bench_addresses`:

- Name: `bench-rule-00001` …
- **Source / destination:** 1–20 random leaf addresses each (deterministic seed)
- **Service / action:** built-in COT objects (`HTTPS`, `SSH`, … / `Permit`, `Deny`)

## Run

```bash
cd /home/christian/homelab/docker/netbox_dev
docker compose up -d netbox netbox-worker

# Full run (200k IPAM rows + rules — slow)
docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py

# Smoke test (seconds to a few minutes)
docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py \
  --leaf-count 1000 --rule-count 100

# Rules only (leaves already present)
docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py \
  --skip-addresses

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

### CLI options

| Option | Default | Description |
|--------|---------|-------------|
| `--rulebook-slug` | `nsm_rb_bench_addresses` | Target COT rulebook |
| `--rulebook-id` | — | Legacy: COT by primary key |
| `--leaf-count` | `200000` | Host address count |
| `--rule-count` | `13000` | COT rules |
| `--skip-addresses` | off | Skip IPAM + addresses |
| `--skip-rules` | off | Skip rules |
| `--keep-rules` | off | Do not delete existing `bench-rule-*` |
| `--purge` | off | Delete bench data and exit |

## Runtime / output

| Scale | Order of magnitude |
|-------|-------------------|
| 1,000 leaves + 100 rules | Seconds |
| 200,000 leaves | Many minutes (DB, disk, Postgres tuning) |
| 13,000 rules | Minutes (M2M assignments) |

Example output (smoke test):

```text
Rulebook Bench Addresses (nsm_rb_bench_addresses, pk=…): 1,000 leaves, 100 new rules, … multiobject assignments, 12.34s
```

Rulebook in UI: **Security → Rulebooks → Bench Addresses**.

## Related demos

| Demo | Rulebook | Script |
|------|----------|--------|
| Starter | `nsm_rb_demo` | Setup → Starter demo |
| Enterprise DC | (manual COT) | `netbox_nsm/demos/enterprise_dc/import.py` — rulebooks skipped |
