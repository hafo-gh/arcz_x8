"use strict";

const video = document.getElementById("camera");
const state = document.getElementById("stream-state");
const message = document.getElementById("message");
let receivedTrack = false;

const sendControl = async (action, payload) => {
  try {
    const response = await fetch(`/api/control/${action}`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`control returned ${response.status}`);
    return true;
  } catch (error) {
    document.getElementById("gimbal-link").textContent = "LINK ERROR";
    console.error(error);
    return false;
  }
};

const setState = (kind, text, detail) => {
  state.className = `state ${kind}`;
  state.lastElementChild.textContent = text;
  if (kind !== "live") {
    message.classList.remove("hidden");
    message.querySelector("strong").textContent = text;
    message.querySelector("span").textContent = detail || "Automatic reconnection is active.";
  }
};

const reader = new MediaMTXWebRTCReader({
  url: `${window.location.origin}/camera/whep`,
  user: "",
  pass: "",
  token: "",
  onError: (error) => {
    if (!receivedTrack) setState("failed", "STREAM UNAVAILABLE", error);
  },
  onTrack: (event) => {
    receivedTrack = true;
    video.srcObject = event.streams[0];
    video.play().catch(() => {});
    setState("live", "LIVE");
    message.classList.add("hidden");
  },
});

video.addEventListener("stalled", () => setState("waiting", "RECONNECTING"));
video.addEventListener("playing", () => {
  receivedTrack = true;
  setState("live", "LIVE");
  message.classList.add("hidden");
});

document.getElementById("fullscreen").addEventListener("click", async () => {
  if (document.fullscreenElement) await document.exitFullscreen();
  else await document.documentElement.requestFullscreen();
});

// The Jetson dead-man stops motion after 300 ms, so active commands are refreshed at 10 Hz.
const joystick = document.getElementById("joystick");
const joystickKnob = document.getElementById("joystick-knob");
let joystickPointer = null;
let motion = {pan: 0, tilt: 0};
let motionTimer = null;

const updateJoystick = (event) => {
  const bounds = joystick.getBoundingClientRect();
  const radius = bounds.width / 2;
  const limit = radius - 20;
  let x = event.clientX - bounds.left - radius;
  let y = event.clientY - bounds.top - radius;
  const magnitude = Math.hypot(x, y);
  if (magnitude > limit) { x *= limit / magnitude; y *= limit / magnitude; }
  joystickKnob.style.transform = `translate(${x}px, ${y}px)`;
  motion = {pan: Math.round(100 * x / limit), tilt: Math.round(-100 * y / limit)};
};

const stopMotion = () => {
  if (joystickPointer === null) return;
  joystickPointer = null;
  window.clearInterval(motionTimer);
  motionTimer = null;
  motion = {pan: 0, tilt: 0};
  joystickKnob.style.transform = "translate(0, 0)";
  sendControl("move", motion);
};

joystick.addEventListener("pointerdown", (event) => {
  event.preventDefault();
  joystickPointer = event.pointerId;
  joystick.setPointerCapture(event.pointerId);
  updateJoystick(event);
  sendControl("move", motion);
  motionTimer = window.setInterval(() => sendControl("move", motion), 100);
});
joystick.addEventListener("pointermove", (event) => {
  if (event.pointerId === joystickPointer) updateJoystick(event);
});
joystick.addEventListener("pointerup", stopMotion);
joystick.addEventListener("pointercancel", stopMotion);
joystick.addEventListener("lostpointercapture", stopMotion);

document.querySelectorAll("[data-zoom]").forEach((button) => {
  let timer = null;
  const direction = Number(button.dataset.zoom);
  const stop = () => {
    if (timer === null) return;
    window.clearInterval(timer);
    timer = null;
    button.classList.remove("active");
    sendControl("zoom", {direction: 0});
  };
  button.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    button.setPointerCapture(event.pointerId);
    button.classList.add("active");
    sendControl("zoom", {direction});
    timer = window.setInterval(() => sendControl("zoom", {direction}), 150);
  });
  button.addEventListener("pointerup", stop);
  button.addEventListener("pointercancel", stop);
  button.addEventListener("lostpointercapture", stop);
});

