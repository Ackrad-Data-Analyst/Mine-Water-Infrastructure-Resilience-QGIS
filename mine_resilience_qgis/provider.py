"""Processing provider registration."""

from qgis.core import QgsProcessingProvider

from .algorithms.fully_hydro import FullyHydroPreparationAlgorithm
from .algorithms.preflight import FullyHydroPreflightAlgorithm
from .algorithms.mine_resilience import MineResilienceAlgorithm


class FullyHydroProvider(QgsProcessingProvider):
    def loadAlgorithms(self):
        self.addAlgorithm(FullyHydroPreflightAlgorithm())
        self.addAlgorithm(FullyHydroPreparationAlgorithm())
        self.addAlgorithm(MineResilienceAlgorithm())

    def id(self):
        return "mineresilience"

    def name(self):
        return "Mine Water & Infrastructure Resilience"

    def longName(self):
        return self.name()
