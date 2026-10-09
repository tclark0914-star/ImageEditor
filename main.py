"""Image Editor - Milestone 1: a window that opens and displays an image."""
import sys

from PIL import Image, ImageOps
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QImage, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsScene,
    QGraphicsView,
    QMainWindow,
    QMessageBox,
)

IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif);;All files (*)"


class Canvas(QGraphicsView):
    """Shows one image. Mouse wheel zooms, drag with the left button to pan."""

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.item = None

    def show_pixmap(self, pixmap):
        self.scene().clear()
        self.item = self.scene().addPixmap(pixmap)
        self.scene().setSceneRect(self.item.boundingRect())
        self.fit()

    def fit(self):
        if self.item is not None:
            self.resetTransform()
            self.fitInView(self.item, Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Editor")
        self.resize(1000, 700)
        self.canvas = Canvas()
        self.setCentralWidget(self.canvas)

        file_menu = self.menuBar().addMenu("&File")
        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_dialog)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = self.menuBar().addMenu("&View")
        fit_action = QAction("&Fit to window", self)
        fit_action.setShortcut("Ctrl+0")
        fit_action.triggered.connect(self.canvas.fit)
        view_menu.addAction(fit_action)

        self.statusBar().showMessage("File > Open to load an image")

    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open image", "", IMAGE_FILTER)
        if path:
            self.load_image(path)

    def load_image(self, path):
        try:
            img = Image.open(path)
            img = ImageOps.exif_transpose(img).convert("RGBA")
            data = img.tobytes("raw", "RGBA")
            qimage = QImage(
                data, img.width, img.height, img.width * 4, QImage.Format.Format_RGBA8888
            ).copy()  # copy so Qt owns its own memory
        except Exception as error:
            QMessageBox.warning(self, "Could not open image", f"{path}\n\n{error}")
            return False
        self.canvas.show_pixmap(QPixmap.fromImage(qimage))
        self.statusBar().showMessage(f"{path}  -  {img.width} x {img.height} px")
        return True


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    if len(sys.argv) > 1:
        window.load_image(sys.argv[1])
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
