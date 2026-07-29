"""Collect the matching mcap_recorder output for this flight.

``mcap_recorder`` (in arcz_observability) starts a ``ros2 bag record`` the
moment the vehicle arms, writing to ``<mcap_root>/arcz-<UTC arm
timestamp>/``. Both mcap_recorder and this collector react to the *same*
``/arcz/vehicle/is_armed`` message on the *same* companion-computer clock, so
matching by arm time here only needs to absorb ROS/Zenoh transport and
callback-scheduling jitter between the two containers -- unlike the PX4 ULog
match, there is no flight-controller clock involved, so no significant skew
is expected.
"""
import os
import shutil
from datetime import datetime, timezone

DIR_PREFIX = 'arcz-'
DIR_FORMAT = '%Y-%m-%dT%H-%M-%SZ'


class McapCollectorError(Exception):
    pass


def _dir_arm_time(name):
    """Parse the arm-time epoch encoded in an 'arcz-<timestamp>' directory name."""
    if not name.startswith(DIR_PREFIX):
        return None
    try:
        parsed = datetime.strptime(name[len(DIR_PREFIX):], DIR_FORMAT)
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc).timestamp()


def select_mcap_dir(mcap_root, arm_wall, tolerance_s):
    """Return the mcap_recorder output dir whose name is nearest to
    ``arm_wall`` (both companion-computer clock values), or None."""
    if not os.path.isdir(mcap_root):
        return None
    best_path = None
    best_delta = None
    for name in os.listdir(mcap_root):
        candidate_path = os.path.join(mcap_root, name)
        if not os.path.isdir(candidate_path):
            continue
        candidate_time = _dir_arm_time(name)
        if candidate_time is None:
            continue
        delta = abs(candidate_time - arm_wall)
        if delta > tolerance_s:
            continue
        if best_delta is None or delta < best_delta:
            best_path = candidate_path
            best_delta = delta
    return best_path


def collect_mcap_recording(spec, workdir, context):
    """Copy the flight's mcap_recorder output into workdir.

    Returns ``(artifact_count, cleanup_paths)``, where ``cleanup_paths``
    lists the original mcap_logs directory -- kept in place until the
    flight's zip is confirmed uploaded, then removed by the uploader.
    """
    mcap_root = os.path.expanduser(spec.get('mcap_root', '/mcap_logs'))
    tolerance_s = float(spec.get('match_tolerance_s', 15))
    arm_wall = context.get('arm_wall')
    if arm_wall is None:
        raise McapCollectorError('mcap_recording source needs context.arm_wall')

    source_dir = select_mcap_dir(mcap_root, arm_wall, tolerance_s)
    if source_dir is None:
        raise McapCollectorError(
            'no mcap recording within %.0fs of arm time in %s'
            % (tolerance_s, mcap_root))

    output_name = spec.get('output_name', 'mcap')
    dest_dir = os.path.join(workdir, output_name)
    shutil.copytree(source_dir, dest_dir)
    return 1, [source_dir]
