"""
This is the CLI interface for Paper2GIS, it is used to generate new layouts and extract markup from them. 

@author jonnyhuck

Example usage:
    Convert a map to a Paper2GIS layout:
        `python p2g.py generate -a -2462672.600 -b 9330748.585 -c -2393838.600 -d 9421934.585`
        `python p2g.py generate -a -393872.67 -b 7414244.26 -c -340247.96 -d 7476887.78 -o talla-hart-fells-shade.png -t True -z 11 -s True`

    Extract Markup from an image of a Paper2GIS layout:
        `python p2g.py extract --reference out.png --target ./data/IMG_9441.jpg -o ./out/path.tif --threshold 100 --kernel 0`
"""

# import argparser
from argparse import ArgumentParser

# set up argument parser
parser = ArgumentParser("Paper2GIS")
subparsers = parser.add_subparsers(help='either generate (to make a Paper2GIS layout) or extract (to retrieve markup from a photograph of a used Paper2GIS layout)', dest='command')

# create subparsers
g2p_parser = subparsers.add_parser("generate")
p2g_parser = subparsers.add_parser("extract")


''' SET UP ARGS FOR GENERATE '''

# properties of the map
g2p_parser.add_argument('-a','--bl_x', help='bottom left x coord', required = True)
g2p_parser.add_argument('-b','--bl_y', help='bottom left y coord', required = True)
g2p_parser.add_argument('-c','--tr_x', help='top right x coord', required = True)
g2p_parser.add_argument('-d','--tr_y', help='top right y coord', required = True)
g2p_parser.add_argument('-e','--epsg', help='EPSG code for the map CRS', required=False, default='3857')
g2p_parser.add_argument('-r','--resolution', type=int, help='Resolution of the input map image (dpi)', required=False, default='96')

# path to the map input (this or tiles=True is required)
g2p_parser.add_argument('-i','--input', help='the input map image (file path) - this is ignored if --tiles=True', required=False, default='map.png')

# path to the output file
g2p_parser.add_argument('-o','--output', help='the output data file (file path)', required=False, default='out.png')

# create a map image (this or input file path is required)
g2p_parser.add_argument('-t','--tiles', choices=['True', 'False'], help='create a OSM map (ignores --input)', required=False, default='False')
g2p_parser.add_argument('-f','--fade', type=int, help='intensity of the white filter over the tiles (0-255)', required=False, default=85)
g2p_parser.add_argument('-z','--zoom', type=int, help='requested zoom level of OSM tiles (necessary if using tiles)', required=False, default=0)
g2p_parser.add_argument('-s','--hillshade', choices=['True', 'False'], help='add hillshade to generated OSM map', required=False, default='False')
g2p_parser.add_argument('-sa','--hillshadealpha', type=float, help='the alpha value for the hillshade layer', required=False, default=0.25)


''' SET UP ARGS FOR EXTRACT '''

# for the extraction process
p2g_parser.add_argument('-r','--reference', help='the reference image', required = True)
p2g_parser.add_argument('-t','--target', help='the target image', required = True)
p2g_parser.add_argument('-o','--output', help='the name of the output file', required = False, default='out.shp')
p2g_parser.add_argument('-l','--lowe_distance', type=float, help='the lowe distance threshold', required = False, default=0.5)
p2g_parser.add_argument('-k','--kernel', type=int, help='the size of the kernel used for opening the image', required = False, default=3)
p2g_parser.add_argument('-i','--threshold', type=int, help='the threshold the target image', required = False, default=100)
p2g_parser.add_argument('-m','--homo_matches', type=int, help='the number of matches required for homography', required = False, default=12)

# TODO: Needs implementing
# TODO: perhaps also make this happen automatically if not enough matches are found? Need to experiment...
p2g_parser.add_argument('-f','--frame', type=int, help='a frame to add round the image if the map is too close to the edge', required = False, default=0)

# for vector data cleaning
p2g_parser.add_argument('-a','--min_area', type=float, help='the area below which features will be rejected', required = False, default = 1000)
p2g_parser.add_argument('-x','--min_ratio', type=float, help='the ratio (long/short) below which features will be rejected', required = False, default = 0.2)
p2g_parser.add_argument('-b','--buffer', type=float, help='buffer around the edge used for data cleaning', required = False, default = 10)

# for vector output - do you want a convex hull or not?
p2g_parser.add_argument('-cc','--convex_hull', choices=['True', 'False'], help='store convex hulls of extracted shapes?', required = False, default = 'False')
p2g_parser.add_argument('-cx','--centroid', choices=['True', 'False'], help='store centroids of extracted shapes?', required = False, default = 'False')
p2g_parser.add_argument('-cr','--representative point', choices=['True', 'False'], help='store representative points of extracted shapes?', required = False, default = 'False')
p2g_parser.add_argument('-cb','--boundary', choices=['True', 'False'], help='extract polygons from boundaries (rather than shaded areas)', required = False, default = 'False')

# runtime settings
p2g_parser.add_argument('-d','--demo', choices=['True', 'False'], help='the output data file', required = False, default = 'False')


''' PARSE ARGS AND RUN '''

# parse arguments
args = parser.parse_args()

# generate the layout and save to the specified file
if args.command == "generate":
    from paper2gis.gis2paper import run_generate
    run_generate(args.bl_x, args.bl_y, args.tr_x, args.tr_y, args.epsg, 
        args.resolution, args.input, args.output, args.tiles == 'True', 
        args.fade, args.zoom, args.hillshade=='True', args.hillshadealpha==0.25)

# extract markup from a photograph of a map and store the result in the specified file
elif args.command == "extract":
    from paper2gis.paper2gis import run_extract
    run_extract(args.reference, args.target, args.output, args.lowe_distance,
        args.threshold, args.kernel, args.homo_matches, args.min_area,
        args.min_ratio, args.buffer, args.convex_hull=='True', 
        args.representative_point=='True', args.centroid=='True', 
        args.boundary=='True', args.demo=='True')