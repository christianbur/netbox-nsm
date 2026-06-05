#!/usr/bin/env python3
"""
Integration-Tests für das netbox-nsm Plugin.

Testet alle REST-API-Endpoints sowie die Inherited-Links-API und das Security
Panel über echte HTTP-Requests gegen die laufende NetBox-Dev-Instanz.

Usage:
    python3 tests/integration_test.py

Voraussetzungen:
    - NetBox-Dev-Container läuft (https://netbox-dev.anwx.de)
    - Zugangsdaten: admin / Chip123!
    - Python 3.8+, keine externen Abhängigkeiten
"""

import http.cookiejar
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

# ─── Konfiguration ────────────────────────────────────────────────────────────

BASE_URL = "https://netbox-dev.anwx.de"
USERNAME = "admin"
PASSWORD = "Chip123!"

# ContentType-IDs (ermittelt via Brute-Force gegen die laufende DB)
CT_PREFIX = 95
CT_IPADDRESS = 97

# Bekannte Test-Objekte (aus DB-Dump)
KNOWN = {
    "prefix_with_direct_links": 2,      # 10.0.0.0/24  (2 direkte NSM-Links)
    "prefix_parent": 1,                 # 10.0.0.0/8   (hat direkte NSM-Links)
    "ip_with_inherited_links": 501,     # 10.0.0.10/24 (liegt in /24 und /8)
    "rulebook_pk": 1,
    "rule_pk": 1,
    "object_link_pk": 1,
    "type_config_pk": 1,
    "rulebook_field_pk": 1,
    "rulebook_field_type_pk": 5,
    "rule_object_item_pk": 1,
}

# ─── Hilfsfunktionen ──────────────────────────────────────────────────────────

# SSL-Kontext für self-signed Zertifikate (nur in Test-Umgebung!)
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


@dataclass
class Result:
    name: str
    passed: bool
    detail: str = ""


_results: list[Result] = []


def _record(name: str, passed: bool, detail: str = "") -> bool:
    _results.append(Result(name, passed, detail))
    status = "PASS" if passed else "FAIL"
    icon = "✓" if passed else "✗"
    print(f"  {icon} [{status}] {name}" + (f"  — {detail}" if detail else ""))
    return passed


# ─── HTTP-Session ─────────────────────────────────────────────────────────────

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(jar),
    urllib.request.HTTPSHandler(context=_ssl_ctx),
)


def _get_csrf() -> str:
    for c in jar:
        if c.name == "csrftoken":
            return c.value
    return ""


def _request(
    method: str,
    path: str,
    data: Optional[dict] = None,
    is_api: bool = True,
) -> tuple[int, Any]:
    """Führt einen HTTP-Request aus und gibt (status_code, parsed_body) zurück."""
    url = BASE_URL + path
    body = urllib.parse.urlencode(data).encode() if data else None
    headers: dict[str, str] = {
        "Accept": "application/json",
        "X-CSRFToken": _get_csrf(),
    }
    if data:
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with opener.open(req) as resp:
            raw = resp.read().decode(errors="replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        status = e.code

    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, raw


def _get(path: str) -> tuple[int, Any]:
    return _request("GET", path)


def _post(path: str, data: dict) -> tuple[int, Any]:
    return _request("POST", path, data=data)


def _json_request(method: str, path: str, payload: Optional[dict] = None) -> tuple[int, Any]:
    """JSON-basierter API-Request (für POST/PATCH/DELETE auf REST-Endpoints)."""
    url = BASE_URL + path
    body = json.dumps(payload).encode() if payload is not None else None
    headers: dict[str, str] = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-CSRFToken": _get_csrf(),
        "Referer": BASE_URL + "/",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with opener.open(req) as resp:
            raw = resp.read().decode(errors="replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        status = e.code
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, raw


def login() -> bool:
    """Meldet sich bei NetBox an und speichert Session-Cookies."""
    # 1. GET /login/ → CSRF-Cookie + csrfmiddlewaretoken aus HTML holen
    url = BASE_URL + "/login/"
    req = urllib.request.Request(url, headers={"Accept": "text/html"})
    try:
        with opener.open(req) as resp:
            html = resp.read().decode(errors="replace")
    except Exception as e:
        print(f"  FEHLER beim GET /login/: {e}")
        return False

    # csrfmiddlewaretoken aus dem HTML-Form extrahieren
    m = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', html)
    if not m:
        print("  FEHLER: csrfmiddlewaretoken nicht im Login-Formular gefunden")
        return False
    csrf_form = m.group(1)

    # 2. POST /login/ mit Credentials + form-token
    data = urllib.parse.urlencode({
        "username": USERNAME,
        "password": PASSWORD,
        "csrfmiddlewaretoken": csrf_form,
        "next": "/",
    }).encode()
    req2 = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": url,
            "X-CSRFToken": csrf_form,
        },
        method="POST",
    )
    try:
        with opener.open(req2) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception as e:
        print(f"  FEHLER beim POST /login/: {e}")
        return False

    if status in (200, 302):
        print(f"  Login erfolgreich (HTTP {status})")
        return True
    print(f"  Login FEHLGESCHLAGEN (HTTP {status})")
    return False


