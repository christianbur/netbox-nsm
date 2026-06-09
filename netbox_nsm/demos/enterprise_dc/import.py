"""
Enterprise DC Demo — import script
===================================
Run via:
  docker exec netbox-dev bash -c \
    "cd /app/netbox/netbox && python manage.py shell < \
     /opt/netbox-nsm/netbox_nsm/demos/enterprise_dc/import.py"

What this creates
-----------------
NetBox DCIM/Virtualization:
  • Site DC-01
  • Manufacturers: Cisco, Dell
  • Device Types: Nexus 9516 (Spine), Nexus 93180YC-EX (Leaf), Dell R750 (HV)
  • Device Roles: spine-switch, leaf-switch, hypervisor
  • Racks: 1 infra + 2 spine + 2/zone = 25 racks
  • Devices: 2 Spines, 22 Leafs, 24 Hypervisors (2/zone + 2 Infra)
  • Cables: 4×40GE per Leaf→Spine, 4×10GE per HV→Leaf-pair (vPC)
  • Cluster Type: VMware vSphere
  • Cluster: dc-vsphere + gcp-dmz (GCE)
  • VMs: 50/zone × 10 zones + 6 infra + 10 GCP = 516 VMs
  • Prefixes + IPs

NSM:
  • 11 Zones (prod, integration-1..3, dev-1..3, test-1..3, infrastructure)
  • Addresses (subnets per zone + User + OOB + HV-MGMT + GCP)
  • Labels (Env × App × Role × Tier)
  • Services (~28)
  • Rulebooks: trustsec-core (90), trustsec-infra (11),
               illumio-intra-zone (25), fw-dc-inter-zone,
               fw-mgmt, fw-user-access, fw-sase,
               fw-internet-outer, fw-internet-inner,
               fw-gcp-dmz, fw-vpn-partner
"""

import sys
from django.db import transaction

print("=" * 60)
print("Enterprise DC Demo — starting import")
print("=" * 60)

# ─── 0. Verify NSM COT types exist ────────────────────────────────────────────
try:
    from netbox_custom_objects.models import CustomObjectType
    from netbox_nsm.models import TypeConfig

    REQUIRED = [
        "nsm_zones",
        "nsm_addresses",
        "nsm_labels",
        "nsm_services",
        "nsm_action",
    ]
    missing = [
        s for s in REQUIRED if not CustomObjectType.objects.filter(slug=s).exists()
    ]
    if missing:
        print(f"ERROR: Missing COT types: {missing}")
        print("Run Setup → Import all types first.")
        sys.exit(1)
    missing_tc = []
    for s in REQUIRED:
        cot = CustomObjectType.objects.get(slug=s)
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(cot.get_model())
        if not TypeConfig.objects.filter(content_type=ct).exists():
            missing_tc.append(s)
    if missing_tc:
        print(f"ERROR: Missing TypeConfigs for: {missing_tc}")
        print("Run Setup → Create all TypeConfigs first.")
        sys.exit(1)
    print("✓ COT types and TypeConfigs present")
except ImportError as e:
    print(f"ERROR: {e}")
    sys.exit(1)

# ─── 1. Helpers ───────────────────────────────────────────────────────────────


def gc(klass, **kwargs):
    """get_or_create, returns instance."""
    obj, _ = klass.objects.get_or_create(**kwargs)
    return obj


def gcu(klass, lookup, **update):
    """get_or_create with defaults, then update if changed."""
    obj, created = klass.objects.get_or_create(**lookup, defaults=update)
    if not created:
        for k, v in update.items():
            setattr(obj, k, v)
        obj.save()
    return obj


# ─── 2. DCIM — Site, Manufacturers, Device Types, Roles ───────────────────────
print("\n[1/8] DCIM base objects...")

from dcim.models import (
    Site,
    Manufacturer,
    DeviceType,
    DeviceRole,
    Rack,
    Device,
    Interface,
    Cable,
)
from dcim.choices import DeviceStatusChoices, CableTypeChoices, InterfaceTypeChoices

site = gcu(Site, {"slug": "dc-01"}, name="DC-01", status="active")

mfr_cisco = gc(Manufacturer, slug="cisco", defaults={"name": "Cisco"})
mfr_dell = gc(Manufacturer, slug="dell", defaults={"name": "Dell"})

dt_spine = gcu(
    DeviceType,
    {"slug": "nexus-9516"},
    manufacturer=mfr_cisco,
    model="Nexus 9516",
    u_height=14,
)
dt_leaf = gcu(
    DeviceType,
    {"slug": "nexus-93180yc-ex"},
    manufacturer=mfr_cisco,
    model="Nexus 93180YC-EX",
    u_height=1,
)
dt_hv = gcu(
    DeviceType,
    {"slug": "dell-r750"},
    manufacturer=mfr_dell,
    model="PowerEdge R750",
    u_height=2,
)

role_spine = gc(
    DeviceRole,
    slug="spine-switch",
    defaults={"name": "Spine Switch", "color": "1a237e"},
)
role_leaf = gc(
    DeviceRole, slug="leaf-switch", defaults={"name": "Leaf Switch", "color": "0d47a1"}
)
role_hv = gc(
    DeviceRole, slug="hypervisor", defaults={"name": "Hypervisor", "color": "004d40"}
)

print("  ✓ site, manufacturers, device types, roles")

