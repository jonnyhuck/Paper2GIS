"""
Generate maps for use with the Paper2GIS system

@author jonnyhuck
"""

# python mapgen.py -a -253416.76422779588028789 -b 7076444.70266312919557095 -c -244881.40985959535464644 -d 7080278.71288163959980011 -e 27700 -f out.png

import mapnik, qrcode, argparse, uuid
from scalebar import addScaleBar
from math import ceil
from PIL import Image, ImageOps, ImageDraw, ImageFont


def mm2px(mm, dpi=96):
	"""
	1 inch = 25.4mm 96dpi is therefore...
	"""
	return int(ceil(mm * dpi / 25.4))


'''
qgis get bounds (convenient for testing)
print iface.mapCanvas().extent().asWktCoordinates()
-253416.76422779588028789 7076444.70266312919557095, -244881.40985959535464644 7080278.71288163959980011
'''

# parse user arguments
parser = argparse.ArgumentParser(description='Perform viewshed calculations')
parser.add_argument('-a','--bl_x', help='bottom left x coord', required = True)
parser.add_argument('-b','--bl_y', help='bottom left y coord', required = True)
parser.add_argument('-c','--tr_x', help='top right x coord', required = True)
parser.add_argument('-d','--tr_y', help='top right y coord', required = True)
parser.add_argument('-e','--epsg', help='EPSG code for the map CRS', required = True)
parser.add_argument('-f','--file', help='the output data file', required = True)
args = parser.parse_args()

# extract values from arguments (all as strings)
blX = args.bl_x
blY = args.bl_y
trX = args.tr_x
trY = args.tr_y
epsg = args.epsg
filepath = args.file

'''
The version parameter is an integer from 1 to 40 that controls the size of the QR Code (the smallest, version 1, is a 21x21 matrix). Set to None and use the fit parameter when making the code to determine this automatically.
The error_correction parameter controls the error correction used for the QR Code. The following four constants are made available on the qrcode package:
	ERROR_CORRECT_L
		About 7% or less errors can be corrected.
	ERROR_CORRECT_M (default)
		About 15% or less errors can be corrected.
	ERROR_CORRECT_Q
		About 25% or less errors can be corrected.
	ERROR_CORRECT_H.
		About 30% or less errors can be corrected.
The box_size parameter controls how many pixels each box of the QR code is.
The border parameter controls how many boxes thick the border should be (the default is 4, which is the minimum according to the specs).
'''

# init qrcode object
qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_L,
    box_size=10,
    border=4,
)

# add data to qr object, 'make' and export to image
qr.add_data(''.join(["[", blX, ",", blY, ",", trX, ",", trY, ",", epsg, "]"]))
qr.make(fit=True)
qrcode = qr.make_image()

'''
To get OSM Bright...
https://tilemill-project.github.io/tilemill/docs/guides/osm-bright-mac-quickstart/
cp ~/Documents/MapBox/projects/OSMBright > ./
cd OSMBright
carto project.mml > style.xml
change line 407 to:
        "file": "/Users/jonnyhuck/Dropbox/Manchester/Research/Paper2GIS/map_gen/mapbox-osm-bright-f1c8780/shp/10m-populated-places-simple/10m-populated-places-simple.shp", 

...then if you want the Blossom version...
https://github.com/stekhn/blossom
carto OSMBright/project.mml > OSMBright/style.xml
'''

# Page dimensions in mm
w_mm = 297
h_mm = 210

# make the map using mapnik stylesheet
stylesheet = 'OSMBright/style.xml'
# stylesheet = 'OSMBright-Blossom/style.xml'
image = 'map.png'
m = mapnik.Map(mm2px(w_mm-10), mm2px(160))
mapnik.load_map(m, stylesheet)
m.zoom_to_box(mapnik.Box2d(float(blX), float(blY), float(trX), float(trY)))
mapnik.render_to_file(m, image)
map = ImageOps.expand(Image.open('map.png'), border=2, fill='black')

# paste map and QR onto a page
page = Image.new('RGB', (mm2px(w_mm), mm2px(h_mm)), 'white')

# put the map and the qrcode on the page
page.paste(map, (mm2px(5), mm2px(5)))
page.paste(qrcode.resize((mm2px(32), mm2px(32))), (mm2px(5), mm2px(170)))

# add some circles for dempster-shafer - get drawing context for page
draw = ImageDraw.Draw(page)

# working backwards, 5mm from edge of page
x = 5

# circle diameter
ed = 20

# 5 iterations
for i in xrange(5):
	
	# draw circles 5mm apart for each iteration
	draw.ellipse([mm2px(w_mm-x-ed), mm2px(170), mm2px(w_mm-x), mm2px(170+ed)], fill='white', outline='black')
	x += ed + 5

# get unique number hex (truncate to 8 characters)
uid = uuid.uuid4().hex[:8]

# get the dimensions of the text
tw, th = draw.textsize(uid)

# prepare a font
font = ImageFont.truetype('./open-sans/OpenSans-Regular.ttf', 12)

# add uid text
pw, ph = page.size

draw.text((pw/2, ph-mm2px(10)), uid, fill='black', font=font)

# add a scalebar to the bottom left of the map
addScaleBar(m, page, False)

# save the result
page.save(filepath, 'PNG')

# show the result
page.show()