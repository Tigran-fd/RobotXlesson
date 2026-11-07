import tkinter as tk
from gui.main_window import ArduPilotGUI

if __name__ == "__main__":
    root = tk.Tk()
    app = ArduPilotGUI(root)
    root.mainloop()