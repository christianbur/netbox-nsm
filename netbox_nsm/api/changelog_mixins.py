"""Parent-object changelog hooks for REST API writes."""

from netbox_nsm.changelog_utils import (
    record_rule_assignment_changelog,
    record_rulebook_layout_changelog,
    record_rulebook_rules_changelog,
    snapshot_instance,
)
from netbox_nsm.models import Rule


class RulebookLayoutChangelogMixin:
    def _snapshot_rulebook(self, rulebook):
        return snapshot_instance(rulebook)

    def perform_create(self, serializer):
        rulebook = serializer.validated_data["rulebook"]
        prechange = self._snapshot_rulebook(rulebook)
        super().perform_create(serializer)
        record_rulebook_layout_changelog(rulebook, self.request, prechange)

    def perform_update(self, serializer):
        rulebook = serializer.instance.rulebook
        prechange = self._snapshot_rulebook(rulebook)
        super().perform_update(serializer)
        record_rulebook_layout_changelog(rulebook, self.request, prechange)

    def perform_destroy(self, instance):
        rulebook = instance.rulebook
        prechange = self._snapshot_rulebook(rulebook)
        super().perform_destroy(instance)
        record_rulebook_layout_changelog(rulebook, self.request, prechange)


class RulebookFieldTypeLayoutChangelogMixin:
    def perform_create(self, serializer):
        rulebook = serializer.validated_data["field"].rulebook
        prechange = snapshot_instance(rulebook)
        super().perform_create(serializer)
        record_rulebook_layout_changelog(rulebook, self.request, prechange)

    def perform_update(self, serializer):
        rulebook = serializer.instance.field.rulebook
        prechange = snapshot_instance(rulebook)
        super().perform_update(serializer)
        record_rulebook_layout_changelog(rulebook, self.request, prechange)

    def perform_destroy(self, instance):
        rulebook = instance.field.rulebook
        prechange = snapshot_instance(rulebook)
        super().perform_destroy(instance)
        record_rulebook_layout_changelog(rulebook, self.request, prechange)


class RuleAssignmentChangelogMixin:
    def _snapshot_rule(self, rule):
        return snapshot_instance(
            Rule.objects.prefetch_related(
                "object_items__field",
                "object_items__content_type",
                "group_items__field",
                "group_items__security_group",
            ).get(pk=rule.pk)
        )

    def perform_create(self, serializer):
        rule = serializer.validated_data["rule"]
        rb_prechange = snapshot_instance(rule.rulebook)
        prechange = self._snapshot_rule(rule)
        super().perform_create(serializer)
        record_rule_assignment_changelog(rule, self.request, prechange)
        record_rulebook_rules_changelog(rule.rulebook, self.request, rb_prechange)

    def perform_update(self, serializer):
        rule = serializer.instance.rule
        rb_prechange = snapshot_instance(rule.rulebook)
        prechange = self._snapshot_rule(rule)
        super().perform_update(serializer)
        record_rule_assignment_changelog(rule, self.request, prechange)
        record_rulebook_rules_changelog(rule.rulebook, self.request, rb_prechange)

    def perform_destroy(self, instance):
        rule = instance.rule
        rb_prechange = snapshot_instance(rule.rulebook)
        prechange = self._snapshot_rule(rule)
        super().perform_destroy(instance)
        record_rule_assignment_changelog(rule, self.request, prechange)
        record_rulebook_rules_changelog(rule.rulebook, self.request, rb_prechange)


class RuleRulesChangelogMixin:
    def perform_create(self, serializer):
        rulebook = serializer.validated_data["rulebook"]
        rb_prechange = snapshot_instance(rulebook)
        super().perform_create(serializer)
        record_rulebook_rules_changelog(rulebook, self.request, rb_prechange)

    def perform_update(self, serializer):
        rulebook = serializer.instance.rulebook
        rb_prechange = snapshot_instance(rulebook)
        super().perform_update(serializer)
        record_rulebook_rules_changelog(rulebook, self.request, rb_prechange)

    def perform_destroy(self, instance):
        rulebook = instance.rulebook
        rb_prechange = snapshot_instance(rulebook)
        super().perform_destroy(instance)
        record_rulebook_rules_changelog(rulebook, self.request, rb_prechange)