# ─── Test-Gruppen ─────────────────────────────────────────────────────────────


def test_api_list_endpoints():
    """Alle LIST-Endpoints geben HTTP 200 mit count-Feld zurück."""
    endpoints = [
        ("object-groups",                     "/api/plugins/netbox-nsm/object-groups/"),
        ("rulebooks",    "/api/plugins/netbox-nsm/rulebooks/"),
        ("rules",        "/api/plugins/netbox-nsm/rules/"),
        ("rulebook-assignments", "/api/plugins/netbox-nsm/rulebook-assignments/"),
        ("object-links",                      "/api/plugins/netbox-nsm/object-links/"),
        ("type-configs",                      "/api/plugins/netbox-nsm/type-configs/"),
        ("rulebook-fields",                   "/api/plugins/netbox-nsm/rulebook-fields/"),
        ("rulebook-field-types",              "/api/plugins/netbox-nsm/rulebook-field-types/"),
        ("rule-object-items",                 "/api/plugins/netbox-nsm/rule-object-items/"),
        ("rule-group-items",                  "/api/plugins/netbox-nsm/rule-group-items/"),
    ]
    for name, path in endpoints:
        status, body = _get(path)
        ok = status == 200 and isinstance(body, dict) and "count" in body
        count = body.get("count", "?") if isinstance(body, dict) else "?"
        _record(f"LIST {name}", ok, f"HTTP {status}, count={count}")


def test_api_detail_endpoints():
    """Detail-Endpoints für bekannte Objekte geben HTTP 200 zurück."""
    detail_tests = [
        ("rulebook detail",         f"/api/plugins/netbox-nsm/rulebooks/{KNOWN['rulebook_pk']}/"),
        ("rule detail",             f"/api/plugins/netbox-nsm/rules/{KNOWN['rule_pk']}/"),
        ("object-link detail",      f"/api/plugins/netbox-nsm/object-links/{KNOWN['object_link_pk']}/"),
        ("type-config detail",      f"/api/plugins/netbox-nsm/type-configs/{KNOWN['type_config_pk']}/"),
        ("rulebook-field detail",   f"/api/plugins/netbox-nsm/rulebook-fields/{KNOWN['rulebook_field_pk']}/"),
        ("rulebook-field-type det", f"/api/plugins/netbox-nsm/rulebook-field-types/{KNOWN['rulebook_field_type_pk']}/"),
        ("rule-object-item detail", f"/api/plugins/netbox-nsm/rule-object-items/{KNOWN['rule_object_item_pk']}/"),
    ]
    for name, path in detail_tests:
        status, body = _get(path)
        ok = status == 200 and isinstance(body, dict) and "id" in body
        _record(f"DETAIL {name}", ok, f"HTTP {status}")


