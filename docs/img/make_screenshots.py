#!/usr/bin/env python3
"""Screenshot-Skript für netbox-nsm Plugin Dokumentation.

Alle Funktionen — vollständige Abdeckung aller Plugin-Seiten.
Konfigurierte Object-IDs (Stand: 2026-06):
  typeconfig_pk  = 5
  rulebook_zone  = 4   (TrustSec Infra — zone-based, 11 rules, gute Feldstruktur)
  rulebook_big   = 3   (TrustSec Core — 48 rules, für Policy Rules)
  rulebook_addr  = 6   (fw-dc-inter-zone — address+zone)
  rulebook_demo  = 1   (Demo Zone Matrix — 6 rules, 4 zones, matrix doc example)
  rulebook_demo_addr = 2  (Demo - Addresses — Starter-Demo, address-based)
  addr_ct_id     = 234  (nsm_addresses ContentType — Enterprise DC demo)
  addr_g4_pk     = 103  (address group g4)
  addr_g3_pk     = 102  (address group g3)
  rule_rich      = 13  (prod-to-integration-1, meiste Objekte)
  prefix_pk      = 6   (10.1.0.0/16 — prod direct, trust inherited from 10.0.0.0/8)
  assign_pfx_pk  = 6   (Assign Link screenshots — same prefix; propagation dropdown)
  ip_pk          = 501 (10.0.0.10/24)
  device_pk      = 29  (HV-DEV2-01 — hat NSM-Link)
  zone_pk        = 1   (prod — Security Panel mit Rulebooks, Prefix, VMs)
  pfx_ct_id      = 95
"""

from playwright.sync_api import sync_playwright
import time, os

BASE = "https://netbox-dev.anwx.de"
OUT  = "/home/christian/homelab/docker/netbox_dev/netbox-nsm/docs/img"

# ── Konfigurierte IDs ────────────────────────────────────────────────────────
TC_PK       = 5
RB_ZONE     = 4
RB_BIG      = 3
RB_ADDR     = 6
RB_DEMO     = 1
RB_DEMO_ADDR = 2
ADDR_CT_ID  = 234
ADDR_G4_PK  = 103
ADDR_G3_PK  = 102
RULE_PK     = 13
PREFIX_PK   = 6
ASSIGN_PFX_PK = 6
IP_PK       = 501
DEVICE_PK   = 29
ZONE_PK     = 1
PFX_CT_ID   = 95
VM_NAME     = "app-01-test-1"   # Enterprise DC demo — zone test-1
# ─────────────────────────────────────────────────────────────────────────────

