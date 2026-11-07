class MapController:

    def __init__(self, mavlink_controller):
        self.mavlink_controller = mavlink_controller

    def get_drone_position(self):
        position = self.mavlink_controller.get_drone_position()

        if position is None:
            return None

        latitude = position["latitude"]
        longitude = position["longitude"]

        if not (-90 <= latitude <= 90):
            return None

        if not (-180 <= longitude <= 180):
            return None

        return position