def test_api_filters():
    """Filter-Parameter funktionieren korrekt."""
    filter_tests = [
        # (Testname, Pfad, erwartet_count_gte, erwartet_feld)
        ("object-links filter by object_a_id",
         f"/api/plugins/netbox-nsm/object-links/?object_a_id={KNOWN['prefix_with_direct_links']}",
         1, None),
        ("rulebook-fields filter by rulebook",
         f"/api/plugins/netbox-nsm/rulebook-fields/?rulebook_id={KNOWN['rulebook_pk']}",
         1, None),
        ("rule-object-items filter by rule",
         f"/api/plugins/netbox-nsm/rule-object-items/?rule_id={KNOWN['rule_pk']}",
         1, None),
        ("type-configs limit=2",
         "/api/plugins/netbox-nsm/type-configs/?limit=2",
         1, None),
    ]
    for name, path, min_count, _ in filter_tests:
        status, body = _get(path)
        count = body.get("count", 0) if isinstance(body, dict) else 0
        ok = status == 200 and count >= min_count
        _record(f"FILTER {name}", ok, f"HTTP {status}, count={count}")


def test_inherited_links():
    """Inherited-Links-API gibt korrekte Ergebnisse zurück."""
    # Prefix 10.0.0.0/24 (pk=2) liegt in 10.0.0.0/8 (pk=1), der direkte Links hat
    status, body = _get(
        f"/plugins/netbox-nsm/api/inherited-links/?ct_id={CT_PREFIX}&obj_id={KNOWN['prefix_with_direct_links']}"
    )
    ok = status == 200 and isinstance(body, dict) and "total" in body
    total = body.get("total", "?") if isinstance(body, dict) else "?"
    _record("inherited-links Prefix (total > 0)", ok and isinstance(total, int) and total > 0,
            f"HTTP {status}, total={total}")

    # IPAddress 10.0.0.10/24 (pk=501) liegt in /24 und /8 → sollte inherited links haben
    status2, body2 = _get(
        f"/plugins/netbox-nsm/api/inherited-links/?ct_id={CT_IPADDRESS}&obj_id={KNOWN['ip_with_inherited_links']}"
    )
    ok2 = status2 == 200 and isinstance(body2, dict) and body2.get("total", 0) > 0
    total2 = body2.get("total", "?") if isinstance(body2, dict) else "?"
    _record("inherited-links IPAddress (total > 0)", ok2, f"HTTP {status2}, total={total2}")

    # Struktur-Check: groups-Feld mit type_key und objects
    groups = body2.get("groups", []) if isinstance(body2, dict) else []
    has_structure = (
        len(groups) > 0
        and "type_key" in groups[0]
        and "objects" in groups[0]
        and len(groups[0]["objects"]) > 0
    )
    _record("inherited-links response structure", has_structure,
            f"groups={len(groups)}, first_group_objects={len(groups[0]['objects']) if groups else 0}")

    # Fehlerbehandlung: ungültige Parameter
    status_bad, _ = _get("/plugins/netbox-nsm/api/inherited-links/")
    _record("inherited-links bad request → 400", status_bad == 400, f"HTTP {status_bad}")


def test_security_panel():
    """Das Security Panel ist im HTML der Prefix-Detailseite vorhanden."""
    status, body = _get(f"/ipam/prefixes/{KNOWN['prefix_with_direct_links']}/")
    if not isinstance(body, str):
        _record("security panel HTML present", False, "Keine HTML-Antwort")
        return

    # Das NSM-Panel rendert entweder nsm_security_links.html oder nsm-inh-container
    has_nsm = "nsm" in body.lower() or "netbox-nsm" in body.lower()
    _record("security panel: NSM-HTML in Prefix-Detailseite", has_nsm,
            f"HTTP {status}, nsm-Token gefunden: {has_nsm}")

    # Prüfen ob inherited-links Container vorhanden
    has_inherited = "inherited" in body.lower() or "nsm-inh" in body.lower()
    _record("security panel: inherited-links Container", has_inherited,
            f"inherited-Token gefunden: {has_inherited}")

    # Prüfen ob die Seite Rulebook-Daten enthält
    has_rulebook = "rulebook" in body.lower() or "matrix" in body.lower()
    _record("security panel: rulebook-Inhalte sichtbar", has_rulebook,
            f"rulebook-Token gefunden: {has_rulebook}")


