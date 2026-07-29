"""Download the PX4 ULog (.ulg) for the just-finished flight over MAVLink.

The default path uses MAVLink FTP, whose burst reader has sequence checking,
gap detection, and retransmission. This is reliable through the Orin's
MAVProxy UDP route. The older LOG_REQUEST_DATA implementation remains
available as ``download_protocol: log_transfer`` for direct serial links.

Transport is configurable (serial USB/UART, or UDP/TCP over LAN); pymavlink
handles all three via its connection strings.

Notes learned from real PX4 firmware:
  * PX4 only talks to us once it has seen a GCS *heartbeat*, so we emit one at
    ~1 Hz throughout.
  * The autopilot is MAVLink component 1 (MAV_COMP_ID_AUTOPILOT1).
  * Logs live on the SD card; with no card inserted there are simply no logs.
"""
import datetime
import os
import time

LOG_DATA_CHUNK = 90  # bytes carried per LOG_DATA message
DEFAULT_REQUEST_WINDOW = LOG_DATA_CHUNK * 256  # 23 KiB; avoids UDP burst loss


class UlogDownloadError(Exception):
    pass


class LogBuffer:
    """Reassembles LOG_DATA chunks (by offset) into a complete log.

    Separated out so the gap-tracking / completion logic is unit-testable
    without any MAVLink connection.
    """

    def __init__(self, size):
        self.size = size
        self._buf = bytearray(size)
        self._have = bytearray(size)  # 1 where a byte has been received
        self._received = 0
        self._first_missing = 0

    def add(self, ofs, data):
        if ofs < 0 or ofs > self.size:
            return
        end = min(ofs + len(data), self.size)
        n = end - ofs
        if n <= 0:
            return
        self._buf[ofs:end] = data[:n]
        for i in range(ofs, end):
            if not self._have[i]:
                self._have[i] = 1
                self._received += 1
        if ofs <= self._first_missing < end:
            while self._first_missing < self.size and self._have[self._first_missing]:
                self._first_missing += 1

    def received_bytes(self):
        return self._received

    def is_complete(self):
        return self.received_bytes() == self.size

    def next_missing(self, max_len=None):
        """Return (offset, length) of the first missing run, or None if done."""
        i = self._first_missing
        n = self.size
        if i >= n:
            return None
        j = i
        while j < n and not self._have[j]:
            j += 1
        length = j - i
        if max_len is not None:
            length = min(length, max_len)
        return (i, length)

    def getvalue(self):
        return bytes(self._buf)


def build_connection(spec):
    """Create a pymavlink connection from a px4_ulog source spec."""
    from pymavlink import mavutil

    transport = (spec.get('transport') or 'serial').lower()
    if transport == 'serial':
        port = spec.get('serial_port', '/dev/ttyACM0')
        baud = int(spec.get('serial_baud', 115200))
        return mavutil.mavlink_connection(port, baud=baud)
    if transport == 'udp':
        # e.g. "udpin:0.0.0.0:14550" (listen) or "udpout:<ip>:14550"
        url = spec.get('udp_url', 'udpin:0.0.0.0:14550')
        return mavutil.mavlink_connection(url)
    if transport == 'tcp':
        url = spec.get('tcp_url', 'tcp:127.0.0.1:5760')
        return mavutil.mavlink_connection(url)
    raise UlogDownloadError('unknown transport: %r' % transport)


