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


def get_osm_map(bl_x, bl_y, tr_x, tr_y, zoom, w, h, dpi=96, crs=None, fade=85):
	"""
	* Return an OSM map as a PIL image
	* 
	* Parameters:
	*     bl_x, bl_y, tr_x, tr_y: desired map bounds (overidden by the desired map dimensions)
	*     zoom: zoom level of the map tiles
	*     w, h: desired dimensions of the output image (overides the map bounds)
	*     dpi: resolution of the output image (default 96)
	*     crs: the crs of the input coordinates (default Web Mercator)
	*     fade: (0-255) the intensity of the white filter
	"""

	# load additional libraries
	from io import BytesIO
	from PIL.Image import BILINEAR
	from matplotlib import pyplot as plt
	from cartopy.io.img_tiles import OSM
	from numpy import reshape, frombuffer, uint8

	# user warning if zoom has not been set
	if zoom == 0:
		print("\nWARNING: the tile zoom level is set to 0 (default), which will not likely give a satisfactory \
			map unless you are drawing a map of the wole world.\n")

	# get OSM tile interface
	tiler = OSM()

	# if no CRS is specified, assume Web Mercator
	if crs is None:
		crs = tiler.crs

	# enforce dimensions, preserving the width of the original dimensions
	map_w = tr_x - bl_x
	map_h = tr_y - bl_y

	# here the map is too wide so preserve the width (add height)
	if (map_w / map_h) < (w / h):
		half_map_height = (map_w * h / w) / 2
		mid_point = bl_y + map_h / 2
		bl_y = mid_point - half_map_height
		tr_y = mid_point + half_map_height

	# otherwise it is too tall, so preserve height (add width)
	else:               
		half_map_width = (map_h * w / h) / 2
		mid_point = bl_x + map_w / 2
		bl_x = mid_point - half_map_width
		tr_x = mid_point + half_map_width

	# create a figure at the desired size and a GeoAxis
	# TODO: This ia a bodge where I make the map too big then shrink - shouldn't be necessary
	fig = plt.figure(figsize=(w/dpi*1.5, h/dpi*1.5), dpi=dpi)
	ax = fig.add_subplot(1, 1, 1, projection=tiler.crs)

	# set the desired map extent on the axis
	ax.set_extent([bl_x, tr_x, bl_y, tr_y], crs=crs)

	# add the map tiles to the axis
	# TODO: Can I set zoom level automatically...?
	ax.add_image(tiler, zoom)
	b = ax.get_window_extent()

	# load map into buffer then array
	# TODO: This seems to be dependent on screen resolution - I think that the problem is actually
	#   ax.get_window_extent
	io_buf = BytesIO()
	fig.savefig(io_buf, format='raw', bbox_inches='tight', pad_inches=0) # dont set dpi?
	io_buf.seek(0)
	img_arr = reshape(frombuffer(io_buf.getvalue(), dtype=uint8), newshape=(int(b.height), int(b.width), -1))
	io_buf.close()

	# convert array to image
	map = Image.fromarray(img_arr).convert('RGBA')

	# overlay white filter and return
	filter = Image.new('RGBA', map.size, 'white')
	filter.putalpha(fade)
	map.paste(filter, (0,0), filter)

	# convert back to RGB and return
	map.convert('RGB')
	# TODO: This is a bodge where I make the map too big then shrink - shouldn't be necessary
	map = map.resize((w,h), resample=BILINEAR)
	return map


def mm2px(mm, dpi=96):
	"""
	1 inch = 25.4mm 96dpi is therefore...
	"""
	return int(ceil(mm * dpi / 25.4))


def run_generate(blX, blY, trX, trY, epsg, dpi, in_path, out_path, tiles, fade, zoom):
	"""
	Generate a Paper2GIS layout from an existing map, or generate one from tiles
	
	TODO: implement resolution options?
	TODO: add args for page settings (presets and orientations?), tile zoom level and fade
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
	# this is from JS to scale between resolutions
	# width =   parseInt(3508 / 300 * 96 - mm2px(10, 96));
	# height =  parseInt(4961 / 300 * 96 - mm2px(40, 96));

	# scaling for the noise border
	divider = 10

	'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
	'''''''''''''''''''''''''''''''''''''' DRAWING ''''''''''''''''''''''''''''''''''''''''''
	'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

	# make new blank, page sized image
	page = Image.new('RGB', (page_w, page_h), 'white')

	# get input image or create one from tiles
	try:
		in_map = get_osm_map(float(blX), float(blY), float(trX), float(trY), zoom, 1084, 1436, fade) if tiles else Image.open(in_path)
	except FileNotFoundError:
		print("ERROR: cannot open input map file, please check file path")
		exit()

	# open the map and add black border
	map = expand(expand(in_map, border=4, fill='black'), border=2, fill='white')

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