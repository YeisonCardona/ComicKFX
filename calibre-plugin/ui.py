import os
import sys
import tempfile
import zipfile
from pathlib import Path

from calibre.gui2.actions import InterfaceAction
from calibre.gui2 import info_dialog


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


class GenerateComicKFX(InterfaceAction):

    name = "Generate Comic KFX"

    action_spec = (
        "Generate Comic KFX",
        None,
        "Generate optimized KFX for comics",
        None,
    )

    def _prepare_runtime_libraries(self):
        plugin_dir = os.path.dirname(os.path.abspath(__file__))

        # Si estamos en desarrollo por symlink o carpeta directa
        target_lib_dir = os.path.join(plugin_dir, "_comic_kfx_libs")
        real_lib_path = os.path.join(target_lib_dir, "lib")

        # Si la carpeta lib local de desarrollo existe, la usamos directamente
        if not os.path.exists(real_lib_path):
            # Fallback por si acaso se empaqueta como zip en producción
            if ".zip" in plugin_dir:
                zip_path = plugin_dir.split(".zip")[0] + ".zip"
                plugins_dir = os.path.dirname(zip_path)
                target_lib_dir = os.path.join(plugins_dir, "_comic_kfx_libs")
                real_lib_path = os.path.join(target_lib_dir, "lib")
                if not os.path.exists(real_lib_path):
                    os.makedirs(target_lib_dir, exist_ok=True)
                    with zipfile.ZipFile(zip_path, "r") as z:
                        for filename in z.namelist():
                            if filename.startswith("lib/"):
                                z.extract(filename, target_lib_dir)

        if real_lib_path not in sys.path:
            sys.path.insert(0, real_lib_path)

    def genesis(self):
        resources = self.load_resources(["images/comic.png"])
        pixmap = QPixmap()
        loaded = pixmap.loadFromData(resources["images/comic.png"])

        if loaded:
            icon = QIcon(pixmap)
            self.qaction.setIcon(icon)

        self.qaction.triggered.connect(self.run)

    def run(self):
        self._prepare_runtime_libraries()
        from kckfxgen.pipeline import convert_to_kfx

        rows = self.gui.library_view.selectionModel().selectedRows()

        if not rows:
            info_dialog(
                self.gui, "Generate Comic KFX", "Select a book first.", show=True
            )
            return

        # Obtener IDs internos
        model = self.gui.library_view.model()
        book_ids = list(map(model.id, rows))

        # Utilizar la API nueva
        db = self.gui.current_db.new_api

        cbz = []
        ids = []
        missinng = []

        for book_id in book_ids:

            # Metadatos
            mi = db.get_metadata(book_id)

            # Formatos disponibles
            formats = db.formats(book_id)

            # Rutas físicas de los formatos
            format_paths = {}

            for fmt in formats:
                format_paths[fmt] = db.format_abspath(book_id, fmt)

            if "CBZ" in format_paths:
                cbz.append(format_paths["CBZ"])
                ids.append(book_id)
            else:
                missinng.append(mi.title)

        if missinng:
            info_dialog(
                self.gui,
                "Generate Comic KFX",
                f"Missing CBZ for\n{'\n'.join(missinng)}",
                show=True,
            )

        dialog = GenerateComicKFXDialog(
            f"The following titles will be converted into optimized KFX comic files:\n\n{'\n'.join([Path(file).name for file in cbz])}\n\n",
            self.gui,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            reading_order = "RTL" if dialog.rtl.isChecked() else "LTR"
            content_type = "PDOC" if dialog.pdoc.isChecked() else "EBOOK"

            if reading_order == "RTL":
                page_progression = "rtl"
                split_page_order = "right-left"
            else:
                page_progression = "ltr"
                split_page_order = "left-right"

            for cbz_file, book_id in zip(cbz, ids):

                with tempfile.TemporaryDirectory(prefix="comic_kfx_") as tmp:
                    tmp_path = Path(tmp)

                    convert_to_kfx(
                        Path(cbz_file),
                        kfx_output_dir=tmp_path,
                        page_progression=page_progression,
                        split_page_order=split_page_order,
                        page_spread_previews=True,
                        cde_content_type=content_type,
                        layout_view="virtual",
                    )

                    kfx_file = next(tmp_path.rglob("*.kfx"), None)
                    if kfx_file:
                        db.add_format(book_id, "KFX", kfx_file, replace=True)

                    else:
                        raise FileNotFoundError("No KFX file was generated.")

            info_dialog(
                self.gui,
                "Generate Comic KFX",
                "All KFX files have been generated successfully.",
                show=True,
            )
