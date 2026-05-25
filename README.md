# NetBox NSM Plugin
[Netbox](https://github.com/netbox-community/netbox) plugin for Security and NAT related objects documentation.

<div align="center">
<a href="https://pypi.org/project/netbox-nsm/"><img src="https://img.shields.io/pypi/v/netbox-nsm" alt="PyPi"/></a>
<a href="https://github.com/andy-shady-org/netbox-nsm/stargazers"><img src="https://img.shields.io/github/stars/andy-shady-org/netbox-nsm?style=flat" alt="Stars Badge"/></a>
<a href="https://github.com/andy-shady-org/netbox-nsm/network/members"><img src="https://img.shields.io/github/forks/andy-shady-org/netbox-nsm?style=flat" alt="Forks Badge"/></a>
<a href="https://github.com/andy-shady-org/netbox-nsm/issues"><img src="https://img.shields.io/github/issues/andy-shady-org/netbox-nsm" alt="Issues Badge"/></a>
<a href="https://github.com/andy-shady-org/netbox-nsm/pulls"><img src="https://img.shields.io/github/issues-pr/andy-shady-org/netbox-nsm" alt="Pull Requests Badge"/></a>
<a href="https://github.com/andy-shady-org/netbox-nsm/graphs/contributors"><img alt="GitHub contributors" src="https://img.shields.io/github/contributors/andy-shady-org/netbox-nsm?color=2b9348"></a>
<a href="https://github.com/andy-shady-org/netbox-nsm/blob/master/LICENSE"><img src="https://img.shields.io/github/license/andy-shady-org/netbox-nsm?color=2b9348" alt="License Badge"/></a>
<a href="https://github.com/psf/black"><img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Code Style Black"/></a>
<a href="https://pepy.tech/project/netbox-nsm"><img alt="Downloads" src="https://static.pepy.tech/badge/netbox-nsm"></a>
<a href="https://pepy.tech/project/netbox-nsm"><img alt="Downloads/Week" src="https://static.pepy.tech/badge/netbox-nsm/month"></a>
<a href="https://pepy.tech/project/netbox-nsm"><img alt="Downloads/Month" src="https://static.pepy.tech/badge/netbox-nsm/week"></a>
</div>


## Features

This plugin provides following Models:

* CustomPrefix
* Addresses
* Address Sets
* Address Lists
* Security Zones
* Security Zone Policies
* NAT Pools
* NAT Pool Members
* NAT Rule-sets
* NAT Rules
* Firewall Filters
* Firewall Filter Rules
* Firewall Policers

## Compatibility

| NetBox Version | NetBox NSM Version |
|----------------|-------------------------|
| NetBox 4.2     | \>= 1.0.2               |
| NetBox 4.3     | \>= 1.1.0               |
| NetBox 4.4     | \>= 1.3.0               |
| NetBox 4.5     | \>= 1.4.0               |
| NetBox 4.6     | \>= 1.5.0               |

## Installation

The plugin is available as a Python package in pypi and can be installed with pip  

```
pip install netbox-nsm
```
Enable the plugin in /opt/netbox/netbox/netbox/configuration.py:
```
PLUGINS = ['netbox_nsm']
```
Restart NetBox and add `netbox-nsm` to your local_requirements.txt

Perform database migrations:
```bash
cd /opt/netbox
source venv/bin/activate
python ./netbox/manage.py migrate netbox_nsm
python ./netbox/manage.py reindex netbox_nsm
```

Full documentation on using plugins with NetBox: [Using Plugins - NetBox Documentation](https://netbox.readthedocs.io/en/stable/plugins/)


## Configuration

The following options are available:
* `virtual_ext_page`: String (default left) Virtual Machine related objects table position. The following values are available:  
left, right, full_width. Set empty value for disable.
* `interface_ext_page`: String (default full_width) Interface related objects table position. The following values are available:  
left, right, full_width. Set empty value for disable.
* `address_ext_page`: String (default right) Address/Address Set related objects table position. The following values are available:  
left, right, full_width. Set empty value for disable.
* `top_level_menu`: Boolean (default True) Display plugin menu at the top level. The following values are available: True, False.
* `assignments_menu`: Boolean (default False) Display assignments within the plugin menu. The following values are available: True, False.

## Contribute

Contributions are always welcome! Please see the [Contribution Guidelines](CONTRIBUTING.md)


## Documentation

For further information, please refer to the full documentation: [Using NetBox NSM](docs/using_netbox_nsm.md)


## Credits

- Thanks to Peter Eckel for providing some lovely examples which I've happily borrowed, and for providing excellent guidance.
- Thanks to Dan Sheppard for the abstracted field generation stuff which I also used.
- Thanks to Kris Beevers and Mark Coleman at Netbox Labs for encouragement and engagement.
