# Changelog

All notable changes to **netbox-nsm** are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] - 2025-06-06

First release in the 0.2.x line.

### Added

- Security Panel on prefixes, IPs, devices, VMs, and custom objects
- Rulebooks with flexible field/column layout and AG Grid policy views
- Zone matrix, All Rules grid, IP Analysis, and Object Analyzer
- Setup wizard with built-in custom object types and demo rulebooks
- REST API for rulebooks, rules, type configs, object links, and related objects
- Squashed database schema in a single `0001_initial` migration

### Requires

- NetBox 4.5+
- [netbox-custom-objects](https://github.com/netboxlabs/netbox-custom-objects)

### Notes

- Documentation-only plugin — no firewall push or policy enforcement
- See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for open items

[0.2.0]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.2.0
