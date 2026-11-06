from calibre.customize import InterfaceActionBase


class ComicKFXPlugin(InterfaceActionBase):

    name = "Comic KFX"
    description = "Generate optimized KFX books for comics"
    supported_platforms = ["windows", "osx", "linux"]
    author = "Dunderlab"
    version = (1, 0, 0)
    minimum_calibre_version = (5, 0, 0)

    actual_plugin = "calibre_plugins.comic_kfx.ui:ComicKFX"
