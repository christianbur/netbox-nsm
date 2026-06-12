# Running tests

NetBox NSM uses Django’s built-in test runner (`manage.py test`), not pytest. GitHub CI runs the same command against a fresh PostgreSQL database.

## Homelab dev container (`docker/netbox_dev`)

In the homelab stack, the plugin is bind-mounted into the NetBox container:

| Path | Role |
|------|------|
| Host: `docker/netbox_dev/netbox-nsm/` | Your working copy |
| Container: `/opt/netbox-nsm/` | Editable plugin install |
| Container: `/opt/netbox/netbox/manage.py` | NetBox test runner |

Start the stack from the homelab repo:

```bash
cd docker/netbox_dev
docker compose up -d netbox netbox-dev-db netbox-dev-redis
```

### Full suite (matches CI)

From `docker/netbox_dev/`:

```bash
docker compose exec netbox python /opt/netbox/netbox/manage.py test netbox_nsm.tests --parallel -v2
```

This recreates the `test_netbox` database on each run (no `--keepdb`), same as [`.github/workflows/test.yml`](../.github/workflows/test.yml).

### Faster local runs

Keep the test database between runs:

```bash
docker compose exec netbox python /opt/netbox/netbox/manage.py test netbox_nsm.tests --keepdb -v2
```

Run one module or one test:

```bash
docker compose exec netbox python /opt/netbox/netbox/manage.py test \
  netbox_nsm.tests.test_rulebook_rules_tab --keepdb -v2

docker compose exec netbox python /opt/netbox/netbox/manage.py test \
  netbox_nsm.tests.test_rulebook_rules_tab.RulebookRulesLayoutTests.test_object_cells_render_all_items_without_js_expand \
  --keepdb -v2
```

Add `-T` to `docker compose exec` when piping output in scripts; omit it in an interactive terminal.

### Reset a broken test database

If `--keepdb` runs show odd failures (duplicate users, stale data), drop the test DB and run without `--keepdb`:

```bash
docker compose exec netbox-db psql -U netbox -c 'DROP DATABASE IF EXISTS test_netbox;'
docker compose exec netbox python /opt/netbox/netbox/manage.py test netbox_nsm.tests --parallel -v2
```

### Code formatting (Black)

CI uses `psf/black@stable` on the `netbox_nsm` package. Check locally:

```bash
pip install 'black[colorama]==26.5.1'
black --check netbox_nsm
black netbox_nsm   # apply fixes
```

Inside the dev container, Black is not pre-installed; run it on the host against the bind-mounted tree.

## Standalone NetBox install

If NetBox is installed directly on a host (see [CONTRIBUTING.md](../CONTRIBUTING.md)):

```bash
source /opt/netbox/venv/bin/activate
cd /opt/netbox/netbox
python manage.py test netbox_nsm.tests --parallel -v2
```

Install the plugin in editable mode first: `pip install -e /path/to/netbox-nsm`.

## What CI runs

| Workflow | Trigger | Command |
|----------|---------|---------|
| **Lint** (`.github/workflows/black.yml`) | `pull_request`; `push` to `main` | `black --check netbox_nsm` |
| **Test with NetBox** (`.github/workflows/test.yml`) | same | Checkout NetBox `main` + `netbox-custom-objects`, migrate, then `python netbox/manage.py test netbox_nsm.tests --parallel -v2` |

CI uses **Python 3.12** on `ubuntu-latest`. The dev container may use a newer Python (e.g. 3.14); behaviour should match, but re-run without `--keepdb` before trusting a green local run.

Pushes to feature branches with an open PR do **not** start duplicate push + pull_request jobs — only the PR workflow runs until merge to `main`.

## Test layout

Tests live under `netbox_nsm/tests/`. Shared bases and GraphQL helpers are in `netbox_nsm/tests/custom.py`. The suite covers REST API (including `test_ip_analysis_rest_api`), rulebook/rules/matrix views, Security Panel, setup wizard, and related utilities.
