"""
Generate maps for use with the Paper2GIS system

All sizes in pixels unless otehrwise stated with _mm in variable name

@author jonnyhuck
"""

# python mapgen.py -a -253416.7 -b 7076444.7 -c -244881.4 -d 7080278.7 -e 3857 -f out.png

import mapnik, qrcode, argparse, uuid
from datetime import datetime
from PIL import Image, ImageOps, ImageDraw, ImageFont
from math import floor, log10, ceil

def mm2px(mm, dpi=96):
	"""
	1 inch = 25.4mm 96dpi is therefore...
	"""
	return int(ceil(mm * dpi / 25.4))


def getScaleBar(m):
	"""
	* Construct a quick and dirty scalebar, at a sensible width of approx 20% the width of the map
	* Returned as a PIL Image object
	*
	* Parameters:
	*  - m: 		mapnik Map object 
	"""

	# get the m per pixel on the map
	mPerPx = m.scale()

	# how many metres is 20% of the width of the map?
	twentyPc = m.width * 0.2 * mPerPx

	# get the order of magnitude
	oom = 10 ** floor(log10(twentyPc))

	# get the desired width of the scalebar in m
	mScaleBar = round(twentyPc / oom) * oom

	# get the desired width of the scalebar in px
	pxScaleBar = round(mScaleBar/mPerPx)

	# make some text for the scalebar (sort units)
	if oom >= 1000:
		scaleText = str(int(mScaleBar/1000)) + "km"
	else:
		scaleText = str(int(mScaleBar)) + "m"
		
	# set scale bar positioning parameters
	lBuffer    = mm2px(2)	# distance from the line to the end of the box
	tickHeight = mm2px(3)	# height of the tick marks
	
	# new image for scalebar
	scalebarImg = Image.new('RGB', (int(pxScaleBar+lBuffer+lBuffer), lBuffer+lBuffer+tickHeight), 'white')
	
	# get PIL context to draw on
	sb_draw = ImageDraw.Draw(scalebarImg)

	# prepare a font
	font = ImageFont.truetype('./open-sans/OpenSans-Regular.ttf', 12)
	
	# get the dimensions of the text
	tw, th = sb_draw.textsize(scaleText, font=font)
	
	sbw, sbh = scalebarImg.size
		
	# add background
	sb_draw.rectangle([
		(1, 1), (sbw-1, sbh-1)], 
		outline=('black'), fill=('white'))

	# add lines
	sb_draw.line([
		(lBuffer, sbh-tickHeight-lBuffer), 
		(lBuffer, sbh-lBuffer),
		(lBuffer+pxScaleBar, sbh-lBuffer), 
		(lBuffer+pxScaleBar, sbh-tickHeight-lBuffer)], 
		fill='black', width=1)
 
	# add label
	sb_draw.text(
		((sbw-tw)/2, sbh-tickHeight-lBuffer-mm2px(1.5)), 
		scaleText, fill='black', font=font)
	
	return scalebarImg


'''
qgis get bounds (convenient for testing)
print iface.mapCanvas().extent().asWktCoordinates()
-253416.76422779588028789 7076444.70266312919557095, -244881.40985959535464644 7080278.71288163959980011
'''

# parse user arguments
parser = argparse.ArgumentParser(description='Paper2GIS Map Generator')
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

# get unique number hex (truncate to 8 characters)
uid = uuid.uuid4().hex[:8]

print ','.join([blX, blY, trX, trY, epsg, uid])

# add data to qr object, 'make' and export to image
qr.add_data(','.join([blX, blY, trX, trY, epsg, uid]))
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

''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
'''''''''''''''''''''''''''''''''''''SETTINGS'''''''''''''''''''''''''''''''''''''''''''''
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

## TODO: these could be incorporated into the args to allow different page sizes etc...

# page dimensions in mm
w_mm = 297
h_mm = 210

# the gap between the map and the qr code etc
map_buffer = mm2px(3)

#  page dimensions in px
page_w = mm2px(w_mm)
page_h = mm2px(h_mm)

# resolution
dpi = 96

# buffer around page in mm
page_buffer = mm2px(5)

# qr code size
qr_size = mm2px(32)

# the height of the map
map_height = mm2px(163)

# circle diameter
ed = mm2px(18)

# gap between circles
eg = mm2px(2)

stylesheet = 'OSMBright/style.xml'
# stylesheet = 'OSMBright-Blossom/style.xml'

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
'''''''''''''''''''''''''''''''''''''END SETTINGS'''''''''''''''''''''''''''''''''''''''''
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

# make new blank, page sized image
page = Image.new('RGB', (page_w, page_h), 'white')

# make the map using mapnik stylesheet, add border and add to the page
image = 'map.png'
m = mapnik.Map(page_w - page_buffer*2, map_height)
mapnik.load_map(m, stylesheet)
m.zoom_to_box(mapnik.Box2d(float(blX), float(blY), float(trX), float(trY)))
mapnik.render_to_file(m, image)
map = ImageOps.expand(Image.open('map.png'), border=2, fill='black')
page.paste(map, (page_buffer, page_buffer))

# add qr code to the map
page.paste(qrcode.resize((qr_size, qr_size)), (page_buffer, map_height+map_buffer+page_buffer))

# open the north arrow and add to the page
north = Image.open('north.png').resize((qr_size-page_buffer, qr_size-page_buffer))
page.paste(north, (page_buffer + qr_size + page_buffer, map_height+map_buffer+page_buffer/2+page_buffer))

# add a scalebar to the page
scalebar = getScaleBar(m)
page.paste(scalebar, (page_buffer*3 + qr_size + north.size[0], map_height+map_buffer+page_buffer/2+page_buffer))

# add some circles for dempster-shafer - get drawing context for page
draw = ImageDraw.Draw(page)

# working backwards, 5mm from edge of page
x = page_buffer

# 5 iterations
for i in xrange(5):
	
	# draw circles 5mm apart for each iteration
	draw.ellipse([page_w-x-ed, page_buffer+map_height+map_buffer+page_buffer/2, page_w-x, page_buffer+map_height+map_buffer+page_buffer/2+ed], fill='white', outline='black')
	x += ed + eg

# these are the values needed to crop out the dempster-shafer bit...
print page_w-x, map_height+page_buffer

# prepare a font
font = ImageFont.truetype('./open-sans/OpenSans-Regular.ttf', 12)

# get the dimensions of the text and page
tw, th = draw.textsize(uid, font=font)

# add attribution text
year = str(datetime.today().year)
attributionText = "".join(["Paper2GIS Copyright ", year, " Dr Jonny Huck: https://github.com/jonnyhuck/paper2gis. Map data Copyright ", year, " OpenStreetMap Contributors"])
draw.text((page_buffer, page_h-mm2px(3)-th), attributionText, fill='black', font=font)

# add uuid text
# draw.text((page_w - tw - page_buffer, map_height+mm2px(1.5) + th), uid, fill='black', font=font)
draw.text((page_buffer*3 + qr_size + north.size[0] + (scalebar.size[0]/2) - tw/2, map_height+map_buffer+mm2px(1.5)+(page_buffer/2)+scalebar.size[1]+page_buffer), uid, fill='black', font=font)

# save the result
page.save(filepath, 'PNG')

# show the result
page.show()