# ─── 3. Racks ─────────────────────────────────────────────────────────────────
print("\n[2/8] Racks...")

DEMO_DOMAIN = "demo.de"

# Zone-Name → DNS-Subdomain (FQDN: {host}.{sub}.demo.de)
ZONE_DNS_SUB = {
    "prod": "prod",
    "integration-1": "int1",
    "integration-2": "int2",
    "integration-3": "int3",
    "dev-1": "dev1",
    "dev-2": "dev2",
    "dev-3": "dev3",
    "test-1": "tst1",
    "test-2": "tst2",
    "test-3": "tst3",
    "infrastructure": "infra",
}

ZONES = [
    ("prod", "10.1"),
    ("integration-1", "10.2"),
    ("integration-2", "10.3"),
    ("integration-3", "10.4"),
    ("dev-1", "10.5"),
    ("dev-2", "10.6"),
    ("dev-3", "10.7"),
    ("test-1", "10.8"),
    ("test-2", "10.9"),
    ("test-3", "10.10"),
]

rack_spine = gc(
    Rack, site=site, name="SPINE-A01", defaults={"u_height": 42, "status": "active"}
)
rack_infra = gc(
    Rack, site=site, name="INFRA-A01", defaults={"u_height": 42, "status": "active"}
)

zone_racks = {}
for zname, _ in ZONES:
    slug = zname.replace("-", "").upper()
    r1 = gc(
        Rack,
        site=site,
        name=f"{slug}-A01",
        defaults={"u_height": 42, "status": "active"},
    )
    r2 = gc(
        Rack,
        site=site,
        name=f"{slug}-A02",
        defaults={"u_height": 42, "status": "active"},
    )
    zone_racks[zname] = (r1, r2)

print(f"  ✓ {2 + 1 + len(ZONES)*2} racks")

# ─── 4. Spine Switches ────────────────────────────────────────────────────────
print("\n[3/8] Spine Switches + Leaf Switches + Hypervisors...")

spines = []
for i, sp_name in enumerate(["SPINE-01", "SPINE-02"], 1):
    d = gcu(
        Device,
        {"name": sp_name, "site": site},
        device_type=dt_spine,
        role=role_spine,
        rack=rack_spine,
        position=1 + (i - 1) * 14,
        status=DeviceStatusChoices.STATUS_ACTIVE,
    )
    spines.append(d)


def _ensure_iface(device, name, iface_type=InterfaceTypeChoices.TYPE_100GE_QSFP28):
    return gc(Interface, device=device, name=name, defaults={"type": iface_type})


# Spine uplink interfaces (numbered per leaf connection)
sp_uplink_counter = [1, 1]  # per spine

leaf_devices = {}  # zname → (leaf1, leaf2)
hv_devices = {}  # zname → (hv1, hv2)
infra_hvs = []


def _create_leaf_pair(zname, rack_a, rack_b, leaf_prefix, u_base=3):
    l1 = gcu(
        Device,
        {"name": f"LEAF-{leaf_prefix}-01", "site": site},
        device_type=dt_leaf,
        role=role_leaf,
        rack=rack_a,
        position=u_base,
        status=DeviceStatusChoices.STATUS_ACTIVE,
    )
    l2 = gcu(
        Device,
        {"name": f"LEAF-{leaf_prefix}-02", "site": site},
        device_type=dt_leaf,
        role=role_leaf,
        rack=rack_b,
        position=u_base,
        status=DeviceStatusChoices.STATUS_ACTIVE,
    )
    return l1, l2


def _create_hv_pair(zname, rack_a, rack_b, hv_prefix, u_base=5):
    h1 = gcu(
        Device,
        {"name": f"HV-{hv_prefix}-01", "site": site},
        device_type=dt_hv,
        role=role_hv,
        rack=rack_a,
        position=u_base,
        status=DeviceStatusChoices.STATUS_ACTIVE,
    )
    h2 = gcu(
        Device,
        {"name": f"HV-{hv_prefix}-02", "site": site},
        device_type=dt_hv,
        role=role_hv,
        rack=rack_b,
        position=u_base,
        status=DeviceStatusChoices.STATUS_ACTIVE,
    )
    return h1, h2


# Infra
l_infra1, l_infra2 = _create_leaf_pair(
    "infra", rack_infra, rack_infra, "INFRA", u_base=3
)
h_infra1, h_infra2 = _create_hv_pair("infra", rack_infra, rack_infra, "INFRA", u_base=7)
infra_hvs = [h_infra1, h_infra2]
leaf_devices["infrastructure"] = (l_infra1, l_infra2)
hv_devices["infrastructure"] = (h_infra1, h_infra2)

# Zone leafs + HVs
LEAF_PREFIXES = {
    "prod": "PROD",
    "integration-1": "INT1",
    "integration-2": "INT2",
    "integration-3": "INT3",
    "dev-1": "DEV1",
    "dev-2": "DEV2",
    "dev-3": "DEV3",
    "test-1": "TST1",
    "test-2": "TST2",
    "test-3": "TST3",
}

for zname, _ in ZONES:
    pfx = LEAF_PREFIXES[zname]
    rack_a, rack_b = zone_racks[zname]
    l1, l2 = _create_leaf_pair(zname, rack_a, rack_b, pfx)
    h1, h2 = _create_hv_pair(zname, rack_a, rack_b, pfx)
    leaf_devices[zname] = (l1, l2)
    hv_devices[zname] = (h1, h2)

