"""Configuration loading for arcz_postflight.

Loads ``postflight_dump.yaml`` (installed into the package share directory, or
an explicit path) and exposes it via dotted-key lookups with sane defaults.
Per-vehicle values (vehicle_id, the mrblack server address) live in the root
``.env`` instead of this file, so the same YAML ships unchanged to every
vehicle -- see ``_apply_env_overrides``.
"""
import copy
import os

import yaml

PACKAGE_NAME = 'arcz_postflight'

DEFAULTS = {
    'vehicle_id': '',
    'flight_if_armed_for_s': 5.0,
    'armed_topic': '/arcz/vehicle/is_armed',
    'data_root': '/data',
    'collection': {
        'poll_interval_s': 10.0,
        'max_attempts': 3,
        'initial_delay_s': 5.0,
        'backoff_min_s': 10.0,
        'backoff_max_s': 300.0,
        'sources': [],
    },
    'upload': {
        'endpoint': 'https://example.com/uploads',
        'protocol': 'tus',
        # Cellular/Tailscale links can drop long-lived request bodies.  Small
        # tus chunks make each acknowledged offset a useful recovery point.
        'chunk_size': 64 * 1024,
        'poll_interval_s': 30.0,
        'max_attempts': 100,
        'backoff_min_s': 5.0,
        'backoff_max_s': 300.0,
        'probe_host': None,
        'probe_port': None,
        'probe_timeout_s': 3.0,
        'delete_after_upload': True,
        'auth_token': None,
        'auth_token_env': None,
    },
}


def _deep_merge(base, override):
    """Recursively merge ``override`` onto a copy of ``base``."""
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def default_config_path():
    """Return the installed postflight_dump.yaml path, with a source-tree fallback."""
    try:
        from ament_index_python.packages import get_package_share_directory
        share = get_package_share_directory(PACKAGE_NAME)
        candidate = os.path.join(share, 'config', 'postflight_dump.yaml')
        if os.path.exists(candidate):
            return candidate
    except Exception:
        pass
    # Fallback: repo root next to this package (useful for tests / dev).
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'config', 'postflight_dump.yaml',
    )


class Config:
    """Parsed configuration with dotted-key access."""

    def __init__(self, path=None):
        self.path = os.path.expanduser(path or default_config_path())
        with open(self.path, 'r') as handle:
            loaded = yaml.safe_load(handle) or {}
        self._data = _deep_merge(DEFAULTS, loaded)
        self._apply_env_overrides()

    def _apply_env_overrides(self):
        """Per-vehicle values that live in the root .env, not the tracked YAML."""
        vehicle_id = os.environ.get('VEHICLE_ID')
        if vehicle_id:
            self._data['vehicle_id'] = vehicle_id

        mrblack_host = os.environ.get('MRBLACK_HOST')
        if mrblack_host:
            self._data['upload']['endpoint'] = (
                'http://%s/api/flight-uploads' % mrblack_host)
            # Let the existing endpoint_host_port() fallback in uploader_node
            # derive probe_host/probe_port from the endpoint above.
            self._data['upload']['probe_host'] = None
            self._data['upload']['probe_port'] = None

    def get(self, dotted_key, default=None):
        """Look up ``a.b.c`` style keys, returning ``default`` if missing."""
        node = self._data
        for part in dotted_key.split('.'):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    @property
    def data_root(self):
        return os.path.expanduser(self.get('data_root'))

    @property
    def armed_topic(self):
        return self.get('armed_topic')

    @property
    def flight_if_armed_for_s(self):
        return float(self.get('flight_if_armed_for_s'))

    @property
    def vehicle_id(self):
        return str(self.get('vehicle_id') or '')
