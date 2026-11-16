import tkinter as tk
from tkinter import ttk
from tkintermapview import TkinterMapView


class MapWindow(ttk.Frame):

    UPDATE_INTERVAL = 500

    def __init__(self, parent, map_controller):
        super().__init__(parent)

        self.map_controller = map_controller

        self.drone_marker = None
        self.after_id = None
        self.first_position_received = False

        self.latitude_text = tk.StringVar(value="Latitude: --")
        self.longitude_text = tk.StringVar(value="Longitude: --")
        self.altitude_text = tk.StringVar(value="Altitude: --")
        self.heading_text = tk.StringVar(value="Heading: --")

        self.follow_drone = tk.BooleanVar(value=True)

        self._build_ui()
        self._schedule_update()

    def _build_ui(self):
        info_frame = ttk.Frame(self, padding=10)
        info_frame.pack(fill="x")

        ttk.Label(
            info_frame,
            textvariable=self.latitude_text,
        ).pack(anchor="w", pady=2)

        ttk.Label(
            info_frame,
            textvariable=self.longitude_text,
        ).pack(anchor="w", pady=2)

        ttk.Label(
            info_frame,
            textvariable=self.altitude_text,
        ).pack(anchor="w", pady=2)

        ttk.Label(
            info_frame,
            textvariable=self.heading_text,
        ).pack(anchor="w", pady=2)

        ttk.Checkbutton(
            info_frame,
            text="Follow Drone",
            variable=self.follow_drone,
        ).pack(anchor="w", pady=5)

        self.map_widget = TkinterMapView(
            self,
            corner_radius=0,
        )

        self.map_widget.set_tile_server(
            "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        )

        self.map_widget.pack(
            fill="both",
            expand=True,
        )

        self.map_widget.set_position(0, 0)
        self.map_widget.set_zoom(2)

    def _schedule_update(self):
        if self.winfo_exists():
            self.after_id = self.after(
                self.UPDATE_INTERVAL,
                self._update_position,
            )

    def _update_position(self):
        position = self.map_controller.get_drone_position()

        if position is not None:
            latitude = position["latitude"]
            longitude = position["longitude"]
            altitude = position["altitude"]
            heading = position["heading"]

            self.latitude_text.set(
                f"Latitude: {latitude:.7f}"
            )

            self.longitude_text.set(
                f"Longitude: {longitude:.7f}"
            )

            self.altitude_text.set(
                f"Altitude: {altitude:.2f} m"
            )

            self.heading_text.set(
                f"Heading: {heading:.1f}°"
                if heading is not None
                else "Heading: --"
            )

            if self.drone_marker is None:
                self.drone_marker = self.map_widget.set_marker(
                    latitude,
                    longitude,
                    text="Drone",
                )
            else:
                self.drone_marker.set_position(
                    latitude,
                    longitude,
                )

            if self.follow_drone.get():
                if not self.first_position_received:
                    self.map_widget.set_zoom(16)
                    self.first_position_received = True

                self.map_widget.set_position(
                    latitude,
                    longitude,
                )

        self._schedule_update()

    def close(self):
        if self.after_id is not None:
            self.after_cancel(self.after_id)
            self.after_id = None

        self.destroy()