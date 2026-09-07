"""One-run mine water and infrastructure resilience screening for QGIS."""

from __future__ import annotations

import json
from pathlib import Path

from qgis import processing
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingOutputFile, QgsProcessingOutputFolder, QgsProcessingOutputVectorLayer,
    QgsProcessingParameterBoolean, QgsProcessingParameterCrs,
    QgsProcessingParameterEnum, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFile, QgsProcessingParameterNumber,
    QgsProcessingParameterRasterLayer, QgsProcessingParameterString,
    QgsProject, QgsRasterLayer, QgsVectorLayer, QgsUnitTypes,
)

from ..core import utc_now, write_json
from ..mining_core import write_engineering_report, write_methodology


class MineResilienceAlgorithm(QgsProcessingAlgorithm):
    OUTPUT_PARENT = "OUTPUT_PARENT"
    PROJECT_NAME = "PROJECT_NAME"
    BOUNDARY = "BOUNDARY"
    SOURCE_MODE = "SOURCE_MODE"
    TARGET_CRS = "TARGET_CRS"
    DEM = "DEM"
    DEM_Z_UNITS = "DEM_Z_UNITS"
    ROADS = "ROADS"
    RAILROADS = "RAILROADS"
    STREAMS = "STREAMS"
    LAND_COVER = "LAND_COVER"
    SOILS = "SOILS"
    FLOOD_100 = "FLOOD_100"
    FLOOD_500 = "FLOOD_500"
    FACILITIES = "FACILITIES"
    RECEPTORS = "RECEPTORS"
    MONITORING = "MONITORING"
    DRAINAGE_ACRES = "DRAINAGE_ACRES"
    MIN_SLOPE = "MIN_SLOPE"
    RAINFALL_MM = "RAINFALL_MM"
    RUNOFF_COEFF = "RUNOFF_COEFF"
    CRITICALITY = "CRITICALITY"
    HAZARD_WEIGHT = "HAZARD_WEIGHT"
    TERRAIN_WEIGHT = "TERRAIN_WEIGHT"
    CRITICALITY_WEIGHT = "CRITICALITY_WEIGHT"
    STREAM_BUFFER_M = "STREAM_BUFFER_M"
    ADD_TO_MAP = "ADD_TO_MAP"
    OUTPUT_FOLDER = "OUTPUT_FOLDER"
    OUTPUT_CROSSINGS = "OUTPUT_CROSSINGS"
    OUTPUT_CATCHMENTS = "OUTPUT_CATCHMENTS"
    OUTPUT_EXPOSED_FACILITIES = "OUTPUT_EXPOSED_FACILITIES"
    OUTPUT_REPORT = "OUTPUT_REPORT"

    def name(self): return "mine_resilience_screening"
    def displayName(self): return "Mine Water & Infrastructure Resilience - Complete Screening"
    def group(self): return "00 - START HERE"
    def groupId(self): return "start_here"
    def createInstance(self): return MineResilienceAlgorithm()
    def flags(self): return super().flags() | QgsProcessingAlgorithm.FlagNoThreading

    def shortHelpString(self):
        return (
            "Runs a traceable, boundary-driven mine water and infrastructure screening. "
            "It fetches global public terrain/reference data when requested, derives drainage, "
            "ranks transport crossings, delineates screening catchments, evaluates facility "
            "exposure, and writes GIS/CSV/HTML/JSON deliverables. Mine facilities should be "
            "polygons (pit, TSF, waste dump, plant, pond). Results require engineering and field review."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(self.OUTPUT_PARENT, "Existing output parent folder", behavior=QgsProcessingParameterFile.Folder))
        self.addParameter(QgsProcessingParameterString(self.PROJECT_NAME, "Project/run name", defaultValue="Mine_Resilience_Screening"))
        self.addParameter(QgsProcessingParameterFeatureSource(self.BOUNDARY, "Mine study boundary polygon(s)", types=[QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterEnum(self.SOURCE_MODE, "Source policy", options=["Automatic global public sources, with manual overrides", "Manual/authoritative inputs only"], defaultValue=0))
        self.addParameter(QgsProcessingParameterCrs(self.TARGET_CRS, "Projected target CRS (blank = automatic local WGS 84 UTM)", optional=True))
        self.addParameter(QgsProcessingParameterRasterLayer(self.DEM, "Authoritative DEM override", optional=True))
        self.addParameter(QgsProcessingParameterEnum(self.DEM_Z_UNITS, "DEM elevation units", options=["Same as CRS", "Metres", "Feet"], defaultValue=0))
        self.addParameter(QgsProcessingParameterFeatureSource(self.ROADS, "Mine/public roads override", types=[QgsProcessing.TypeVectorLine], optional=True))
        self.addParameter(QgsProcessingParameterFeatureSource(self.RAILROADS, "Railways override", types=[QgsProcessing.TypeVectorLine], optional=True))
        self.addParameter(QgsProcessingParameterFeatureSource(self.STREAMS, "Authoritative streams override", types=[QgsProcessing.TypeVectorLine], optional=True))
        self.addParameter(QgsProcessingParameterRasterLayer(self.LAND_COVER, "Land-cover raster override", optional=True))
        self.addParameter(QgsProcessingParameterFeatureSource(self.SOILS, "Soils polygons override", types=[QgsProcessing.TypeVectorPolygon], optional=True))
        self.addParameter(QgsProcessingParameterFeatureSource(self.FLOOD_100, "100-year flood-hazard polygons", types=[QgsProcessing.TypeVectorPolygon], optional=True))
        self.addParameter(QgsProcessingParameterFeatureSource(self.FLOOD_500, "500-year flood-hazard polygons", types=[QgsProcessing.TypeVectorPolygon], optional=True))
        self.addParameter(QgsProcessingParameterFeatureSource(self.FACILITIES, "Mine facilities/areas (pit, TSF, dump, plant, ponds)", types=[QgsProcessing.TypeVectorPolygon], optional=True))
        self.addParameter(QgsProcessingParameterFeatureSource(self.RECEPTORS, "Critical receptors/assets (optional points)", types=[QgsProcessing.TypeVectorPoint], optional=True))
        self.addParameter(QgsProcessingParameterFeatureSource(self.MONITORING, "Monitoring locations (optional points)", types=[QgsProcessing.TypeVectorPoint], optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.DRAINAGE_ACRES, "Minimum drainage area for stream initiation (acres; REVIEW REQUIRED)", type=QgsProcessingParameterNumber.Double, defaultValue=25.0, minValue=0.01))
        self.addParameter(QgsProcessingParameterNumber(self.MIN_SLOPE, "Sink-fill minimum slope (degrees; REVIEW REQUIRED)", type=QgsProcessingParameterNumber.Double, defaultValue=0.1, minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(self.RAINFALL_MM, "Screening storm rainfall depth (mm; 0 disables volume estimate)", type=QgsProcessingParameterNumber.Double, defaultValue=0.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(self.RUNOFF_COEFF, "Screening runoff coefficient 0-1 (REVIEW REQUIRED)", type=QgsProcessingParameterNumber.Double, defaultValue=0.0, minValue=0.0, maxValue=1.0))
        self.addParameter(QgsProcessingParameterNumber(self.CRITICALITY, "Default transport asset criticality 1-5", type=QgsProcessingParameterNumber.Integer, defaultValue=3, minValue=1, maxValue=5))
        self.addParameter(QgsProcessingParameterNumber(self.HAZARD_WEIGHT, "Drainage hazard weight", type=QgsProcessingParameterNumber.Double, defaultValue=0.50, minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(self.TERRAIN_WEIGHT, "Terrain/slope weight", type=QgsProcessingParameterNumber.Double, defaultValue=0.20, minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(self.CRITICALITY_WEIGHT, "Asset criticality weight", type=QgsProcessingParameterNumber.Double, defaultValue=0.30, minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(self.STREAM_BUFFER_M, "Stream proximity screening buffer (metres; REVIEW REQUIRED)", type=QgsProcessingParameterNumber.Double, defaultValue=50.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterBoolean(self.ADD_TO_MAP, "Add engineering review layers and zoom to site", defaultValue=True))
        self.addOutput(QgsProcessingOutputFolder(self.OUTPUT_FOLDER, "Complete project folder"))
        self.addOutput(QgsProcessingOutputVectorLayer(self.OUTPUT_CROSSINGS, "Ranked transport/drainage crossings"))
        self.addOutput(QgsProcessingOutputVectorLayer(self.OUTPUT_CATCHMENTS, "Screening catchments"))
        self.addOutput(QgsProcessingOutputVectorLayer(self.OUTPUT_EXPOSED_FACILITIES, "Facilities near drainage"))
        self.addOutput(QgsProcessingOutputFile(self.OUTPUT_REPORT, "Engineering screening report"))

    def checkParameterValues(self, parameters, context):
        ok, message = super().checkParameterValues(parameters, context)
        if not ok: return ok, message
        weights = [self.parameterAsDouble(parameters, key, context) for key in (self.HAZARD_WEIGHT, self.TERRAIN_WEIGHT, self.CRITICALITY_WEIGHT)]
        if sum(weights) <= 0: return False, "At least one risk weight must be greater than zero."
        target = self.parameterAsCrs(parameters, self.TARGET_CRS, context)
        if target.isValid():
            units = QgsUnitTypes.toString(target.mapUnits()).lower()
            if "meter" not in units and "metre" not in units:
                return False, "Mine Resilience requires a projected CRS in metres; leave blank for automatic local UTM."
        if self.parameterAsEnum(parameters, self.SOURCE_MODE, context) == 1 and self.parameterAsRasterLayer(parameters, self.DEM, context) is None:
            return False, "Manual-only mode requires a DEM."
        return True, ""

    def _run(self, alg, params, context, feedback):
        if feedback.isCanceled(): raise QgsProcessingException("Processing canceled by user.")
        feedback.pushInfo(f"Running {alg}")
        return processing.run(alg, params, context=context, feedback=feedback, is_child_algorithm=True)

    @staticmethod
    def _gpkg(path, layer): return f"{path}|layername={layer}"

    def _field(self, source, name, formula, field_type, gpkg, context, feedback, length=0, precision=3):
        output = self._gpkg(gpkg, name)
        return self._run("native:fieldcalculator", {"INPUT": source, "FIELD_NAME": name.split("__")[-1], "FIELD_TYPE": field_type,
            "FIELD_LENGTH": length, "FIELD_PRECISION": precision, "FORMULA": formula, "OUTPUT": output}, context, feedback)["OUTPUT"]

    def processAlgorithm(self, p, context, feedback):
        feedback.pushInfo("Stage 1/6: running global hydrology and reference-data preparation.")
        base = self._run("mineresilience:fully_hydro_preparation", {
            "OUTPUT_PARENT": self.parameterAsFile(p, self.OUTPUT_PARENT, context),
            "PROJECT_NAME": self.parameterAsString(p, self.PROJECT_NAME, context),
            "BOUNDARY": p[self.BOUNDARY], "SOURCE_MODE": self.parameterAsEnum(p, self.SOURCE_MODE, context),
            "TARGET_CRS": p.get(self.TARGET_CRS), "DEM": p.get(self.DEM), "DEM_Z_UNITS": self.parameterAsEnum(p, self.DEM_Z_UNITS, context),
            "ROADS": p.get(self.ROADS), "RAILROADS": p.get(self.RAILROADS), "REFERENCE_STREAMS": p.get(self.STREAMS),
            "LAND_COVER": p.get(self.LAND_COVER), "SOILS": p.get(self.SOILS), "FEMA_100": p.get(self.FLOOD_100), "FEMA_500": p.get(self.FLOOD_500),
            "DRAINAGE_ACRES": self.parameterAsDouble(p, self.DRAINAGE_ACRES, context), "MIN_SLOPE": self.parameterAsDouble(p, self.MIN_SLOPE, context), "ADD_TO_MAP": False,
        }, context, feedback)
        root = Path(base["OUTPUT_FOLDER"])
        manifest_path = Path(base["OUTPUT_MANIFEST"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        outputs = manifest["outputs"]
        mine_dir = root / "03_Mine_Resilience"
        mine_dir.mkdir(parents=True, exist_ok=True)
        gpkg = mine_dir / "Mine_Resilience_Results.gpkg"
        csv_dir = mine_dir / "Tables"; csv_dir.mkdir(exist_ok=True)
        boundary = base["OUTPUT_BOUNDARY"]

        feedback.pushInfo("Stage 2/6: polygonizing hydrologic basins into screening catchments.")
        catchments = self._gpkg(gpkg, "screening_catchments")
        poly = self._run("gdal:polygonize", {"INPUT": outputs["basin"], "BAND": 1, "FIELD": "basin_id", "EIGHT_CONNECTEDNESS": False, "EXTRA": "", "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT}, context, feedback)["OUTPUT"]
        fixed = self._run("native:fixgeometries", {"INPUT": poly, "METHOD": 1, "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT}, context, feedback)["OUTPUT"]
        self._run("native:clip", {"INPUT": fixed, "OVERLAY": boundary, "OUTPUT": catchments}, context, feedback)
        rainfall = self.parameterAsDouble(p, self.RAINFALL_MM, context)
        coefficient = self.parameterAsDouble(p, self.RUNOFF_COEFF, context)
        catch_area = self._field(catchments, "catchments__area_ha", "$area/10000", 0, gpkg, context, feedback)
        catch_volume = self._field(catch_area, "catchments__screen_m3", f'"area_ha"*10000*{rainfall}/1000*{coefficient}', 0, gpkg, context, feedback)

        feedback.pushInfo("Stage 3/6: ranking transport/drainage crossings from contributing area, slope, and criticality.")
        crossings = outputs.get("potential_crossings")
        ranked = ""
        if crossings:
            sampled = self._run("native:rastersampling", {"INPUT": crossings, "RASTERCOPY": outputs["accumulation"], "COLUMN_PREFIX": "acc_", "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT}, context, feedback)["OUTPUT"]
            sampled = self._run("native:rastersampling", {"INPUT": sampled, "RASTERCOPY": outputs["slope_percent"], "COLUMN_PREFIX": "slope_", "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT}, context, feedback)["OUTPUT"]
            pixel_area = abs(float(manifest["pixel_width"]) * float(manifest["pixel_height"]))
            minimum_ha = self.parameterAsDouble(p, self.DRAINAGE_ACRES, context) * 0.40468564224
            step = self._field(sampled, "crossings__uparea_ha", f'abs(coalesce("acc_1",0))*{pixel_area}/10000', 0, gpkg, context, feedback)
            hazard_formula = f'CASE WHEN "uparea_ha">={minimum_ha*16} THEN 5 WHEN "uparea_ha">={minimum_ha*8} THEN 4 WHEN "uparea_ha">={minimum_ha*4} THEN 3 WHEN "uparea_ha">={minimum_ha*2} THEN 2 ELSE 1 END'
            step = self._field(step, "crossings__hazard_sc", hazard_formula, 1, gpkg, context, feedback, precision=0)
            step = self._field(step, "crossings__terrain_sc", 'CASE WHEN abs(coalesce("slope_1",0))>=20 THEN 5 WHEN abs(coalesce("slope_1",0))>=10 THEN 4 WHEN abs(coalesce("slope_1",0))>=5 THEN 3 WHEN abs(coalesce("slope_1",0))>=2 THEN 2 ELSE 1 END', 1, gpkg, context, feedback, precision=0)
            criticality = self.parameterAsInt(p, self.CRITICALITY, context)
            step_fields = {field.name().lower(): field.name() for field in QgsVectorLayer(step, "crossings", "ogr").fields()}
            source_criticality = step_fields.get("transport_criticality")
            criticality_formula = (
                f'clamp(1,5,coalesce("{source_criticality}",{criticality}))'
                if source_criticality else str(criticality)
            )
            step = self._field(step, "crossings__criticality", criticality_formula, 1, gpkg, context, feedback, precision=0)
            hw, tw, cw = [self.parameterAsDouble(p, key, context) for key in (self.HAZARD_WEIGHT, self.TERRAIN_WEIGHT, self.CRITICALITY_WEIGHT)]
            risk_formula = f'round(20*("hazard_sc"*{hw}+"terrain_sc"*{tw}+"criticality"*{cw})/{hw+tw+cw},2)'
            step = self._field(step, "crossings__risk_score", risk_formula, 0, gpkg, context, feedback)
            ranked = self._field(step, "ranked_crossings__risk_band", 'CASE WHEN "risk_score">=80 THEN \'CRITICAL\' WHEN "risk_score">=60 THEN \'HIGH\' WHEN "risk_score">=40 THEN \'MODERATE\' ELSE \'LOW\' END', 2, gpkg, context, feedback, length=12, precision=0)
            self._run("native:savefeatures", {"INPUT": ranked, "OUTPUT": str(csv_dir / "ranked_crossings.csv")}, context, feedback)

        feedback.pushInfo("Stage 4/6: evaluating facilities and drainage proximity.")
        exposed = ""
        facilities = self.parameterAsSource(p, self.FACILITIES, context)
        impacted_catchments = ""
        if facilities:
            fac_fix = self._run("native:fixgeometries", {"INPUT": p[self.FACILITIES], "METHOD": 1, "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT}, context, feedback)["OUTPUT"]
            fac_project = self._run("native:reprojectlayer", {"INPUT": fac_fix, "TARGET_CRS": QgsVectorLayer(boundary, "b", "ogr").crs(), "CONVERT_CURVED_GEOMETRIES": True, "OUTPUT": self._gpkg(gpkg, "mine_facilities")}, context, feedback)["OUTPUT"]
            stream_buffer = self._run("native:buffer", {"INPUT": outputs["derived_stream_lines"], "DISTANCE": self.parameterAsDouble(p, self.STREAM_BUFFER_M, context), "SEGMENTS": 8, "END_CAP_STYLE": 0, "JOIN_STYLE": 0, "MITER_LIMIT": 2, "DISSOLVE": True, "SEPARATE_DISJOINT": False, "OUTPUT": self._gpkg(gpkg, "stream_proximity_zone")}, context, feedback)["OUTPUT"]
            hazard_zones = [stream_buffer]
            hazard_zones.extend(outputs[key] for key in ("flood_hazard_100yr", "flood_hazard_500yr") if outputs.get(key))
            exposure_zone = stream_buffer
            if len(hazard_zones) > 1:
                exposure_zone = self._run("native:mergevectorlayers", {"LAYERS": hazard_zones, "CRS": QgsVectorLayer(boundary, "b", "ogr").crs(), "OUTPUT": self._gpkg(gpkg, "combined_water_exposure_zones")}, context, feedback)["OUTPUT"]
            exposed = self._run("native:extractbylocation", {"INPUT": fac_project, "PREDICATE": [0], "INTERSECT": exposure_zone, "OUTPUT": self._gpkg(gpkg, "facilities_in_water_exposure_zones")}, context, feedback)["OUTPUT"]
            impacted_catchments = self._run("native:extractbylocation", {"INPUT": catch_volume, "PREDICATE": [0], "INTERSECT": fac_project, "OUTPUT": self._gpkg(gpkg, "facility_intersecting_catchments")}, context, feedback)["OUTPUT"]

        feedback.pushInfo("Stage 5/6: preserving receptors/monitoring data and writing review tables.")
        for key, name in ((self.RECEPTORS, "critical_receptors"), (self.MONITORING, "monitoring_locations")):
            if self.parameterAsSource(p, key, context):
                self._run("native:reprojectlayer", {"INPUT": p[key], "TARGET_CRS": QgsVectorLayer(boundary, "b", "ogr").crs(), "CONVERT_CURVED_GEOMETRIES": True, "OUTPUT": self._gpkg(gpkg, name)}, context, feedback)
        self._run("native:savefeatures", {"INPUT": catch_volume, "OUTPUT": str(csv_dir / "catchment_screening.csv")}, context, feedback)

        feedback.pushInfo("Stage 6/6: writing auditable methodology, manifest, and engineering report.")
        methodology = {
            "product": "Mine Water & Infrastructure Resilience 1.0", "completed_utc": utc_now(),
            "status": "COMPLETE_WITH_ENGINEERING_REVIEW_REQUIRED", "rainfall_mm": rainfall,
            "runoff_coefficient": coefficient, "stream_buffer_m": self.parameterAsDouble(p, self.STREAM_BUFFER_M, context),
            "risk_weights": {"drainage_hazard": hw if crossings else self.parameterAsDouble(p, self.HAZARD_WEIGHT, context), "terrain": tw if crossings else self.parameterAsDouble(p, self.TERRAIN_WEIGHT, context), "asset_criticality": cw if crossings else self.parameterAsDouble(p, self.CRITICALITY_WEIGHT, context)},
            "risk_method": "Weighted 1-5 component scores scaled to 0-100. Bands: >=80 critical, >=60 high, >=40 moderate, else low.",
            "limitations": ["Screening only; no final culvert, channel, flood, TSF, geotechnical, dewatering, or hydraulic design.", "Automatic public data must be replaced or verified against authoritative survey and mine records.", "Rainfall/runoff inputs are user engineering assumptions and are not automatically selected design criteria.", "Facility exposure means geometric intersection with the stream buffer and any supplied flood-hazard polygons; it is not a computed flood inundation result."],
        }
        method_path = mine_dir / "ENGINEERING_METHODOLOGY.json"; write_methodology(method_path, methodology)
        report_path = mine_dir / "MINE_RESILIENCE_SCREENING_REPORT.html"
        summary = {"Project": self.parameterAsString(p, self.PROJECT_NAME, context), "Completed UTC": methodology["completed_utc"], "Target CRS": manifest["target_crs"], "Minimum drainage area (acres)": self.parameterAsDouble(p, self.DRAINAGE_ACRES, context), "Screening storm rainfall (mm)": rainfall, "Runoff coefficient": coefficient, "Ranked crossings": "Created" if ranked else "Not created - transport or stream lines unavailable", "Facility exposure": "Created" if exposed else "Not created - facilities not supplied", "Results GeoPackage": gpkg, "Base hydrology manifest": manifest_path}
        write_engineering_report(report_path, summary)
        final = {"product": methodology["product"], "status": methodology["status"], "project_root": str(root), "results": {"catchments": str(catch_volume), "impacted_catchments": str(impacted_catchments), "ranked_crossings": str(ranked), "facilities_near_drainage": str(exposed), "report": str(report_path), "methodology": str(method_path), "base_manifest": str(manifest_path)}}
        write_json(mine_dir / "MINE_RESILIENCE_MANIFEST.json", final)

        self._load = []
        if self.parameterAsBoolean(p, self.ADD_TO_MAP, context):
            self._load = [("vector", boundary, "Mine study boundary"), ("raster", outputs["hillshade"], "Terrain hillshade"), ("vector", outputs["derived_stream_lines"], "DEM-derived drainage"), ("vector", catch_volume, "Screening catchments")]
            if ranked: self._load.append(("vector", ranked, "Ranked transport crossings - REVIEW REQUIRED"))
            if exposed: self._load.append(("vector", exposed, "Facilities near drainage - REVIEW REQUIRED"))
            if impacted_catchments: self._load.append(("vector", impacted_catchments, "Facility-intersecting catchments"))
        return {self.OUTPUT_FOLDER: str(root), self.OUTPUT_CROSSINGS: ranked, self.OUTPUT_CATCHMENTS: catch_volume, self.OUTPUT_EXPOSED_FACILITIES: exposed, self.OUTPUT_REPORT: str(report_path)}

    def postProcessAlgorithm(self, context, feedback):
        project = QgsProject.instance()
        group = project.layerTreeRoot().findGroup("Mine Resilience - Engineering Review") or project.layerTreeRoot().addGroup("Mine Resilience - Engineering Review")
        boundary_layer = None
        for kind, source, name in getattr(self, "_load", []):
            layer = QgsRasterLayer(source, name) if kind == "raster" else QgsVectorLayer(source, name, "ogr")
            if layer.isValid():
                project.addMapLayer(layer, False); group.addLayer(layer)
                if name == "Mine study boundary": boundary_layer = layer
            else: feedback.pushWarning(f"Output could not be loaded: {source}")
        if boundary_layer:
            try:
                from qgis.utils import iface
                iface.mapCanvas().setExtent(boundary_layer.extent()); iface.mapCanvas().refresh()
            except Exception as exc: feedback.pushWarning(f"Layers loaded, but map zoom failed: {exc}")
        return {}
