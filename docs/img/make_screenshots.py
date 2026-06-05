#!/usr/bin/env python3
"""Screenshot-Skript für netbox-nsm Plugin Dokumentation.

Alle Funktionen — vollständige Abdeckung aller Plugin-Seiten.
Konfigurierte Object-IDs (Stand: 2026-06):
  typeconfig_pk  = 5
  rulebook_zone  = 4   (TrustSec Infra — zone-based, 11 rules, gute Feldstruktur)
  rulebook_big   = 3   (TrustSec Core — 48 rules, für Policy/Analysis)
  rulebook_addr  = 6   (fw-dc-inter-zone — address+zone, für IP-Analysis)
  rulebook_demo  = 1   (Demo Zone Matrix — 6 rules, für Zone-Matrix)
  rule_rich      = 13  (prod-to-integration-1, meiste Objekte)
  prefix_pk      = 6   (10.1.0.0/16 — hat NSM-Link)
  ip_pk          = 501 (10.0.0.10/24)
  device_pk      = 29  (HV-DEV2-01 — hat NSM-Link)
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
RULE_PK     = 13
PREFIX_PK   = 6
IP_PK       = 501
DEVICE_PK   = 29
PFX_CT_ID   = 95
# ─────────────────────────────────────────────────────────────────────────────

IP_ANALYSIS = (
    f"?ip_ct={PFX_CT_ID}&ip_pk={PREFIX_PK}&ip_name=10.1.0.0%2F16"
    f"&ip_ct_b={PFX_CT_ID}&ip_pk_b={PREFIX_PK}&ip_name_b=10.1.0.0%2F16"
)

PAGES = [
    # ── Navigation & Konfiguration ──────────────────────────────────────────
    ("01-navigation.png",
     f"{BASE}/plugins/netbox-nsm/setup/",
     "Navigationsmenü — Security-Bereich geöffnet"),

    ("01-setup.png",
     f"{BASE}/plugins/netbox-nsm/setup/",
     "Setup-Wizard"),

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

    ("07-object-group-detail.png",
     f"{BASE}/plugins/custom-objects/nsm_zones/1/",
     "nsm_zones — Zonen-Detail"),

    ("08-builtin-types.png",
     f"{BASE}/plugins/custom-objects/custom-object-types/",
     "Custom Object Types — Übersicht aller Built-in Types"),

    ("09-yaml-bundle.png",
     f"{BASE}/plugins/netbox-nsm/setup/",
     "Setup — Schema-Bundle / YAML-Import"),

    # ── Security Policies ───────────────────────────────────────────────────
    ("05-rulebook-list.png",
     f"{BASE}/plugins/netbox-nsm/rulebooks/",
     "Rulebook-Liste"),

    ("06-rulebook-detail.png",
     f"{BASE}/plugins/netbox-nsm/rulebooks/{RB_ZONE}/",
     "Rulebook-Detail — Felder & Konfiguration"),

    ("07-policy-rules.png",
     f"{BASE}/plugins/netbox-nsm/rulebooks/{RB_BIG}/rules/",
     "Rules-Tab — Regeln mit farbigen Pills"),

    ("08-policy-analysis.png",
     f"{BASE}/plugins/netbox-nsm/rulebooks/{RB_BIG}/analysis/",
     "Analysis-Tab — Statistiken"),

    ("09-zone-matrix.png",
     f"{BASE}/plugins/netbox-nsm/rulebooks/{RB_DEMO}/matrix/",
     "Matrix-Tab (AG Grid)"),

    ("10-ip-analysis.png",
     f"{BASE}/plugins/netbox-nsm/rulebooks/{RB_ADDR}/ipanalysis/{IP_ANALYSIS}",
     "IP-Analysis — Copy & CSV-Export"),

    ("10-security-policy-address.png",
     f"{BASE}/plugins/netbox-nsm/rulebooks/{RB_ADDR}/rules/",
     "Rules mit Address-Objekten"),

    # ── Security Rule Detail ────────────────────────────────────────────────
    ("11-security-rule-detail.png",
     f"{BASE}/plugins/netbox-nsm/rules/{RULE_PK}/",
     "Security Rule Detail — Source/Dest Trees, CSV-Export"),

    # ── Object Analyzer ─────────────────────────────────────────────────────
    ("11-object-analyzer.png",
     f"{BASE}/plugins/netbox-nsm/object-analyzer/",
     "Object Analyzer — leer"),

    # ── Security Panel auf IPAM/DCIM-Objekten ───────────────────────────────
    ("12-prefix-nsm-panel.png",
     f"{BASE}/ipam/prefixes/{PREFIX_PK}/",
     "Prefix — Security Panel"),

    ("12b-prefix-security-linked.png",
     f"{BASE}/ipam/prefixes/{PREFIX_PK}/",
     "Prefix — Security Panel mit Link"),

    ("14-prefix-security-panel-filled.png",
     f"{BASE}/ipam/prefixes/{PREFIX_PK}/",
     "Prefix — Security Panel gefüllt"),

    ("15-prefix-security-tab.png",
     f"{BASE}/ipam/prefixes/{PREFIX_PK}/",
     "Prefix — Security-Tab mit Links"),

    ("13-ipaddress-nsm-panel.png",
     f"{BASE}/ipam/ip-addresses/{IP_PK}/",
     "IP-Adresse — Security Panel (inherited)"),

    ("16-ipaddress-security-tab.png",
     f"{BASE}/ipam/ip-addresses/{IP_PK}/",
     "IP-Adresse — Security-Tab"),

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


def screenshot(page, filename, url, description=""):
    if not url:
        print(f"  [{filename}] SKIP (no URL)")
        return
    print(f"  [{filename}] {description}")
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
