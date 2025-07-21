import cv2
import numpy as np
from pyzbar.pyzbar import decode
import csv
import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.utils import platform
from jnius import autoclass

if platform == "android":
    from android.permissions import request_permissions

valid_barcodes = set()


class MainScreen(Screen):
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        self.name = 'main'

        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)

        self.title_label = Label(text="Barcode Scanner by OCTAVYTE", font_size=24, size_hint=(1, 0.2))
        layout.add_widget(self.title_label)

        self.import_btn = Button(text="Import CSV/TXT File", size_hint=(1, 0.3))
        self.import_btn.bind(on_press=self.show_file_chooser)
        layout.add_widget(self.import_btn)

        self.permission_status_label = Label(text="Permission Status: Unknown", size_hint=(1, 0.1))
        layout.add_widget(self.permission_status_label)

        self.exit_btn = Button(text="Exit", size_hint=(1, 0.3))
        self.exit_btn.bind(on_press=self.exit_app)
        layout.add_widget(self.exit_btn)

        self.add_widget(layout)

    def on_enter(self, *args):
        if platform == "android":
            self.check_permissions()

    def check_permissions(self):
        if platform == "android":
            from jnius import autoclass
            Environment = autoclass('android.os.Environment')
            if Environment.isExternalStorageManager():
                self.permission_status_label.text = "Permission Status: Granted"
                return True
            else:
                self.permission_status_label.text = "Permission Status: Denied"
                return False

    def show_file_chooser(self, instance):
        if platform == "android":
            if not self.check_permissions():
                self.show_message("Permission Denied", "Storage permission is required to load files. Please grant permission in settings.")
                self.open_settings()
                return

        content = BoxLayout(orientation='vertical')
        from jnius import autoclass
        Environment = autoclass('android.os.Environment')
        default_path = Environment.getExternalStorageDirectory().getPath()
        file_chooser = FileChooserListView(path=default_path, filters=['*.csv', '*.txt'])
        content.add_widget(file_chooser)

        btn_layout = BoxLayout(size_hint=(1, 0.1))
        cancel_btn = Button(text="Cancel")
        load_btn = Button(text="Load")

        btn_layout.add_widget(cancel_btn)
        btn_layout.add_widget(load_btn)
        content.add_widget(btn_layout)

        popup = Popup(title="Select CSV/TXT File", content=content, size_hint=(0.9, 0.9))

        cancel_btn.bind(on_press=popup.dismiss)
        load_btn.bind(on_press=lambda x: self.load_file(file_chooser.path, file_chooser.selection, popup))

        popup.open()

    def load_file(self, path, selection, popup):
        if selection:
            file_path = os.path.join(path, selection[0])
            global valid_barcodes
            valid_barcodes = set()

            try:
                if file_path.endswith('.csv'):
                    with open(file_path, mode='r') as file:
                        reader = csv.reader(file)
                        for row in reader:
                            for data in row:
                                valid_barcodes.add(data.strip())
                elif file_path.endswith('.txt'):
                    with open(file_path, mode='r') as file:
                        for line in file:
                            valid_barcodes.add(line.strip())

                if valid_barcodes:
                    self.manager.current = 'scanner'
                else:
                    self.show_message("Warning", "No valid barcodes found in the file.")
            except Exception as e:
                self.show_message("Error", f"Failed to load file: {str(e)}")

        popup.dismiss()

    def show_message(self, title, message):
        content = Label(text=message)
        popup = Popup(title=title, content=content, size_hint=(0.8, 0.4))
        popup.open()

    def open_settings(self, *args):
        if platform == "android":
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            Settings = autoclass('android.provider.Settings')
            Uri = autoclass('android.net.Uri')

            app_package_name = PythonActivity.mActivity.getPackageName()
            intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
            uri = Uri.fromParts("package", app_package_name, None)
            intent.setData(uri)
            PythonActivity.mActivity.startActivity(intent)

    def exit_app(self, instance):
        App.get_running_app().stop()