class Px4LogClient:
    """Connects to a PX4 FC and downloads ULog files over MAVLink.

    All MAVLink sends happen from the calling thread (heartbeats are emitted
    inline via ``_maybe_beat`` inside the receive loops). A single writer
    avoids interleaving bytes on the serial port, which would corrupt frames.
    """

    def __init__(self, spec):
        self.spec = spec
        self.conn = build_connection(spec)
        self.tgt_sys = int(spec.get('target_system', 0)) or None
        self.tgt_comp = int(spec.get('target_component', 1))
        self._last_beat = 0.0

    def __enter__(self):
        hb_timeout = float(self.spec.get('heartbeat_timeout_s', 15))
        # A MAVProxy ``--out=udpin:...`` endpoint does not know our return
        # address until it receives the first datagram. Announce this GCS
        # before waiting so the router can begin forwarding FC heartbeats.
        self._maybe_beat(force=True)
        if self.conn.wait_heartbeat(timeout=hb_timeout) is None:
            raise UlogDownloadError('no MAVLink heartbeat within %.0fs' % hb_timeout)
        if self.tgt_sys is None:
            self.tgt_sys = self.conn.target_system or 1
        self._maybe_beat(force=True)
        return self

    def __exit__(self, *exc):
        try:
            self.conn.close()
        except Exception:
            pass

    def _maybe_beat(self, force=False):
        """Emit a GCS heartbeat at ~1 Hz so PX4 keeps talking to us."""
        from pymavlink import mavutil
        now = time.time()
        if not force and now - self._last_beat < 1.0:
            return
        self._last_beat = now
        try:
            self.conn.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_GCS,
                mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
        except Exception:
            pass

    def list_logs(self):
        """Return {id: (size, time_utc)} for all logs on the SD card."""
        timeout = float(self.spec.get('list_timeout_s', 20))
        self.conn.mav.log_request_list_send(
            self.tgt_sys, self.tgt_comp, 0, 0xffff)
        logs = {}
        num_logs = None
        deadline = time.time() + timeout
        last_req = time.time()
        while time.time() < deadline:
            self._maybe_beat()
            msg = self.conn.recv_match(type='LOG_ENTRY', blocking=True, timeout=1)
            if msg is None:
                if not logs and time.time() - last_req > 2:
                    self.conn.mav.log_request_list_send(
                        self.tgt_sys, self.tgt_comp, 0, 0xffff)
                    last_req = time.time()
                continue
            num_logs = msg.num_logs
            if num_logs == 0:
                return {}
            logs[msg.id] = (msg.size, msg.time_utc)
            if len(logs) >= num_logs:
                break
        if num_logs is not None and len(logs) < num_logs:
            raise UlogDownloadError(
                'incomplete log list: got %d of %d entries' % (len(logs), num_logs))
        return logs

    @staticmethod
    def select_log(logs, spec, context):
        """Pick the log id for the flight. Default: newest (highest id)."""
        if not logs:
            return None
        mode = (spec.get('select') or 'newest').lower()
        if mode == 'by_time' and context and context.get('disarm_wall'):
            # Choose the log whose UTC timestamp is the latest at/under disarm.
            disarm = context['disarm_wall']
            timed = [(lid, t) for lid, (_s, t) in logs.items() if t]
            candidates = [(lid, t) for lid, t in timed if t <= disarm + 5]
            if candidates:
                return max(candidates, key=lambda kv: kv[1])[0]
        # Newest by id.
        return max(logs.keys())

    def download(self, log_id, size, dest_path):
        """Download one log to dest_path, re-requesting any missing chunks."""
        timeout = float(self.spec.get('download_timeout_s', 600))
        stall_timeout = float(self.spec.get('stall_timeout_s', 1.5))
        request_window = int(
            self.spec.get('request_window_bytes', DEFAULT_REQUEST_WINDOW))
        request_window = max(LOG_DATA_CHUNK, min(request_window, 1024 * 1024))
        buf = LogBuffer(size)

        def request_from(ofs, count):
            self.conn.mav.log_request_data_send(
                self.tgt_sys, self.tgt_comp, log_id, ofs, count)

        first_count = min(request_window, size)
        request_from(0, first_count)
        requested_end = first_count
        deadline = time.time() + timeout
        last_progress = buf.received_bytes()
        last_change = time.time()

        while not buf.is_complete():
            if time.time() > deadline:
                raise UlogDownloadError(
                    'download timed out at %d/%d bytes' % (buf.received_bytes(), size))
            self._maybe_beat()
            msg = self.conn.recv_match(type='LOG_DATA', blocking=True, timeout=1)
            if msg is not None and msg.id == log_id:
                data = bytes(bytearray(msg.data[:msg.count]))
                buf.add(msg.ofs, data)

            now = buf.received_bytes()
            if now != last_progress:
                last_progress = now
                last_change = time.time()

            gap = buf.next_missing(max_len=request_window)
            if gap is None:
                break
            ofs, length = gap
            if ofs >= requested_end:
                # The current window is complete. Ask for the next bounded
                # window rather than making PX4 flood the lossy UDP route.
                length = min(request_window, size - ofs)
                request_from(ofs, length)
                requested_end = ofs + length
                last_change = time.time()
            elif time.time() - last_change > stall_timeout:
                # Re-request only the missing part of the current window.
                length = min(length, requested_end - ofs)
                request_from(ofs, length)
                last_change = time.time()

        tmp = dest_path + '.part'
        with open(tmp, 'wb') as handle:
            handle.write(buf.getvalue())
        os.replace(tmp, dest_path)
        # Politely tell the FC we are done streaming logs.
        try:
            self.conn.mav.log_request_end_send(self.tgt_sys, self.tgt_comp)
        except Exception:
            pass
        return dest_path


def ftp_log_candidates(entries, directory, context):
    """Convert MAVFTP directory entries into timestamped ULog candidates."""
    try:
        log_date = datetime.datetime.strptime(
            directory.rsplit('/', 1)[-1], '%Y-%m-%d').date()
    except ValueError:
        return []
    candidates = []
    for entry in entries:
        if entry.is_dir or not entry.name.lower().endswith('.ulg'):
            continue
        try:
            log_time = datetime.datetime.strptime(
                entry.name[:-4], '%H_%M_%S').time()
        except ValueError:
            continue
        started = datetime.datetime.combine(
            log_date, log_time, tzinfo=datetime.timezone.utc).timestamp()
        candidates.append({
            'path': directory.rstrip('/') + '/' + entry.name,
            'name': entry.name,
            'size': int(entry.size_b),
            'started_wall': started,
            'arm_delta_s': abs(started - float(context['arm_wall'])),
        })
    return candidates


