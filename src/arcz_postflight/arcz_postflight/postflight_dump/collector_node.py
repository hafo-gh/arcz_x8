"""Collector node.

Watches the armed topic. When the drone disarms after having been armed for
at least ``flight_if_armed_for_s``, it persists a collection task *immediately*
(so a subsequent power loss cannot lose the fact that a flight happened). A
background worker then drains the collection queue: it gathers the configured
flight data, packs it into a single zip, and enqueues that zip for upload.
"""
import json
import os
import shutil
import threading
import time
import uuid
import zipfile

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile
from rclpy.qos import ReliabilityPolicy
from std_msgs.msg import Bool

from arcz_postflight.postflight_dump import store as st
from arcz_postflight.postflight_dump.collectors import CollectorError, run_sources
from arcz_postflight.postflight_dump.config import Config


class CollectorNode(Node):

    def __init__(self):
        super().__init__('collector_node')
        self.declare_parameter('config_file', '')
        cfg_path = self.get_parameter('config_file').value or None
        self.config = Config(cfg_path)

        self.data_root = self.config.data_root
        self.work_dir = os.path.join(self.data_root, 'work')
        self.upload_dir = os.path.join(self.data_root, 'queue', 'upload')
        os.makedirs(self.work_dir, exist_ok=True)
        os.makedirs(self.upload_dir, exist_ok=True)

        self.store = st.Store(os.path.join(self.data_root, 'state.db'))
        flights_reset, uploads_reset = self.store.recover()
        self.get_logger().info(
            'Recovered on startup: %d flights, %d uploads reset to pending'
            % (flights_reset, uploads_reset))

        self.threshold_s = self.config.flight_if_armed_for_s
        self.vehicle_id = self.config.vehicle_id
        try:
            uuid.UUID(self.vehicle_id)
        except ValueError as exc:
            raise ValueError('vehicle_id must be configured as a UUID') from exc
        self.poll_interval = float(self.config.get('collection.poll_interval_s'))
        self.max_attempts = int(self.config.get('collection.max_attempts'))
        self.initial_delay = float(self.config.get('collection.initial_delay_s'))
        self.backoff_min = float(self.config.get('collection.backoff_min_s'))
        self.backoff_max = float(self.config.get('collection.backoff_max_s'))
        self.sources = self.config.get('collection.sources', [])

        # Arm-state tracking. Monotonic for duration (immune to clock jumps),
        # wall clock for human-readable metadata.
        self._armed = False
        self._arm_monotonic = None
        self._arm_wall = None

        self._wake = threading.Event()
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._collection_loop, daemon=True)
        self._worker.start()

        armed_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(
            Bool, self.config.armed_topic, self._on_armed, armed_qos)
        self.get_logger().info(
            'Collector up. Listening on %s (flight >= %.1fs). data_root=%s'
            % (self.config.armed_topic, self.threshold_s, self.data_root))
        # Kick the worker in case pending tasks already exist from a prior boot.
        self._wake.set()

    # -- armed topic ---------------------------------------------------------
    def _on_armed(self, msg):
        armed = bool(msg.data)
        if armed == self._armed:
            return
        self._armed = armed
        if armed:
            self._arm_monotonic = time.monotonic()
            self._arm_wall = time.time()
            self.get_logger().info('ARMED')
        else:
            self._handle_disarm()

    def _handle_disarm(self):
        disarm_wall = time.time()
        if self._arm_monotonic is None:
            return
        duration = time.monotonic() - self._arm_monotonic
        self.get_logger().info('DISARMED after %.1fs' % duration)
        if duration >= self.threshold_s:
            flight_id = self.store.enqueue_flight(
                self._arm_wall, disarm_wall, duration, self.initial_delay)
            self.get_logger().info(
                'Flight %d qualifies (%.1fs >= %.1fs); collection queued'
                % (flight_id, duration, self.threshold_s))
            self._wake.set()
        else:
            self.get_logger().info(
                'Ignored: armed only %.1fs (< %.1fs)'
                % (duration, self.threshold_s))
        self._arm_monotonic = None
        self._arm_wall = None

    # -- collection worker ---------------------------------------------------
    def _collection_loop(self):
        while not self._stop.is_set():
            processed_any = False
            while not self._stop.is_set():
                task = self.store.claim_next_collection(self.max_attempts)
                if task is None:
                    break
                processed_any = True
                self._process_flight(task)
            if not processed_any:
                self._wake.wait(timeout=self.poll_interval)
                self._wake.clear()

    def _process_flight(self, task):
        flight_id = task['id']
        flight_work = os.path.join(self.work_dir, 'flight_%d' % flight_id)
        try:
            if os.path.exists(flight_work):
                shutil.rmtree(flight_work)
            os.makedirs(flight_work, exist_ok=True)

            context = {
                'queue_id': flight_id,
                'flight_id': task['flight_uuid'],
                'vehicle_id': self.vehicle_id,
                'schema_version': 1,
                'arm_wall': task['arm_wall'],
                'disarm_wall': task['disarm_wall'],
                'armed_duration': task['armed_duration'],
            }
            with open(os.path.join(flight_work, 'metadata.json'), 'w') as handle:
                json.dump(context, handle, indent=2, sort_keys=True)

            n, cleanup_paths = run_sources(self.sources, flight_work, context)
            self.get_logger().info(
                'Flight %d: collected %d artifact group(s)' % (flight_id, n))

            zip_path = self._zip_flight(flight_id, flight_work, task)
            size = os.path.getsize(zip_path)
            self.store.mark_collected(flight_id, zip_path, size, cleanup_paths)
            shutil.rmtree(flight_work, ignore_errors=True)
            self.get_logger().info(
                'Flight %d collected -> %s (%d bytes); queued for upload'
                % (flight_id, os.path.basename(zip_path), size))
        except (CollectorError, OSError, Exception) as exc:  # noqa: B902
            self.get_logger().error('Flight %d collection failed: %s'
                                    % (flight_id, exc))
            delay = min(
                self.backoff_min * (2 ** max(0, task['attempts'] - 1)),
                self.backoff_max,
            )
            self.store.mark_collection_failed(
                flight_id, exc, self.max_attempts, delay)
            shutil.rmtree(flight_work, ignore_errors=True)

    def _zip_flight(self, flight_id, flight_work, task):
        stamp = time.strftime('%Y%m%dT%H%M%S', time.gmtime(task['disarm_wall']))
        final_name = 'flight_%s_%s.zip' % (task['flight_uuid'], stamp)
        final_path = os.path.join(self.upload_dir, final_name)
        part_path = final_path + '.part'
        # Write to .part then atomically rename, so a partial zip never enters
        # the upload queue.
        with zipfile.ZipFile(part_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(flight_work):
                for name in files:
                    abs_path = os.path.join(root, name)
                    arc = os.path.relpath(abs_path, flight_work)
                    zf.write(abs_path, arc)
        os.replace(part_path, final_path)
        return final_path

    def destroy_node(self):
        self._stop.set()
        self._wake.set()
        if self._worker.is_alive():
            self._worker.join(timeout=5.0)
        try:
            self.store.close()
        except Exception:
            pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = CollectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