def test_api_pagination():
    """Pagination funktioniert (offset + limit)."""
    status1, body1 = _get("/api/plugins/netbox-nsm/object-links/?limit=5&offset=0")
    status2, body2 = _get("/api/plugins/netbox-nsm/object-links/?limit=5&offset=5")

    ok = (
        status1 == 200
        and status2 == 200
        and isinstance(body1, dict)
        and isinstance(body2, dict)
    )
    if ok:
        ids1 = {r["id"] for r in body1.get("results", [])}
        ids2 = {r["id"] for r in body2.get("results", [])}
        no_overlap = len(ids1 & ids2) == 0
        _record("pagination: keine überlappenden IDs", ok and no_overlap,
                f"page1={sorted(ids1)}, page2={sorted(ids2)}")
    else:
        _record("pagination: keine überlappenden IDs", False, f"HTTP {status1}, {status2}")


def test_api_display_field():
    """Das display-Feld ist in allen Endpunkten vorhanden."""
    endpoints_with_pk = [
        ("rulebook-fields display",         f"/api/plugins/netbox-nsm/rulebook-fields/{KNOWN['rulebook_field_pk']}/"),
        ("rulebook-field-types display",    f"/api/plugins/netbox-nsm/rulebook-field-types/{KNOWN['rulebook_field_type_pk']}/"),
        ("rule-object-items display",       f"/api/plugins/netbox-nsm/rule-object-items/{KNOWN['rule_object_item_pk']}/"),
        ("object-links display",            f"/api/plugins/netbox-nsm/object-links/{KNOWN['object_link_pk']}/"),
        ("type-configs display",            f"/api/plugins/netbox-nsm/type-configs/{KNOWN['type_config_pk']}/"),
        ("rulebooks display",               f"/api/plugins/netbox-nsm/rulebooks/{KNOWN['rulebook_pk']}/"),
    ]
    for name, path in endpoints_with_pk:
        status, body = _get(path)
        has_display = isinstance(body, dict) and "display" in body
        _record(f"display field: {name}", has_display, f"HTTP {status}")


