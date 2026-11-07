import os
import sys
import tempfile
from pathlib import Path

from calibre.gui2.actions import InterfaceAction
from calibre.gui2 import info_dialog, error_dialog

from qt.core import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QRadioButton,
    QDialogButtonBox,
    QButtonGroup,
    QIcon,
    QPixmap,
    QGroupBox,
    QThread,
    pyqtSignal,
)


class GenerateComicKFXDialog(QDialog):

    def __init__(self, text, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Generate Comic KFX")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(text))

        # Read direction
        direction_box = QGroupBox("Read direction:")
        direction_layout = QVBoxLayout(direction_box)

        self.direction_group = QButtonGroup(self)
        self.rtl = QRadioButton("RTL (Right to Left, Asian comics)")
        self.rtl.setChecked(True)
        self.ltr = QRadioButton("LTR (Left to Right, Western comics)")

        self.direction_group.addButton(self.rtl)
        self.direction_group.addButton(self.ltr)

        direction_layout.addWidget(self.rtl)
        direction_layout.addWidget(self.ltr)
        layout.addWidget(direction_box)

        # Content type
        content_box = QGroupBox("Content type:")
        content_layout = QVBoxLayout(content_box)

        self.content_group = QButtonGroup(self)
        self.pdoc = QRadioButton("PDOC (Displayed in Kindle Documents)")
        self.ebook = QRadioButton("EBOOK (Displayed in Kindle Books)")
        self.ebook.setChecked(True)

        self.content_group.addButton(self.ebook)
        self.content_group.addButton(self.pdoc)

        content_layout.addWidget(self.ebook)
        content_layout.addWidget(self.pdoc)
        layout.addWidget(content_box)

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class ComicKfxWorker(QThread):
    progress_updated = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, db, cbz_items, options, runtime_lib_path):
        super().__init__()
        self.db = db
        self.cbz_items = cbz_items  # List of tuples: (book_id, cbz_path)
        self.options = options
        self.runtime_lib_path = runtime_lib_path

    def _prepare_runtime_libraries(self):
        if self.runtime_lib_path not in sys.path:
            sys.path.insert(0, self.runtime_lib_path)

    def run(self):
        try:
            self._prepare_runtime_libraries()
            from kckfxgen.pipeline import convert_to_kfx

            total = len(self.cbz_items)
            for idx, (book_id, cbz_file) in enumerate(self.cbz_items, 1):
                mi = self.db.get_metadata(book_id)
                self.progress_updated.emit(f"Converting ({idx}/{total}): {mi.title}")

                with tempfile.TemporaryDirectory(prefix="comic_kfx_") as tmp:
                    tmp_path = Path(tmp)

                    convert_to_kfx(
                        Path(cbz_file),
                        kfx_output_dir=tmp_path,
                        page_progression=self.options["page_progression"],
                        split_page_order=self.options["split_page_order"],
                        page_spread_previews=True,
                        cde_content_type=self.options["content_type"],
                        layout_view="virtual",
                        book_title=mi.title,
                        book_author=", ".join(mi.authors),
                        book_publisher=mi.publisher,
                    )

                    kfx_file = next(tmp_path.rglob("*.kfx"), None)
                    if kfx_file:
                        self.db.add_format(book_id, "KFX", kfx_file, replace=True)
                    else:
                        raise FileNotFoundError(
                            f"No KFX file generated for '{mi.title}'."
                        )

            self.finished.emit(True, "All KFX files have been generated successfully.")
        except Exception as e:
            self.finished.emit(False, str(e))


class GenerateComicKFX(InterfaceAction):

    name = "Generate Comic KFX"

    action_spec = (
        "Generate Comic KFX",
        None,
        "Generate optimized KFX for comics",
        None,
    )

    def _get_lib_path(self):
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        target_lib_dir = os.path.join(plugin_dir, "_comic_kfx_libs")
        real_lib_path = os.path.join(target_lib_dir, "lib")

        if not os.path.exists(real_lib_path):
            if ".zip" in plugin_dir:
                zip_path = plugin_dir.split(".zip")[0] + ".zip"
                plugins_dir = os.path.dirname(zip_path)
                target_lib_dir = os.path.join(plugins_dir, "_comic_kfx_libs")
                real_lib_path = os.path.join(target_lib_dir, "lib")
                if not os.path.exists(real_lib_path):
                    os.makedirs(target_lib_dir, exist_ok=True)
                    import zipfile

                    with zipfile.ZipFile(zip_path, "r") as z:
                        for filename in z.namelist():
                            if filename.startswith("lib/"):
                                z.extract(filename, target_lib_dir)
        return real_lib_path

    def genesis(self):
        resources = self.load_resources(["images/comic.png"])
        pixmap = QPixmap()
        loaded = pixmap.loadFromData(resources["images/comic.png"])

        if loaded:
            icon = QIcon(pixmap)
            self.qaction.setIcon(icon)

        self.qaction.triggered.connect(self.run)

    def run(self):
        rows = self.gui.library_view.selectionModel().selectedRows()

        if not rows:
            info_dialog(
                self.gui, "Generate Comic KFX", "Select a book first.", show=True
            )
            return

        model = self.gui.library_view.model()
        book_ids = list(map(model.id, rows))
        db = self.gui.current_db.new_api

        cbz_items = []
        missing = []

        for book_id in book_ids:
            mi = db.get_metadata(book_id)
            formats = db.formats(book_id)
            format_paths = {fmt: db.format_abspath(book_id, fmt) for fmt in formats}

            if "CBZ" in format_paths:
                cbz_items.append((book_id, format_paths["CBZ"]))
            else:
                missing.append(mi.title)

        if missing:
            info_dialog(
                self.gui,
                "Generate Comic KFX",
                f"Missing CBZ for:\n{'\n'.join(missing)}",
                show=True,
            )
            if not cbz_items:
                return

        cbz_filenames = [Path(path).name for _, path in cbz_items]
        dialog = GenerateComicKFXDialog(
            f"The following titles will be converted into optimized KFX comic files:\n\n{'\n'.join(cbz_filenames)}\n\n",
            self.gui,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            reading_order = "RTL" if dialog.rtl.isChecked() else "LTR"
            content_type = "PDOC" if dialog.pdoc.isChecked() else "EBOOK"

            options = {
                "page_progression": "rtl" if reading_order == "RTL" else "ltr",
                "split_page_order": (
                    "right-left" if reading_order == "RTL" else "left-right"
                ),
                "content_type": content_type,
            }

            runtime_lib_path = self._get_lib_path()

            # Disable UI action or lock interaction if desired, and start the background thread
            self.gui.status_bar.showMessage("Preparing KFX conversion worker...")

            self.worker = ComicKfxWorker(db, cbz_items, options, runtime_lib_path)
            self.worker.progress_updated.connect(self.on_progress_updated)
            self.worker.finished.connect(self.on_finished)
            self.worker.start()

    def on_progress_updated(self, message):
        self.gui.status_bar.showMessage(message)

    def on_finished(self, success, message):
        self.gui.status_bar.clearMessage()
        if success:
            info_dialog(self.gui, "Generate Comic KFX", message, show=True)
            self.gui.library_view.model().reset()
        else:
            error_dialog(
                self.gui,
                "Generate Comic KFX",
                f"Conversion failed:\n{message}",
                show=True,
            )
