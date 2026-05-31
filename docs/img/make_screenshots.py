#!/usr/bin/env python3
"""Screenshot-Skript für netbox-nsm Plugin Dokumentation."""

from playwright.sync_api import sync_playwright
import time

BASE = "https://netbox-dev.anwx.de"
OUT  = "/home/christian/homelab/docker/netbox_dev/netbox-nsm/docs/img"

PAGES = [
    ("01-setup.png",          f"{BASE}/plugins/netbox-nsm/setup/"),
    ("02-type-config-list.png", f"{BASE}/plugins/netbox-nsm/type-config/"),
    ("03-type-config-detail.png", None),   # wird nach Laden von Liste dynamisch ermittelt
    ("04-object-builder.png", f"{BASE}/plugins/netbox-nsm/object-builder/config/"),
    ("05-rulebook-list.png",  f"{BASE}/plugins/netbox-nsm/security-policy/"),
    ("06-rulebook-detail.png", f"{BASE}/plugins/netbox-nsm/security-policy/4/"),
    ("07-policy-rules.png",   f"{BASE}/plugins/netbox-nsm/security-policy/4/policy/"),
    ("08-policy-analysis.png", f"{BASE}/plugins/netbox-nsm/security-policy/4/analysis/"),
    ("09-zone-matrix.png",    f"{BASE}/plugins/netbox-nsm/security-policy/4/zonematrix/"),
    ("10-ip-analysis.png",    f"{BASE}/plugins/netbox-nsm/security-policy/4/ipanalysis/?ip_ct=180&ip_pk=20&ip_name=n-10.0.0.0%2F8"),
    ("11-object-analyzer.png", f"{BASE}/plugins/netbox-nsm/object-analyzer/"),
    ("12-prefix-nsm-panel.png", f"{BASE}/ipam/prefixes/2/"),
    ("12b-prefix-nsm-panel-linked.png", f"{BASE}/ipam/prefixes/2/"),  # after enterprise demo
    ("13-ipaddress-nsm-panel.png", f"{BASE}/ipam/ip-addresses/20/"),
]

def login(page):
    page.goto(f"{BASE}/login/")
    page.fill("#id_username", "admin")
    page.fill("#id_password", "admin")
    page.click("[type=submit]")
    page.wait_for_load_state("networkidle")
    print("  [login] OK")

def screenshot(page, filename, url):
    if url is None:
        return
    print(f"  [{filename}] {url}")
    page.goto(url)
    page.wait_for_load_state("networkidle")
    time.sleep(0.5)
    page.screenshot(path=f"{OUT}/{filename}", full_page=True)
    print(f"  [{filename}] gespeichert")

CHROMIUM = "/nix/store/20ra63h4njcpr9v7vz34vhgrkm8g0icp-chromium-146.0.7680.177/bin/chromium"

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, executable_path=CHROMIUM)
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    page = ctx.new_page()

    login(page)

    # TypeConfig-Detail-URL dynamisch ermitteln
    page.goto(f"{BASE}/plugins/netbox-nsm/type-config/")
    page.wait_for_load_state("networkidle")
    first = page.query_selector("table tbody tr td a")
    tc_url = first.get_attribute("href") if first else None
    if tc_url and not tc_url.startswith("http"):
        tc_url = BASE + tc_url

    for filename, url in PAGES:
        if filename == "03-type-config-detail.png":
            url = tc_url
        screenshot(page, filename, url)

    browser.close()
    print("\nFertig!")
