"""
* Generate maps for use with the Paper2GIS system
* All sizes in pixels unless otherwise stated with _mm in variable name
*
* @author jonnyhuck
"""

from sys import exit
from math import ceil
from uuid import uuid4
from qrcode import QRCode
from numpy.random import rand
from datetime import datetime
from PIL.ImageOps import expand
from PIL import Image, ImageDraw, ImageFont
from qrcode.constants import ERROR_CORRECT_L


def mm2px(mm, dpi=96):
	"""
	1 inch = 25.4mm 96dpi is therefore...
	"""
	return int(ceil(mm * dpi / 25.4))


def run_generate(blX, blY, trX, trY, epsg, dpi, in_path, out_path, tiles):
	"""
	Generate a Paper2GIS layout from an existing map
	
	TODO: implement tiles
	TODO: implement resolution options
	TODO: add args for page settings (presets and orientations?)
	---
	Info on QR Args:
		- The qrcode version parameter is an integer from 1 to 40 that controls the size of the QR Code (the smallest, version 1, is a 21x21 matrix). 
		Set to None and use the fit parameter when making the code to determine this automatically.
		- The error_correction parameter controls the error correction used for the QR Code. The following four constants are made available 
			on the qrcode package:
				ERROR_CORRECT_L
					About 7% or less errors can be corrected.
				ERROR_CORRECT_M (default)
					About 15% or less errors can be corrected.
				ERROR_CORRECT_Q
					About 25% or less errors can be corrected.
				ERROR_CORRECT_H.
					About 30% or less errors can be corrected.
		- The box_size parameter controls how many pixels each box of the QR code is.
		- The border parameter controls how many boxes thick the border should be (the default is 4, which is the minimum according to the specs).
	"""

	# init qrcode object
	qr = QRCode(
		version=1,
		error_correction=ERROR_CORRECT_L,
		box_size=10,
		border=4,
	)

	# get unique number hex (truncate to 8 characters)
	uid = uuid4().hex[:8]

	# page dimensions in mm
	w_mm = 297
	h_mm = 420

	# the gap between the map and the qr code etc
	map_buffer = mm2px(6)

	#  page dimensions in px
	page_w = mm2px(w_mm)
	page_h = mm2px(h_mm)

	# buffer around page in mm
	page_buffer = mm2px(3, dpi)

	# qr code size
	qr_size = mm2px(30, dpi)

	# the height of the map
	map_height = 1436

	# MAP DIMENSIONS 1084 x 1436 @ 96dpi
	# see JS script for conversion from other resolutions...

	# scaling for the noise border
	divider = 10

	'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
	'''''''''''''''''''''''''''''''''''''' DRAWING ''''''''''''''''''''''''''''''''''''''''''
	'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

	# make new blank, page sized image
	page = Image.new('RGB', (page_w, page_h), 'white')

	# open the map and add black border
	map = expand(expand(Image.open(in_path), border=4, fill='black'), border=2, fill='white')

	# generate random colours
	noise = rand((map_height + page_buffer*2 + 6*2)//divider, page_w//divider, 3) * 255

	# turn random noise into greyscale image
	noise_im = Image.fromarray(noise.astype('uint8')).resize((noise.shape[1]*divider, noise.shape[0]*divider), Image.NEAREST).convert('L')
	page.paste(noise_im, (0, 0))

	# add the map to the image
	page.paste(map, (page_buffer, page_buffer))

	# add data to qr object, 'make' and export to image
	qr.add_data(','.join([blX, blY, trX, trY, epsg, str(page_buffer+6), str(page_buffer+6), str(page_buffer+map.size[0]-6), str(page_buffer+map.size[1]-6), uid]))
	qr.make(fit=True)
	qrcode_im = qr.make_image()

	print(','.join([blX, blY, trX, trY, epsg, str(page_buffer+6), str(page_buffer+6), str(page_buffer+map.size[0]-6), str(page_buffer+map.size[1]-6), uid]))

	# add qr code to the map
	page.paste(qrcode_im.resize((qr_size, qr_size)), (page_w - page_buffer - qr_size, map_height + map_buffer + page_buffer))

	# open the north arrow and add to the page
	try:
		north = Image.open('./resources/north.png').resize((qr_size - page_buffer, qr_size - page_buffer))
	except FileNotFoundError:
		print("ERROR: Cannot find North Arrow file - please check installation")
		exit()
	page.paste(north, (page_w - page_buffer - (qr_size*2), map_height + map_buffer + page_buffer // 2 + page_buffer), north)

	# get drawing context for page
	draw = ImageDraw.Draw(page)

	# prepare a font
	try:
		font = ImageFont.truetype('./resources/OpenSans-Regular.ttf', 12)
	except OSError:
		print("ERROR: Cannot find Open Sans font file - please check installation")
		exit()

	# get the dimensions of the text and page
	_, th = draw.textsize(uid, font=font)

	# add attribution text
	year = str(datetime.today().year)
	attributionText = "".join(["Paper2GIS Copyright ", year, " Dr Jonny Huck: https://github.com/jonnyhuck/paper2gis. Map data Copyright ", year, " OpenStreetMap Contributors"])
	draw.text((page_buffer, page_h - mm2px(3) - th), attributionText, fill='black', font=font)

	# add uuid text
	draw.text((page_buffer, page_h - mm2px(5) - th*2), uid, fill='black', font=font)

	# validate out_path is a png
	if out_path[-4:] != ".png":
		out_path += ".png"

	# save the result
	try:
		page.save(out_path, 'PNG')
	except FileNotFoundError:
		print("ERROR: Cannot create output file - please check file path")
		exit()