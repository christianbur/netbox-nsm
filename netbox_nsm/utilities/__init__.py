__all__ = ("get_group_chains_for_object",)


def get_group_chains_for_object(app_label, model_name, pk):
    """
    Return all ObjectGroup chains that reference an object (IPAddress, Prefix, etc.)
    via ObjectCustomObjects.

    For IPAddress objects, also finds chains via containing prefixes (inherited membership).

    Returns a list of dicts::
        [
            {
                "oco": <ObjectCustomObject>,
                "oco_url": "...",
                "inherited": False,
                "via": None,          # or <Prefix> if inherited
                "chain": [<ObjectGroup>, <ObjectGroup>, ...],  # leaf → root
            },
            ...
        ]
    """
    from netbox_nsm.models import ObjectCustomType, ObjectCustomObject, ObjectGroup

    canonical = f"{app_label}.{model_name}".lower()

    def _ocos_for(ct_model, obj_pk):
        """Return PKs of OCOs belonging to any custom type with an object_ref field for ct_model."""
        pks = set()
        for ct in ObjectCustomType.objects.prefetch_related("custom_objects"):
            for fd in (ct.field_definitions or []):
                if fd.get("type") == "object_ref" and fd.get("model", "").lower() == ct_model:
                    filter_key = f"field_data__{fd['name']}__pk"
                    matched = ct.custom_objects.filter(**{filter_key: obj_pk}).values_list("pk", flat=True)
                    pks.update(matched)
        return pks

    def _get_paths(group, visited=None):
        """All paths from group up to root(s). Returns list of lists, each path is [group, parent, grandparent, ...]."""
        if visited is None:
            visited = frozenset()
        if group.pk in visited:
            return [[group]]
        parents = list(group.parent_groups.all())
        if not parents:
            return [[group]]
        all_paths = []
        for parent in parents:
            for path in _get_paths(parent, visited | {group.pk}):
                all_paths.append([group] + path)
        return all_paths

    def _build_chains(oco_pks, inherited=False, via=None):
        chains = []
        ocos = (
            ObjectCustomObject.objects
            .filter(pk__in=oco_pks)
            .prefetch_related("object_groups__parent_groups")
        )
        for oco in ocos:
            for group in oco.object_groups.all():
                for path in _get_paths(group):
                    chains.append({
                        "oco": oco,
                        "oco_url": oco.get_absolute_url(),
                        "inherited": inherited,
                        "via": via,
                        "chain": path,  # [direct_group, ..., root_group]
                    })
        return chains

    # Direct matches
    direct_pks = _ocos_for(canonical, pk)
    result = _build_chains(direct_pks, inherited=False)

    # For IPAddress: also check containing prefixes
    if model_name == "ipaddress":
        try:
            from ipam.models import IPAddress, Prefix
            ip = IPAddress.objects.get(pk=pk)
            containing = Prefix.objects.filter(prefix__net_contains_or_equals=str(ip.address.ip))
            for prefix in containing:
                p_pks = _ocos_for("ipam.prefix", prefix.pk)
                # Exclude any that were already found directly
                p_pks -= direct_pks
                if p_pks:
                    result.extend(_build_chains(p_pks, inherited=True, via=prefix))
        except Exception:
            pass

    return result
