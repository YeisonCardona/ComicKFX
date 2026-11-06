from calibre.customize import InterfaceActionBase


class GenerateComicKFXPlugin(InterfaceActionBase):

    name = "Generate Comic KFX"
    description = "Generate optimized KFX books for comics"
    supported_platforms = ["windows", "osx", "linux"]
    author = "Dunderlab"
    version = (1, 0, 0)
    minimum_calibre_version = (5, 0, 0)

    actual_plugin = "calibre_plugins.generate_comic_kfx.ui:GenerateComicKFX"