def select_ftp_log(candidates, context, tolerance_s=120):
    """Select the log whose filename timestamp is nearest the recorded arm."""
    if not candidates or not context or context.get('arm_wall') is None:
        return None
    disarm = float(context.get('disarm_wall') or context['arm_wall'])
    valid = [
        candidate for candidate in candidates
        if candidate['size'] > 0
        and candidate['started_wall'] <= disarm + 5
        and candidate['arm_delta_s'] <= float(tolerance_s)
    ]
    return min(valid, key=lambda item: item['arm_delta_s']) if valid else None


def collect_px4_ulog_ftp(spec, workdir, context, dest):
    """Collect the matching PX4 ULog through MAVLink FTP."""
    from pymavlink.mavftp import MAVFTP

    arm_time = datetime.datetime.fromtimestamp(
        float(context['arm_wall']), tz=datetime.timezone.utc)
    directory = '/fs/microsd/log/' + arm_time.strftime('%Y-%m-%d')
    timeout = float(spec.get('download_timeout_s', 600))
    tolerance = float(spec.get('match_tolerance_s', 120))
    part_path = dest + '.part'

    with Px4LogClient(spec) as client:
        ftp = MAVFTP(client.conn, client.tgt_sys, client.tgt_comp)
        result = ftp.cmd_list([directory])
        if int(result.return_code) != 0:
            raise UlogDownloadError(
                'MAVFTP could not list PX4 log directory %s (error %s)'
                % (directory, result.return_code))
        selected = select_ftp_log(
            ftp_log_candidates(ftp.list_result, directory, context),
            context,
            tolerance,
        )
        if selected is None:
            raise UlogDownloadError(
                'no PX4 ULog within %.0fs of arm time in %s'
                % (tolerance, directory))
        try:
            result = ftp.cmd_get([selected['path'], part_path])
            if int(result.return_code) != 0:
                raise UlogDownloadError(
                    'MAVFTP could not open %s (error %s)'
                    % (selected['path'], result.return_code))
            result = ftp.process_ftp_reply('get', timeout=timeout)
            if int(result.return_code) != 0:
                raise UlogDownloadError(
                    'MAVFTP download failed for %s (error %s)'
                    % (selected['path'], result.return_code))
            actual_size = os.path.getsize(part_path)
            if actual_size != selected['size']:
                raise UlogDownloadError(
                    'MAVFTP size mismatch for %s: got %d of %d bytes'
                    % (selected['path'], actual_size, selected['size']))
            os.replace(part_path, dest)
        except Exception:
            try:
                os.remove(part_path)
            except OSError:
                pass
            raise
    return selected


def collect_px4_ulog(spec, workdir, context):
    """Collector entry point: download the flight's ULog into workdir.

    Returns 1 on success. Raises UlogDownloadError if no log is available
    (the ULog is the mandatory source, so the caller treats this as a failure
    worth retrying).
    """
    output_name = spec.get('output_name', 'fc')
    dest = os.path.join(workdir, '%s.ulg' % output_name)
    protocol = (spec.get('download_protocol') or 'mavftp').lower()
    if protocol == 'mavftp':
        selected = collect_px4_ulog_ftp(spec, workdir, context, dest)
        with open(os.path.join(workdir, 'fc_ulog.info'), 'w') as handle:
            handle.write(
                'protocol=mavftp\nremote_path=%s\nsize=%d\nstarted_utc=%s\n'
                % (
                    selected['path'],
                    selected['size'],
                    datetime.datetime.fromtimestamp(
                        selected['started_wall'],
                        tz=datetime.timezone.utc,
                    ).isoformat(),
                )
            )
        return 1
    if protocol != 'log_transfer':
        raise UlogDownloadError(
            'unknown PX4 ULog download_protocol: %r' % protocol)

    with Px4LogClient(spec) as client:
        logs = client.list_logs()
        if not logs:
            raise UlogDownloadError(
                'flight controller reports no logs (SD card missing/empty?)')
        log_id = client.select_log(logs, spec, context)
        size, time_utc = logs[log_id]
        if size <= 0:
            raise UlogDownloadError('selected log %d has zero size' % log_id)
        client.download(log_id, size, dest)
    # Record which log we grabbed alongside the flight metadata.
    with open(os.path.join(workdir, 'fc_ulog.info'), 'w') as handle:
        handle.write('log_id=%d\nsize=%d\ntime_utc=%d\n' % (log_id, size, time_utc))
    return 1
