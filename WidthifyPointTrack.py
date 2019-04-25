import arcpy
from math import atan2, pi
import sys

# overwrite outputs
arcpy.env.overwriteOutput = True

# input dataset
source_points = arcpy.GetParameterAsText(0)  # source dataset

# input parameters
case_field = arcpy.GetParameterAsText(1)  # parameter to control breaking lines
sort_field = arcpy.GetParameterAsText(2)  # parameter to control sorting vertices
primary_p = arcpy.GetParameterAsText(3)  # parameter used to stretch the geometry width
secondary_p = arcpy.GetParameterAsText(4)  # secondary variable that we'll carry over for symbology
min_width = arcpy.GetParameterAsText(5)  # minimum width of a polygon that should be created
max_width = arcpy.GetParameterAsText(6)  # maximum width of a polygon that should be created
cap_type = arcpy.GetParameterAsText(7)  # select the end cap type
break_dict = {}  # containing to hold break values

# output parameters
output_polygons = arcpy.GetParameterAsText(8)  # output location FGDB


format_dict = {'String': 'Text', 'Integer': 'Long', 'OID': 'Short', 'Double': 'Double', 'Date': 'Date', 'SmallInteger': 'Short'}


def msg(message):
    arcpy.AddMessage(message)
    print(message)


def width_buffer(attribute_value, actual_values, min_bound, max_bound):
    # scale incoming attribute values to fit within defined buffer range
    # this converts the attribute value to a buffer distance within defined range
    width = round(((float(max_bound) - float(min_bound))*(attribute_value - min(actual_values))/(max(actual_values)-min(actual_values))) + float(min_bound), 0)/2
    return width


def find_angle(x1, x2, y1, y2):
    dx = x2 - x1
    dy = y2 - y1
    found_angle = atan2(dx, dy) * 180 / pi
    return found_angle


# gather details pertaining to the primary attribute variable
msg('Understanding the primary attribute parameter...')
value_list = []
with arcpy.da.SearchCursor(in_table=source_points, field_names=primary_p) as parameter_cursor:
    msg('...scanning attribute values...')
    for row in parameter_cursor:
        value_list.append(row[0])
msg('Scan complete.\n\n')

# assign min/max values
min_attribute = min(value_list)
max_attribute = max(value_list)
msg('Minimum and maximum values assigned: min({0}), max({1})'.format(min_attribute, max_attribute))
range_attribute = max_attribute - min_attribute
msg('Range identified: {0}'.format(range_attribute))


# create the output feature class
# find and assign the workspace
workspace_index = output_polygons.rfind('\\')
workspace = output_polygons[:workspace_index]
output_name = output_polygons[workspace_index + 1:]
# set spatial reference to match the input
sr = arcpy.Describe(source_points).spatialReference
msg('Creating "{0}" feature class to store outputs'.format(output_name))
msg('...output spatial reference: {0}'.format(sr))
arcpy.CreateFeatureclass_management(out_path=workspace,
                                        out_name=output_name,
                                        geometry_type="POLYGON",
                                        spatial_reference=sr)

# add schema
msg('...adding required fields...')
# get case and sort fields
fields = arcpy.ListFields(source_points)
case_sort_dict = {}
for field in fields:
    if field.name == case_field:
        case_sort_dict['case_type'] = format_dict[field.type]
    elif field.name == sort_field:
        case_sort_dict['sort_type'] = format_dict[field.type]
    else:
        pass
# create fields
arcpy.AddFields_management(in_table=output_polygons, field_description=[
    ['POINT_FID', 'SHORT'],
    ['CASE_FIELD', case_sort_dict['case_type']],
    ['SORT_FIELD', case_sort_dict['sort_type']],
    ['PRIMARY_VALUE_FROM', 'DOUBLE'],
    ['PRIMARY_VALUE_TO', 'DOUBLE'],
    ['PRIMARY_CLASSED_FROM', 'SHORT'],
    ['PRIMARY_CLASSED_TO', 'SHORT'],
    ['SECONDARY_VALUE_FROM', 'DOUBLE'],
    ['SECONDARY_VALUE_TO', 'DOUBLE'],
    ['POLYGON_ANGLE', 'DOUBLE']
    ])
msg('Output feature class created.')

