# Bench: 1M addresses + 13k rules

Standalone load generator for performance and UI testing. **Not** part of the Setup wizard
(unlike `create_demo_addresses_scale` in Setup → Demos).

## Files

| Path | Role |
|------|------|
| `scripts/create_addresses_million_scale.py` | CLI entry point |
| `netbox_nsm/demos/addresses_million_scale.py` | Implementation |

## Prerequisites

- `netbox-custom-objects` with built-in COTs (`nsm_addresses`, `nsm_services`, `nsm_action`)
- Target rulebook exists with fields **source**, **destination**, **service**, **action**  
  Default: pk **2** (`Demo - Addresses` — create via Setup demo or manually)

## Data model

All bench objects use the name prefix `bench-` (separate from Setup demos `demo-addr-*`).

### Nested `nsm_addresses` (field `group`)

```
100 regions     bench-reg-000 … bench-reg-099
  └─ 1 000 sites    bench-site-0000 … (10 per region)
      └─ 10 000 subnets   bench-net-00000 … (10 per site, each with ipam.Prefix /24)
          └─ 1 000 000 hosts   bench-ip-0000000 … (100 /32 hosts per subnet)
```

IP space: contiguous `/24` blocks in **10.128.0.0/9** (10.128.0.0/24 …).

Leaf addresses reference:

- `ip_address` → NetBox IPAM `/32`
- `prefix` → parent subnet `/24`
- `group` → parent subnet group (`bench-net-*`)

### Policy rules

Default **13 000** rules on the target rulebook:

- Name: `bench-rule-00001` …
- **Source / destination:** 1–20 random leaf addresses each (deterministic seed)
- **Service / action:** from built-in COT objects (`https`, `ssh`, … / `permit`, `deny`)

## Usage (netbox-dev)

After image build or with live mount `./netbox-nsm` → `/opt/netbox-nsm`:

```bash
# Full run — long (1M IPAM rows + 1M+ COT rows + 13k rules)
docker exec netbox-dev python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py

# Smoke test
docker exec netbox-dev python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py \
  --leaf-count 1000 --rule-count 100

# Rules only (leaves already present)
docker exec netbox-dev python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py \
  --skip-addresses

# Addresses only
docker exec netbox-dev python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py \
  --skip-rules

# Remove all bench-* data (+ linked bench IPAM)
docker exec netbox-dev python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py \
  --purge
```

### CLI options

| Option | Default | Description |
|--------|---------|-------------|
| `--rulebook-id` | `2` | Target rulebook primary key |
| `--leaf-count` | `1000000` | Leaf host addresses (max 1M with current hierarchy) |
| `--rule-count` | `13000` | Policy rules to create |
| `--skip-addresses` | off | Skip IPAM + COT creation |
| `--skip-rules` | off | Skip rule creation |
| `--keep-rules` | off | Do not delete existing `bench-rule-*` before create |
| `--purge` | off | Delete bench data and exit |

## Runtime expectations

| Scale | Rough order of magnitude |
|-------|---------------------------|
| 1 000 leaves + 100 rules | seconds |
| 1 000 000 leaves | tens of minutes to hours (DB size, disk, Postgres tuning) |
| 13 000 rules | minutes (bulk inserts) |

Monitor Postgres disk and run smaller `--leaf-count` first on limited hardware.

## Related

- Setup demo (6k rules, 80 zone/address pairs): Setup → **create_demo_addresses_scale**
- Zone scale demo (12k rules, 300 zones): `scripts/create_scale_demo.py`
