"""Security tab registration, context, and related-tab rows."""

from netbox_nsm.security.tab.cot_metadata import cot_link_table_flag
from netbox_nsm.security.tab.registry import register_security_tabs

__all__ = ("cot_link_table_flag", "register_security_tabs")