PAGES = [
    # ── Navigation & Konfiguration ──────────────────────────────────────────
    ("01-navigation.png",
     f"{BASE}/plugins/netbox-nsm/setup/",
     "Navigationsmenü — Security-Bereich geöffnet"),

    ("01-setup.png",
     f"{BASE}/plugins/netbox-nsm/setup/",
     "Setup — 4 Sections (Menu, COTs, TypeConfig, Demo)"),

    ("02-type-config-list.png",
     f"{BASE}/plugins/netbox-nsm/type-config/",
     "TypeConfig-Liste"),

    ("03-type-config-detail.png",
     f"{BASE}/plugins/netbox-nsm/type-config/{TC_PK}/",
     "TypeConfig-Detail"),

    # ── Custom Objects (via netbox-custom-objects) ──────────────────────────
    ("04-object-list.png",
     f"{BASE}/plugins/custom-objects/nsm_addresses/",
     "nsm_addresses — Objekt-Liste"),

    ("05-object-detail.png",
     f"{BASE}/plugins/custom-objects/nsm_addresses/1/",
     "nsm_addresses — Objekt-Detail"),

    ("06-object-groups.png",
     f"{BASE}/plugins/custom-objects/nsm_zones/",
     "nsm_zones — Zonen-Liste"),

    ("07-zone-detail.png",
     f"{BASE}/plugins/custom-objects/nsm_zones/{ZONE_PK}/",
     "nsm_zones — Zonen-Detail (prod) mit Security Panel"),

    ("08-builtin-types.png",
     f"{BASE}/plugins/custom-objects/custom-object-types/",
     "Custom Object Types — Übersicht aller Built-in Types"),

    # ── Security Policies ───────────────────────────────────────────────────
    ("05-rulebook-list.png",
     f"{BASE}/plugins/netbox-nsm/rulebooks/",
     "Rulebook-Liste — All Rules (read-only), Hierarchie, Spalten"),

    ("06-rulebook-detail.png",
     f"{BASE}/plugins/netbox-nsm/rulebooks/{RB_BIG}/",
     "Rulebook-Detail — Enterprise - TrustSec Core, Fields-Hierarchie"),

    ("07-policy-rules.png",
     f"{BASE}/plugins/netbox-nsm/rulebooks/{RB_BIG}/rules/"
     "?group_by=col:Source::Zones&nsm_q=Name(server+OR+db)+AND+Source.Zones(dmz)",
     "Rules-Tab — AG Grid, Gruppierung Source.Zones, Filter-Query, Pills"),

    ("07-policy-rules-demo-group.png",
     f"{BASE}/plugins/netbox-nsm/rulebooks/{RB_DEMO}/rules/"
     "?nsm_q=view(group)",
     "Rules — Demo Zone Matrix, Group view (view(group), 7 rules)"),

    ("09-zone-matrix.png",
     f"{BASE}/plugins/netbox-nsm/rulebooks/{RB_BIG}/matrix/",
     "Matrix-Tab — Enterprise TrustSec Core (AG Grid)"),

    ("09-zone-matrix-demo-undirected.png",
     f"{BASE}/plugins/netbox-nsm/rulebooks/{RB_DEMO}/rules/"
     "?nsm_q=Destination.Zones(dmz+OR+mgmt)+AND+Source.Zones(dmz+OR+mgmt)+AND+view(matrix)"
     "&matrix_row=col:Source::Zones&matrix_col=col:Destination::Zones"
     "&mode=undirected&src_q=dmz+OR+mgmt&dst_q=dmz+OR+mgmt",
     "Matrix — Demo Zone Matrix (undirected, dmz/mgmt 2×2 subset — primary doc example)"),

    ("09-zone-matrix-demo-directed.png",
     f"{BASE}/plugins/netbox-nsm/rulebooks/{RB_DEMO}/rules/"
     "?nsm_q=view(matrix)&matrix_row=col:Source::Zones&matrix_col=col:Destination::Zones"
     "&src_q=dmz+OR+mgmt&dst_q=dmz+OR+mgmt",
     "Matrix — Demo Zone Matrix (full 4×4 grid, view(matrix) — doc reference)"),

    ("10-security-policy-address.png",
     f"{BASE}/plugins/netbox-nsm/rulebooks/{RB_ADDR}/rules/",
     "Rules mit Address-Objekten"),

    ("10-ip-analysis.png",
     f"{BASE}/plugins/netbox-nsm/rulebooks/{RB_ZONE}/ipanalysis/"
     f"?ip_ct={ADDR_CT_ID}&ip_pk={ADDR_G4_PK}&ip_name=g4"
     f"&ip2_ct={ADDR_CT_ID}&ip2_pk={ADDR_G3_PK}&ip2_name=g3",
     "IP Analysis — TrustSec Infra, g4 vs g3, CSV copy paths"),

    # ── Security Rule Add / Detail ──────────────────────────────────────────
    ("11-rule-add.png",
     f"{BASE}/plugins/netbox-nsm/rules/add/?rulebook={RB_DEMO_ADDR}",
     "Add Security Rule — Demo - Addresses, Objects tabs, Type/Elements picker"),

    ("11-security-rule-detail.png",
     f"{BASE}/plugins/netbox-nsm/rules/{RULE_PK}/",
     "Security Rule Detail — Source/Dest Trees, CSV-Export"),

    # ── Object Analyzer ─────────────────────────────────────────────────────
    ("11-object-analyzer.png",
     f"{BASE}/plugins/netbox-nsm/object-analyzer/",
     f"Object Analyzer — VM {VM_NAME}, Links/Zone/Rulebooks (interaktiv)"),

    # ── Security Panel auf IPAM/DCIM-Objekten ───────────────────────────────
    # Prefix 10.1.0.0/16 (PK 6): prod (direct zone + address FK), trust (inherited from 10.0.0.0/8)
    ("12-prefix-security-panel.png",
     f"{BASE}/ipam/prefixes/{PREFIX_PK}/",
     "Prefix 10.1.0.0/16 — Security Panel (direct + inherited)"),

    ("15-prefix-security-tab.png",
     f"{BASE}/ipam/prefixes/{PREFIX_PK}/",
     "Prefix 10.1.0.0/16 — Security-Tab (gleiches Bild wie 12-prefix-security-panel)"),

    ("13-ipaddress-nsm-panel.png",
     f"{BASE}/ipam/ip-addresses/{IP_PK}/",
     "IP-Adresse — Security Panel (inherited)"),

    ("16-ipaddress-security-tab.png",
     f"{BASE}/ipam/ip-addresses/{IP_PK}/",
     "IP-Adresse — Security-Tab"),

    ("17-assign-picker.png",
     f"{BASE}/plugins/netbox-nsm/object-link/assign/"
     f"?ct_id={PFX_CT_ID}&obj_id={ASSIGN_PFX_PK}&return_url=/ipam/prefixes/{ASSIGN_PFX_PK}/",
     "Assign Link — New Link form (Link type closed)"),

    ("17-assign-link-propagation-types.png",
     f"{BASE}/plugins/netbox-nsm/object-link/assign/"
     f"?ct_id={PFX_CT_ID}&obj_id={ASSIGN_PFX_PK}&return_url=/ipam/prefixes/{ASSIGN_PFX_PK}/",
     "Assign Link — Link type dropdown (all propagation modes)"),

    ("14-device-security-panel.png",
     f"{BASE}/dcim/devices/{DEVICE_PK}/",
     "Device — Security Panel"),

    ("12-security-policy-labels.png",
     f"{BASE}/plugins/netbox-nsm/rulebooks/{RB_BIG}/rules/",
     "Rules — farbige Labels / colored Pills"),

    ("13-custom-object-assignments.png",
     f"{BASE}/plugins/netbox-nsm/rulebooks/{RB_ADDR}/rules/",
     "Rules — Custom Object Assignments"),
]