def test_custom_objects_crud():
    """Custom-Object-Typen (nsm_action, nsm_addresses, nsm_labels, nsm_services,
    nsm_zones) mit Anlegen, Ändern und Löschen testen."""

    # ── custom-object-types LIST ──────────────────────────────────────────────
    status, body = _get("/api/plugins/custom-objects/custom-object-types/")
    ok = status == 200 and isinstance(body, dict) and body.get("count", 0) >= 5
    _record("custom-object-types LIST (≥5)", ok,
            f"HTTP {status}, count={body.get('count','?') if isinstance(body,dict) else '?'}")

    # Alle 5 erwarteten Typen vorhanden?
    if isinstance(body, dict):
        slugs = {r["slug"] for r in body.get("results", [])}
        for slug in ("nsm_action", "nsm_addresses", "nsm_labels", "nsm_services", "nsm_zones"):
            _record(f"custom-object-type vorhanden: {slug}", slug in slugs,
                    f"gefunden: {slug in slugs}")

    # ── CRUD pro Typ ──────────────────────────────────────────────────────────
    # (endpoint, create_payload, update_payload, display_check_key)
    crud_cases = [
        (
            "nsm_action",
            "/api/plugins/custom-objects/nsm_action/",
            {"name": "__test_action"},
            {"name": "__test_action_upd"},
            "name",
        ),
        (
            "nsm_addresses",
            "/api/plugins/custom-objects/nsm_addresses/",
            {"name": "__test_address"},
            {"name": "__test_address_upd"},
            "name",
        ),
        (
            "nsm_labels",
            "/api/plugins/custom-objects/nsm_labels/",
            {"name": "__test_label"},
            {"name": "__test_label_upd"},
            "name",
        ),
        (
            "nsm_services",
            "/api/plugins/custom-objects/nsm_services/",
            {"name": "__test_service"},
            {"name": "__test_service_upd"},
            "name",
        ),
        (
            "nsm_zones",
            "/api/plugins/custom-objects/nsm_zones/",
            {"name": "__test_zone"},
            {"name": "__test_zone_upd"},
            "name",
        ),
    ]

    created_ids: dict[str, int] = {}

    for type_name, list_path, create_payload, update_payload, check_key in crud_cases:
        prefix = f"custom-obj {type_name}"

        # LIST
        s, b = _get(list_path)
        count_before = b.get("count", 0) if isinstance(b, dict) else 0
        _record(f"{prefix} LIST", s == 200 and isinstance(b, dict) and "count" in b,
                f"HTTP {s}, count={count_before}")

        # CREATE (POST)
        s, b = _json_request("POST", list_path, create_payload)
        created_id = b.get("id") if isinstance(b, dict) else None
        ok_create = s == 201 and created_id is not None
        _record(f"{prefix} CREATE", ok_create,
                f"HTTP {s}, id={created_id}")
        if not ok_create:
            _record(f"{prefix} UPDATE", False, "skipped – CREATE fehlgeschlagen")
            _record(f"{prefix} DELETE", False, "skipped – CREATE fehlgeschlagen")
            continue
        created_ids[type_name] = created_id

        # READ (GET Detail)
        s, b = _get(f"{list_path}{created_id}/")
        _record(f"{prefix} READ (detail)", s == 200 and isinstance(b, dict) and b.get("id") == created_id,
                f"HTTP {s}")

        # UPDATE (PATCH)
        s, b = _json_request("PATCH", f"{list_path}{created_id}/", update_payload)
        updated_val = b.get(check_key) if isinstance(b, dict) else None
        expected_val = update_payload.get(check_key)
        ok_update = s == 200 and updated_val == expected_val
        _record(f"{prefix} UPDATE", ok_update,
                f"HTTP {s}, {check_key}={updated_val!r} (erwartet {expected_val!r})")

        # DELETE
        s, _ = _json_request("DELETE", f"{list_path}{created_id}/")
        _record(f"{prefix} DELETE", s == 204, f"HTTP {s}")

        # Verify gone (GET nach DELETE → 404)
        s, _ = _get(f"{list_path}{created_id}/")
        _record(f"{prefix} nach DELETE nicht mehr abrufbar", s == 404,
                f"HTTP {s} (erwartet 404)")


# ─── Zusammenfassung ─────────────────────────────────────────────────────────

def test_rulebook_crud():
    """Rulebook erstellen, ändern und löschen."""
    list_path = "/api/plugins/netbox-nsm/rulebooks/"

    # CREATE
    s, b = _json_request("POST", list_path, {"name": "__test-rulebook", "rulebook_type": "policy"})
    rb_id = b.get("id") if isinstance(b, dict) else None
    ok_create = s == 201 and rb_id is not None
    _record("rulebook CREATE", ok_create, f"HTTP {s}, id={rb_id}")
    if not ok_create:
        _record("rulebook READ", False, "skipped")
        _record("rulebook UPDATE", False, "skipped")
        _record("rulebook DELETE", False, "skipped")
        return

    # READ
    s, b = _get(f"{list_path}{rb_id}/")
    _record("rulebook READ (detail)", s == 200 and b.get("name") == "__test-rulebook",
            f"HTTP {s}, name={b.get('name')!r}")

    # UPDATE (PATCH)
    s, b = _json_request("PATCH", f"{list_path}{rb_id}/",
                         {"name": "__test-rulebook-upd", "description": "test-desc"})
    ok_upd = s == 200 and b.get("name") == "__test-rulebook-upd"
    _record("rulebook UPDATE", ok_upd, f"HTTP {s}, name={b.get('name')!r}")

    # DELETE
    s, _ = _json_request("DELETE", f"{list_path}{rb_id}/")
    _record("rulebook DELETE", s == 204, f"HTTP {s}")

    # Verify gone
    s, _ = _get(f"{list_path}{rb_id}/")
    _record("rulebook nach DELETE nicht mehr abrufbar", s == 404, f"HTTP {s}")


