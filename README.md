# Widthify-Points
This tool generates polygon features from a dataset of ordered points such as GPS track logs. The create polygons span the distance between a point and the proceeding point. In addition, these polygons are scaled in varying width based on a selected attribute value of the input points.The resulting geometry of the polygons visualizes the changes in the selected attribute value over the course of the track dataset.

# Parameters:
# Source_Points
The input dataset containing ordered data points. These could be GPS tracks or any other data provided it is order and has some attribute value that could be used to scale the polygon width. *At this point the input points must be sorted prior to the script consuming the dataset.

# Attribute_Parameter
The selected attribute to be used for visualization. This attribute will be used to scale the width of the polygons.

# Secondary_Parameter
The selected attribute to be used for visualization. This attribute will be used to scale the width of the polygons.

# Number_of_Breaks
The number of breaks determines how the primary attribute will be classified in the output. The tool will assess the existing range of values within the input data and create and equal interval class breaks based on the number of selected breaks. *Further development could potentially yield a greater range of classification options.

# Minimum_width
The minimum width sets the polygon width for the lowest data class. This will dictate the width of the most narrow polygon within the output. *I use the pointFromAngleAnDistance method on the Point Geometry to achieve the offset distance. I'm not sure what units the offset is performed in but from my experience it reverts to the unit of the spatial reference.

# Maximum_width
The maximum width sets the polygon width for the highest data class. This will dictate the width of the widest polygon within the output. *I use the pointFromAngleAnDistance method on the Point Geometry to achieve the offset distance. I'm not sure what units the offset is performed in but from my experience it reverts to the unit of the spatial reference.

# Output_polygons
The output polygon feature class.
