"""Uploader node.

Whenever the companion computer is online and there are zips in the upload
queue, it uploads them one at a time using a resumable protocol (tus by
default). Resume state -- the server-assigned upload URL and the confirmed
byte offset -- is persisted per file, so an upload interrupted by power loss
or a dropped link continues from where it stopped rather than restarting.
"""
import json
import os
import random
import shutil
import threading
import time

import rclpy
from rclpy.node import Node

from arcz_postflight.postflight_dump import store as st
from arcz_postflight.postflight_dump.config import Config
from arcz_postflight.postflight_dump.connectivity import endpoint_host_port, is_online
from arcz_postflight.postflight_dump.upload_backends import UploadError, get_backend


class UploaderNode(Node):

    def __init__(self):
        super().__init__('malp_postflight_uploader')
        self.declare_parameter('config_file', '')
        cfg_path = self.get_parameter('config_file').value or None
        self.config = Config(cfg_path)

        self.data_root = self.config.data_root
        self.store = st.Store(os.path.join(self.data_root, 'state.db'))

        self.protocol = self.config.get('upload.protocol')
        self.backend = get_backend(self.protocol)
        self.poll_interval = float(self.config.get('upload.poll_interval_s'))
        self.max_attempts = int(self.config.get('upload.max_attempts'))
        self.backoff_min = float(self.config.get('upload.backoff_min_s'))
        self.backoff_max = float(self.config.get('upload.backoff_max_s'))
        self.delete_after = bool(self.config.get('upload.delete_after_upload'))

        endpoint = self.config.get('upload.endpoint')
        probe_host = self.config.get('upload.probe_host')
        probe_port = self.config.get('upload.probe_port')
        if not probe_host:
            probe_host, probe_port = endpoint_host_port(endpoint)
        self.probe_host = probe_host
        self.probe_port = probe_port or 443
        self.probe_timeout = float(self.config.get('upload.probe_timeout_s'))

        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._upload_loop, daemon=True)
        self._worker.start()
        self.get_logger().info(
            'Uploader up. protocol=%s endpoint=%s' % (self.protocol, endpoint))

    def _online(self):
        return is_online(self.probe_host, self.probe_port, self.probe_timeout)

    def _upload_loop(self):
        backoff = self.backoff_min
        while not self._stop.is_set():
            if not self._online():
                self.get_logger().debug('Offline; waiting.')
                self._sleep(self.poll_interval)
                continue

            task = self.store.claim_next_upload(self.max_attempts)
            if task is None:
                backoff = self.backoff_min
                self._sleep(self.poll_interval)
                continue

            ok = self._upload_one(task)
            if ok:
                backoff = self.backoff_min
            else:
                # Jittered exponential backoff before trying the next attempt.
                delay = min(backoff, self.backoff_max) * (0.5 + random.random())
                self._sleep(delay)
                backoff = min(backoff * 2, self.backoff_max)

    def _upload_one(self, task):
        upload_id = task['id']
        zip_path = task['zip_path']
        if not os.path.exists(zip_path):
            self.get_logger().error(
                'Upload %d: file missing (%s); parking as failed'
                % (upload_id, zip_path))
            self.store.mark_upload_failed(
                upload_id, 'missing file', self.max_attempts)
            return False

        # Re-stat in case size in DB is stale.
        task['size'] = os.path.getsize(zip_path)

        def progress_cb(offset, upload_url=None):
            self.store.update_upload_progress(upload_id, offset, upload_url)

        def should_continue():
            # Connectivity is probed before an upload is claimed. Once a
            # resumable transfer is active, let the real PATCH request decide
            # whether the link works. Probing again before every chunk adds a
            # TCP handshake per 64 KiB and can falsely abort a healthy transfer
            # on intermittent cellular/Tailscale links.
            return not self._stop.is_set()

        try:
            self.get_logger().info(
                'Upload %d: sending %s (from offset %d/%d)'
                % (upload_id, os.path.basename(zip_path),
                   task.get('offset') or 0, task['size']))
            self.backend(self.config, task, progress_cb, should_continue)
            self.store.mark_uploaded(upload_id)
            self.get_logger().info('Upload %d: complete.' % upload_id)
            if self.delete_after:
                try:
                    os.remove(zip_path)
                except OSError:
                    pass
            self._cleanup_originals(upload_id, task.get('cleanup_paths'))
            return True
        except UploadError as exc:
            self.get_logger().warning('Upload %d failed: %s' % (upload_id, exc))
            failure_limit = task['attempts'] if exc.terminal else self.max_attempts
            self.store.mark_upload_failed(upload_id, exc, failure_limit)
            return False
        except Exception as exc:  # noqa: B902
            self.get_logger().error(
                'Upload %d unexpected error: %s' % (upload_id, exc))
            self.store.mark_upload_failed(upload_id, exc, self.max_attempts)
            return False

    def _cleanup_originals(self, upload_id, cleanup_paths_json):
        """Remove original-location sources (e.g. the raw mcap recording)
        now that this flight's data is confirmed uploaded."""
        try:
            paths = json.loads(cleanup_paths_json or '[]')
        except ValueError:
            return
        for path in paths:
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                elif os.path.exists(path):
                    os.remove(path)
            except OSError as exc:
                self.get_logger().warning(
                    'Upload %d: failed to clean up %s: %s' % (upload_id, path, exc))

    def _sleep(self, seconds):
        """Interruptible sleep that returns early on shutdown."""
        self._stop.wait(timeout=max(0.0, seconds))

    def destroy_node(self):
        self._stop.set()
        if self._worker.is_alive():
            self._worker.join(timeout=5.0)
        try:
            self.store.close()
        except Exception:
            pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = UploaderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