def test_rule_crud():
    """Rule im Test-Rulebook erstellen, ändern und löschen.

    Erstellt zuerst ein temporäres Rulebook, dann eine Rule darin.
    """
    rb_path = "/api/plugins/netbox-nsm/rulebooks/"
    rule_path = "/api/plugins/netbox-nsm/rules/"

    # Test-Rulebook anlegen
    s, rb = _json_request("POST", rb_path, {"name": "__test-rb-for-rule", "rulebook_type": "policy"})
    if s != 201 or not rb.get("id"):
        _record("rule CREATE", False, f"Rulebook-Anlage fehlgeschlagen: HTTP {s}")
        _record("rule UPDATE", False, "skipped")
        _record("rule DELETE", False, "skipped")
        return
    rb_id = rb["id"]

    # CREATE rule
    s, b = _json_request("POST", rule_path, {
        "rulebook": rb_id,
        "name": "__test-rule",
        "index": 10,
    })
    rule_id = b.get("id") if isinstance(b, dict) else None
    ok_create = s == 201 and rule_id is not None
    _record("rule CREATE", ok_create, f"HTTP {s}, id={rule_id}, rulebook={rb_id}")

    if ok_create:
        # READ
        s, b = _get(f"{rule_path}{rule_id}/")
        _record("rule READ (detail)", s == 200 and b.get("name") == "__test-rule",
                f"HTTP {s}, name={b.get('name')!r}")

        # UPDATE — Name + enabled ändern
        s, b = _json_request("PATCH", f"{rule_path}{rule_id}/",
                             {"name": "__test-rule-upd", "enabled": False})
        ok_upd = (s == 200
                  and b.get("name") == "__test-rule-upd"
                  and b.get("enabled") is False)
        _record("rule UPDATE", ok_upd,
                f"HTTP {s}, name={b.get('name')!r}, enabled={b.get('enabled')}")

        # DELETE rule
        s, _ = _json_request("DELETE", f"{rule_path}{rule_id}/")
        _record("rule DELETE", s == 204, f"HTTP {s}")

        # Verify gone
        s, _ = _get(f"{rule_path}{rule_id}/")
        _record("rule nach DELETE nicht mehr abrufbar", s == 404, f"HTTP {s}")
    else:
        _record("rule READ", False, "skipped")
        _record("rule UPDATE", False, "skipped")
        _record("rule DELETE", False, "skipped")
        _record("rule nach DELETE nicht mehr abrufbar", False, "skipped")

    # Test-Rulebook wieder aufräumen
    _json_request("DELETE", f"{rb_path}{rb_id}/")


