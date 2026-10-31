import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from mavlink_controller import MAVLinkController


class ArduPilotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ArduPilot Ground Control")
        self.root.geometry("1420x890")
        self.root.resizable(False, False)

        self.controller = MAVLinkController()

        self.connection_string = tk.StringVar(
            value="udpin:0.0.0.0:14551"
        )
        self.status_text = tk.StringVar(value="Disconnected")
        self.mode_text = tk.StringVar(value="Unknown")
        self.armed_text = tk.StringVar(value="Disarmed")
        self.takeoff_altitude = tk.StringVar(value="10")

        self._build_ui()
        self._set_controls_enabled(False)

        self.root.protocol("WM_DELETE_WINDOW", self.close_application)

        self.log("Application started.")
        self._update_vehicle_state()

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.pack(fill="both", expand=True)

        # Connection section
        connection_frame = ttk.LabelFrame(
            main_frame,
            text="Connection",
            padding=10,
        )
        connection_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(
            connection_frame,
            text="Connection string:",
        ).grid(row=0, column=0, sticky="w")

        self.connection_entry = ttk.Entry(
            connection_frame,
            textvariable=self.connection_string,
            width=35,
        )
        self.connection_entry.grid(
            row=1,
            column=0,
            padx=(0, 8),
            pady=5,
            sticky="ew",
        )

        self.connect_button = ttk.Button(
            connection_frame,
            text="Connect",
            command=self.connect,
        )
        self.connect_button.grid(row=1, column=1, pady=5)

        self.close_button = ttk.Button(
            connection_frame,
            text="Close Connection",
            command=self.disconnect,
            state="disabled",
        )
        self.close_button.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(5, 0),
        )

        connection_frame.columnconfigure(0, weight=1)

        # Connection status only
        connection_status_frame = ttk.LabelFrame(
            main_frame,
            text="Connection Status",
            padding=10,
        )
        connection_status_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(
            connection_status_frame,
            text="Status:",
        ).grid(row=0, column=0, sticky="w")

        self.connection_status_label = ttk.Label(
            connection_status_frame,
            textvariable=self.status_text,
        )
        self.connection_status_label.grid(
            row=0,
            column=1,
            sticky="w",
            padx=10,
        )

        # Vehicle information
        vehicle_frame = ttk.LabelFrame(
            main_frame,
            text="Vehicle Status",
            padding=10,
        )
        vehicle_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(
            vehicle_frame,
            text="Flight mode:",
        ).grid(row=0, column=0, sticky="w", pady=3)

        ttk.Label(
            vehicle_frame,
            textvariable=self.mode_text,
        ).grid(row=0, column=1, sticky="w", padx=10, pady=3)

        ttk.Label(
            vehicle_frame,
            text="Armed status:",
        ).grid(row=1, column=0, sticky="w", pady=3)

        ttk.Label(
            vehicle_frame,
            textvariable=self.armed_text,
        ).grid(row=1, column=1, sticky="w", padx=10, pady=3)

        # Flight modes
        modes_frame = ttk.LabelFrame(
            main_frame,
            text="Flight Modes",
            padding=10,
        )
        modes_frame.pack(fill="x", pady=(0, 10))

        modes = [
            "GUIDED",
            "STABILIZE",
            "LOITER",
            "LAND",
            "RTL",
        ]

        self.mode_buttons = []

        for index, mode in enumerate(modes):
            button = ttk.Button(
                modes_frame,
                text=mode.title(),
                command=lambda selected_mode=mode: self.change_mode(
                    selected_mode
                ),
            )
            button.grid(
                row=index // 3,
                column=index % 3,
                padx=5,
                pady=5,
                sticky="ew",
            )
            self.mode_buttons.append(button)

        for column in range(3):
            modes_frame.columnconfigure(column, weight=1)

        # Vehicle control
        arm_frame = ttk.LabelFrame(
            main_frame,
            text="Vehicle Control",
            padding=10,
        )
        arm_frame.pack(fill="x", pady=(0, 10))

        self.arm_button = ttk.Button(
            arm_frame,
            text="Arm Vehicle",
            command=self.arm,
        )
        self.arm_button.pack(fill="x")

        # Takeoff control
        takeoff_frame = ttk.LabelFrame(
            main_frame,
            text="Takeoff",
            padding=10,
        )
        takeoff_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(
            takeoff_frame,
            text="Altitude (meters):",
        ).grid(row=0, column=0, sticky="w", padx=(0, 10))

        self.altitude_entry = ttk.Entry(
            takeoff_frame,
            textvariable=self.takeoff_altitude,
            width=15,
        )
        self.altitude_entry.grid(row=0, column=1, padx=5)

        self.takeoff_button = ttk.Button(
            takeoff_frame,
            text="Takeoff",
            command=self.takeoff,
        )
        self.takeoff_button.grid(row=0, column=2, padx=10)

        takeoff_frame.columnconfigure(3, weight=1)

        # Activity logs
        logs_frame = ttk.LabelFrame(
            main_frame,
            text="Activity Logs",
            padding=10,
        )
        logs_frame.pack(fill="both", expand=True)

        self.logs_text = tk.Text(
            logs_frame,
            height=8,
            state="disabled",
            wrap="word",
            font=("Courier", 10),
        )
        self.logs_text.pack(
            side="left",
            fill="both",
            expand=True,
        )

        scrollbar = ttk.Scrollbar(
            logs_frame,
            orient="vertical",
            command=self.logs_text.yview,
        )
        scrollbar.pack(side="right", fill="y")

        self.logs_text.configure(yscrollcommand=scrollbar.set)

        self.clear_logs_button = ttk.Button(
            main_frame,
            text="Clear Logs",
            command=self.clear_logs,
        )
        self.clear_logs_button.pack(anchor="e", pady=(5, 0))

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}\n"

        self.logs_text.configure(state="normal")
        self.logs_text.insert("end", entry)
        self.logs_text.see("end")
        self.logs_text.configure(state="disabled")

    def clear_logs(self):
        self.logs_text.configure(state="normal")
        self.logs_text.delete("1.0", "end")
        self.logs_text.configure(state="disabled")

        self.log("Logs cleared.")

    def _set_controls_enabled(self, enabled):
        state = "normal" if enabled else "disabled"

        for button in self.mode_buttons:
            button.configure(state=state)

        self.arm_button.configure(state=state)

        self.close_button.configure(
            state="normal" if enabled else "disabled"
        )

        self.connection_entry.configure(
            state="disabled" if enabled else "normal"
        )

        self.connect_button.configure(
            state="disabled" if enabled else "normal"
        )
        self.takeoff_button.configure(state=state)
        self.altitude_entry.configure(state=state)

    def connect(self):
        address = self.connection_string.get().strip()

        if not address:
            messagebox.showerror(
                "Connection Error",
                "Enter a connection string.",
            )
            return

        self.connect_button.configure(state="disabled")
        self.connection_entry.configure(state="disabled")

        self.log(f"Connecting to {address}...")

        self.controller.connect(
            address,
            self._connection_callback,
        )

    def _connection_callback(self, success, message):
        self.root.after(
            0,
            lambda: self._handle_connection_result(success, message),
        )

    def _handle_connection_result(self, success, message):
        if success:
            self.status_text.set("Connected")
            self.log(message)
            self._set_controls_enabled(True)
        else:
            self.status_text.set("Disconnected")
            self.log(f"Connection failed: {message}")
            self._set_controls_enabled(False)

    def change_mode(self, mode):
        self.log(f"Requesting flight mode: {mode}")

        self.controller.set_mode(
            mode,
            lambda success, message: self.root.after(
                0,
                lambda: self._handle_command_result(
                    success,
                    message,
                ),
            ),
        )

    def _handle_command_result(self, success, message):
        if success:
            self.log(message)
        else:
            self.log(f"Command failed: {message}")
            messagebox.showwarning("Command Result", message)

    def arm(self):
        self.arm_button.configure(state="disabled")
        self.log("Arming vehicle...")

        self.controller.arm(
            lambda success, message: self.root.after(
                0,
                lambda: self._handle_arm_result(success, message),
            )
        )

    def _handle_arm_result(self, success, message):
        self.arm_button.configure(
            state="normal" if self.controller.connected else "disabled"
        )

        if success:
            self.log(message)
        else:
            self.log(f"Arming failed: {message}")
            messagebox.showwarning("Arming Result", message)


    def takeoff(self):
        try:
            altitude = float(self.takeoff_altitude.get())

            if altitude <= 0:
                raise ValueError("Altitude must be greater than zero.")

        except ValueError as exc:
            messagebox.showerror("Invalid Altitude", str(exc))
            return

        self.takeoff_button.configure(state="disabled")
        self.log(f"Requesting takeoff to {altitude} meters...")

        self.controller.takeoff(
            altitude,
            lambda success, message: self.root.after(
                0,
                lambda: self._handle_takeoff_result(success, message),
            ),
        )

    def _handle_takeoff_result(self, success, message):
        self.takeoff_button.configure(
            state="normal" if self.controller.connected else "disabled"
        )

        if success:
            self.log(message)
        else:
            self.log(f"Takeoff failed: {message}")
            messagebox.showwarning("Takeoff Result", message)

    def disconnect(self):
        self.controller.disconnect()

        self.status_text.set("Disconnected")
        self.mode_text.set("Unknown")
        self.armed_text.set("Disarmed")

        self._set_controls_enabled(False)
        self.log("Connection closed.")

    def _update_vehicle_state(self):
        state = self.controller.get_vehicle_state()

        if state["connected"]:
            self.mode_text.set(state["mode"])
            self.armed_text.set(
                "Armed" if state["armed"] else "Disarmed"
            )

        self.root.after(500, self._update_vehicle_state)

    def close_application(self):
        self.controller.disconnect()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ArduPilotGUI(root)
    root.mainloop()