class ScannerScreen(Screen):
    def __init__(self, **kwargs):
        super(ScannerScreen, self).__init__(**kwargs)
        self.name = 'scanner'

        self.layout = BoxLayout(orientation='vertical', padding=10, spacing=10)

        # Camera display
        self.camera_display = Image(size_hint=(1, 0.7))
        self.layout.add_widget(self.camera_display)

        # Status label
        self.status_label = Label(text="Ready to scan", size_hint=(1, 0.1))
        self.layout.add_widget(self.status_label)

        # Button layout
        btn_layout = BoxLayout(size_hint=(1, 0.2), spacing=10)

        self.back_btn = Button(text="Back")
        self.back_btn.bind(on_press=self.go_back)
        btn_layout.add_widget(self.back_btn)

        self.layout.add_widget(btn_layout)

        self.add_widget(self.layout)

        # Camera initialization
        self.camera = None
        self.current_barcode = None
        self.image_reader = None
        self.camera_device = None
        self.camera_session = None

    def on_enter(self):
        if platform == "android":
            self.init_camera()
        else:
            self.camera = cv2.VideoCapture(0)
            self.camera.set(3, 640)
            self.camera.set(4, 480)
        Clock.schedule_interval(self.update_camera, 1.0 / 30.0)

    def init_camera(self):
        try:
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Context = autoclass('android.content.Context')
            CameraManager = autoclass('android.hardware.camera2.CameraManager')
            ImageFormat = autoclass('android.graphics.ImageFormat')
            ImageReader = autoclass('android.media.ImageReader')
            Handler = autoclass('android.os.Handler')
            Looper = autoclass('android.os.Looper')

            activity = PythonActivity.mActivity
            camera_manager = activity.getSystemService(Context.CAMERA_SERVICE)
            camera_id = camera_manager.getCameraIdList()[0]

            self.image_reader = ImageReader.newInstance(640, 480, ImageFormat.YUV_420_888, 2)
            self.image_reader.setOnImageAvailableListener(self.on_image_available, Handler(Looper.getMainLooper()))

            camera_manager.openCamera(camera_id, StateCallback(self), None)
        except Exception as e:
            self.show_message("Error", f"Failed to initialize camera: {str(e)}")
            self.go_back(None)

    def on_image_available(self, reader):
        try:
            image = reader.acquireLatestImage()
            if not image:
                return

            width = image.getWidth()
            height = image.getHeight()
            planes = image.getPlanes()

            y_buffer = planes[0].getBuffer()
            u_buffer = planes[1].getBuffer()
            v_buffer = planes[2].getBuffer()

            # Create numpy arrays from the buffers
            y_array = np.array(y_buffer.array(), dtype=np.uint8)
            u_array = np.array(u_buffer.array(), dtype=np.uint8)
            v_array = np.array(v_buffer.array(), dtype=np.uint8)

            # Create the YUV image
            yuv_image = np.zeros(width * height * 3 // 2, dtype=np.uint8)
            yuv_image[:width * height] = y_array
            yuv_image[width * height:width * height + width * height // 4] = u_array
            yuv_image[width * height + width * height // 4:] = v_array
            yuv_image = yuv_image.reshape((height * 3 // 2, width))

            # Convert to BGR
            img = cv2.cvtColor(yuv_image, cv2.COLOR_YUV2BGR_I420)

            self.status_label.text = "Ready to scan"
            barcodes = decode(img)

            if barcodes:
                self.process_barcodes(img, barcodes)

            self.update_texture(img)
            image.close()
        except Exception as e:
            self.show_message("Error", f"Failed to process image: {str(e)}")


    def create_camera_preview_session(self):
        try:
            CaptureRequest = autoclass('android.hardware.camera2.CaptureRequest')
            CameraCaptureSession = autoclass('android.hardware.camera2.CameraCaptureSession')
            ArrayList = autoclass('java.util.ArrayList')

            surfaces = ArrayList()
            surfaces.add(self.image_reader.getSurface())

            self.camera_device.createCaptureSession(surfaces, self.create_capture_session_callback(), None)
        except Exception as e:
            self.show_message("Error", f"Failed to create camera preview session: {str(e)}")
            self.go_back(None)

    def create_capture_session_callback(self):
        CameraCaptureSession = autoclass('android.hardware.camera2.CameraCaptureSession')
        CaptureRequest = autoclass('android.hardware.camera2.CaptureRequest')

        class SessionStateCallback(CameraCaptureSession.StateCallback):
            def __init__(self, owner):
                super().__init__()
                self.owner = owner

            def onConfigured(self, session):
                self.owner.camera_session = session
                self.owner.start_preview()

            def onConfigureFailed(self, session):
                pass

        return SessionStateCallback(self)

    def start_preview(self):
        CaptureRequest = autoclass('android.hardware.camera2.CaptureRequest')
        builder = self.camera_device.createCaptureRequest(self.camera_device.TEMPLATE_PREVIEW)
        builder.addTarget(self.image_reader.getSurface())
        self.camera_session.setRepeatingRequest(builder.build(), None, None)

    def on_leave(self):
        # Stop camera when leaving screen
        if self.camera:
            self.camera.release()
            self.camera = None
        Clock.unschedule(self.update_camera)

    def update_camera(self, dt):
        if platform == "android":
            # The image processing is now triggered by on_image_available
            pass
        else:
            if not self.camera:
                return

            success, img = self.camera.read()
            if not success:
                return

            self.status_label.text = "Ready to scan"
            barcodes = decode(img)

            if barcodes:
                self.process_barcodes(img, barcodes)

            self.update_texture(img)

    def process_barcodes(self, img, barcodes):
        for barcode in barcodes:
            self.current_barcode = barcode.data.decode("utf-8")
            is_valid = self.current_barcode in valid_barcodes

            self.draw_barcode_feedback(img, barcode, is_valid)

    def draw_barcode_feedback(self, img, barcode, is_valid):
        result_text = "Valid" if is_valid else "Invalid"
        if is_valid:
            color = (0, 255, 0)  # Green
        else:
            color = (0, 0, 255)  # Red

        self.status_label.text = f"Validation: {result_text} ({self.current_barcode})"

        # Draw bounding box
        pts = np.array([barcode.polygon], np.int32).reshape((-1, 1, 2))
        cv2.polylines(img, [pts], True, color, 5)

        # Add a purple border for invalid barcodes
        if not is_valid:
            cv2.polylines(img, [pts], True, (128, 0, 128), 10)

        # Add validation text
        pts2 = barcode.rect
        text_position = (pts2[0], pts2[1] - 10)
        cv2.putText(img, result_text, text_position, cv2.FONT_HERSHEY_SIMPLEX, 1, color, 3)

    def update_texture(self, img):
        buf = cv2.flip(img, 0).tostring()
        texture = Texture.create(size=(img.shape[1], img.shape[0]), colorfmt='bgr')
        texture.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
        self.camera_display.texture = texture

    def go_back(self, instance):
        self.manager.current = 'main'

    def show_message(self, title, message):
        content = Label(text=message)
        popup = Popup(title=title, content=content, size_hint=(0.8, 0.4))
        popup.open()

class StateCallback(autoclass('java.lang.Object')):
    __javainterfaces__ = ['android/hardware/camera2/CameraDevice$StateCallback']

    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def onOpened(self, camera):
        self.owner.camera_device = camera
        self.owner.create_camera_preview_session()

    def onDisconnected(self, camera):
        camera.close()
        self.owner.camera_device = None

    def onError(self, camera, error):
        camera.close()
        self.owner.camera_device = None

class BarcodeScannerApp(App):
    def build(self):
        if platform == "android":
            request_permissions([
                'android.permission.CAMERA',
                'android.permission.MANAGE_EXTERNAL_STORAGE'
            ])
        self.sm = ScreenManager()
        self.sm.add_widget(MainScreen())
        self.sm.add_widget(ScannerScreen())
        return self.sm


if __name__ == '__main__':
    BarcodeScannerApp().run()