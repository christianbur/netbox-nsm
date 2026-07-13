"""Tests for Security Panel row action URL helpers."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.template.loader import get_template
from django.test import SimpleTestCase

from netbox_nsm.objects.group_m2m import GROUP_M2M_LABEL_MEMBER, GroupM2mRelation
from netbox_nsm.security.actions.panel_link_actions import (
    address_ipam_fk_action_urls,
    address_ipam_fk_ref_action_urls,
    append_return_url,
    group_m2m_action_urls,
    object_link_action_urls,
    object_link_assign_url,
    object_link_panel_delete_url,
    object_link_panel_edit_url,
)


class ObjectLinkActionUrlTests(SimpleTestCase):
    @patch("netbox_nsm.security.actions.panel_link_actions.reverse")
    def test_object_link_action_urls(self, mock_reverse):
        mock_reverse.side_effect = [
            "/plugins/netbox-nsm/object-link/7/edit/",
            "/plugins/netbox-nsm/object-link/7/delete/",
        ]
        link = SimpleNamespace(pk=7)
        urls = object_link_action_urls(link, "/ipam/prefixes/5/")
        self.assertEqual(
            urls["edit_url"],
            "/plugins/netbox-nsm/object-link/7/edit/?return_url=%2Fipam%2Fprefixes%2F5%2F",
        )
        self.assertEqual(
            urls["delete_url"],
            "/plugins/netbox-nsm/object-link/7/delete/?return_url=%2Fipam%2Fprefixes%2F5%2F",
        )
        mock_reverse.assert_any_call(
            "plugins:netbox_nsm:object_link_edit",
            kwargs={"pk": 7},
        )
        mock_reverse.assert_any_call(
            "plugins:netbox_nsm:object_link_delete",
            kwargs={"pk": 7},
        )


class AppendReturnUrlTests(SimpleTestCase):
    def test_appends_query_param(self):
        url = append_return_url("/edit/", "/ipam/prefixes/5/")
        self.assertIn("return_url=", url)
        self.assertIn("%2Fipam%2Fprefixes%2F5%2F", url)


class ObjectLinkPanelEditUrlTests(SimpleTestCase):
    @patch("netbox_nsm.security.actions.panel_link_actions.find_object_link_between", return_value=None)
    @patch(
        "netbox_nsm.security.actions.panel_link_actions.object_link_assign_url", return_value="/assign/"
    )
    def test_fk_only_uses_assign_url(self, mock_assign, _find):
        prefix = SimpleNamespace(pk=5)
        addr = SimpleNamespace(pk=10)
        url = object_link_panel_edit_url(prefix, addr, "/ipam/prefixes/5/")
        self.assertEqual(url, "/assign/")
        mock_assign.assert_called_once_with(prefix, "/ipam/prefixes/5/", object_b=addr)

    @patch("netbox_nsm.security.actions.panel_link_actions.object_link_action_urls")
    @patch("netbox_nsm.security.actions.panel_link_actions.find_object_link_between")
    def test_existing_link_uses_edit_url(self, mock_find, mock_action_urls):
        link = SimpleNamespace(pk=3)
        mock_find.return_value = link
        mock_action_urls.return_value = {"edit_url": "/edit/", "delete_url": "/delete/"}
        prefix = SimpleNamespace(pk=5)
        addr = SimpleNamespace(pk=10)
        url = object_link_panel_edit_url(prefix, addr, "/ipam/prefixes/5/")
        self.assertEqual(url, "/edit/")
        mock_action_urls.assert_called_once_with(link, "/ipam/prefixes/5/")


class ObjectLinkPanelDeleteUrlTests(SimpleTestCase):
    @patch("netbox_nsm.security.actions.panel_link_actions.object_link_action_urls")
    @patch("netbox_nsm.security.actions.panel_link_actions.find_object_link_between")
    def test_existing_link_uses_delete_url(self, mock_find, mock_action_urls):
        link = SimpleNamespace(pk=3)
        mock_find.return_value = link
        mock_action_urls.return_value = {"edit_url": "/edit/", "delete_url": "/delete/"}
        prefix = SimpleNamespace(pk=5)
        addr = SimpleNamespace(pk=10)
        url = object_link_panel_delete_url(
            prefix, addr, "/ipam/prefixes/5/", fallback="/clear/"
        )
        self.assertEqual(url, "/delete/")
        mock_action_urls.assert_called_once_with(link, "/ipam/prefixes/5/")

    @patch("netbox_nsm.security.actions.panel_link_actions.find_object_link_between", return_value=None)
    def test_fk_only_uses_fallback(self, _find):
        prefix = SimpleNamespace(pk=5)
        addr = SimpleNamespace(pk=10)
        url = object_link_panel_delete_url(
            prefix, addr, "/ipam/prefixes/5/", fallback="/clear/"
        )
        self.assertEqual(url, "/clear/")


class ObjectLinkAssignUrlTests(SimpleTestCase):
    @patch(
        "netbox_nsm.security.links.cot_link_schema.get_object_link_cot_slug",
        return_value="nsm_object_link",
    )
    @patch(
        "netbox_nsm.security.links.cot_link_schema.get_object_link_schema",
        return_value=SimpleNamespace(host_field="netbox_object", security_field="security_object"),
    )
    @patch("netbox_nsm.security.links.object_link_service.classify_link_endpoints")
    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.security.actions.panel_link_actions.reverse", return_value="/cot-add")
    def test_builds_prefilled_assign_url(self, mock_reverse, mock_ct, mock_classify, _schema, _slug):
        mock_classify.return_value = (
            type("Prefix", (), {"pk": 5})(),
            type("Zone", (), {"pk": 10})(),
        )
        mock_ct.objects.get_for_model.side_effect = [
            SimpleNamespace(pk=234),
            SimpleNamespace(pk=99),
        ]
        prefix = type("Prefix", (), {"pk": 5, "__str__": lambda self: "10.0.0.0/24"})()
        addr = type("Zone", (), {"pk": 10, "__str__": lambda self: "web-zone"})()
        url = object_link_assign_url(prefix, "/ipam/prefixes/5/", object_b=addr)
        self.assertTrue(url.startswith("/cot-add?"))
        self.assertIn("ct_id=234", url)
        self.assertIn("obj_id=5", url)
        self.assertIn("object_a_type_id=234", url)
        self.assertIn("object_a_id=5", url)
        self.assertIn("object_b_type_id=99", url)
        self.assertIn("object_b_id=10", url)
        self.assertIn("netbox_object__ct=234", url)
        self.assertIn("netbox_object__obj=5", url)
        self.assertIn("security_object__ct=99", url)
        self.assertIn("security_object__obj=10", url)
        self.assertIn("status=active", url)
        self.assertIn("name=", url)
        self.assertIn("return_url=", url)
        mock_reverse.assert_called_once_with(
            "plugins:netbox_custom_objects:customobject_add",
            kwargs={"custom_object_type": "nsm_object_link"},
        )

    @patch(
        "netbox_nsm.security.links.cot_link_schema.get_object_link_cot_slug",
        return_value="nsm_object_link",
    )
    @patch(
        "netbox_nsm.security.links.cot_link_schema.get_object_link_schema",
        return_value=SimpleNamespace(host_field="netbox_object", security_field="security_object"),
    )
    @patch("netbox_nsm.security.object_link_cot_form.object_link_field_prefix_for_ct", return_value="security_object")
    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.security.actions.panel_link_actions.reverse", return_value="/cot-add")
    def test_builds_policy_side_assign_url(self, mock_reverse, mock_ct, _prefix, _schema, _slug):
        mock_ct.objects.get_for_model.return_value = SimpleNamespace(pk=272)
        group = type("Group", (), {"pk": 1, "__str__": lambda self: "G-DNS"})()
        url = object_link_assign_url(group, "/back/")
        self.assertIn("object_b_type_id=272", url)
        self.assertIn("object_b_id=1", url)
        self.assertNotIn("ct_id=", url)
        self.assertNotIn("obj_id=", url)
        self.assertIn("security_object__ct=272", url)
        self.assertIn("security_object__obj=1", url)


class AddressIpamFkActionUrlTests(SimpleTestCase):
    @patch(
        "netbox_nsm.security.actions.panel_link_actions.address_ipam_fk_clear_url",
        return_value="/clear/",
    )
    @patch(
        "netbox_nsm.security.actions.panel_link_actions.object_link_panel_delete_url",
        return_value="/delete/",
    )
    @patch(
        "netbox_nsm.security.actions.panel_link_actions.object_link_panel_edit_url",
        return_value="/edit/",
    )
    def test_ref_action_urls_include_edit_and_delete(
        self, mock_edit, mock_delete, _clear
    ):
        prefix = SimpleNamespace(pk=5)
        addr = SimpleNamespace(pk=10)
        urls = address_ipam_fk_ref_action_urls(prefix, addr, "prefix", "/back/")
        self.assertEqual(urls["edit_url"], "/edit/")
        self.assertEqual(urls["delete_url"], "/delete/")
        mock_edit.assert_called_once_with(prefix, addr, "/back/")
        mock_delete.assert_called_once()

    @patch(
        "netbox_nsm.security.actions.panel_link_actions.address_ipam_fk_clear_url",
        return_value="/clear/",
    )
    @patch(
        "netbox_nsm.security.actions.panel_link_actions.object_link_panel_delete_url",
        return_value="/delete/",
    )
    @patch(
        "netbox_nsm.security.actions.panel_link_actions.object_link_panel_edit_url",
        return_value="/edit/",
    )
    def test_forward_action_urls_include_edit_and_delete(
        self, mock_edit, mock_delete, _clear
    ):
        addr = SimpleNamespace(pk=10)
        ipam = SimpleNamespace(pk=1)
        urls = address_ipam_fk_action_urls(addr, "prefix", ipam, "/back/")
        self.assertEqual(urls["edit_url"], "/edit/")
        self.assertEqual(urls["delete_url"], "/delete/")
        mock_edit.assert_called_once_with(addr, ipam, "/back/")
        mock_delete.assert_called_once()


class GroupM2mActionUrlTests(SimpleTestCase):
    @patch(
        "netbox_nsm.security.actions.panel_link_actions.object_link_panel_delete_url",
        return_value="/delete/",
    )
    @patch(
        "netbox_nsm.security.actions.panel_link_actions.group_m2m_remove_url", return_value="/remove/"
    )
    @patch("netbox_nsm.security.actions.panel_link_actions.group_m2m_edit_url", return_value="/edit/")
    def test_group_m2m_action_urls_include_edit_and_remove(
        self, _edit, _remove, mock_delete
    ):
        group = SimpleNamespace(pk=1)
        member = SimpleNamespace(pk=2)
        related = SimpleNamespace(pk=3)
        relation = GroupM2mRelation(
            related,
            GROUP_M2M_LABEL_MEMBER,
            remove_group=group,
            remove_member=member,
        )
        page = SimpleNamespace(pk=99)
        urls = group_m2m_action_urls(relation, "/back/", page_obj=page)
        self.assertEqual(urls["edit_url"], "/edit/")
        self.assertEqual(urls["delete_url"], "/delete/")
        mock_delete.assert_called_once_with(
            page, related, "/back/", fallback="/remove/"
        )

    @patch(
        "netbox_nsm.security.actions.panel_link_actions.group_m2m_remove_url", return_value="/remove/"
    )
    @patch("netbox_nsm.security.actions.panel_link_actions.group_m2m_edit_url", return_value="/edit/")
    def test_group_m2m_action_urls_without_page_obj_use_remove(self, _edit, _remove):
        group = SimpleNamespace(pk=1)
        member = SimpleNamespace(pk=2)
        related = SimpleNamespace(pk=3)
        relation = GroupM2mRelation(
            related,
            GROUP_M2M_LABEL_MEMBER,
            remove_group=group,
            remove_member=member,
        )
        urls = group_m2m_action_urls(relation, "/back/")
        self.assertEqual(urls["edit_url"], "/edit/")
        self.assertEqual(urls["delete_url"], "/remove/")

    @patch("netbox_nsm.security.actions.panel_link_actions.reverse", return_value="/panel-edit/")
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_group_m2m_edit_url_builds_query_string(self, mock_ct, mock_reverse):
        from netbox_nsm.security.actions.panel_link_actions import group_m2m_edit_url

        mock_ct.objects.get_for_model.side_effect = [
            SimpleNamespace(pk=11),
            SimpleNamespace(pk=22),
        ]
        group = SimpleNamespace(pk=1)
        member = SimpleNamespace(pk=2)
        url = group_m2m_edit_url(group, member, "/ipam/prefixes/5/")
        self.assertIn("/panel-edit/?", url)
        self.assertIn("group_ct_id=11", url)
        self.assertIn("group_id=1", url)
        self.assertIn("member_ct_id=22", url)
        self.assertIn("member_id=2", url)
        mock_reverse.assert_called_once_with("plugins:netbox_nsm:group_m2m_edit")


class PanelLinkClearTemplateTests(SimpleTestCase):
    def test_address_ipam_fk_clear_template_compiles(self):
        get_template("netbox_nsm/address_ipam_fk_clear.html")

    def test_group_m2m_remove_template_compiles(self):
        get_template("netbox_nsm/group_m2m_remove.html")

    def test_object_link_delete_template_compiles(self):
        get_template("netbox_nsm/object_link_delete.html")