def test_object_link_crud():
    """ObjectLink (Prefix ↔ NSM-Zone) erstellen, ändern und löschen."""
    link_path = "/api/plugins/netbox-nsm/object-links/"

    # CREATE: Prefix pk=3 ↔ Zone pk=1 (trust)
    # Prefix pk=3 = 10.254.0.0/24 — hat laut DB noch keine Zone-Links auf Zone 1
    s, b = _json_request("POST", link_path, {
        "object_a_type": "ipam.prefix",
        "object_a_id": 3,
        "object_b_type": "netbox_custom_objects.table5model",
        "object_b_id": 1,
        "comment": "test-link",
    })
    link_id = b.get("id") if isinstance(b, dict) else None
    ok_create = s == 201 and link_id is not None
    display = b.get('display') if isinstance(b, dict) else '?'
    _record("object-link CREATE", ok_create,
            f"HTTP {s}, id={link_id}, display={display!r}")

    if not ok_create:
        _record("object-link READ", False, "skipped")
        _record("object-link UPDATE (comment)", False, "skipped")
        _record("object-link DELETE", False, "skipped")
        _record("object-link nach DELETE nicht mehr abrufbar", False, "skipped")
        return

    # READ
    s, b = _get(f"{link_path}{link_id}/")
    ok_read = (s == 200
               and b.get("object_a_type") == "ipam.prefix"
               and b.get("object_a_id") == 3
               and b.get("object_b_type") == "netbox_custom_objects.table5model"
               and b.get("object_b_id") == 1)
    _record("object-link READ (detail)", ok_read, f"HTTP {s}, display={b.get('display')!r}")

    # UPDATE — comment ändern (object_a/b können nicht geändert werden wegen unique_together)
    s, b = _json_request("PATCH", f"{link_path}{link_id}/", {"comment": "updated-comment"})
    ok_upd = s == 200 and b.get("comment") == "updated-comment"
    _record("object-link UPDATE (comment)", ok_upd,
            f"HTTP {s}, comment={b.get('comment')!r}")

    # DELETE
    s, _ = _json_request("DELETE", f"{link_path}{link_id}/")
    _record("object-link DELETE", s == 204, f"HTTP {s}")

    # Verify gone
    s, _ = _get(f"{link_path}{link_id}/")
    _record("object-link nach DELETE nicht mehr abrufbar", s == 404, f"HTTP {s}")

    # Conflict-Test: doppelten Link anlegen und danach wieder löschen
    s1, b1 = _json_request("POST", link_path, {
        "object_a_type": "ipam.prefix", "object_a_id": 3,
        "object_b_type": "netbox_custom_objects.table5model", "object_b_id": 2,
    })
    dup_id = b1.get("id") if isinstance(b1, dict) else None
    if s1 == 201 and dup_id:
        s2, _ = _json_request("POST", link_path, {
            "object_a_type": "ipam.prefix", "object_a_id": 3,
            "object_b_type": "netbox_custom_objects.table5model", "object_b_id": 2,
        })
        _record("object-link duplicate → 400", s2 == 400, f"HTTP {s2}")
        _json_request("DELETE", f"{link_path}{dup_id}/")
    else:
        _record("object-link duplicate → 400", False, f"Erst-Anlage fehlgeschlagen: HTTP {s1}")


