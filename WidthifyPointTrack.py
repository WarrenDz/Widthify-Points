# HEADER

import arcpy
from math import atan2, pi
import sys

# overwrite outputs
arcpy.env.overwriteOutput = True

# input dataset
source_points = arcpy.GetParameterAsText(0)  # source dataset with the attributes to symbolize

# input parameters
primary_p = arcpy.GetParameterAsText(1)  # parameter used to stretch the geometry width
secondary_p = arcpy.GetParameterAsText(2)  # secondary variable that we'll carry over for symbology
num_breaks = arcpy.GetParameterAsText(3)  # number of classes to break the primary variable into
min_width = arcpy.GetParameterAsText(4)  # minimum width of a polygon that should be created
max_width = arcpy.GetParameterAsText(5)  # maximum width of a polygon that should be created
break_dict = {}  # containing to hold break values

# output parameters
output_polygons = arcpy.GetParameterAsText(6)  # output location FGDB


# defined functions
def msg(message):
    arcpy.AddMessage(message)
    print(message)


def width_factor(attribute_value, dictionary):
    for k, v in dictionary.items():
        if attribute_value <= dictionary[k][0]:
            attribute = k
            break
        else:
            attribute = num_breaks
    msg('assigned: {0}'.format(attribute))
    return attribute


def find_angle(x1, x2, y1, y2):
    dx = x2 - x1
    dy = y2 - y1
    found_angle = atan2(dx, dy) * 180 / pi
    return found_angle

# WILL NEED TO WRITE PROPER DEFINITION FOR DETERMINING OFFSET


# GATHER DETAILS IN THE PRIMARY ATTRIBUTE VARIABLE
msg('Understanding the primary attribute parameter...')
value_list = []
with arcpy.da.SearchCursor(in_table=source_points, field_names=primary_p) as parameter_cursor:
    msg('Scanning attribute values...')
    for row in parameter_cursor:
        value_list.append(row[0])
msg('Scan complete.\n\n')

# assign min/max values
min_attribute = min(value_list)
max_attribute = max(value_list)
msg('Minimum and maximum values assigned: min({0}), max({1})'.format(min_attribute, max_attribute))
range_attribute = max_attribute - min_attribute
msg('Range identified: {0}'.format(range_attribute))
step = range_attribute/float(num_breaks)
msg('Range step identified: {0}\n'.format(step))

# assign polygon width values
width_range = float(max_width) - float(min_width)
width_step = width_range/float(num_breaks)
msg('Assigned width step: {0}'.format(width_step))

# create dictionary of break values [attribute, width]
for i in range(1, int(num_breaks)+1, 1):
    break_value = i * step + min_attribute
    width_value = i * width_step + float(min_width)
    break_dict[i] = [break_value, width_value]
    msg('Assigned dictionary break value {0}: {1}'.format(i, break_dict[i]))

# CREATE THE OUTPUT FEATURE CLASS
# find & assign the workspace
workspace_index = output_polygons.rfind('\\')
workspace = output_polygons[:workspace_index]
output_name = output_polygons[workspace_index + 1:]
# set spatial reference to match the input
sr = arcpy.Describe(source_points).spatialReference
msg('Output spatial reference: {0}'.format(sr))
msg('Creating "{0}" feature class to store outputs'.format(output_name))
arcpy.CreateFeatureclass_management(out_path=workspace,
                                        out_name=output_name,
                                        geometry_type="POLYGON",
                                        spatial_reference=sr)
# add schema
msg('Adding required fields...')
# need to have field type detection eventually
arcpy.AddFields_management(in_table=output_polygons, field_description=[
    ['POINT_FID', 'SHORT'],
    ['PRIMARY_VALUE_FROM', 'DOUBLE'],
    ['PRIMARY_VALUE_TO', 'DOUBLE'],
    ['PRIMARY_CLASSED_FROM', 'SHORT'],
    ['PRIMARY_CLASSED_TO', 'SHORT'],
    ['SECONDARY_VALUE_FROM', 'DOUBLE'],
    ['SECONDARY_VALUE_TO', 'DOUBLE'],
    ])
msg('Output feature class created.')

