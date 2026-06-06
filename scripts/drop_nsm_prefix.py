#!/usr/bin/env python3
"""Entfernt redundantes NSM-Präfix aus Modellen, Dateien und Referenzen.

Voraussetzung: leere DB / nur 0001_initial.

Ausführen im Plugin-Root:
  python3 scripts/drop_nsm_prefix.py
  python3 scripts/drop_nsm_prefix.py --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "netbox_nsm"

# Reihenfolge: längere Tokens zuerst
TEXT_REPLACEMENTS = [
    # Modelle & Indizes
    ("RulebookAssignment", "RulebookAssignment"),
    ("RuleObjectItem", "RuleObjectItem"),
    ("RuleGroupItem", "RuleGroupItem"),
    ("RulebookIndex", "RulebookIndex"),
    ("ObjectGroupMember", "ObjectGroupMember"),
    ("ObjectGroupIndex", "ObjectGroupIndex"),
    ("PropertyTypeIndex", "PropertyTypeIndex"),
    ("PropertyIndex", "PropertyIndex"),
    ("Rulebook", "Rulebook"),
    ("ObjectGroup", "ObjectGroup"),
    ("ObjectLink", "ObjectLink"),
    ("PropertyType", "PropertyType"),
    ("PropertyField", "PropertyField"),
    ("Section", "Section"),
    ("Property", "Property"),
    ("Rule", "Rule"),
    # Views / Forms / Tables / API (gleiches Muster)
    ("ObjectTypeElementsApiView", "ObjectTypeElementsApiView"),
    # Serializer / ViewSet / FilterSet / Form / Table Suffixe
    ("RulebookAssignmentSerializer", "RulebookAssignmentSerializer"),
    ("RulebookAssignmentFilterSet", "RulebookAssignmentFilterSet"),
    ("RulebookAssignmentFilterForm", "RulebookAssignmentFilterForm"),
    ("RulebookAssignmentForm", "RulebookAssignmentForm"),
    ("RulebookAssignmentTable", "RulebookAssignmentTable"),
    ("RulebookAssignmentViewSet", "RulebookAssignmentViewSet"),
    ("RulebookAssignmentListView", "RulebookAssignmentListView"),
    ("RulebookAssignmentEditView", "RulebookAssignmentEditView"),
    ("RulebookAssignmentDeleteView", "RulebookAssignmentDeleteView"),
    ("RulebookAssignmentBulkDeleteView", "RulebookAssignmentBulkDeleteView"),
    ("RuleObjectItemSerializer", "RuleObjectItemSerializer"),
    ("RuleObjectItemFilterSet", "RuleObjectItemFilterSet"),
    ("RuleObjectItemViewSet", "RuleObjectItemViewSet"),
    ("RuleGroupItemSerializer", "RuleGroupItemSerializer"),
    ("RuleGroupItemFilterSet", "RuleGroupItemFilterSet"),
    ("RuleGroupItemViewSet", "RuleGroupItemViewSet"),
    ("RulebookSerializer", "RulebookSerializer"),
    ("RulebookFilterSet", "RulebookFilterSet"),
    ("RulebookFilterForm", "RulebookFilterForm"),
    ("RulebookBulkEditForm", "RulebookBulkEditForm"),
    ("RulebookBulkAssignForm", "RulebookBulkAssignForm"),
    ("RulebookForm", "RulebookForm"),
    ("RulebookTable", "RulebookTable"),
    ("RulebookViewSet", "RulebookViewSet"),
    ("RulebookAnalysisView", "RulebookAnalysisView"),
    ("RulebookVisualizationView", "RulebookVisualizationView"),
    ("RulebookIPAnalysisView", "RulebookIPAnalysisView"),
    ("RulebookView", "RulebookView"),
    ("RulebookPolicyColumnsView", "RulebookPolicyColumnsView"),
    ("RulebookRulesView", "RulebookRulesView"),
    ("RulebookListView", "RulebookListView"),
    ("RulebookEditView", "RulebookEditView"),
    ("RulebookDeleteView", "RulebookDeleteView"),
    ("RulebookBulkEditView", "RulebookBulkEditView"),
    ("RulebookBulkDeleteView", "RulebookBulkDeleteView"),
    ("RulebookBulkAssignView", "RulebookBulkAssignView"),
    ("RuleSerializer", "RuleSerializer"),
    ("RuleFilterSet", "RuleFilterSet"),
    ("RuleFilterForm", "RuleFilterForm"),
    ("RuleForm", "RuleForm"),
    ("RuleTable", "RuleTable"),
    ("RuleViewSet", "RuleViewSet"),
    ("RuleView", "RuleView"),
    ("RuleListView", "RuleListView"),
    ("RuleEditView", "RuleEditView"),
    ("RuleDeleteView", "RuleDeleteView"),
    ("ObjectGroupSerializer", "ObjectGroupSerializer"),
    ("ObjectGroupFilterSet", "ObjectGroupFilterSet"),
    ("ObjectGroupFilterForm", "ObjectGroupFilterForm"),
    ("ObjectGroupBulkEditForm", "ObjectGroupBulkEditForm"),
    ("ObjectGroupForm", "ObjectGroupForm"),
    ("ObjectGroupTable", "ObjectGroupTable"),
    ("ObjectGroupViewSet", "ObjectGroupViewSet"),
    ("ObjectGroupView", "ObjectGroupView"),
    ("ObjectGroupListView", "ObjectGroupListView"),
    ("ObjectGroupEditView", "ObjectGroupEditView"),
    ("ObjectGroupDeleteView", "ObjectGroupDeleteView"),
    ("ObjectGroupBulkEditView", "ObjectGroupBulkEditView"),
    ("ObjectGroupBulkDeleteView", "ObjectGroupBulkDeleteView"),
    ("ObjectGroupAssignmentsView", "ObjectGroupAssignmentsView"),
    ("ObjectGroupAreaView", "ObjectGroupAreaView"),
    ("ObjectLinkSerializer", "ObjectLinkSerializer"),
    ("ObjectLinkFilterSet", "ObjectLinkFilterSet"),
    ("ObjectLinkAssignForm", "ObjectLinkAssignForm"),
    ("ObjectLinkViewSet", "ObjectLinkViewSet"),
    ("ObjectLinkAssignView", "ObjectLinkAssignView"),
    ("ObjectLinkEditView", "ObjectLinkEditView"),
    ("ObjectLinkDeleteView", "ObjectLinkDeleteView"),
    # Tests
    ("RulebookAPITest", "RulebookAPITest"),
    ("RuleAPITest", "RuleAPITest"),
    ("_RulebookPluginAPITestMixin", "_RulebookPluginAPITestMixin"),
    # Migration / DB constraint fragments (lowercase model names)
    ("rulebookassignment", "rulebookassignment"),
    ("ruleobjectitem", "ruleobjectitem"),
    ("rulegroupitem", "rulegroupitem"),
    ("objectgroupmember", "objectgroupmember"),
    ("objectgroup", "objectgroup"),
    ("objectlink", "objectlink"),
    ("propertytype", "propertytype"),
    ("propertyfield", "propertyfield"),
    ("property", "property"),
    ("section", "section"),
    ("rulebook", "rulebook"),
    ("rule", "rule"),
    # Template paths & static (nach Klassen, damit netbox_nsm/ nicht kaputt geht)
    ("netbox_nsm/rulebook_", "netbox_nsm/rulebook_"),
    ("netbox_nsm/rule.", "netbox_nsm/rule."),
    ("netbox_nsm/rule_", "netbox_nsm/rule_"),
    ("netbox_nsm/objectgroup", "netbox_nsm/objectgroup"),
    ("netbox_nsm/object_link", "netbox_nsm/object_link"),
    ("netbox_nsm/property", "netbox_nsm/property"),
    ("netbox_nsm/inc/security_links", "netbox_nsm/inc/security_links"),
    ("netbox_nsm/js/rule_form", "netbox_nsm/js/rule_form"),
    ("netbox_nsm/js/object_group_form", "netbox_nsm/js/object_group_form"),
    ("netbox_nsm/js/visible_when", "netbox_nsm/js/visible_when"),
    # Permissions in templates
    ("view_rulebook", "view_rulebook"),
    ("add_rulebook", "add_rulebook"),
    ("change_rulebook", "change_rulebook"),
    ("delete_rulebook", "delete_rulebook"),
    ("view_rule", "view_rule"),
    ("add_rule", "add_rule"),
    ("change_rule", "change_rule"),
    ("delete_rule", "delete_rule"),
    ("view_objectgroup", "view_objectgroup"),
    ("add_objectgroup", "add_objectgroup"),
    ("change_objectgroup", "change_objectgroup"),
    ("delete_objectgroup", "delete_objectgroup"),
    ("view_rulebookassignment", "view_rulebookassignment"),
    ("add_rulebookassignment", "add_rulebookassignment"),
    ("view_objectlink", "view_objectlink"),
    ("add_objectlink", "add_objectlink"),
    # Choices module
    ("rulebook_choices", "rulebook_choices"),
    ("choices/rulebook", "choices/rulebook"),
    # Import paths (module renames)
    ("models.rulebook", "models.rulebook"),
    ("models.object_group", "models.object_group"),
    ("models.object_link", "models.object_link"),
    ("models.section", "models.section"),
    ("models.property", "models.property"),
    ("models.type_config", "models.type_config"),
    ("views.rulebook", "views.rulebook"),
    ("views.object_group", "views.object_group"),
    ("views.object_link", "views.object_link"),
    ("views.type_config", "views.type_config"),
    ("tables.rulebook", "tables.rulebook"),
    ("tables.object_group", "tables.object_group"),
    ("tables.type_config", "tables.type_config"),
    ("forms.rulebook", "forms.rulebook"),
    ("forms.object_group", "forms.object_group"),
    ("forms.object_link", "forms.object_link"),
    ("forms.type_config", "forms.type_config"),
    ("filtersets.rulebook", "filtersets.rulebook"),
    ("filtersets.object_group", "filtersets.object_group"),
    ("filtersets.extras", "filtersets.extras"),
    ("serializers_.rulebook", "serializers_.rulebook"),
    ("serializers_.object_group", "serializers_.object_group"),
    ("serializers_.object_link", "serializers_.object_link"),
    ("serializers_.type_config", "serializers_.type_config"),
    ("from .rulebook", "from .rulebook"),
    ("from .object_group", "from .object_group"),
    ("from .object_link", "from .object_link"),
    ("from .type_config", "from .type_config"),
    ("from .section", "from .section"),
    ("from .property", "from .property"),
    # URL names (object-link)
    ("nsm_object_link_assign", "object_link_assign"),
    ("nsm_object_link_edit", "object_link_edit"),
    ("nsm_object_link_delete", "object_link_delete"),
    # filtersets __init__ after extras.py rename
    ("from .nsm_extra import", "from .extras import"),
]

FILE_RENAMES = [
    # models
    ("models/nsm_policy.py", "models/rulebook.py"),
    ("models/nsm_object_group.py", "models/object_group.py"),
    ("models/nsm_object_link.py", "models/object_link.py"),
    ("models/nsm_section.py", "models/section.py"),
    ("models/nsm_property.py", "models/property.py"),
    ("models/nsm_type_config.py", "models/type_config.py"),
    # views
    ("views/nsm_policy.py", "views/rulebook.py"),
    ("views/nsm_object_group.py", "views/object_group.py"),
    ("views/nsm_object_link.py", "views/object_link.py"),
    ("views/nsm_type_config.py", "views/type_config.py"),
    # tables / forms / filtersets
    ("tables/nsm_policy.py", "tables/rulebook.py"),
    ("tables/nsm_object_group.py", "tables/object_group.py"),
    ("tables/nsm_type_config.py", "tables/type_config.py"),
    ("forms/nsm_policy.py", "forms/rulebook.py"),
    ("forms/nsm_object_group.py", "forms/object_group.py"),
    ("forms/nsm_object_link.py", "forms/object_link.py"),
    ("forms/nsm_type_config.py", "forms/type_config.py"),
    ("filtersets/nsm_policy.py", "filtersets/rulebook.py"),
    ("filtersets/nsm_object_group.py", "filtersets/object_group.py"),
    ("filtersets/nsm_extra.py", "filtersets/extras.py"),
    ("choices/rulebook_choices.py", "choices/rulebook_choices.py"),
    # api
    ("api/serializers_/nsm_policy.py", "api/serializers_/rulebook.py"),
    ("api/serializers_/nsm_object_group.py", "api/serializers_/object_group.py"),
    ("api/serializers_/nsm_object_link.py", "api/serializers_/object_link.py"),
    ("api/serializers_/nsm_type_config.py", "api/serializers_/type_config.py"),
    # static
    ("static/netbox_nsm/js/rule_form.js", "static/netbox_nsm/js/rule_form.js"),
    (
        "static/netbox_nsm/js/object_group_form.js",
        "static/netbox_nsm/js/object_group_form.js",
    ),
    ("static/netbox_nsm/js/visible_when.js", "static/netbox_nsm/js/visible_when.js"),
    # templates
    (
        "templates/netbox_nsm/rulebook_policy.html",
        "templates/netbox_nsm/rulebook_policy.html",
    ),
    (
        "templates/netbox_nsm/rulebook_list.html",
        "templates/netbox_nsm/rulebook_list.html",
    ),
    ("templates/netbox_nsm/rulebook.html", "templates/netbox_nsm/rulebook.html"),
    (
        "templates/netbox_nsm/rulebook_matrix.html",
        "templates/netbox_nsm/rulebook_matrix.html",
    ),
    (
        "templates/netbox_nsm/rulebook_ipanalysis.html",
        "templates/netbox_nsm/rulebook_ipanalysis.html",
    ),
    (
        "templates/netbox_nsm/rulebook_visualization.html",
        "templates/netbox_nsm/rulebook_visualization.html",
    ),
    (
        "templates/netbox_nsm/rulebook_bulk_assign.html",
        "templates/netbox_nsm/rulebook_bulk_assign.html",
    ),
    (
        "templates/netbox_nsm/rulebook_analysis.html",
        "templates/netbox_nsm/rulebook_analysis.html",
    ),
    ("templates/netbox_nsm/rule.html", "templates/netbox_nsm/rule.html"),
    ("templates/netbox_nsm/rule_edit.html", "templates/netbox_nsm/rule_edit.html"),
    ("templates/netbox_nsm/objectgroup.html", "templates/netbox_nsm/objectgroup.html"),
    (
        "templates/netbox_nsm/objectgroup_list.html",
        "templates/netbox_nsm/objectgroup_list.html",
    ),
    (
        "templates/netbox_nsm/objectgroup_edit.html",
        "templates/netbox_nsm/objectgroup_edit.html",
    ),
    (
        "templates/netbox_nsm/objectgroup_assignments.html",
        "templates/netbox_nsm/objectgroup_assignments.html",
    ),
    (
        "templates/netbox_nsm/objectgroup_area.html",
        "templates/netbox_nsm/objectgroup_area.html",
    ),
    (
        "templates/netbox_nsm/object_link_assign.html",
        "templates/netbox_nsm/object_link_assign.html",
    ),
    (
        "templates/netbox_nsm/object_link_edit.html",
        "templates/netbox_nsm/object_link_edit.html",
    ),
    (
        "templates/netbox_nsm/object_link_delete.html",
        "templates/netbox_nsm/object_link_delete.html",
    ),
    ("templates/netbox_nsm/property.html", "templates/netbox_nsm/property.html"),
    (
        "templates/netbox_nsm/propertytype.html",
        "templates/netbox_nsm/propertytype.html",
    ),
    (
        "templates/netbox_nsm/inc/security_links.html",
        "templates/netbox_nsm/inc/security_links.html",
    ),
]

DELETE_PATHS = [
    "tables/nsm_object.py",
    "tables/nsm_object_type.py",
    "forms/nsm_object.py",
    "forms/nsm_object_type.py",
    "filtersets/nsm_object.py",
    "filtersets/nsm_object_type.py",
    "api/serializers_/nsm_object.py",
    "api/serializers_/nsm_object_type.py",
    "api/serializers_/nsm_object_assignment.py",
    "scripts/rename_nsm_modules.sh",
]

SKIP_DIRS = {".git", "__pycache__", "locale", ".pytest_cache"}
TEXT_EXTENSIONS = {
    ".py",
    ".html",
    ".md",
    ".js",
    ".json",
    ".po",
    ".txt",
    ".yml",
    ".yaml",
}


def should_process(path: Path) -> bool:
    if any(part in SKIP_DIRS for part in path.parts):
        return False
    return path.suffix in TEXT_EXTENSIONS or path.name.endswith(".html")


def apply_replacements(content: str) -> str:
    for old, new in TEXT_REPLACEMENTS:
        content = content.replace(old, new)
    return content


def process_files(dry_run: bool) -> int:
    changed = 0
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or not should_process(path):
            continue
        text = path.read_text(encoding="utf-8")
        new_text = apply_replacements(text)
        if new_text != text:
            changed += 1
            if dry_run:
                print(f"would update: {path.relative_to(ROOT)}")
            else:
                path.write_text(new_text, encoding="utf-8")
                print(f"updated: {path.relative_to(ROOT)}")
    return changed


def rename_files(dry_run: bool) -> None:
    for old_rel, new_rel in FILE_RENAMES:
        old = PKG / old_rel
        new = PKG / new_rel
        if not old.exists():
            continue
        if new.exists():
            print(f"skip rename (target exists): {new_rel}", file=sys.stderr)
            continue
        if dry_run:
            print(f"would mv: {old_rel} -> {new_rel}")
        else:
            new.parent.mkdir(parents=True, exist_ok=True)
            old.rename(new)
            print(f"mv: {old_rel} -> {new_rel}")


def delete_stubs(dry_run: bool) -> None:
    for rel in DELETE_PATHS:
        path = ROOT / rel
        if not path.exists():
            continue
        if dry_run:
            print(f"would delete: {rel}")
        else:
            path.unlink()
            print(f"deleted: {rel}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(f"Plugin root: {ROOT}")
    n = process_files(args.dry_run)
    rename_files(args.dry_run)
    delete_stubs(args.dry_run)
    print(f"Done. {n} file(s) with text changes.")
    if args.dry_run:
        print("Dry-run — nichts geschrieben.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