def test_rulebook_fields_workflow():
    """Rulebook mit Feldern und Regel anlegen, ändern und löschen."""
    rb_path = "/api/plugins/netbox-nsm/rulebooks/"
    field_path = "/api/plugins/netbox-nsm/rulebook-fields/"
    rule_path = "/api/plugins/netbox-nsm/rules/"

    s, rb = _json_request(
        "POST", rb_path, {"name": "__test-rb-fields", "rulebook_type": "policy"}
    )
    rb_id = rb.get("id") if isinstance(rb, dict) else None
    ok_rb = s == 201 and rb_id is not None
    _record("workflow rulebook CREATE", ok_rb, f"HTTP {s}, id={rb_id}")
    if not ok_rb:
        for step in (
            "workflow field CREATE",
            "workflow rule CREATE",
            "workflow rule DELETE",
            "workflow field DELETE",
            "workflow rulebook DELETE",
        ):
            _record(step, False, "skipped")
        return

    s, field = _json_request(
        "POST",
        field_path,
        {
            "rulebook": rb_id,
            "slug": "api_dest",
            "name": "API Destination",
            "placement": "destination",
            "sort_order": 40,
        },
    )
    field_id = field.get("id") if isinstance(field, dict) else None
    ok_field = s == 201 and field_id is not None
    _record("workflow field CREATE", ok_field, f"HTTP {s}, id={field_id}")

    rule_id = None
    if ok_field:
        s, rule = _json_request(
            "POST",
            rule_path,
            {
                "rulebook": rb_id,
                "name": "__test-workflow-rule",
                "index": 25,
            },
        )
        rule_id = rule.get("id") if isinstance(rule, dict) else None
        ok_rule = s == 201 and rule_id is not None
        _record("workflow rule CREATE", ok_rule, f"HTTP {s}, id={rule_id}")

        if ok_rule:
            s, rule = _json_request(
                "PATCH",
                f"{rule_path}{rule_id}/",
                {"name": "__test-workflow-rule-upd"},
            )
            _record(
                "workflow rule UPDATE",
                s == 200 and rule.get("name") == "__test-workflow-rule-upd",
                f"HTTP {s}, name={rule.get('name')!r}",
            )
            s, _ = _json_request("DELETE", f"{rule_path}{rule_id}/")
            _record("workflow rule DELETE", s == 204, f"HTTP {s}")
        else:
            _record("workflow rule UPDATE", False, "skipped")
            _record("workflow rule DELETE", False, "skipped")

        s, _ = _json_request("DELETE", f"{field_path}{field_id}/")
        _record("workflow field DELETE", s == 204, f"HTTP {s}")
    else:
        _record("workflow rule CREATE", False, "skipped")
        _record("workflow rule UPDATE", False, "skipped")
        _record("workflow rule DELETE", False, "skipped")
        _record("workflow field DELETE", False, "skipped")

    s, _ = _json_request("DELETE", f"{rb_path}{rb_id}/")
    _record("workflow rulebook DELETE", s == 204, f"HTTP {s}")


# ─── Zusammenfassung ─────────────────────────────────────────────────────────────

def print_summary():
    total = len(_results)
    passed = sum(1 for r in _results if r.passed)
    failed = total - passed

    print()
    print("=" * 65)
    print(f"  Ergebnis: {passed}/{total} Tests bestanden", end="")
    if failed:
        print(f"  ({failed} FEHLGESCHLAGEN)")
    else:
        print("  — alle Tests OK")
    print("=" * 65)

    if failed:
        print("\nFehlgeschlagene Tests:")
        for r in _results:
            if not r.passed:
                print(f"  ✗ {r.name}" + (f"  — {r.detail}" if r.detail else ""))
        sys.exit(1)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"netbox-nsm Integration-Tests — {BASE_URL}")
    print("=" * 65)

    print("\n[0] Authentifizierung")
    if not login():
        print("Abbruch: Login fehlgeschlagen.")
        sys.exit(1)

    print("\n[1] API List-Endpoints")
    test_api_list_endpoints()

    print("\n[2] API Detail-Endpoints")
    test_api_detail_endpoints()

    print("\n[3] API Filter-Parameter")
    test_api_filters()

    print("\n[4] API Pagination")
    test_api_pagination()

    print("\n[5] display-Feld in allen Endpoints")
    test_api_display_field()

    print("\n[6] Inherited-Links-API")
    test_inherited_links()

    print("\n[7] Security Panel (HTML)")
    test_security_panel()

    print("\n[8] Custom Objects CRUD (nsm_action / nsm_addresses / nsm_labels / nsm_services / nsm_zones)")
    test_custom_objects_crud()

    print("\n[9] Rulebook CRUD")
    test_rulebook_crud()

    print("\n[10] Rule CRUD (im Test-Rulebook)")
    test_rule_crud()

    print("\n[11] ObjectLink CRUD")
    test_object_link_crud()

    print("\n[12] Rulebook + Fields + Rule Workflow")
    test_rulebook_fields_workflow()

    print_summary()


if __name__ == "__main__":
    main()