print(
    f"  ✓ {len(spines)} spines, {len(leaf_devices)*2} leafs, {len(hv_devices)*2} hypervisors"
)

# ─── 5. Cables (Spine↔Leaf, Leaf↔HV) ─────────────────────────────────────────
print("\n[4/8] Cables...")

cable_count = 0


def _cable(a_iface, b_iface):
    global cable_count
    if Cable.objects.filter(terminations__interface=a_iface).exists():
        return
    c = Cable(type=CableTypeChoices.TYPE_DAC_PASSIVE)
    c.save()
    from dcim.models import CableTermination
    from django.contrib.contenttypes.models import ContentType

    iface_ct = ContentType.objects.get_for_model(Interface)
    CableTermination.objects.get_or_create(
        cable=c,
        cable_end="A",
        defaults={"termination_type": iface_ct, "termination_id": a_iface.pk},
    )
    CableTermination.objects.get_or_create(
        cable=c,
        cable_end="B",
        defaults={"termination_type": iface_ct, "termination_id": b_iface.pk},
    )
    cable_count += 1


# Spine ↔ Leaf (40GE, 4 uplinks per leaf)
sp_port = {spines[0]: 1, spines[1]: 1}
for zname, (l1, l2) in leaf_devices.items():
    for leaf_idx, leaf in enumerate([l1, l2]):
        for sp_idx, spine in enumerate(spines):
            for link_num in range(1, 3):  # 2 links per spine per leaf
                leaf_iface = _ensure_iface(
                    leaf,
                    f"Ethernet1/{49 + sp_idx*2 + (link_num-1)}",
                    InterfaceTypeChoices.TYPE_40GE_QSFP_PLUS,
                )
                spine_iface = _ensure_iface(
                    spine,
                    f"Ethernet1/{sp_port[spine]}",
                    InterfaceTypeChoices.TYPE_40GE_QSFP_PLUS,
                )
                sp_port[spine] += 1
                _cable(leaf_iface, spine_iface)

# HV ↔ Leaf (10GE, 4 ports per HV — 2 per leaf for vPC)
for zname, (h1, h2) in hv_devices.items():
    l1, l2 = leaf_devices[zname]
    hv_port_base = 1
    for hv_idx, hv in enumerate([h1, h2]):
        for leaf_idx, leaf in enumerate([l1, l2]):
            for port_num in range(1, 3):  # 2×10GE per leaf
                hv_iface = _ensure_iface(
                    hv,
                    f"eth{leaf_idx*2 + port_num - 1}",
                    InterfaceTypeChoices.TYPE_10GE_SFP_PLUS,
                )
                leaf_iface = _ensure_iface(
                    leaf,
                    f"Ethernet1/{hv_idx*4 + leaf_idx*2 + port_num}",
                    InterfaceTypeChoices.TYPE_10GE_SFP_PLUS,
                )
                _cable(hv_iface, leaf_iface)

print(f"  ✓ {cable_count} cables (skipped existing)")

# ─── 6. VMs, Prefixes, IPs ────────────────────────────────────────────────────
print("\n[5/8] Clusters, VMs, Prefixes, IPs...")

from virtualization.models import Cluster, ClusterType, VirtualMachine, VMInterface
from ipam.models import Prefix, IPAddress, VRF
from ipam.choices import PrefixStatusChoices

ct_vsphere = gc(ClusterType, slug="vmware-vsphere", defaults={"name": "VMware vSphere"})
ct_gce = gc(
    ClusterType,
    slug="google-compute-engine",
    defaults={"name": "Google Compute Engine"},
)

cluster_dc = gc(Cluster, name="dc-vsphere", defaults={"type": ct_vsphere})
cluster_gcp = gc(Cluster, name="gcp-dmz", defaults={"type": ct_gce})

# VRFs
vrf_core = gc(VRF, name="core", defaults={"rd": "65000:1"})
vrf_mgmt = gc(VRF, name="mgmt", defaults={"rd": "65000:254"})
vrf_gcp = gc(VRF, name="gcp-dmz", defaults={"rd": "65000:200"})

# Supernet
gc(
    Prefix,
    prefix="10.0.0.0/8",
    defaults={
        "vrf": vrf_core,
        "status": "container",
        "description": "DC-01 RFC1918 Adressraum (Container)",
    },
)

# Infrastructure
gc(
    Prefix,
    prefix="10.0.0.0/24",
    defaults={
        "vrf": vrf_core,
        "status": "active",
        "description": "Infrastructure Zone — AD, DNS-Forwarder, SIEM",
    },
)
gc(
    Prefix,
    prefix="10.254.0.0/24",
    defaults={
        "vrf": vrf_mgmt,
        "status": "active",
        "description": "OOB-Management (Out-of-Band)",
    },
)
gc(
    Prefix,
    prefix="10.253.0.0/24",
    defaults={
        "vrf": vrf_mgmt,
        "status": "active",
        "description": "HV-Management (Hypervisor iDRAC/iLO)",
    },
)
gc(
    Prefix,
    prefix="10.100.0.0/23",
    defaults={
        "vrf": vrf_core,
        "status": "active",
        "description": "User/Client-Netz (Endgeräte, VPN-Zugänge)",
    },
)