def login(page):
    page.goto(f"{BASE}/login/")
    page.wait_for_load_state("networkidle")
    page.fill("#id_username", "admin")
    page.fill("#id_password", "Chip123!")
    page.click("[type=submit]")
    page.wait_for_load_state("networkidle")
    print("  [login] OK")


def _capture_object_analyzer(page, vm_name):
    """Search VM, run Analyse, expand prefix + zone for the doc screenshot."""
    page.goto(f"{BASE}/plugins/netbox-nsm/object-analyzer/")
    page.wait_for_load_state("networkidle")
    page.fill("#nsm-oa-search", vm_name)
    time.sleep(1.2)
    item = page.query_selector(".nsm-oa-drop-item")
    if item:
        item.click()
        time.sleep(0.4)
    page.click("button[type=submit].btn-primary")
    page.wait_for_selector(".react-flow__node", timeout=15000)
    time.sleep(1.5)
    # Expand prefix (interfaces/label) and zone (rulebooks) if visible
    for label in ("10.0.1.0/24", "test-1"):
        node = page.query_selector(f".react-flow__node:has-text('{label}')")
        if node:
            node.click()
            time.sleep(0.8)
    zone_grp = page.query_selector(".react-flow__node:has-text('Zone ·')")
    if zone_grp:
        zone_grp.click()
        time.sleep(0.6)
    rb = page.query_selector(".react-flow__node:has-text('Rulebook')")
    if rb:
        rb.click()
        time.sleep(0.6)


def _capture_assign_link_propagation(page, url):
    """Open Assign Link page and expand Link type dropdown for doc screenshot."""
    page.goto(url)
    page.wait_for_load_state("networkidle")
    time.sleep(0.5)
    sel = page.locator("#id_propagation")
    if sel.count():
        sel.click()
        time.sleep(0.4)


def screenshot(page, filename, url, description=""):
    if not url:
        print(f"  [{filename}] SKIP (no URL)")
        return
    print(f"  [{filename}] {description}")
    if filename == "11-object-analyzer.png":
        _capture_object_analyzer(page, VM_NAME)
    elif filename == "17-assign-link-propagation-types.png":
        _capture_assign_link_propagation(page, url)
    else:
        page.goto(url)
        page.wait_for_load_state("networkidle")
    time.sleep(0.8)
    # Aufklappen von Navigation-Accordion falls nötig (Security-Menü)
    try:
        nav_btn = page.query_selector("a.nav-link[href*='netbox-nsm'], button[aria-controls*='security']")
        if nav_btn:
            nav_btn.click()
            time.sleep(0.3)
    except Exception:
        pass
    out_path = os.path.join(OUT, filename)
    page.screenshot(path=out_path, full_page=True)
    size_kb = os.path.getsize(out_path) // 1024
    print(f"    → gespeichert ({size_kb} KB)")


# ── Chromium-Pfad (NixOS) ────────────────────────────────────────────────────
import subprocess
try:
    CHROMIUM = subprocess.check_output(
        ["bash", "-c", "ls /nix/store/*/bin/chromium 2>/dev/null | head -1"],
        text=True
    ).strip()
except Exception:
    CHROMIUM = None

if not CHROMIUM:
    # Fallback: system chromium
    CHROMIUM = "chromium"

print(f"Chromium: {CHROMIUM}")

with sync_playwright() as pw:
    launch_opts = dict(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
    if CHROMIUM and CHROMIUM != "chromium":
        launch_opts["executable_path"] = CHROMIUM

    browser = pw.chromium.launch(**launch_opts)
    ctx = browser.new_context(
        viewport={"width": 1440, "height": 900},
        device_scale_factor=1,
    )
    page = ctx.new_page()

    login(page)

    for filename, url, description in PAGES:
        try:
            screenshot(page, filename, url, description)
        except Exception as e:
            print(f"  [{filename}] FEHLER: {e}")

    browser.close()
    print("\n✓ Alle Screenshots gespeichert.")
