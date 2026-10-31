from threading import Thread, Event, Lock, current_thread
from pymavlink import mavutil
import time

class MAVLinkController:
    MODES = {
        "GUIDED",
        "STABILIZE",
        "LOITER",
        "LAND",
        "RTL",
    }

    RC_MIN = 1000
    RC_MAX = 2000
    RC_CENTER = 1500
    RC_SEND_RATE = 20

    def __init__(self):
        self.vehicle = None
        self.connected = False
        self.connecting = False

        self._stop_event = Event()
        self._monitor_thread = None
        self._lock = Lock()

        self.current_mode = "UNKNOWN"
        self.is_armed = False

        self.rc_channels = {
            "roll": self.RC_CENTER,
            "pitch": self.RC_CENTER,
            "throttle": self.RC_MIN,
            "yaw": self.RC_CENTER,
        }

        self._rc_thread = None
        self._rc_stop_event = Event()
        self._rc_lock = Lock()
        self._mav_send_lock = Lock()
        self.rc_control_enabled = False

    def connect(self, connection_string, callback):
        if self.connecting or self.connected:
            return

        self.connecting = True
        self._stop_event.clear()

        Thread(
            target=self._connect_worker,
            args=(connection_string, callback),
            daemon=True,
        ).start()

    def _connect_worker(self, connection_string, callback):
        vehicle = None

        try:
            vehicle = mavutil.mavlink_connection(connection_string)

            heartbeat = vehicle.wait_heartbeat(timeout=10)

            if heartbeat is None:
                raise TimeoutError("No heartbeat received within 10 seconds.")

            with self._lock:
                self.vehicle = vehicle
                self.connected = True

            callback(True, "Connected to ArduPilot")

            self._monitor_thread = Thread(
                target=self._monitor_worker,
                daemon=True,
            )
            self._monitor_thread.start()

        except Exception as exc:
            if vehicle is not None:
                vehicle.close()

            callback(False, str(exc))

        finally:
            self.connecting = False

    def _monitor_worker(self):
        while not self._stop_event.is_set():
            with self._lock:
                vehicle = self.vehicle

            if vehicle is None:
                break

            try:
                message = vehicle.recv_match(
                    type="HEARTBEAT",
                    blocking=True,
                    timeout=1,
                )

                if message is None:
                    continue

                if message.autopilot == mavutil.mavlink.MAV_AUTOPILOT_INVALID:
                    continue

                mode = mavutil.mode_string_v10(message)
                armed = bool(
                    message.base_mode
                    & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
                )

                self.current_mode = mode
                self.is_armed = armed

            except Exception:
                if not self._stop_event.is_set():
                    break

    def set_mode(self, mode, callback):
        mode = mode.upper()

        if mode not in self.MODES:
            callback(False, f"Unsupported mode: {mode}")
            return

        with self._lock:
            vehicle = self.vehicle

        if not self.connected or vehicle is None:
            callback(False, "Not connected")
            return

        Thread(
            target=self._set_mode_worker,
            args=(vehicle, mode, callback),
            daemon=True,
        ).start()

    def _set_mode_worker(self, vehicle, mode, callback):
        try:
            mode_mapping = vehicle.mode_mapping()

            if not mode_mapping or mode not in mode_mapping:
                raise ValueError(f"Mode {mode} is not supported by this vehicle")

            vehicle.set_mode(mode)

            callback(True, f"Mode change requested: {mode}")

        except Exception as exc:
            callback(False, f"Mode change failed: {exc}")

    def arm(self, callback):
        with self._lock:
            vehicle = self.vehicle

        if not self.connected or vehicle is None:
            callback(False, "Not connected")
            return

        Thread(
            target=self._arm_worker,
            args=(vehicle, callback),
            daemon=True,
        ).start()

    def _arm_worker(self, vehicle, callback):
        try:
            vehicle.arducopter_arm()

            deadline = time.monotonic() + 5

            while time.monotonic() < deadline:
                if vehicle.motors_armed():
                    callback(True, "Vehicle armed successfully")
                    return

                time.sleep(0.1)

            callback(
                False,
                "Arming command sent, but arming was not confirmed within 5 seconds"
            )

        except Exception as exc:
            callback(False, f"Arming failed: {exc}")

    def takeoff(self, altitude, callback):
        with self._lock:
            vehicle = self.vehicle

        if not self.connected or vehicle is None:
            callback(False, "Not connected")
            return

        Thread(
            target=self._takeoff_worker,
            args=(vehicle, altitude, callback),
            daemon=True,
        ).start()

    def _takeoff_worker(self, vehicle, altitude, callback):
        try:
            if not vehicle.motors_armed():
                raise RuntimeError("Vehicle must be armed before takeoff")

            if getattr(self, "current_mode", "UNKNOWN") != "GUIDED":
                raise RuntimeError("Vehicle must be in GUIDED mode")

            vehicle.mav.command_long_send(
                vehicle.target_system,
                vehicle.target_component,
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                float(altitude)
            )

            callback(True, f"Takeoff command sent: {altitude} meters")

        except Exception as exc:
            callback(False, f"Takeoff failed: {exc}")

    def start_rc_control(self):
        with self._lock:
            if not self.connected or self.vehicle is None:
                raise ConnectionError("Vehicle is not connected")

            if self.current_mode != "STABILIZE":
                raise RuntimeError(
                    "RC control is available only in STABILIZE mode"
                )

            if self.rc_control_enabled:
                return

            self._rc_stop_event.clear()
            self.rc_control_enabled = True

            self._rc_thread = Thread(
                target=self._rc_worker,
                daemon=True
            )
            self._rc_thread.start()

    def update_rc_channels(self, roll, pitch, throttle, yaw):
        if not self.rc_control_enabled:
            return

        values = {
            "roll": roll,
            "pitch": pitch,
            "throttle": throttle,
            "yaw": yaw,
        }

        for channel, value in values.items():
            if not self.RC_MIN <= value <= self.RC_MAX:
                raise ValueError(f"Invalid PWM value for {channel}: {value}")

        with self._rc_lock:
            self.rc_channels.update(values)

    def _rc_worker(self):
        interval = 1.0 / self.RC_SEND_RATE

        try:
            while not self._rc_stop_event.is_set():

                with self._lock:
                    if not self.connected or self.vehicle is None:
                        break

                    if self.current_mode != "STABILIZE":
                        break

                    vehicle = self.vehicle

                with self._rc_lock:
                    channels = self.rc_channels.copy()

                try:
                    with self._mav_send_lock:
                        vehicle.mav.rc_channels_override_send(
                            vehicle.target_system,
                            vehicle.target_component,
                            channels["roll"],
                            channels["pitch"],
                            channels["throttle"],
                            channels["yaw"],
                            65535,
                            65535,
                            65535,
                            65535,
                        )

                except Exception:
                    break

                self._rc_stop_event.wait(interval)

        finally:
            self.stop_rc_control()

    def stop_rc_control(self):
        self._rc_stop_event.set()

        if self._rc_thread and self._rc_thread is not current_thread():
            self._rc_thread.join(timeout=1)
            self._rc_thread.join(timeout=1)

        with self._lock:
            vehicle = self.vehicle

        if vehicle is not None and self.connected:
            try:
                with self._mav_send_lock:
                    vehicle.mav.rc_channels_override_send(
                        vehicle.target_system,
                        vehicle.target_component,
                        0,
                        0,
                        0,
                        0,
                        65535,
                        65535,
                        65535,
                        65535,
                    )
            except Exception:
                pass

        self.rc_control_enabled = False
        self._rc_thread = None

        with self._rc_lock:
            self.rc_channels = {
                "roll": self.RC_CENTER,
                "pitch": self.RC_CENTER,
                "throttle": self.RC_MIN,
                "yaw": self.RC_CENTER,
            }

    def get_vehicle_state(self):
        return {
            "connected": self.connected,
            "mode": getattr(self, "current_mode", "UNKNOWN"),
            "armed": getattr(self, "is_armed", False),
        }

    def disconnect(self):
        self.stop_rc_control()
        self._stop_event.set()

        with self._lock:
            vehicle = self.vehicle
            self.vehicle = None
            self.connected = False

        if vehicle is not None:
            try:
                vehicle.close()
            except Exception:
                pass

        self.current_mode = "UNKNOWN"
        self.is_armed = False