# Zone prefixes
ZONE_DESC = {
    "prod": "Production Zone",
    "integration-1": "Integration Zone 1",
    "integration-2": "Integration Zone 2",
    "integration-3": "Integration Zone 3",
    "dev-1": "Development Zone 1",
    "dev-2": "Development Zone 2",
    "dev-3": "Development Zone 3",
    "test-1": "Test Zone 1",
    "test-2": "Test Zone 2",
    "test-3": "Test Zone 3",
}
for zname, oct3 in ZONES:
    prefix_str = f"{oct3}.0.0/16"
    gc(
        Prefix,
        prefix=prefix_str,
        defaults={
            "vrf": vrf_core,
            "status": "active",
            "description": ZONE_DESC.get(zname, zname),
        },
    )

# GCP
gc(
    Prefix,
    prefix="10.200.0.0/16",
    defaults={
        "vrf": vrf_gcp,
        "status": "active",
        "description": "GCP DMZ — Summenprefix alle DMZ-Subnetze",
    },
)
for sub, name in [
    ("10.200.1.0/24", "dmz-web"),
    ("10.200.2.0/24", "dmz-api"),
    ("10.200.3.0/24", "dmz-auth"),
]:
    label = {
        "dmz-web": "GCP DMZ Web-Server",
        "dmz-api": "GCP DMZ API-Server",
        "dmz-auth": "GCP DMZ Auth-Server",
    }[name]
    gc(
        Prefix,
        prefix=sub,
        defaults={"vrf": vrf_gcp, "status": "active", "description": label},
    )

# VM definitions per zone
VM_SPECS = [
    # (hostname_suffix,  ip_suffix,        role_tag,      app_tag,    tier_tag)
    ("ad-dc", "0.10", "dc", "ad", "infrastructure"),
    ("dns", "0.11", "dns-resolver", "dns", "infrastructure"),
    ("ntp", "0.12", "ntp-server", "ntp", "infrastructure"),
    ("syslog", "0.13", "syslog-relay", "logging", "infrastructure"),
    ("pki-ca", "0.14", "pki-ca", "pki", "infrastructure"),
    ("jump", "0.50", "jump-server", "jump", "management"),
    ("mon", "0.51", "collector", "monitoring", "management"),
    ("backup-01", "0.52", "backup-agent", "backup", "management"),
    ("backup-02", "0.53", "backup-agent", "backup", "management"),
    ("web-01", "1.1", "web-server", "web", "frontend"),
    ("web-02", "1.2", "web-server", "web", "frontend"),
    ("web-03", "1.3", "web-server", "web", "frontend"),
    ("web-04", "1.4", "web-server", "web", "frontend"),
    ("web-05", "1.5", "web-server", "web", "frontend"),
    ("web-06", "1.6", "web-server", "web", "frontend"),
    ("web-07", "1.7", "web-server", "web", "frontend"),
    ("web-08", "1.8", "web-server", "web", "frontend"),
    ("web-09", "1.9", "web-server", "web", "frontend"),
    ("web-10", "1.10", "web-server", "web", "frontend"),
    ("app-01", "2.1", "app-server", "app", "application"),
    ("app-02", "2.2", "app-server", "app", "application"),
    ("app-03", "2.3", "app-server", "app", "application"),
    ("app-04", "2.4", "app-server", "app", "application"),
    ("app-05", "2.5", "app-server", "app", "application"),
    ("app-06", "2.6", "app-server", "app", "application"),
    ("app-07", "2.7", "app-server", "app", "application"),
    ("app-08", "2.8", "app-server", "app", "application"),
    ("app-09", "2.9", "app-server", "app", "application"),
    ("app-10", "2.10", "app-server", "app", "application"),
    ("app-11", "2.11", "app-server", "app", "application"),
    ("app-12", "2.12", "app-server", "app", "application"),
    ("app-13", "2.13", "app-server", "app", "application"),
    ("app-14", "2.14", "app-server", "app", "application"),
    ("app-15", "2.15", "app-server", "app", "application"),
    ("db-01", "3.1", "db-primary", "db", "data"),
    ("db-02", "3.2", "db-primary", "db", "data"),
    ("db-03", "3.3", "db-primary", "db", "data"),
    ("db-04", "3.4", "db-primary", "db", "data"),
    ("db-05", "3.5", "db-primary", "db", "data"),
    ("db-06", "3.6", "db-primary", "db", "data"),
    ("db-07", "3.7", "db-primary", "db", "data"),
    ("db-08", "3.8", "db-primary", "db", "data"),
    ("db-09", "3.9", "db-primary", "db", "data"),
    ("db-10", "3.10", "db-primary", "db", "data"),
    ("db-rep-01", "3.11", "db-replica", "db", "data"),
    ("db-rep-02", "3.12", "db-replica", "db", "data"),
    ("db-rep-03", "3.13", "db-replica", "db", "data"),
    ("db-rep-04", "3.14", "db-replica", "db", "data"),
    ("db-rep-05", "3.15", "db-replica", "db", "data"),
    ("db-rep-06", "3.16", "db-replica", "db", "data"),
]

# ── NetBox Tags (für alle Label-Dimensionen) ──────────────────────────────────
from extras.models import Tag as NbTag
from django.contrib.contenttypes.models import ContentType as DjCT

