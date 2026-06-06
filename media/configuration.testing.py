###################################################################
#  This file serves as a base configuration for testing purposes  #
#  only. It is not intended for production use.                   #
###################################################################

ALLOWED_HOSTS = ["*"]

DATABASE = {
    "NAME": "netbox",
    "USER": "netbox",
    "PASSWORD": "netbox",
    "HOST": "localhost",
    "PORT": "",
    "CONN_MAX_AGE": 300,
}

PLUGINS = [
    "netbox_custom_objects",
    "netbox_nsm",
]

REDIS = {
    "tasks": {
        "HOST": "localhost",
        "PORT": 6379,
        "PASSWORD": "",
        "DATABASE": 0,
        "SSL": False,
    },
    "caching": {
        "HOST": "localhost",
        "PORT": 6379,
        "PASSWORD": "",
        "DATABASE": 1,
        "SSL": False,
    },
}

# Parallel `manage.py test --parallel` workers must not share Redis cache entries
# (e.g. all-rules union layout); LocMemCache is per process.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "netbox-nsm-tests",
    }
}

SECRET_KEY = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
API_TOKEN_PEPPERS = {
    1: "TEST-VALUE-DO-NOT-USE-TEST-VALUE-DO-NOT-USE-TEST-VALUE-DO-NOT-USE",
}