let keyboardZoomTimer = null;
let keyboardZoomDirection = 0;
const stopKeyboardZoom = () => {
  if (keyboardZoomTimer === null) return;
  window.clearInterval(keyboardZoomTimer);
  keyboardZoomTimer = null;
  keyboardZoomDirection = 0;
  sendControl("zoom", {direction: 0});
};
window.addEventListener("keydown", (event) => {
  if (event.key !== "PageUp" && event.key !== "PageDown") return;
  event.preventDefault();
  const direction = event.key === "PageUp" ? 1 : -1;
  if (keyboardZoomTimer !== null && keyboardZoomDirection === direction) return;
  stopKeyboardZoom();
  keyboardZoomDirection = direction;
  sendControl("zoom", {direction});
  keyboardZoomTimer = window.setInterval(() => sendControl("zoom", {direction}), 150);
});
window.addEventListener("keyup", (event) => {
  if (event.key !== "PageUp" && event.key !== "PageDown") return;
  event.preventDefault();
  stopKeyboardZoom();
});

document.getElementById("center-gimbal").addEventListener("click", () => sendControl("center", {}));
document.getElementById("auto-focus").addEventListener("click", () => sendControl("focus", {}));

document.querySelectorAll("[data-mode]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (!await sendControl("mode", {mode: button.dataset.mode})) return;
    document.querySelectorAll("[data-mode]").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
  });
});

window.addEventListener("keydown", (event) => {
  if (event.repeat || event.ctrlKey || event.altKey || event.metaKey) return;
  const button = document.querySelector(`[data-shortcut="${event.key.toLowerCase()}"]`);
  if (!button) return;
  event.preventDefault();
  button.click();
});

document.querySelectorAll("[data-capture]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (!await sendControl("capture", {action: button.dataset.capture})) return;
    button.classList.add("active");
    window.setTimeout(() => button.classList.remove("active"), 350);
  });
});

const pressedKeys = new Set();
const keyMotion = () => {
  const pan = (pressedKeys.has("ArrowRight") ? 60 : 0) - (pressedKeys.has("ArrowLeft") ? 60 : 0);
  const tilt = (pressedKeys.has("ArrowUp") ? 60 : 0) - (pressedKeys.has("ArrowDown") ? 60 : 0);
  sendControl("move", {pan, tilt});
};
window.addEventListener("keydown", (event) => {
  if (!event.key.startsWith("Arrow") || pressedKeys.has(event.key)) return;
  event.preventDefault();
  pressedKeys.add(event.key);
  keyMotion();
});
window.addEventListener("keyup", (event) => {
  if (!event.key.startsWith("Arrow")) return;
  event.preventDefault();
  pressedKeys.delete(event.key);
  keyMotion();
});
window.setInterval(() => { if (pressedKeys.size) keyMotion(); }, 100);

const pollHealth = async () => {
  try {
    const [healthResponse, controlResponse] = await Promise.all([
      fetch("/api/health", {cache: "no-store"}),
      fetch("/api/control/status", {cache: "no-store"}),
    ]);
    const health = await healthResponse.json();
    const control = await controlResponse.json();
    document.getElementById("camera-health").textContent = `CAMERA ${health.stream_ready ? "READY" : "OFFLINE"}`;
    document.getElementById("network-health").textContent = `TAILSCALE ${health.tailscale ? "READY" : "OFFLINE"}`;
    document.getElementById("viewer-count").textContent = `VIEWERS ${health.readers ?? 0}`;
    document.getElementById("gimbal-link").textContent = `LINK ${control.reachable ? "READY" : "OFFLINE"}`;
    document.getElementById("record-state").textContent = `RECORD ${control.record_status.replace("_", " ").toUpperCase()}`;
    if (control.selected_mode) {
      document.querySelectorAll("[data-mode]").forEach((item) => item.classList.toggle("active", item.dataset.mode === control.selected_mode));
    }
  } catch (_) {
    document.getElementById("camera-health").textContent = "HEALTH CHECK OFFLINE";
  }
};
pollHealth();
window.setInterval(pollHealth, 3000);
window.addEventListener("beforeunload", () => {
  sendControl("move", {pan: 0, tilt: 0});
  sendControl("zoom", {direction: 0});
  reader.close();
});