_TAG_COLORS = {
    "env:prod": "1565c0",
    "env:integration-1": "2e7d32",
    "env:integration-2": "388e3c",
    "env:integration-3": "43a047",
    "env:dev-1": "e64a19",
    "env:dev-2": "f4511e",
    "env:dev-3": "ff5722",
    "env:test-1": "6a1b9a",
    "env:test-2": "7b1fa2",
    "env:test-3": "8e24aa",
    "env:infrastructure": "880e4f",
    "env:gcp-dmz": "00796b",
    "app:ad": "3f51b5",
    "app:dns": "009688",
    "app:ntp": "4caf50",
    "app:logging": "607d8b",
    "app:pki": "9c27b0",
    "app:web": "2196f3",
    "app:app": "00bcd4",
    "app:db": "ff5722",
    "app:jump": "795548",
    "app:monitoring": "ff9800",
    "app:backup": "8bc34a",
    "tier:infrastructure": "546e7a",
    "tier:frontend": "0277bd",
    "tier:application": "00838f",
    "tier:data": "6a1b9a",
    "tier:management": "558b2f",
}


def _get_tag(key):
    slug = key.replace(":", "-")[:50]
    color = _TAG_COLORS.get(key, "9e9e9e")
    tag, _ = NbTag.objects.get_or_create(
        slug=slug, defaults={"name": key, "color": color}
    )
    return tag


# Alle benötigten Tags vorab anlegen
_tags_needed = set()
for zname, _ in ZONES:
    _tags_needed.add(f"env:{zname}")
_tags_needed.add("env:infrastructure")
_tags_needed.add("env:gcp-dmz")
for suffix, ip_suffix, role, app, tier in VM_SPECS:
    _tags_needed.update({f"app:{app}", f"role:{role}", f"tier:{tier}"})
for _, _, role, app, tier in [
    ("", "", "gc", "ad", "infrastructure"),
    ("", "", "dns-forwarder", "dns", "infrastructure"),
    ("", "", "siem", "monitoring", "infrastructure"),
]:
    _tags_needed.update({f"app:{app}", f"role:{role}", f"tier:{tier}"})
for key in ["role:web-server", "role:api-server", "role:auth-server"]:
    _tags_needed.add(key)

tag_cache = {key: _get_tag(key) for key in sorted(_tags_needed)}
print(f"  ✓ {len(tag_cache)} NetBox tags angelegt")

# ── IP→Interface-Hilfsfunktion ────────────────────────────────────────────────
_iface_ct = DjCT.objects.get_for_model(VMInterface)


def _assign_ip(ip_obj, iface, vrf=None, dns=None):
    """IP an Interface zuweisen (assigned_object) und primary_ip4 setzen."""
    dirty = False
    if (
        ip_obj.assigned_object_type_id != _iface_ct.pk
        or ip_obj.assigned_object_id != iface.pk
    ):
        ip_obj.assigned_object_type = _iface_ct
        ip_obj.assigned_object_id = iface.pk
        dirty = True
    if dns and not ip_obj.dns_name:
        ip_obj.dns_name = dns
        dirty = True
    if vrf and ip_obj.vrf_id != vrf.pk:
        ip_obj.vrf = vrf
        dirty = True
    if dirty:
        ip_obj.save()


def _set_primary(vm, ip_obj):
    vm.refresh_from_db(fields=["primary_ip4"])
    if vm.primary_ip4_id != ip_obj.pk:
        vm.primary_ip4 = ip_obj
        vm.save()


def _set_tags(vm, *tag_keys):
    tags = [tag_cache[k] for k in tag_keys if k in tag_cache]
    existing = set(vm.tags.values_list("pk", flat=True))
    new_pks = {t.pk for t in tags}
    if not new_pks.issubset(existing):
        vm.tags.add(*tags)


# ── Zone-VMs ──────────────────────────────────────────────────────────────────
vm_count = 0
ip_count = 0

