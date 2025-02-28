import flet as ft
import os
import glob
from PIL import Image
from nudenet import NudeDetector
import threading
import time
import shutil
from pathlib import Path

class NudityDetectorApp:
    def __init__(self):
        self.detector = NudeDetector()
        self.scanning = False
        self.scan_thread = None
        self.current_folder = ""
        self.flagged_images = []
        self.current_image_index = 0
        self.detection_threshold = 0.5
        self.scan_progress = 0
        self.total_images = 0
        self.processed_images = 0

    def main(self, page: ft.Page):
        # App setup
        page.title = "Image Content Scanner"
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 20
        page.window_width = 1000
        page.window_height = 700
        page.window_resizable = True

        # UI Components for folder selection and scanning
        self.folder_path = ft.Text(
            value="No folder selected", 
            size=14, 
            color=ft.colors.GREY_400
        )
        
        self.progress_bar = ft.ProgressBar(visible=False)
        self.status_text = ft.Text("", size=14)
        
        # Results section
        self.result_text = ft.Text("", size=16, weight=ft.FontWeight.BOLD)
        
        # Image preview section (initially hidden)
        self.current_image = ft.Image(
            fit=ft.ImageFit.CONTAIN,
            visible=False,
            height=400
        )
        
        self.image_counter = ft.Text(
            value="", 
            size=14, 
            text_align=ft.TextAlign.CENTER
        )
        
        # Navigation buttons for flagged images
        self.prev_button = ft.IconButton(
            icon=ft.icons.ARROW_BACK,
            on_click=self.show_previous_image,
            visible=False
        )
        
        self.next_button = ft.IconButton(
            icon=ft.icons.ARROW_FORWARD,
            on_click=self.show_next_image,
            visible=False
        )
        
        self.keep_button = ft.ElevatedButton(
            "Keep Image",
            icon=ft.icons.CHECK,
            color=ft.colors.WHITE,
            bgcolor=ft.colors.GREEN_700,
            on_click=self.keep_image,
            visible=False
        )
        
        self.delete_button = ft.ElevatedButton(
            "Delete Image",
            icon=ft.icons.DELETE,
            color=ft.colors.WHITE,
            bgcolor=ft.colors.RED_700,
            on_click=self.delete_image,
            visible=False
        )

        # Threshold slider for detection sensitivity
        self.threshold_slider = ft.Slider(
            min=0.1,
            max=0.9,
            divisions=8,
            value=self.detection_threshold,
            label="{value}",
            on_change=self.update_threshold
        )

        # Button to select folder
        select_folder_button = ft.ElevatedButton(
            "Select Folder",
            icon=ft.icons.FOLDER_OPEN,
            on_click=self.pick_directory
        )
        
        # Button to start scanning
        self.scan_button = ft.ElevatedButton(
            "Start Scan",
            icon=ft.icons.SEARCH,
            on_click=self.start_scan,
            disabled=True
        )

        # Building the UI layout
        page.add(
            ft.Row([
                ft.Text("Nudity Content Scanner", style=ft.TextThemeStyle.HEADLINE_MEDIUM)
            ], alignment=ft.MainAxisAlignment.CENTER),
            
            ft.Divider(),
            
            ft.Container(
                content=ft.Column([
                    ft.Text("Select a folder to scan", size=16, weight=ft.FontWeight.BOLD),
                    ft.Row([select_folder_button, self.folder_path]),
                    ft.Row([
                        ft.Text("Detection Threshold: "),
                        self.threshold_slider,
                        ft.Text(f"{self.detection_threshold}")
                    ]),
                    ft.Row([self.scan_button]),
                    self.progress_bar,
                    self.status_text
                ]),
                padding=10,
                border=ft.border.all(1, ft.colors.GREY_400),
                border_radius=10,
                margin=ft.margin.only(bottom=20)
            ),
            
            self.result_text,
            
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        self.prev_button,
                        ft.Column([self.current_image], expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        self.next_button
                    ], alignment=ft.MainAxisAlignment.CENTER),
                    self.image_counter,
                    ft.Row([
                        self.keep_button,
                        self.delete_button
                    ], alignment=ft.MainAxisAlignment.CENTER)
                ]),
                padding=10,
                border=ft.border.all(1, ft.colors.GREY_400),
                border_radius=10,
                visible=False,
                expand=True
            )
        )
        
        # Main container for the flagged images review
        self.review_container = page.controls[-1]

    def update_threshold(self, e):
        self.detection_threshold = round(e.control.value, 1)
        e.page.controls[3].content.controls[2].controls[2].value = f"{self.detection_threshold}"
        e.page.update()

    def pick_directory(self, e):
        def on_dialog_result(e: ft.FilePickerResultEvent):
            if e.path:
                self.current_folder = e.path
                self.folder_path.value = e.path
                self.scan_button.disabled = False
                e.page.update()
        
        file_picker = ft.FilePicker(on_result=on_dialog_result)
        e.page.overlay.append(file_picker)
        e.page.update()
        file_picker.get_directory_path()

    def start_scan(self, e):
        if not self.scanning:
            self.scanning = True
            self.scan_button.disabled = True
            self.progress_bar.visible = True
            self.status_text.value = "Scanning folder for images..."
            e.page.update()
            
            # Start scan in a separate thread
            self.scan_thread = threading.Thread(target=self.scan_folder, args=(e.page,))
            self.scan_thread.daemon = True
            self.scan_thread.start()

    def scan_folder(self, page):
        self.flagged_images = []
        self.current_image_index = 0
        
        # Get all image files
        image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.bmp', '*.webp']
        all_images = []
        
        for ext in image_extensions:
            all_images.extend(glob.glob(os.path.join(self.current_folder, ext)))
            all_images.extend(glob.glob(os.path.join(self.current_folder, '**', ext), recursive=True))
        
        all_images = list(set(all_images))  # Remove duplicates
        self.total_images = len(all_images)
        self.processed_images = 0
        
        if self.total_images == 0:
            self.status_text.value = "No images found in the selected folder."
            self.scanning = False
            self.scan_button.disabled = False
            self.progress_bar.visible = False
            page.update()
            return
        
        # Process each image
        for img_path in all_images:
            try:
                # Update progress
                self.processed_images += 1
                self.scan_progress = self.processed_images / self.total_images
                self.progress_bar.value = self.scan_progress
                
                # Update status
                self.status_text.value = f"Scanning {self.processed_images} of {self.total_images}: {os.path.basename(img_path)}"
                page.update()
                
                # Run detection
                detections = self.detector.detect(img_path)
                
                # Check if any detections exceed the threshold
                for detection in detections:
                    if detection['score'] >= self.detection_threshold:
                        self.flagged_images.append({
                            'path': img_path,
                            'detections': detections
                        })
                        break
                
            except Exception as ex:
                print(f"Error processing {img_path}: {str(ex)}")
        
        # Scanning complete
        self.scanning = False
        self.scan_button.disabled = False
        
        # Update UI with results
        # page.invoke_async(self.update_results, page)
        self.update_results(page)

    def update_results(self, page):
        self.progress_bar.visible = False
        
        if len(self.flagged_images) > 0:
            self.result_text.value = f"Found {len(self.flagged_images)} images with potential nude content"
            self.status_text.value = "Scan complete. Review flagged images below."
            
            # Show first flagged image
            self.show_image(0)
            
            # Show navigation and action buttons
            self.prev_button.visible = True
            self.next_button.visible = True
            self.keep_button.visible = True
            self.delete_button.visible = True
            self.review_container.visible = True
            self.current_image.visible = True
        else:
            self.result_text.value = "No nude content detected in any images"
            self.status_text.value = "Scan complete. No flagged images found."
            self.review_container.visible = False
        
        page.update()

    def show_image(self, index):
        if not self.flagged_images:
            return
        
        # Handle index bounds
        self.current_image_index = max(0, min(index, len(self.flagged_images) - 1))
        
        # Get image path
        img_data = self.flagged_images[self.current_image_index]
        img_path = img_data['path']
        
        # Update the image counter
        self.image_counter.value = f"Image {self.current_image_index + 1} of {len(self.flagged_images)}"
        
        # Update image preview
        self.current_image.src = img_path
        
        # Update buttons states based on position
        self.prev_button.disabled = (self.current_image_index == 0)
        self.next_button.disabled = (self.current_image_index == len(self.flagged_images) - 1)

    def show_next_image(self, e):
        if self.current_image_index < len(self.flagged_images) - 1:
            self.show_image(self.current_image_index + 1)
            e.page.update()

    def show_previous_image(self, e):
        if self.current_image_index > 0:
            self.show_image(self.current_image_index - 1)
            e.page.update()

    def keep_image(self, e):
        if not self.flagged_images:
            return
            
        # Just remove from flagged list and move to next
        current_img = self.flagged_images.pop(self.current_image_index)
        
        # Update counter text
        self.image_counter.value = f"Image {self.current_image_index + 1} of {len(self.flagged_images)}"
        
        # Check if we've processed all images
        if not self.flagged_images:
            self.result_text.value = "All flagged images have been processed"
            self.review_container.visible = False
            e.page.update()
            return
        
        # Show next image or previous if we're at the end
        if self.current_image_index >= len(self.flagged_images):
            self.current_image_index = len(self.flagged_images) - 1
        
        self.show_image(self.current_image_index)
        e.page.update()

    def delete_image(self, e):
        if not self.flagged_images:
            return
            
        # Get current image path
        current_img = self.flagged_images.pop(self.current_image_index)
        img_path = current_img['path']
        
        try:
            # Move to recycle bin instead of permanent deletion
            # Create a "deleted" folder in the same directory as the image
            img_dir = os.path.dirname(img_path)
            deleted_dir = os.path.join(img_dir, "deleted_images")
            
            # Create the folder if it doesn't exist
            os.makedirs(deleted_dir, exist_ok=True)
            
            # Move the file instead of deleting it permanently
            shutil.move(img_path, os.path.join(deleted_dir, os.path.basename(img_path)))
            
            self.status_text.value = f"Moved to 'deleted_images' folder: {os.path.basename(img_path)}"
        except Exception as ex:
            self.status_text.value = f"Error deleting {os.path.basename(img_path)}: {str(ex)}"
        
        # Update counter text
        self.image_counter.value = f"Image {self.current_image_index + 1} of {len(self.flagged_images)}"
        
        # Check if we've processed all images
        if not self.flagged_images:
            self.result_text.value = "All flagged images have been processed"
            self.review_container.visible = False
            e.page.update()
            return
        
        # Show next image or previous if we're at the end
        if self.current_image_index >= len(self.flagged_images):
            self.current_image_index = len(self.flagged_images) - 1
        
        self.show_image(self.current_image_index)
        e.page.update()

def main():
    app = NudityDetectorApp()
    ft.app(target=app.main)

if __name__ == "__main__":
    main()