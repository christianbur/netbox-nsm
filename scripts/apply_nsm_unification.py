#!/usr/bin/env python3
"""
Einmalig ausführen (Plugin-Root netbox-nsm):
  python3 scripts/apply_nsm_unification.py

Benennt Modelle, Permissions, URLs, Templates und verbleibende security_*-Module
auf einheitliche nsm_*-Namen um. Breaking change — nur für Neuinstallationen.
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NSM = ROOT / "netbox_nsm"

# Reihenfolge: längere Tokens zuerst
TEXT_REPLACEMENTS = [
    ("RuleObjectItem", "RuleObjectItem"),
    ("RuleGroupItem", "RuleGroupItem"),
    ("RulebookIndex", "RulebookIndex"),
    ("Rulebook", "Rulebook"),
    ("RulebookAssignment", "RulebookAssignment"),
    ("Rule", "Rule"),
    ("ObjectGroupMember", "ObjectGroupMember"),
    ("ObjectGroupIndex", "ObjectGroupIndex"),
    ("ObjectGroup", "ObjectGroup"),
    ("PropertyTypeIndex", "PropertyTypeIndex"),
    ("PropertyType", "PropertyType"),
    ("PropertyField", "PropertyField"),
    ("PropertyIndex", "PropertyIndex"),
    ("Property", "Property"),
    ("ConfiguredRuleTable", "ConfiguredRuleTable"),
    ("ruleobjectitem", "ruleobjectitem"),
    ("rulegroupitem", "rulegroupitem"),
    ("rulebook", "rulebook"),
    ("rulebookassignment", "rulebookassignment"),
    ("rule", "rule"),
    ("objectgroup", "objectgroup"),
    ("propertytype", "propertytype"),
    ("propertyfield", "propertyfield"),
    ("property", "property"),
    ("nsm_rulebooks", "nsm_rulebooks"),
    ("rulebook-assignments", "rulebook-assignments"),
    ("rulebooks/", "rulebooks/"),
    ("rules/", "rules/"),
    ("netbox_nsm/rulebook_security_policy.html", "netbox_nsm/rulebook_policy.html"),
    (
        "netbox_nsm/rulebook_visualization.html",
        "netbox_nsm/rulebook_visualization.html",
    ),
    ("netbox_nsm/rulebook_ipanalysis.html", "netbox_nsm/rulebook_ipanalysis.html"),
    ("netbox_nsm/rulebook_analysis.html", "netbox_nsm/rulebook_analysis.html"),
    ("netbox_nsm/rulebook_bulk_assign.html", "netbox_nsm/rulebook_bulk_assign.html"),
    ("netbox_nsm/rulebook_matrix.html", "netbox_nsm/rulebook_matrix.html"),
    ("netbox_nsm/rulebook_list.html", "netbox_nsm/rulebook_list.html"),
    ("netbox_nsm/rulebook.html", "netbox_nsm/rulebook.html"),
    ("netbox_nsm/rule_edit.html", "netbox_nsm/rule_edit.html"),
    ("netbox_nsm/rule.html", "netbox_nsm/rule.html"),
    (
        "netbox_nsm/objectgroup_assignments.html",
        "netbox_nsm/objectgroup_assignments.html",
    ),
    ("netbox_nsm/objectgroup_area.html", "netbox_nsm/objectgroup_area.html"),
    ("netbox_nsm/objectgroup_list.html", "netbox_nsm/objectgroup_list.html"),
    ("netbox_nsm/objectgroup_edit.html", "netbox_nsm/objectgroup_edit.html"),
    ("netbox_nsm/objectgroup.html", "netbox_nsm/objectgroup.html"),
    ("netbox_nsm/propertytype.html", "netbox_nsm/propertytype.html"),
    ("netbox_nsm/property.html", "netbox_nsm/property.html"),
    ("netbox_nsm/nsmobjecttype.html", "netbox_nsm/nsmobjecttype.html"),
    ("netbox_nsm/nsmobject_assignments.html", "netbox_nsm/nsmobject_assignments.html"),
    ("netbox_nsm/nsmobject_area.html", "netbox_nsm/nsmobject_area.html"),
    ("netbox_nsm/nsmobject_edit.html", "netbox_nsm/nsmobject_edit.html"),
    ("netbox_nsm/nsmobject.html", "netbox_nsm/nsmobject.html"),
    ("netbox_nsm/inc/nsm_tab.html", "netbox_nsm/inc/nsm_tab.html"),
    ("nsm_tab.html", "nsm_tab.html"),
    ("rulebook_visualization_redirect", "rulebook_visualization_redirect"),
    ("rulebook_bulk_assign", "rulebook_bulk_assign"),
    ("rulebook_policy", "rulebook_policy"),
    ("objectgroup_area_root", "objectgroup_area_root"),
    ("objectgroup_area", "objectgroup_area"),
    ("is_nsm_rules", "is_nsm_rules"),
]

TEMPLATE_RENAMES = {
    "rulebook_security_policy.html": "rulebook_policy.html",
    "rulebook.html": "rulebook.html",
    "rulebook_list.html": "rulebook_list.html",
    "rulebook_matrix.html": "rulebook_matrix.html",
    "rulebook_analysis.html": "rulebook_analysis.html",
    "rulebook_visualization.html": "rulebook_visualization.html",
    "rulebook_ipanalysis.html": "rulebook_ipanalysis.html",
    "rulebook_bulk_assign.html": "rulebook_bulk_assign.html",
    "rule_edit.html": "rule_edit.html",
    "rule.html": "rule.html",
    "objectgroup.html": "objectgroup.html",
    "objectgroup_edit.html": "objectgroup_edit.html",
    "objectgroup_list.html": "objectgroup_list.html",
    "objectgroup_area.html": "objectgroup_area.html",
    "objectgroup_assignments.html": "objectgroup_assignments.html",
    "property.html": "property.html",
    "propertytype.html": "propertytype.html",
    "securityobject.html": "nsmobject.html",
    "securityobject_edit.html": "nsmobject_edit.html",
    "securityobject_area.html": "nsmobject_area.html",
    "securityobject_assignments.html": "nsmobject_assignments.html",
    "securityobjecttype.html": "nsmobjecttype.html",
}

MODULE_RENAMES = [
    ("views/security_policy.py", "views/nsm_policy.py"),
    ("tables/security_policy.py", "tables/nsm_policy.py"),
    ("forms/security_policy.py", "forms/nsm_policy.py"),
    ("filtersets/security_policy.py", "filtersets/nsm_policy.py"),
    ("api/serializers_/security_policy.py", "api/serializers_/nsm_policy.py"),
    ("static/netbox_nsm/js/security_rule_form.js", "static/netbox_nsm/js/rule_form.js"),
]


def replace_in_file(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False
    original = text
    for old, new in TEXT_REPLACEMENTS:
        text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def walk_and_replace(base: Path, suffixes: tuple[str, ...]) -> int:
    count = 0
    for dirpath, _dirnames, filenames in os.walk(base):
        parts = Path(dirpath).parts
        if "migrations" in parts:
            fname = Path(dirpath) / name
            if fname.name != "0020_rename_models_to_nsm.py" and re.match(
                r"^\d{4}_", fname.name
            ):
                continue
        for name in filenames:
            if not name.endswith(suffixes):
                continue
            p = Path(dirpath) / name
            if replace_in_file(p):
                count += 1
    return count


def rename_templates() -> None:
    tpl_root = NSM / "templates" / "netbox_nsm"
    inc = tpl_root / "inc"
    if (inc / "nsm_tab.html").exists():
        shutil.move(inc / "nsm_tab.html", inc / "nsm_tab.html")
    for old, new in TEMPLATE_RENAMES.items():
        src = tpl_root / old
        dst = tpl_root / new
        if src.exists() and not dst.exists():
            shutil.move(str(src), str(dst))


def rename_modules() -> None:
    for old, new in MODULE_RENAMES:
        src = NSM / old
        dst = NSM / new
        if src.exists() and not dst.exists():
            shutil.move(str(src), str(dst))
        elif src.exists() and dst.exists():
            src.unlink()


def main() -> None:
    print(f"Root: {ROOT}")
    n = walk_and_replace(ROOT, (".py", ".html", ".js", ".md"))
    print(f"Updated {n} text files")
    rename_templates()
    print("Templates renamed")
    rename_modules()
    print("Modules renamed")
    print("Done. Run: python manage.py migrate netbox_nsm")


if __name__ == "__main__":
    main()
