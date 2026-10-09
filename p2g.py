"""
This is the CLI interface for Paper2GIS, it is used to generate new layouts and extract markup from them. 

@author jonnyhuck

Example usage:
    Convert a map to a Paper2GIS layout:
        `python p2g.py generate -a -2462672.600 -b 9330748.585 -c -2393838.600 -d 9421934.585`
        `python p2g.py generate -a 3817338.035 -b -1302039.557 -c 3818772.077 -d -1300139.848 -o nkhata-bay.png -t -z 17 -v`

    Extract Markup from an image of a Paper2GIS layout:
        `python p2g.py extract --reference out.png --target ./data/IMG_9441.jpg -o ./out/path.tif --threshold 100 --kernel 0`
        `python p2g.py extract --reference out.png --target ./data/IMG_9441.jpg -o ./out/path.tif --threshold 100 --kernel 0 --verbose`
"""

# import argparser
from argparse import ArgumentParser
from warnings import catch_warnings, simplefilter as warn_filter

# ignore warnings
with catch_warnings():
    warn_filter("ignore")

    # set up argument parser
    parser = ArgumentParser("Paper2GIS")
    subparsers = parser.add_subparsers(help="either: 'generate' to make a Paper2GIS layout; 'extract' to retrieve markup from a photograph of a used Paper2GIS layout; or 'test' to test that a new installation is functioning", dest='command')

    # create subparsers
    g2p_parser = subparsers.add_parser("generate")
    p2g_parser = subparsers.add_parser("extract")
    test_parser = subparsers.add_parser("test")


    ''' SET UP ARGS FOR GENERATE '''

    # properties of the map
    g2p_parser.add_argument('-a','--bl_x', help='bottom left x coord', required = True)
    g2p_parser.add_argument('-b','--bl_y', help='bottom left y coord', required = True)
    g2p_parser.add_argument('-c','--tr_x', help='top right x coord', required = True)
    g2p_parser.add_argument('-d','--tr_y', help='top right y coord', required = True)
    g2p_parser.add_argument('-e','--epsg', help='EPSG code for the map CRS', required=False, default='3857')
    g2p_parser.add_argument('-r','--resolution', type=int, help='Resolution of the input map image (dpi)', required=False, default='96')

    # path to the map input (this or tiles=True is required)
    g2p_parser.add_argument('-i','--input', help='the input map image (file path) - this is ignored if --tiles is used', required=False, default='map.png')

    # path to the output file
    g2p_parser.add_argument('-o','--output', help='the output data file (file path)', required=False, default='out.png')
    
    # descriptive text to add to the layout
    g2p_parser.add_argument('-n','--description', help='Descriptive text that will be printed on the map', required=False, default='')

    # create a map image (this or input file path is required)
    g2p_parser.add_argument('-t','--tiles', nargs='?', const='osm', choices=['osm', 'esri', 'google'], help="create a map from tiles: 'osm' (OpenStreetMap, the default if no value is given), 'esri' (ESRI satellite imagery) or 'google' (Google satellite imagery) - ignores --input", required=False, default=None)
    g2p_parser.add_argument('-f','--fade', type=int, help='intensity of the white filter over the tiles (0-255)', required=False, default=85)
    g2p_parser.add_argument('-z','--zoom', type=int, help='requested zoom level of the tiles (necessary if using tiles)', required=False, default=0)
    g2p_parser.add_argument('-hs','--hillshade', action='store_true', help='add hillshade to generated OSM map', required=False, default=False)
    g2p_parser.add_argument('-sa','--hillshadealpha', type=float, help='the alpha value for the hillshade layer', required=False, default=0.25)
    
    # boundary dataset
    g2p_parser.add_argument('-bf','--boundaryfile', help='a shapefile containing boundary data', required=False, default=None)
    g2p_parser.add_argument('-bw','--boundarywidth', type=int, help='the width (in pixels) of the boundary line', required=False, default=8)
    g2p_parser.add_argument('-bc','--boundarycolour', help='the colour of the boundary line', required=False, default='blue')
    g2p_parser.add_argument('-ba','--boundaryalpha', type=float, help='the alpha (opacity) of the boundary line', required=False, default=0.1)

    # border style
    g2p_parser.add_argument('-ls','--landscape', action='store_true', help='make an A3 landscape layout (default is A3 portrait)', required=False, default=False)
    g2p_parser.add_argument('-nm','--no_markers', action='store_true', help='use the old random noise border instead of ArUco markers (gives a slightly larger map)', required=False, default=False)

    # verbose mode
    g2p_parser.add_argument('-v','--verbose', action='store_true', help='enable verbose output', required=False, default=False)


    ''' SET UP ARGS FOR EXTRACT '''

    # for the extraction process
    p2g_parser.add_argument('-r','--reference', help='the reference image', required = True)
    p2g_parser.add_argument('-t','--target', help='the target image', required = True)
    p2g_parser.add_argument('-o','--output', help='the name of the output file', required = False, default='out.shp')
    p2g_parser.add_argument('-l','--lowe_distance', type=float, help='the lowe distance threshold', required = False, default=0.5)
    p2g_parser.add_argument('-k','--kernel', type=int, help='the size of the kernel used for opening the image', required = False, default=3)
    p2g_parser.add_argument('-i','--threshold', type=int, help='the threshold the target image', required = False, default=100)
    p2g_parser.add_argument('-m','--homo_matches', type=int, help='the number of matches required for homography', required = False, default=12)

    # for locating the map in the photograph (registration)
    p2g_parser.add_argument('-g','--magsac', action='store_true', help='use MAGSAC rather than RANSAC to calculate the homography (more tolerant of bad matches)', required = False, default = False)
    p2g_parser.add_argument('-ds','--downscale', type=float, help='shrink the photo to this multiple of the reference size for SIFT matching (0 to disable)', required = False, default = 1.5)
    p2g_parser.add_argument('-mf','--max_features', type=int, help='the maximum number of SIFT keypoints to use in each image (0 for no limit)', required = False, default = 10000)

    # add user id to the output shapefile
    p2g_parser.add_argument('-u','--uid', type=int, help='user ID number to add the the output shapefile', required = False)

    # TODO: perhaps also make this happen automatically if not enough matches are found? Need to experiment...
    p2g_parser.add_argument('-f','--frame', type=float, help='a frame to add round the image if the map is too close to the edge', required = False, default=0)

    # for vector data cleaning
    p2g_parser.add_argument('-a','--min_area', type=float, help='the area below which features will be rejected', required = False, default = 1000)
    p2g_parser.add_argument('-x','--min_ratio', type=float, help='the ratio (long/short) below which features will be rejected', required = False, default = 0.2)
    p2g_parser.add_argument('-b','--buffer', type=float, help='buffer around the edge used for data cleaning', required = False, default = 10)

    # for vector output - do you want a convex hull or not?
    p2g_parser.add_argument('-cc','--convex_hull', action='store_true', help='store convex hulls of extracted shapes?', required = False, default = False)
    p2g_parser.add_argument('-cx','--centroid', action='store_true', help='store centroids of extracted shapes?', required = False, default = False)
    p2g_parser.add_argument('-cr','--representative_point', action='store_true', help='store representative points of extracted shapes?', required = False, default = False)
    p2g_parser.add_argument('-ce','--exterior', action='store_true', help='extract polygons from boundaries by extracting the outer ring', required = False, default = False)
    p2g_parser.add_argument('-ci','--interior', action='store_true', help='extract polygons from boundaries by extracting the inner rings', required = False, default = False)

    # runtime settings
    p2g_parser.add_argument('-d','--demo', action='store_true', help='write the intermediate images to ./demo', required = False, default = False)
    
    # verbose mode
    p2g_parser.add_argument('-v','--verbose', action='store_true', help='enable verbose output', required=False, default=False)


    ''' PARSE ARGS AND RUN '''

    # parse arguments
    args = parser.parse_args()

    # generate the layout and save to the specified file
    if args.command == "generate":
        from paper2gis.gis2paper import run_generate
        run_generate(args.bl_x, args.bl_y, args.tr_x, args.tr_y, epsg=args.epsg,
            dpi=args.resolution, in_path=args.input, out_path=args.output, descriptive_text=args.description,
            tiles=args.tiles, fade=args.fade, zoom=args.zoom,
            hillshade=args.hillshade, hillshade_alpha=args.hillshadealpha,
            boundary_file=args.boundaryfile, boundary_width=args.boundarywidth,
            boundary_colour=args.boundarycolour, boundary_alpha=args.boundaryalpha,
            verbose=args.verbose, markers=not args.no_markers, landscape=args.landscape)

    # extract markup from a photograph of a map and store the result in the specified file
    elif args.command == "extract":
        from paper2gis.paper2gis import run_extract
        run_extract(args.reference, args.target, args.output, lowe_distance=args.lowe_distance,
            thresh=args.threshold, kernel=args.kernel, homo_matches=args.homo_matches, frame=args.frame,
            min_area=args.min_area, min_ratio=args.min_ratio, buffer=args.buffer, uid=args.uid,
            convex_hull=args.convex_hull, centroid=args.centroid, representative_point=args.representative_point,
            exterior=args.exterior, interior=args.interior, demo=args.demo, verbose=args.verbose,
            magsac=args.magsac, downscale=args.downscale, max_features=args.max_features)

    # run on test dataset, compare result to baseline and report
    elif args.command == "test":
        from PIL import Image, ImageChops
        from numpy import array, count_nonzero
        from paper2gis.paper2gis import run_extract
        from paper2gis.gis2paper import run_generate

        print("\nRunning test image generation...")
        run_generate(-393872.67, 7414244.26, -340247.96, 7476887.78, epsg='3857', dpi=96,
            out_path='test/reference.png', tiles=True, fade=85, zoom=11)
        diff = array(ImageChops.difference(Image.open('test/reference.png'), Image.open('test/testgen.png')))
        print(f"Generation works!\nThe result is {count_nonzero(diff) / diff.size * 100:.2f}% different to the reference version (up to ~15% is expected).")

        print("\nRunning test image extraction...")
        run_extract('test/reference.png', 'test/target.jpg', 'test/test_out.tif')
        diff = array(ImageChops.difference(Image.open('test/out.tif'), Image.open('test/test_out.tif')))
        print(f"Extraction works!\nThe result is {count_nonzero(diff) / diff.size * 100:.2f}% different to the reference version (0% is expected).\n")