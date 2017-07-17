__author__ = "Timofey Samsonov, Lomonosov MSU Faculty of Geography"
__copyright__ = "Copyright 2017"
__license__ = "GPL"
__version__ = "1.0.0"
__email__ = "tsamsonov@geogr.msu.ru"
__status__ = "Production"

import arcpy
from arcpy.sa import *

class Toolbox(object):
    def __init__(self):

        self.label = "Spatial Zoning Tools"
        self.alias = ""

        # List of tool classes associated with this toolbox
        self.tools = [EucAllocationZoning]


class EucAllocationZoning(object):

    def __init__(self):

        self.label = "Euclidian Allocation Zoning"
        self.description = ""
        self.canRunInBackground = True

    def getParameterInfo(self):

        in_features = arcpy.Parameter(
            displayName="Input Features",
            name="in_features",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input")

        in_regions = arcpy.Parameter(
            displayName="Input Clipping Regions (Optional)",
            name="in_regions",
            datatype="GPFeatureLayer",
            parameterType="Optional",
            direction="Input")

        in_resolution = arcpy.Parameter(
            displayName="Spatial Resolution",
            name="in_resolution",
            datatype="GPDouble",
            parameterType="Required",
            direction="Output")
        in_resolution.value = 2

        out_zones = arcpy.Parameter(
            displayName="Output Allocation Zones",
            name="out_zones",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Output")

        params = [in_features, in_regions, in_resolution, out_zones]
        return params

    def isLicensed(self):
        try:
            if arcpy.CheckExtension("Spatial") != "Available":
                raise Exception
        except Exception:
            return False  # tool cannot be executed

        return True  # tool can be executed

    def updateParameters(self, parameters):

        return

    def updateMessages(self, parameters):

        return

    def allocateZones(self, features, regions, resolution, output, workspace):

        arcpy.env.cellSize = resolution
        fieldMappings = arcpy.FieldMappings()

        # Check if the input feature layer has selections
        featuresCopy = features
        desc = arcpy.Describe(features)
        if len(desc.FIDSet) > 0:
            # Copy input features, so that feature selections can be handled correctly
            arcpy.AddMessage("Making a copy of the selected input features...")
            featuresCopy = workspace + "/features"
            arcpy.CopyFeatures_management(features, featuresCopy)

        featlayer = "featlayer"
        arcpy.MakeFeatureLayer_management(featuresCopy, featlayer)


        # Create temporary feature class to which the results will pe appended
        outzones = arcpy.CreateFeatureclass_management(workspace,
                                                       "tempzones",
                                                       "POLYGON",
                                                       "",
                                                       "DISABLED",
                                                       "DISABLED",
                                                       arcpy.Describe(features).spatialReference)

        arcpy.AddField_management(outzones, 'INPUTID', 'LONG')

        if regions:

            # Check, whether the input regions are geometrically correct
            arcpy.RepairGeometry_management(regions)

            arcpy.AddField_management(outzones, 'REGID', 'LONG')
            fieldMappings.addTable(outzones)

            M = int(arcpy.GetCount_management(regions).getOutput(0))

            rows = arcpy.da.SearchCursor(regions, ['SHAPE@', 'OID@'])

            i = 1

            arcpy.SetProgressor("step", "Euclidian Allocation Zoning...", 0, M, 1)

            arcpy.AddMessage("---")

            for row in rows:

                # Set current extent to clipping region
                arcpy.env.extent = row[0].extent

                arcpy.AddMessage("PROCESSING REGION " + str(i) + " FROM " + str(M))

                arcpy.SelectLayerByLocation_management(featlayer, 'intersect', row[0], '', 'new_selection')

                N = int(arcpy.GetCount_management(featlayer).getOutput(0))

                arcpy.AddMessage("Selected " + str(N) + " features")

                if N > 0:

                    # Create raster allocation zones
                    arcpy.AddMessage("Allocation...")
                    outExpand = EucAllocation(featlayer, "", "", "", "OBJECTID")

                    # Vectorize the output
                    rawoutput = workspace + "/raw"
                    arcpy.AddMessage("Converting to polygons...")
                    arcpy.RasterToPolygon_conversion(outExpand, rawoutput, "SIMPLIFY", "Value")

                    # Sometimes vector to raster conversion results in self-intersections, so
                    arcpy.RepairGeometry_management(rawoutput)

                    # Clip polygons
                    arcpy.AddMessage("Clipping polygons...")
                    clippedrawoutput = workspace + "/rawclip"
                    arcpy.Clip_analysis(rawoutput, row[0], clippedrawoutput, "")

                    # Append to the result
                    arcpy.AddMessage("Appending to result...")

                    fldMap = arcpy.FieldMap()
                    fldMap.addInputField(clippedrawoutput, "gridcode")
                    valueField = fldMap.outputField
                    valueField.name, valueField.aliasName, valueField.type = "INPUTID", "INPUTID", "LONG"
                    fldMap.outputField = valueField
                    fieldMappings.addFieldMap(fldMap)

                    # Set current extent to the whole dataset
                    arcpy.env.extent = "MAXOF"

                    arcpy.AddField_management(clippedrawoutput, 'REGID', 'LONG')
                    arcpy.CalculateField_management(clippedrawoutput, 'REGID', row[1])

                    arcpy.Append_management(clippedrawoutput, outzones, "NO_TEST", fieldMappings)

                    # Delete temporary files
                    arcpy.Delete_management(outExpand)
                    arcpy.Delete_management(rawoutput)
                    arcpy.Delete_management(clippedrawoutput)

                else:
                    arcpy.AddMessage("Nothing to add")

                arcpy.SelectLayerByAttribute_management(featlayer, 'CLEAR_SELECTION')

                i += 1
                arcpy.AddMessage("---")
                arcpy.SetProgressorPosition()

            arcpy.ResetProgressor()

            # Write Output
            arcpy.AddMessage("Writing output...")

            # Set current extent to the whole dataset
            arcpy.env.extent = "MAXOF"
            arcpy.CopyFeatures_management(outzones, output)
            arcpy.Delete_management(outzones)

        else:

            N = int(arcpy.GetCount_management(featlayer).getOutput(0))
            arcpy.AddMessage("Selected " + str(N) + " features")

            if N > 0:

                # Create raster allocation zones
                arcpy.AddMessage("Allocation...")
                outExpand = EucAllocation(featlayer, "", "", "", "OBJECTID")

                # Vectorize the output
                rawoutput = workspace + "/raw"
                arcpy.AddMessage("Converting to polygons...")
                arcpy.RasterToPolygon_conversion(outExpand, rawoutput, "SIMPLIFY", "VALUE")

                # Sometimes vector to raster conversion results in self-intersections, so
                arcpy.RepairGeometry_management(rawoutput)

                # Append to the result
                arcpy.AddMessage("Appending to result...")
                arcpy.env.extent = "MAXOF"

                fldMap = arcpy.FieldMap()
                fldMap.addInputField(rawoutput, "gridcode")
                valueField = fldMap.outputField
                valueField.name, valueField.aliasName, valueField.type = "INPUTID", "INPUTID", "LONG"
                fldMap.outputField = valueField
                fieldMappings.addFieldMap(fldMap)
                arcpy.Append_management(rawoutput, outzones, "NO_TEST", fieldMappings)

                # Write Output
                arcpy.AddMessage("Writing output...")
                arcpy.CopyFeatures_management(outzones, output)

                # Delete temporary files
                arcpy.Delete_management(outExpand)
                arcpy.Delete_management(rawoutput)
                arcpy.Delete_management(outzones)
            else:
                arcpy.AddMessage("Empty output")

    def execute(self, parameters, messages):

        features = parameters[0].valueAsText
        regions = parameters[1].valueAsText
        resolution = float(parameters[2].valueAsText)
        output = parameters[3].valueAsText
        workspace = "in_memory"

        # Boiler plate for separating the path and feature class name
        # lexems = output.split('\\')
        # k = len(lexems)
        # outname = lexems[-1]
        # outspace = '\\'.join(lexems[0:k - 2])

        self.allocateZones(features, regions, resolution, output, workspace)