with transaction.atomic():
    for zname, oct3 in ZONES:
        hv1, hv2 = hv_devices[zname]
        for idx, (suffix, ip_suffix, role_tag, app_tag, tier_tag) in enumerate(
            VM_SPECS
        ):
            hostname = f"{suffix}-{zname}"
            hv = hv1 if idx % 2 == 0 else hv2
            vm, _ = VirtualMachine.objects.get_or_create(
                name=hostname,
                defaults={
                    "cluster": cluster_dc,
                    "site": site,
                    "status": "active",
                    "vcpus": 4,
                    "memory": 8192,
                },
            )
            vm_count += 1
            iface, _ = VMInterface.objects.get_or_create(
                virtual_machine=vm, name="eth0"
            )
            ip_str = f"{oct3}.{ip_suffix}/16"
            dns_name = f"{suffix}.{ZONE_DNS_SUB[zname]}.{DEMO_DOMAIN}"
            ip_obj, created = IPAddress.objects.get_or_create(
                address=ip_str,
                defaults={"vrf": vrf_core, "status": "active", "dns_name": dns_name},
            )
            if created:
                ip_count += 1
            _assign_ip(ip_obj, iface, vrf=vrf_core, dns=dns_name)
            _set_primary(vm, ip_obj)
            _set_tags(
                vm,
                f"env:{zname}",
                f"app:{app_tag}",
                f"role:{role_tag}",
                f"tier:{tier_tag}",
            )

    # ── Infra-VMs ─────────────────────────────────────────────────────────────
    INFRA_VMS = [
        ("ad-gc-01", "10.0.0.10", "gc", "ad", "infrastructure"),
        ("ad-gc-02", "10.0.0.11", "gc", "ad", "infrastructure"),
        ("dns-fwd-01", "10.0.0.20", "dns-forwarder", "dns", "infrastructure"),
        ("dns-fwd-02", "10.0.0.21", "dns-forwarder", "dns", "infrastructure"),
        ("siem-01", "10.0.0.30", "siem", "monitoring", "infrastructure"),
        ("siem-02", "10.0.0.31", "siem", "monitoring", "infrastructure"),
    ]
    for hostname, ip_str, role_tag, app_tag, tier_tag in INFRA_VMS:
        vm, _ = VirtualMachine.objects.get_or_create(
            name=hostname,
            defaults={
                "cluster": cluster_dc,
                "site": site,
                "status": "active",
                "vcpus": 4,
                "memory": 16384,
            },
        )
        vm_count += 1
        iface, _ = VMInterface.objects.get_or_create(virtual_machine=vm, name="eth0")
        dns_name = f"{hostname}.infra.{DEMO_DOMAIN}"
        ip_obj, created = IPAddress.objects.get_or_create(
            address=f"{ip_str}/24",
            defaults={"vrf": vrf_core, "status": "active", "dns_name": dns_name},
        )
        if created:
            ip_count += 1
        _assign_ip(ip_obj, iface, vrf=vrf_core, dns=dns_name)
        _set_primary(vm, ip_obj)
        _set_tags(
            vm,
            "env:infrastructure",
            f"app:{app_tag}",
            f"role:{role_tag}",
            f"tier:{tier_tag}",
        )

    # ── GCP-VMs ───────────────────────────────────────────────────────────────
    GCP_VMS = [
        ("dmz-web-01", "10.200.1.10", "web-server", "web", "frontend"),
        ("dmz-web-02", "10.200.1.11", "web-server", "web", "frontend"),
        ("dmz-web-03", "10.200.1.12", "web-server", "web", "frontend"),
        ("dmz-web-04", "10.200.1.13", "web-server", "web", "frontend"),
        ("dmz-web-05", "10.200.1.14", "web-server", "web", "frontend"),
        ("dmz-api-01", "10.200.2.10", "api-server", "app", "application"),
        ("dmz-api-02", "10.200.2.11", "api-server", "app", "application"),
        ("dmz-api-03", "10.200.2.12", "api-server", "app", "application"),
        ("dmz-auth-01", "10.200.3.10", "auth-server", "app", "application"),
        ("dmz-auth-02", "10.200.3.11", "auth-server", "app", "application"),
    ]
    for hostname, ip_str, role_tag, app_tag, tier_tag in GCP_VMS:
        vm, _ = VirtualMachine.objects.get_or_create(
            name=hostname,
            defaults={
                "cluster": cluster_gcp,
                "status": "active",
                "vcpus": 2,
                "memory": 4096,
            },
        )
        vm_count += 1
        iface, _ = VMInterface.objects.get_or_create(virtual_machine=vm, name="eth0")
        dns_name = f"{hostname}.gcp.{DEMO_DOMAIN}"
        ip_obj, created = IPAddress.objects.get_or_create(
            address=f"{ip_str}/24",
            defaults={"vrf": vrf_gcp, "status": "active", "dns_name": dns_name},
        )
        if created:
            ip_count += 1
        _assign_ip(ip_obj, iface, vrf=vrf_gcp, dns=dns_name)
        _set_primary(vm, ip_obj)
        _set_tags(
            vm, "env:gcp-dmz", f"app:{app_tag}", f"role:{role_tag}", f"tier:{tier_tag}"
        )

print(f"  ✓ {vm_count} VMs, {ip_count} new IPs")

# ─── 7. NSM Objects ───────────────────────────────────────────────────────────
print("\n[6/8] NSM COT objects (Zones, Addresses, Labels, Services)...")


def _get_cot_model(slug):
    cot = CustomObjectType.objects.get(slug=slug)
    return cot.get_model()


ZoneModel = _get_cot_model("nsm_zones")
AddrModel = _get_cot_model("nsm_addresses")
LabelModel = _get_cot_model("nsm_labels")
ServiceModel = _get_cot_model("nsm_services")
ActionModel = _get_cot_model("nsm_action")

# ── Zones ──────────────────────────────────────────────────────────────────────
ZONE_DEFS = [
    ("prod", "#1565c0"),
    ("integration-1", "#2e7d32"),
    ("integration-2", "#388e3c"),
    ("integration-3", "#43a047"),
    ("dev-1", "#e64a19"),
    ("dev-2", "#f4511e"),
    ("dev-3", "#ff5722"),
    ("test-1", "#6a1b9a"),
    ("test-2", "#7b1fa2"),
    ("test-3", "#8e24aa"),
    ("infrastructure", "#880e4f"),
]

zones_by_name = {}
for zname, color in ZONE_DEFS:
    obj, _ = ZoneModel.objects.get_or_create(name=zname, defaults={"color": color})
    if obj.color != color:
        obj.color = color
        obj.save()
    zones_by_name[zname] = obj
print(f"  ✓ {len(zones_by_name)} zones")

