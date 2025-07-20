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
from jnius import *

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
            from android.permissions import check_permission
            from jnius import autoclass, cast
            from android.provider import Settings

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
        file_chooser = FileChooserListView(filters=['*.csv', '*.txt'])
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

    def on_enter(self):
        # Start camera when screen is shown
        self.camera = cv2.VideoCapture(0)
        self.camera.set(3, 640)
        self.camera.set(4, 480)
        Clock.schedule_interval(self.update_camera, 1.0 / 30.0)

    def on_leave(self):
        # Stop camera when leaving screen
        if self.camera:
            self.camera.release()
            self.camera = None
        Clock.unschedule(self.update_camera)

    def update_camera(self, dt):
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
        color = (0, 255, 0) if is_valid else (0, 0, 255)

        self.status_label.text = f"Validation: {result_text} ({self.current_barcode})"

        # Draw bounding box
        pts = np.array([barcode.polygon], np.int32).reshape((-1, 1, 2))
        cv2.polylines(img, [pts], True, color, 5)

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


    def open_settings(self, *args):
        if platform == "android":
            from jnius import autoclass
            from kivy.core.window import Window
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            Uri = autoclass('android.net.Uri')
            settings_intent = Intent(autoclass('android.provider.Settings').ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                                     Uri.parse("package:" + PythonActivity.mActivity.getPackageName()))
            PythonActivity.mActivity.startActivity(settings_intent)

class BarcodeScannerApp(App):
    def build(self):
        if platform == "android":
            request_permissions([
                'android.permission.CAMERA'
            ])
        self.sm = ScreenManager()
        self.sm.add_widget(MainScreen())
        self.sm.add_widget(ScannerScreen())
        return self.sm


if __name__ == '__main__':
    BarcodeScannerApp().run()