# open search cursor on input points to gather geometry
index = 0
feature_dict = {}
with arcpy.da.SearchCursor(in_table=source_points, field_names=['OBJECTID', case_field, sort_field,
                                                                primary_p,
                                                                secondary_p,
                                                                'SHAPE@X',
                                                                'SHAPE@Y'],
                           sql_clause=(None,'ORDER BY {0}, {1}'.format(case_field,sort_field))) as s_cursor:
    for row in s_cursor:
        feature_dict[index] = [row[0], row[1], row[2], row[3], row[4], row[5], row[6]]
        index +=1

msg('Input point features consumed.')

# use attributes collected and construct new features from the dictionary
# msg('LAST ITEM: {0}'.format(list(feature_dict.keys())[-1]))
with arcpy.da.InsertCursor(in_table=output_polygons, field_names=[
    'POINT_FID',
    'CASE_FIELD',
    'SORT_FIELD',
    'PRIMARY_VALUE_FROM',
    'PRIMARY_VALUE_TO',
    'PRIMARY_CLASSED_FROM',
    'PRIMARY_CLASSED_TO',
    'SECONDARY_VALUE_FROM',
    'SECONDARY_VALUE_TO',
    'POLYGON_ANGLE',
    'SHAPE@'
]) as i_cursor:
    record = 0
    # iterate through the values in the feature_dictionary and construct new geometry for each set of points
    for key, value in feature_dict.items():
        current_case = feature_dict[key][1]
        msg('Processing {0} of {1} points with case {2}...'.format(key, list(feature_dict.keys())[-1], current_case))
        if key == list(feature_dict.keys())[-1] - 1:
            # process as the point that terminates a line and the dataset
            msg('process as a line and dataset terminator')
            if cap_type == "TAPER":
                # define reference points for taper
                cx = float(feature_dict[key][5])
                cy = float(feature_dict[key][6])

                px = float(feature_dict[key - 1][5])
                py = float(feature_dict[key - 1][6])

                nx = float(feature_dict[key + 1][5])
                ny = float(feature_dict[key + 1][6])

                # find the angle between the initial point and the proceeding point
                angle = find_angle(px, nx, py, ny)

                # calculate the offset for the proceeding point
                offset1 = width_buffer(feature_dict[key][3], value_list, min_width, max_width)
                offset2 = width_buffer(feature_dict[key][3], value_list, min_width, max_width)

                # create a point geometry object based on the first point
                current_point = arcpy.PointGeometry(
                    arcpy.Point(nx, ny), sr)  # reconstruct geometry of selected point
                new_point1 = current_point  # commit the coordinates of the first point as a point object variable
                del current_point

                # construct a pair of points based on the second last point and the calculated offset
                next_point = arcpy.PointGeometry(
                    arcpy.Point(cx, cy), sr)  # reconstruct geometry of the proceeding point
                new_point3 = next_point.pointFromAngleAndDistance(angle + 90, offset1, "GEODESIC")
                new_point2 = next_point.pointFromAngleAndDistance(angle - 90, offset1, "GEODESIC")
                del next_point

                # create a set of polygon coordinates from the 3 coordinate pairs
                new_pointList = [new_point1, new_point2, new_point3]
                coordinates = []

            else:
                # define reference points for butt cap
                cx = float(feature_dict[key][5])
                cy = float(feature_dict[key][6])

                px = float(feature_dict[key - 1][5])
                py = float(feature_dict[key - 1][6])

                nx = float(feature_dict[key + 1][5])
                ny = float(feature_dict[key + 1][6])

                # find the angle between the initial point and the proceeding point
                angle = find_angle(px, nx, py, ny)

                # generate an offset distance using the width_factor of the point
                offset1 = width_buffer(feature_dict[key][3], value_list, min_width, max_width)
                offset2 = width_buffer(feature_dict[key - 1][3], value_list, min_width, max_width)

                # create new points based on the current points
                current_point = arcpy.PointGeometry(
                    arcpy.Point(cx, cy), sr)  # reconstruct geometry of selected point
                new_point1 = current_point.pointFromAngleAndDistance(angle + 90, offset1, "GEODESIC")
                new_point2 = current_point.pointFromAngleAndDistance(angle - 90, offset1, "GEODESIC")
                del current_point

                next_point = arcpy.PointGeometry(
                    arcpy.Point(nx, ny), sr)  # reconstruct geometry of the proceeding point
                new_point4 = next_point.pointFromAngleAndDistance(angle + 90, offset2, "GEODESIC")
                new_point3 = next_point.pointFromAngleAndDistance(angle - 90, offset2, "GEODESIC")
                del next_point

                # create new polygon coordinates
                new_pointList = [new_point1, new_point2, new_point3, new_point4]
                coordinates = []

            # insert new polygon using generated coordinates
            for pnt in new_pointList:
                coord_parts = pnt.getPart(0)
                coords = (coord_parts.X, coord_parts.Y)
                coordinates.append(coords)

            try:
                # attempt to insert a polygon into the new feature class
                # msg('Attempting insert')
                data = [feature_dict[key][0], feature_dict[key][1], feature_dict[key][2], feature_dict[key][3],
                        feature_dict[key + 1][3], offset1, offset2, feature_dict[key][4],
                        feature_dict[key + 1][4], find_angle(px, nx, py, ny), coordinates]
                i_cursor.insertRow(data)

            except:
                e = sys.exc_info()[1]
                msg('Insert failed: {0}'.format(e.args[0]))

        elif key == list(feature_dict.keys())[-1]:
            # process as the final point and skip it
            msg('process as final point, therefore skip')

        else:
            next_case = feature_dict[key + 1][1]
            # last_case = feature_dict[key - 1][1]
            msg('current case: {0} - next case: {1}'.format(current_case, next_case))
            if record == 0:
                # process new first point
                msg('processing new first point...')
                if cap_type == "TAPER":
                    msg(key)
                    # define reference points for taper
                    cx = float(feature_dict[key][5])
                    cy = float(feature_dict[key][6])

                    nx = float(feature_dict[key + 1][5])
                    ny = float(feature_dict[key + 1][6])

                    nx2 = float(feature_dict[key + 2][5])
                    ny2 = float(feature_dict[key + 2][6])

                    # find the angle between the initial point and the proceeding point
                    angle = find_angle(cx, nx2, cy, ny2)

                    # calculate the offset for the proceeding point
                    offset1 = width_buffer(feature_dict[key + 1][3], value_list, min_width, max_width)
                    offset2 = width_buffer(feature_dict[key][3], value_list, min_width, max_width)

                    # create a point geometry object based on the first point
                    current_point = arcpy.PointGeometry(
                        arcpy.Point(cx, cy), sr)  # reconstruct geometry of selected point
                    new_point1 = current_point  # commit the coordinates of the first point as a point object variable
                    del current_point

                    # construct a pair of points based on the second point and the calculated offset
                    next_point = arcpy.PointGeometry(
                        arcpy.Point(nx, ny), sr)  # reconstruct geometry of the proceeding point
                    new_point3 = next_point.pointFromAngleAndDistance(angle + 90, offset1, "GEODESIC")
                    new_point2 = next_point.pointFromAngleAndDistance(angle - 90, offset1, "GEODESIC")
                    del next_point

                    # create a set of polygon coordinates from the 3 coordinate pairs
                    new_pointList = [new_point1, new_point2, new_point3]
                    coordinates = []

                else:
                    # define reference points for butt cap
                    cx = float(feature_dict[key][5])
                    cy = float(feature_dict[key][6])

                    nx = float(feature_dict[key + 1][5])
                    ny = float(feature_dict[key + 1][6])

                    nx2 = float(feature_dict[key + 2][5])
                    ny2 = float(feature_dict[key + 2][6])

                    # find the angle between the initial point and the proceeding point
                    angle = find_angle(cx, nx2, cy, ny2)

                    # generate an offset distance using the width_factor of the point
                    offset1 = width_buffer(feature_dict[key][3], value_list, min_width, max_width)
                    offset2 = width_buffer(feature_dict[key + 1][3], value_list, min_width, max_width)


                    # create new points based on the current points
                    current_point = arcpy.PointGeometry(
                        arcpy.Point(cx, cy), sr)  # reconstruct geometry of selected point
                    new_point1 = current_point.pointFromAngleAndDistance(angle + 90, offset1, "GEODESIC")
                    new_point2 = current_point.pointFromAngleAndDistance(angle - 90, offset1, "GEODESIC")
                    del current_point

                    next_point = arcpy.PointGeometry(
                        arcpy.Point(nx, ny), sr)  # reconstruct geometry of the proceeding point
                    new_point4 = next_point.pointFromAngleAndDistance(angle + 90, offset2, "GEODESIC")
                    new_point3 = next_point.pointFromAngleAndDistance(angle - 90, offset2, "GEODESIC")
                    del next_point

                    # create new polygon coordinates
                    new_pointList = [new_point1, new_point2, new_point3, new_point4]
                    coordinates = []

                # insert new polygon using generated coordinates
                for pnt in new_pointList:
                    coord_parts = pnt.getPart(0)
                    coords = (coord_parts.X, coord_parts.Y)
                    coordinates.append(coords)

                try:
                    # attempt to insert a polygon into the new feature class
                    # msg('Attempting insert')
                    data = [feature_dict[key][0], feature_dict[key][1], feature_dict[key][2], feature_dict[key][3],
                            feature_dict[key + 1][3], offset2, offset1, feature_dict[key][4],
                            feature_dict[key + 1][4], find_angle(cx, nx, cy, ny), coordinates]
                    i_cursor.insertRow(data)

                except:
                    e = sys.exc_info()[1]
                    msg('Insert failed: {0}'.format(e.args[0]))

                # increment the record counter
                record += 1

            elif record > 0 and current_case == next_case and current_case == feature_dict[key + 2][1]:
                # process continuation point
                msg('processing continuation point...')

                cx = float(feature_dict[key][5])
                cy = float(feature_dict[key][6])

                px = float(feature_dict[key - 1][5])
                py = float(feature_dict[key - 1][6])

                nx1 = float(feature_dict[key + 1][5])
                ny1 = float(feature_dict[key + 1][6])

                nx = float(feature_dict[key + 2][5])
                ny = float(feature_dict[key + 2][6])

                # find the angle between preceding point and the proceeding point
                angle1 = find_angle(px, nx1, py, ny1)

                # find the angle between the proceeding point and the point proceeding that one
                angle2 = find_angle(cx, nx, cy, ny)

                # generate an offset distance using the width_factor and the primary attribute value of the point
                offset1 = width_buffer(feature_dict[key][3], value_list, min_width, max_width)
                offset2 = width_buffer(feature_dict[key + 1][3], value_list, min_width, max_width)

                # report width factor and break value
                # create new points based on the current point
                current_point = arcpy.PointGeometry(
                    arcpy.Point(cx, cy), sr)  # reconstruct geometry of selected point
                new_point1 = current_point.pointFromAngleAndDistance(angle1 + 90, offset1, "GEODESIC")
                new_point2 = current_point.pointFromAngleAndDistance(angle1 - 90, offset1, "GEODESIC")
                del current_point

                next_point = arcpy.PointGeometry(
                    arcpy.Point(nx1, ny1), sr)  # reconstruct geometry of the proceeding point
                new_point4 = next_point.pointFromAngleAndDistance(angle2 + 90, offset2, "GEODESIC")
                new_point3 = next_point.pointFromAngleAndDistance(angle2 - 90, offset2, "GEODESIC")
                del next_point

                # create new polygon
                new_pointList = [new_point1, new_point2, new_point3, new_point4]
                coordinates = []
                for pnt in new_pointList:
                    coord_parts = pnt.getPart(0)
                    coords = (coord_parts.X, coord_parts.Y)
                    coordinates.append(coords)

                try:
                    # attempt to insert a polygon into the new feature class
                    # msg('Attempting insert')
                    data = [feature_dict[key][0], feature_dict[key][1], feature_dict[key][2], feature_dict[key][3],
                            feature_dict[key + 1][3], offset1, offset2, feature_dict[key][4],
                            feature_dict[key + 1][4], find_angle(cx, nx1, cy, ny1), coordinates]
                    i_cursor.insertRow(data)

                except:
                    e = sys.exc_info()[1]
                    msg('Insert failed: {0}'.format(e.args[0]))
                # increment the record counter
                record += 1

            elif record > 0 and current_case != next_case:
                # process as a line termination point
                msg('processing termination point...')
                if cap_type == "TAPER":
                    # define reference points for taper
                    cx = float(feature_dict[key][5])
                    cy = float(feature_dict[key][6])

                    px = float(feature_dict[key - 1][5])
                    py = float(feature_dict[key - 1][6])

                    px2 = float(feature_dict[key - 2][5])
                    py2 = float(feature_dict[key - 2][6])

                    # find the angle between the initial point and the proceeding point
                    angle = find_angle(px2, cx, py2, cy)

                    # calculate the offset for the proceeding point

                    offset1 = width_buffer(feature_dict[key - 1][3], value_list, min_width, max_width)
                    offset2 = width_buffer(feature_dict[key][3], value_list, min_width, max_width)

                    # create a point geometry object based on the first point
                    current_point = arcpy.PointGeometry(
                        arcpy.Point(cx, cy), sr)  # reconstruct geometry of selected point
                    new_point1 = current_point  # commit the coordinates of the first point as a point object variable
                    del current_point

                    # construct a pair of points based on the second last point and the calculated offset
                    next_point = arcpy.PointGeometry(
                        arcpy.Point(px, py), sr)  # reconstruct geometry of the proceeding point
                    new_point3 = next_point.pointFromAngleAndDistance(angle + 90, offset1, "GEODESIC")
                    new_point2 = next_point.pointFromAngleAndDistance(angle - 90, offset1, "GEODESIC")
                    del next_point

                    # create a set of polygon coordinates from the 3 coordinate pairs
                    new_pointList = [new_point1, new_point2, new_point3]
                    coordinates = []

                else:
                    # define reference points for butt cap
                    cx = float(feature_dict[key][5])
                    cy = float(feature_dict[key][6])

                    px = float(feature_dict[key - 1][5])
                    py = float(feature_dict[key - 1][6])

                    px2 = float(feature_dict[key - 2][5])
                    py2 = float(feature_dict[key - 2][6])

                    c_x1 = float(feature_dict[key][5])
                    c_x2 = float(feature_dict[key + 1][5])
                    c_y1 = float(feature_dict[key][6])
                    c_y2 = float(feature_dict[key + 1][6])

                    # find the angle between the initial point and the proceeding point
                    angle1 = find_angle(px2, cx, py2, cy)
                    angle2 = find_angle(px, cx, py, cy)

                    # generate an offset distance using the width_factor of the point
                    offset1 = width_buffer(feature_dict[key][3], value_list, min_width, max_width)
                    offset2 = width_buffer(feature_dict[key - 1][3], value_list, min_width, max_width)

                    # create new points based on the current points
                    current_point = arcpy.PointGeometry(
                        arcpy.Point(cx, cy), sr)  # reconstruct geometry of selected point
                    new_point1 = current_point.pointFromAngleAndDistance(angle2 + 90, offset1, "GEODESIC")
                    new_point2 = current_point.pointFromAngleAndDistance(angle2 - 90, offset1, "GEODESIC")
                    del current_point

                    next_point = arcpy.PointGeometry(
                        arcpy.Point(px, py), sr)  # reconstruct geometry of the proceeding point
                    new_point4 = next_point.pointFromAngleAndDistance(angle1 + 90, offset2, "GEODESIC")
                    new_point3 = next_point.pointFromAngleAndDistance(angle1 - 90, offset2, "GEODESIC")
                    del next_point

                    # create new polygon coordinates
                    new_pointList = [new_point1, new_point2, new_point3, new_point4]
                    coordinates = []

                # insert new polygon using generated coordinates
                for pnt in new_pointList:
                    coord_parts = pnt.getPart(0)
                    coords = (coord_parts.X, coord_parts.Y)
                    coordinates.append(coords)

                try:
                    # attempt to insert a polygon into the new feature class
                    # msg('Attempting insert')
                    data = [feature_dict[key][0], feature_dict[key][1], feature_dict[key][2], feature_dict[key - 1][3],
                            feature_dict[key][3], offset1, offset2, feature_dict[key - 1][4],
                            feature_dict[key][4], find_angle(cx, nx, cy, ny), coordinates]
                    i_cursor.insertRow(data)

                except:
                    e = sys.exc_info()[1]
                    msg('Insert failed: {0}'.format(e.args[0]))

                # increment the record counter
                record = 0