# ── Addresses ─────────────────────────────────────────────────────────────────
ADDR_DEFS = [
    ("10.0.0.0/24", "infrastructure"),
    ("10.1.0.0/16", "prod"),
    ("10.2.0.0/16", "integration-1"),
    ("10.3.0.0/16", "integration-2"),
    ("10.4.0.0/16", "integration-3"),
    ("10.5.0.0/16", "dev-1"),
    ("10.6.0.0/16", "dev-2"),
    ("10.7.0.0/16", "dev-3"),
    ("10.8.0.0/16", "test-1"),
    ("10.9.0.0/16", "test-2"),
    ("10.10.0.0/16", "test-3"),
    ("10.100.0.0/23", "user-clients"),
    ("10.253.0.0/24", "hv-mgmt"),
    ("10.254.0.0/24", "oob-mgmt"),
    ("10.200.0.0/16", "gcp-dmz"),
    ("10.200.1.0/24", "gcp-dmz-web"),
    ("10.200.2.0/24", "gcp-dmz-api"),
    ("10.200.3.0/24", "gcp-dmz-auth"),
    ("0.0.0.0/0", "internet"),
]

addrs_by_name = {}
for addr_str, name in ADDR_DEFS:
    # Try to link to the matching IPAM Prefix; fall back to storing CIDR in comments
    prefix_obj = None
    if addr_str != "0.0.0.0/0":
        try:
            prefix_obj = Prefix.objects.get(prefix=addr_str)
        except (Prefix.DoesNotExist, Prefix.MultipleObjectsReturned):
            pass
    defaults = (
        {"prefix": prefix_obj, "comments": ""} if prefix_obj else {"comments": addr_str}
    )
    obj, created = AddrModel.objects.get_or_create(name=name, defaults=defaults)
    if not created and prefix_obj and obj.prefix_id is None:
        obj.prefix = prefix_obj
        obj.comments = ""
        obj.save()
    addrs_by_name[name] = obj
print(f"  ✓ {len(addrs_by_name)} addresses")

# ── Labels (4 dimensions) ─────────────────────────────────────────────────────
LABEL_DEFS = [
    # (name, label_type)
    # Env
    ("prod", "env"),
    ("integration-1", "env"),
    ("integration-2", "env"),
    ("integration-3", "env"),
    ("dev-1", "env"),
    ("dev-2", "env"),
    ("dev-3", "env"),
    ("test-1", "env"),
    ("test-2", "env"),
    ("test-3", "env"),
    ("infrastructure", "env"),
    # App
    ("ad", "app"),
    ("dns", "app"),
    ("ntp", "app"),
    ("logging", "app"),
    ("pki", "app"),
    ("web", "app"),
    ("app", "app"),
    ("db", "app"),
    ("jump", "app"),
    ("monitoring", "app"),
    ("backup", "app"),
    # Role
    ("dc", "role"),
    ("gc", "role"),
    ("dns-resolver", "role"),
    ("dns-forwarder", "role"),
    ("ntp-server", "role"),
    ("syslog-relay", "role"),
    ("pki-ca", "role"),
    ("web-server", "role"),
    ("app-server", "role"),
    ("db-primary", "role"),
    ("db-replica", "role"),
    ("jump-server", "role"),
    ("collector", "role"),
    ("siem", "role"),
    ("backup-agent", "role"),
    ("dc-gc", "role"),
    # Tier
    ("infrastructure", "tier"),
    ("frontend", "tier"),
    ("application", "tier"),
    ("data", "tier"),
    ("management", "tier"),
]

labels_by_key = {}
for lname, ltype in LABEL_DEFS:
    obj, _ = LabelModel.objects.get_or_create(
        name=lname,
        defaults={"label_type": ltype} if hasattr(LabelModel, "label_type") else {},
    )
    # store field data if model supports it
    labels_by_key[f"{ltype}:{lname}"] = obj
print(f"  ✓ {len(labels_by_key)} labels")

# ── Services ──────────────────────────────────────────────────────────────────
SVC_DEFS = [
    # (name, protocol, port)
    ("SSH", "tcp", 22),
    ("HTTPS", "tcp", 443),
    ("HTTP", "tcp", 80),
    ("RDP", "tcp", 3389),
    ("DNS-UDP", "udp", 53),
    ("DNS-TCP", "tcp", 53),
    ("NTP", "udp", 123),
    ("Syslog-UDP", "udp", 514),
    ("Syslog-TCP", "tcp", 6514),
    ("LDAP", "tcp", 389),
    ("LDAP-UDP", "udp", 389),
    ("LDAPS", "tcp", 636),
    ("Kerberos-TCP", "tcp", 88),
    ("Kerberos-UDP", "udp", 88),
    ("SMB", "tcp", 445),
    ("RPC-EPM", "tcp", 135),
    ("Kpasswd-TCP", "tcp", 464),
    ("Kpasswd-UDP", "udp", 464),
    ("GC-LDAP", "tcp", 3268),
    ("GC-LDAPS", "tcp", 3269),
    ("RPC-Dyn", "tcp", 50000),
    ("MySQL", "tcp", 3306),
    ("PostgreSQL", "tcp", 5432),
    ("MSSQL", "tcp", 1433),
    ("Prometheus", "tcp", 9100),
    ("Telegraf", "udp", 8125),
    ("Logstash", "tcp", 5044),
    ("Elasticsearch", "tcp", 9200),
    ("Backup", "tcp", 10000),
    ("App-HTTP", "tcp", 8080),
    ("App-HTTPS", "tcp", 8443),
    ("BGP", "tcp", 179),
    ("IPSec-UDP", "udp", 4500),
    ("IPSec-ESP", "ip", 0),
]

