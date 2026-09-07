"""QGIS entry point for Mine Water & Infrastructure Resilience."""


def classFactory(iface):
    from .plugin import FullyHydroPreparationPlugin

    return FullyHydroPreparationPlugin(iface)
