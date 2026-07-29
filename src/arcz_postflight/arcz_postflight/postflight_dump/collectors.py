"""Pluggable flight-data collectors.

Each collector takes the flight's working directory and a context dict, and
writes whatever it produces into ``workdir``. Everything left in ``workdir``
ends up in the flight zip. New source types can be added here without
touching the node logic; sources are selected in configuration.yaml under
``collection.sources`` by their ``type``.
"""
import fnmatch
import glob
import os
import shutil
import subprocess
import time


class CollectorError(Exception):
    pass


def _safe_name(name, index):
    base = ''.join(c if c.isalnum() or c in ('-', '_', '.') else '_' for c in str(name))
    return base or ('source_%d' % index)


def collect_copy_paths(spec, workdir, context):
    """Copy files/dirs matching each glob in ``paths`` into workdir/copied/."""
    dest_root = os.path.join(workdir, 'copied')
    os.makedirs(dest_root, exist_ok=True)
    modified_within = spec.get('modified_within_s')
    cutoff = None
    if modified_within is not None:
        cutoff = context.get('disarm_wall', time.time()) - float(modified_within)

    copied = 0
    for pattern in spec.get('paths', []):
        pattern = os.path.expanduser(pattern)
        for match in glob.glob(pattern):
            if cutoff is not None and os.path.getmtime(match) < cutoff:
                continue
            base = os.path.basename(match.rstrip('/')) or 'root'
            target = os.path.join(dest_root, base)
            try:
                if os.path.isdir(match):
                    shutil.copytree(match, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(match, target)
                copied += 1
            except OSError as exc:
                raise CollectorError('copy failed for %s: %s' % (match, exc))
    return copied


def collect_command(spec, workdir, context, index):
    """Run a shell command; capture stdout+stderr into <name>.log."""
    name = _safe_name(spec.get('name', 'command_%d' % index), index)
    command = spec.get('command')
    if not command:
        raise CollectorError('command source %r has no "command"' % name)
    log_path = os.path.join(workdir, '%s.log' % name)
    try:
        completed = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=spec.get('timeout_s', 60),
        )
    except subprocess.TimeoutExpired as exc:
        raise CollectorError('command %r timed out: %s' % (name, exc))
    with open(log_path, 'w') as handle:
        handle.write('# command: %s\n' % command)
        handle.write('# exit_code: %s\n\n' % completed.returncode)
        handle.write('----- STDOUT -----\n')
        handle.write(completed.stdout or '')
        handle.write('\n----- STDERR -----\n')
        handle.write(completed.stderr or '')
    return 1


def run_sources(sources, workdir, context):
    """Run every configured source in order. Returns total artifacts produced."""
    total = 0
    for index, spec in enumerate(sources or []):
        stype = spec.get('type')
        if stype == 'copy_paths':
            total += collect_copy_paths(spec, workdir, context)
        elif stype == 'command':
            total += collect_command(spec, workdir, context, index)
        elif stype == 'px4_ulog':
            from arcz_postflight.postflight_dump.px4_ulog import collect_px4_ulog
            total += collect_px4_ulog(spec, workdir, context)
        else:
            raise CollectorError('unknown collection source type: %r' % stype)
    return total