svcs_by_name = {}
for sname, proto, port in SVC_DEFS:
    obj, _ = ServiceModel.objects.get_or_create(
        name=sname,
        defaults={"protocol": proto, "port": port if port else None},
    )
    svcs_by_name[sname] = obj
print(f"  ✓ {len(svcs_by_name)} services")

# ── Actions ────────────────────────────────────────────────────────────────────
actions_by_name = {}
for aname, color in [("Permit", "#28a745"), ("Deny", "#dc3545"), ("Reject", "#fd7e14")]:
    obj, _ = ActionModel.objects.get_or_create(name=aname, defaults={"color": color})
    if obj.color != color:
        obj.color = color
        obj.save()
    actions_by_name[aname.lower()] = obj
print(f"  ✓ {len(actions_by_name)} actions")

# ─── 8. Rulebooks ─────────────────────────────────────────────────────────────
print("\n[7/8] Rulebooks + Rules...")
print("  SKIP: native ORM rulebooks removed — use COT rulebooks (nsm_rb_*) via Setup wizard.")

# ─── 9. ObjectLinks: Prefix + VM → Zone ────────────────────────────────────
print("\n[8/8] NSM Object Links (Prefix → Zone, VM → Zone)...")

from netbox_nsm.objects.link_propagation import CotObjectLinkPropagationChoices
from netbox_nsm.objects.object_link_service import create_or_update_links
from ipam.models import Prefix
from django.contrib.contenttypes.models import ContentType as DjCT2

prefix_ct = DjCT2.objects.get_for_model(Prefix)
vm_ct = DjCT2.objects.get_for_model(VirtualMachine)


def _link(obj_a, ct_a, obj_b, ct_b):
    create_or_update_links(
        obj_a,
        obj_b,
        cot_propagation=CotObjectLinkPropagationChoices.DIRECT,
    )


link_count = 0

# ── Prefix → Zone ─────────────────────────────────────────────────────────────
# Zone-Name → Prefix-CIDR Mapping
ZONE_PREFIX_MAP = {
    "prod": "10.1.0.0/16",
    "integration-1": "10.2.0.0/16",
    "integration-2": "10.3.0.0/16",
    "integration-3": "10.4.0.0/16",
    "dev-1": "10.5.0.0/16",
    "dev-2": "10.6.0.0/16",
    "dev-3": "10.7.0.0/16",
    "test-1": "10.8.0.0/16",
    "test-2": "10.9.0.0/16",
    "test-3": "10.10.0.0/16",
    "infrastructure": "10.0.0.0/24",
}
# GCP-Subnetze → Zone "infrastructure" (kein eigener Zone-Eintrag für GCP-DMZ Präfix)
GCP_PREFIX_ZONE_MAP = {
    "10.200.0.0/16": "infrastructure",
    "10.200.1.0/24": "infrastructure",
    "10.200.2.0/24": "infrastructure",
    "10.200.3.0/24": "infrastructure",
}

with transaction.atomic():
    for zname, cidr in ZONE_PREFIX_MAP.items():
        zone_obj = zones_by_name.get(zname)
        if not zone_obj:
            continue
        try:
            prefix_obj = Prefix.objects.get(prefix=cidr)
            _link(prefix_obj, prefix_ct, zone_obj, zone_ct)
            link_count += 1
        except Prefix.DoesNotExist:
            pass

    for cidr, zname in GCP_PREFIX_ZONE_MAP.items():
        zone_obj = zones_by_name.get(zname)
        if not zone_obj:
            continue
        try:
            prefix_obj = Prefix.objects.get(prefix=cidr)
            _link(prefix_obj, prefix_ct, zone_obj, zone_ct)
            link_count += 1
        except Prefix.DoesNotExist:
            pass

print(f"  ✓ {link_count} Prefix→Zone Links")

# ── VM → Zone ─────────────────────────────────────────────────────────────────
# ENV-Tag → Zone Mapping
ENV_TO_ZONE = {f"env:{z}": z for z in zones_by_name}
ENV_TO_ZONE["env:gcp-dmz"] = "infrastructure"  # GCP VMs → infrastructure zone

vm_link_count = 0
with transaction.atomic():
    for vm in VirtualMachine.objects.prefetch_related("tags"):
        tag_names = {t.name for t in vm.tags.all()}
        zone_obj = None
        for tag_name in tag_names:
            if tag_name in ENV_TO_ZONE:
                zone_obj = zones_by_name.get(ENV_TO_ZONE[tag_name])
                break
        if zone_obj:
            _link(vm, vm_ct, zone_obj, zone_ct)
            vm_link_count += 1

print(f"  ✓ {vm_link_count} VM→Zone Links")

# ─── Done ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("Enterprise DC Demo — import complete!")
print(f"  Zones:      {len(zones_by_name)}")
print(f"  Addresses:  {len(addrs_by_name)}")
print(f"  Labels:     {len(labels_by_key)}")
print(f"  Services:   {len(svcs_by_name)}")
print(f"  VMs:        {vm_count}")
print("  Rulebooks:  (native ORM removed — deploy COT rulebooks via Setup)")
print(f"  ObjLinks:   {link_count + vm_link_count} (Prefix→Zone + VM→Zone)")
print("=" * 60)
