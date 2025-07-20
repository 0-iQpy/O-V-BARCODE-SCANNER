from kivy.utils import platform
from kivy.graphics.texture import Texture
from kivy.clock import Clock
if platform == 'android':
    from kivy.core.camera import Camera as KivyCamera
else:
    import cv2
import numpy as np


class CameraController:
    def __init__(self, resolution=(640, 480), **kwargs):
        self.resolution = resolution
        self.camera = None
        self.texture = None
        self.is_running = False

    def start(self):
        try:
            if platform == 'android':
                self.camera = KivyCamera(index=0, resolution=self.resolution, play=True)
            else:
                self.camera = cv2.VideoCapture(0)
                self.camera.set(3, self.resolution[0])
                self.camera.set(4, self.resolution[1])
            self.is_running = True
        except Exception as e:
            print(f"Error starting camera: {e}")
            self.is_running = False

    def stop(self):
        if self.is_running:
            if platform == 'android':
                if self.camera:
                    self.camera.stop()
                    self.camera = None
            else:
                if self.camera:
                    self.camera.release()
                    self.camera = None
            self.is_running = False

    def get_frame(self):
        if not self.is_running:
            return None
        try:
            if platform == 'android':
                if self.camera and self.camera.texture:
                    texture = self.camera.texture
                    size = texture.size
                    pixels = texture.pixels
                    image = np.frombuffer(pixels, dtype='uint8').reshape(size[1], size[0], 4)
                    return cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
            else:
                success, frame = self.camera.read()
                if success:
                    return frame
        except Exception as e:
            print(f"Error getting frame: {e}")
        return None

    def get_texture(self):
        if platform == 'android':
            return self.camera.texture
        else:
            frame = self.get_frame()
            if frame is not None:
                buf = cv2.flip(frame, 0).tostring()
                texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
                texture.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
                return texture
        return None
