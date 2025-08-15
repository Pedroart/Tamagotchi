class Camera:
    def __init__(self, cfg):
        self.cx = cfg["SCREEN_W"] / 2
        self.cy = cfg["SCREEN_H"] * 0.55 + cfg["SCENE_Y_OFFSET"]
        self.focal = cfg["FOCAL"]
        self.x = cfg["CAM_X"]; self.y = cfg["CAM_Y"]; self.z = cfg["CAM_Z"]

    def project(self, x, y, z):
        X = x - self.x; Y = y - self.y; Z = z - self.z
        if Z <= 0.05: return None
        sx = self.cx + self.focal * (X / Z)
        sy = self.cy - self.focal * (Y / Z)
        return (sx, sy), Z
