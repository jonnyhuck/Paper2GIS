"""
Generate maps for use with the Paper2GIS system

All sizes in pixels unless otherwise stated with _mm in variable name

@author jonnyhuck

carto OSMBright/project.mml > OSMBright/style.xml && node test.js && python mapgen.py
"""

# python mapgen.py -a -253416.7 -b 7076444.7 -c -244881.4 -d 7080278.7 -e 3857 -f out.png

import qrcode, uuid
from datetime import datetime
from PIL import Image, ImageOps, ImageDraw, ImageFont
from math import floor, log10, ceil

def mm2px(mm, dpi=96):
	"""
	1 inch = 25.4mm 96dpi is therefore...
	"""
	return int(ceil(mm * dpi / 25.4))


# parse user arguments
# parser = argparse.ArgumentParser(description='Paper2GIS Map Generator')
# parser.add_argument('-a','--bl_x', help='bottom left x coord', required = True)
# parser.add_argument('-b','--bl_y', help='bottom left y coord', required = True)
# parser.add_argument('-c','--tr_x', help='top right x coord', required = True)
# parser.add_argument('-d','--tr_y', help='top right y coord', required = True)
# parser.add_argument('-e','--epsg', help='EPSG code for the map CRS', required = True)
# parser.add_argument('-f','--file', help='the output data file', required = True)
# args = parser.parse_args()

# extract values from arguments (all as strings)
# blX = args.bl_x
# blY = args.bl_y
# trX = args.tr_x
# trY = args.tr_y
# epsg = args.epsg
# filepath = args.file

blX = str(-844518.0759830498136580)
blY = str(7741060.5331264697015285)
trX = str(-820571.3187695243395865)
trY = str(7772566.3288495466113091)
epsg = str(3857)
filepath = "out.png"

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

print(','.join([blX, blY, trX, trY, epsg, uid]))

# add data to qr object, 'make' and export to image
qr.add_data(','.join([blX, blY, trX, trY, epsg, uid]))
qr.make(fit=True)
qrcode = qr.make_image()

# page dimensions in mm
w_mm = 297
h_mm = 420

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
map_height = 1436


'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
'''''''''''''''''''''''''''''''''''''END SETTINGS'''''''''''''''''''''''''''''''''''''''''
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

# make new blank, page sized image
page = Image.new('RGB', (page_w, page_h), 'white')

map = ImageOps.expand(Image.open('map.png'), border=4, fill='black')
page.paste(map, (page_buffer, page_buffer))

# add qr code to the map
page.paste(qrcode.resize((qr_size, qr_size)), (page_w - page_buffer - qr_size, map_height + map_buffer + page_buffer))

# open the north arrow and add to the page
north = Image.open('north.png').resize((qr_size - page_buffer, qr_size - page_buffer))
page.paste(north, (page_w - page_buffer - (qr_size*2), map_height + map_buffer + page_buffer // 2 + page_buffer), north)

# get drawing context for page
draw = ImageDraw.Draw(page)

# prepare a font
font = ImageFont.truetype('./open-sans/OpenSans-Regular.ttf', 12)

# get the dimensions of the text and page
tw, th = draw.textsize(uid, font=font)

# add attribution text
year = str(datetime.today().year)
attributionText = "".join(["Paper2GIS Copyright ", year, " Dr Jonny Huck: https://github.com/jonnyhuck/paper2gis. Map data Copyright ", year, " OpenStreetMap Contributors"])
draw.text((page_buffer, page_h - mm2px(3) - th), attributionText, fill='black', font=font)

# add uuid text
draw.text((page_buffer, page_h - mm2px(5) - th*2), uid, fill='black', font=font)

# save the result
page.save(filepath, 'PNG')