# open search cursor  on input points to gather geometry
index = 0
feature_dict = {}
with arcpy.da.SearchCursor(in_table=source_points, field_names=['OBJECTID',
                                                                primary_p,
                                                                secondary_p,
                                                                'SHAPE@X',
                                                                'SHAPE@Y']) as s_cursor:
    for row in s_cursor:
        feature_dict[index] = [row[0], row[1], row[2], row[3], row[4]]
        index +=1

msg('Input point features consumed.')

# use attributes collected and construct new features from the dictionary
msg('LAST ITEM: {0}'.format(list(feature_dict.keys())[-1]))
with arcpy.da.InsertCursor(in_table=output_polygons, field_names=[
    'POINT_FID',
    'PRIMARY_VALUE_FROM',
    'PRIMARY_VALUE_TO',
    'PRIMARY_CLASSED_FROM',
    'PRIMARY_CLASSED_TO',
    'SECONDARY_VALUE_FROM',
    'SECONDARY_VALUE_TO',
    'SHAPE@'
]) as i_cursor:
    for key, value in feature_dict.items():
        msg('KEY: {0}, INDEX: {1}'.format(key, index))
        if key == 0:
            msg('Processing as first point (triangle)')
            # find the angle between the initial point and the proceeding point
            angle = find_angle(float(feature_dict[key][3]), float(feature_dict[key+1][3]), float(feature_dict[key][4]), float(feature_dict[key+1][4]))
            msg('Initial angle: {0}'.format(angle))
            offset = width_factor(feature_dict[key+1][1], break_dict)
            bv = break_dict[offset][1]
            msg('offset: {0}'.format(offset))
            current_point = arcpy.PointGeometry(
                arcpy.Point(float(feature_dict[key][3]), float(feature_dict[key][4])),
                sr)  # reconstruct geometry of selected point
            new_point1 = current_point
            del current_point
            next_point = arcpy.PointGeometry(
                arcpy.Point(float(feature_dict[key + 1][3]), float(feature_dict[key + 1][4])),
                sr)  # reconstruct geometry of the proceeding point
            new_point3 = next_point.pointFromAngleAndDistance(angle + 90, bv / 2, "GEODESIC")
            new_point2 = next_point.pointFromAngleAndDistance(angle - 90, bv / 2, "GEODESIC")
            del next_point
            # create new polygon
            new_pointList = [new_point1, new_point2, new_point3]
            coordinates = []
            for pnt in new_pointList:
                coord_parts = pnt.getPart(0)
                coords = (coord_parts.X, coord_parts.Y)
                coordinates. append(coords)

            try:
                msg('Attempting insert')
                # 'OBJECTID', primary_param, secondary_param, 'SHAPE@X', 'SHAPE@Y'
                # 'LINE_FID', 'PRIMARY_VALUE', 'PRIMARY_CLASSED', 'SECONDARY_VALUE', 'SHAPE@'
                data = [feature_dict[key][0], feature_dict[key][1], feature_dict[key+1][1], width_factor(feature_dict[key][1], break_dict), width_factor(feature_dict[key+1][1], break_dict), feature_dict[key+1][2], feature_dict[key][2], coordinates]
                i_cursor.insertRow(data)
            except:
                e = sys.exc_info()[1]
                msg('Insert failed: {0}'.format(e.args[0]))

        elif index == int(key + 2):
            msg('Process as second last point (triangle)')
            # find the angle between the initial point and the proceeding point
            angle = find_angle(float(feature_dict[key-1][3]), float(feature_dict[key][3]), float(feature_dict[key-1][4]), float(feature_dict[key][4]))
            msg('Initial angle: {0}'.format(angle))
            offset = width_factor(feature_dict[key-1][1], break_dict)
            bv = break_dict[offset][1]
            msg('offset: {0}'.format(offset))
            current_point = arcpy.PointGeometry(
                arcpy.Point(float(feature_dict[key-1][3]), float(feature_dict[key-1][4])),
                sr)  # reconstruct geometry of selected point
            new_point1 = current_point.pointFromAngleAndDistance(angle + 90, bv / 2, "GEODESIC")
            new_point2 = current_point.pointFromAngleAndDistance(angle - 90, bv / 2, "GEODESIC")
            del current_point
            next_point = arcpy.PointGeometry(
                arcpy.Point(float(feature_dict[key][3]), float(feature_dict[key][4])),
                sr)  # reconstruct geometry of the proceeding point
            new_point3 = next_point
            del next_point
            # create new polygon
            new_pointList = [new_point1, new_point2, new_point3]
            coordinates = []
            for pnt in new_pointList:
                coord_parts = pnt.getPart(0)
                coords = (coord_parts.X, coord_parts.Y)
                coordinates. append(coords)

            try:
                msg('Attempting insert')
                # 'OBJECTID', primary_param, secondary_param, 'SHAPE@X', 'SHAPE@Y'
                # 'LINE_FID', 'PRIMARY_VALUE', 'PRIMARY_CLASSED', 'SECONDARY_VALUE', 'SHAPE@'
                data = [feature_dict[key][0], feature_dict[key][1], feature_dict[key+1][1], width_factor(feature_dict[key][1], break_dict), width_factor(feature_dict[key+1][1], break_dict), feature_dict[key+1][2], feature_dict[key][2], coordinates]
                i_cursor.insertRow(data)
            except:
                e = sys.exc_info()[1]
                msg('Insert failed: {0}'.format(e.args[0]))
        elif index == int(key + 1):
            msg('Process as last point, therefore skip')
            pass
        else:
            msg('Processing as normal point')
            # find the angle between preceding point and the proceeding point
            angle1 = find_angle(float(feature_dict[key-1][3]), float(feature_dict[key][3]), float(feature_dict[key-1][4]), float(feature_dict[key][4]))
            # find the angle between the proceeding point and the point proceeding that one
            angle2 = find_angle(float(feature_dict[key][3]), float(feature_dict[key+1][3]), float(feature_dict[key][4]), float(feature_dict[key+1][4]))
            msg('Initial angle: {0}, Closing angle: {1}'.format(angle1, angle2))
            # generate an offset distance using the width_factor function and the primary attribute value of the point
            offset1 = width_factor(feature_dict[key][1], break_dict)
            bv1 = break_dict[offset1][1]
            offset2 = width_factor(feature_dict[key+1][1], break_dict)
            bv2 = break_dict[offset2][1]

            # report width factor and break value
            msg('offsets: 1:{0}, 2:{1}'.format(offset1, offset2))
            # create new points based on the current point
            current_point = arcpy.PointGeometry(
                arcpy.Point(float(feature_dict[key][3]), float(feature_dict[key][4])),
                sr)  # reconstruct geometry of selected point
            new_point1 = current_point.pointFromAngleAndDistance(angle1 + 90, bv1/2, "GEODESIC")
            new_point2 = current_point.pointFromAngleAndDistance(angle1 - 90, bv1/2, "GEODESIC")
            del current_point
            next_point = arcpy.PointGeometry(
                arcpy.Point(float(feature_dict[key+1][3]), float(feature_dict[key+1][4])),
                sr)  # reconstruct geometry of the proceeding point
            new_point4 = next_point.pointFromAngleAndDistance(angle2 + 90, bv2/2, "GEODESIC")
            new_point3 = next_point.pointFromAngleAndDistance(angle2 - 90, bv2/2, "GEODESIC")
            del next_point
            # create new polygon
            new_pointList = [new_point1, new_point2, new_point3, new_point4]
            coordinates = []
            for pnt in new_pointList:
                coord_parts = pnt.getPart(0)
                coords = (coord_parts.X, coord_parts.Y)
                coordinates. append(coords)

            try:
                msg('Attempting insert')
                # 'OBJECTID', primary_param, secondary_param, 'SHAPE@X', 'SHAPE@Y'
                # 'LINE_FID', 'PRIMARY_VALUE', 'PRIMARY_CLASSED', 'SECONDARY_VALUE', 'SHAPE@'
                data = [feature_dict[key][0], feature_dict[key][1], feature_dict[key+1][1], width_factor(feature_dict[key][1], break_dict), width_factor(feature_dict[key+1][1], break_dict), feature_dict[key+1][2], feature_dict[key][2], coordinates]
                i_cursor.insertRow(data)
            except:
                e = sys.exc_info()[1]
                msg('Insert failed: {0}'.format(e.args[0]))


