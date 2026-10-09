"""
* Generate maps for use with the Paper2GIS system
* All sizes in pixels unless otherwise stated with _mm in variable name
*
* @author jonnyhuck
"""

from sys import exit
from os import path
from math import ceil
from io import BytesIO
from qrcode import QRCode
from hashlib import sha256
from numpy.random import rand
from datetime import datetime
from PIL.ImageOps import expand
from fiona.errors import DriverError
from PIL import Image, ImageDraw, ImageFont
from qrcode.constants import ERROR_CORRECT_L
from cartopy.io.img_tiles import GoogleTiles, OSM
from paper2gis.markers import MARKER_PX, MARKER_MODULE_PX, draw_marker, get_dictionary


# Module-level verbose flag
_VERBOSE = False

# resources directory (relative to this file, so that it works from any working directory)
RESOURCES = path.join(path.dirname(path.abspath(__file__)), '..', 'resources')

def vprint(*args, **kwargs):
	"""Print only if verbose mode is enabled"""
	if _VERBOSE:
		print(*args, **kwargs)

class ShadedReliefESRI(GoogleTiles):
    """
    * Custom class for hillshade tiles from ESRI, see: 
	*	https://stackoverflow.com/questions/37423997/cartopy-shaded-relief
	"""
    def _image_url(self, tile):
        x, y, z = tile
        url = ('https://server.arcgisonline.com/ArcGIS/rest/services/' \
               'World_Shaded_Relief/MapServer/tile/{z}/{y}/{x}.jpg').format(
               z=z, y=y, x=x)
        return url

class SatelliteESRI(GoogleTiles):
    """
    * Custom class for satellite imagery tiles from ESRI, see: 
	"""
    def _image_url(self, tile):
        x, y, z = tile
        url = ('https://server.arcgisonline.com/ArcGIS/rest/services/' \
               'World_Imagery/MapServer/tile/{z}/{y}/{x}.jpg').format(
               z=z, y=y, x=x)
        return url


# the available tile sources: name -> (function to get the tiler, attribution text)
TILE_SOURCES = {
	'osm': (lambda: OSM(), "Map data Copyright {year} OpenStreetMap Contributors."),
	'esri': (lambda: SatelliteESRI(), "Imagery Copyright {year} Esri, Maxar, Earthstar Geographics, and the GIS User Community."),
	'google': (lambda: GoogleTiles(style='satellite'), "Imagery Copyright {year} Google."),
}


def figure_to_image(fig, dpi=None):
	"""
	* Convert a pyplot Figure to a PIL Image
	"""
	buf = BytesIO()
	fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
	buf.seek(0)
	img = Image.open(buf)
	return img.convert("RGBA")


def get_osm_map(bl_x, bl_y, tr_x, tr_y, zoom, w, h, dpi=96, crs=None, source='osm', fade=85, hillshade=False, hillshade_alpha=0.25,
				boundary_file=None, boundary_width=8, boundary_colour='blue', boundary_alpha=0.1):
	"""
	* Return an OSM map as a PIL image
	* 
	* Parameters:
	*     bl_x, bl_y, tr_x, tr_y: desired map bounds (overidden by the desired map dimensions)
	*     zoom: zoom level of the map tiles
	*     w, h: desired dimensions of the output image (overides the map bounds)
	*     dpi: resolution of the output image (default 96)
	*     crs: the crs of the input coordinates (default Web Mercator)
	*     source: the tiles to use - 'osm' (OpenStreetMap), 'esri' (ESRI satellite) or 'google' (Google satellite)
	*     fade: (0-255) the intensity of the white filter
	"""
	# load additional libraries
	from PIL.Image import BILINEAR
	from matplotlib import pyplot as plt

	vprint(f"Downloading {source.upper()} tiles (zoom={zoom}, dimensions={w}x{h})...")

	# user warning if zoom has not been set
	if zoom == 0:
		print("\nWARNING: the tile zoom level is set to 0 (default), which will not likely give a satisfactory \
			map unless you are drawing a map of the wole world.\n")

	# get the tile interface for the requested source
	tiler = TILE_SOURCES[source][0]()

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
		vprint(f"Adjusted bounds to fit template (added height)")

	# otherwise it is too tall, so preserve height (add width)
	else:               
		half_map_width = (map_h * w / h) / 2
		mid_point = bl_x + map_w / 2
		bl_x = mid_point - half_map_width
		tr_x = mid_point + half_map_width
		vprint(f"Adjusted bounds to fit template (added width)")

	# create a figure at the desired size and a GeoAxis
	# TODO: This ia a bodge where I make the map too big then shrink - shouldn't be necessary
	fig = plt.figure(figsize=(w/dpi*1.5, h/dpi*1.5), dpi=dpi)
	fig.subplots_adjust(0,0,1,1)
	ax = fig.add_subplot(1, 1, 1, projection=tiler.crs)

	# set the desired map extent on the axis
	ax.set_extent([bl_x, tr_x, bl_y, tr_y], crs=tiler.crs)

	# add the map tiles to the axis and get extent
	# TODO: Can I set zoom level automatically...?
	ax.add_image(tiler, zoom)
	
	# add hillshade if needed
	if hillshade:
		vprint(f"Adding hillshade layer (alpha={hillshade_alpha})")
		shade = ShadedReliefESRI()
		ax.add_image(shade, zoom, alpha=hillshade_alpha)
	
	# add LD boundary
	if boundary_file:
		vprint(f"Adding boundary layer: {boundary_file}")
		import cartopy.io.shapereader as shpreader
		
		# open the boundary file
		try:
			reader = shpreader.Reader(boundary_file)

			# add to the map
			ax.add_geometries(reader.geometries(), crs=tiler.crs, facecolor='none', edgecolor=boundary_colour, 
					 linewidth=boundary_width, alpha=boundary_alpha)
			
		except DriverError:
			if boundary_file[-4:] != ".shp":
				print(f"ERROR: Could not open Shapefile {boundary_file}, please check file extension")
			else:
				print(f"ERROR: Could not open Shapefile {boundary_file}, please check file path")
			exit()
		
	# convert map image (pyplot Figure) to PIL Image
	map = figure_to_image(fig)

	# overlay white filter and return (allow for the fade caused by the hillshade if needed)
	filter = Image.new('RGBA', map.size, 'white')
	fade = int(fade - (hillshade_alpha * 255) + 0.5) if hillshade else fade
	filter.putalpha(fade)
	map.paste(filter, (0,0), filter)

	# convert back to RGB and return
	map = map.convert('RGB')
	# TODO: This is a bodge where I make the map too big then shrink - shouldn't be necessary
	map = map.resize((w,h), resample=BILINEAR)
	return (bl_x, bl_y, tr_x, tr_y), map


def mm2px(mm, dpi=96):
	"""
	* 1 inch = 25.4mm 96dpi is therefore...
	"""
	return int(ceil(mm * dpi / 25.4))


def make_uid(georeferencing, source):
	"""
	* Make the map id (8 hex characters) as a hash of everything that defines the map, so that
	*  two identical maps generated at different times get the same id (and so a photo of one
	*  can be extracted using the other as the reference). The map image itself is not used, as
	*  tiles are not rendered identically every time they are downloaded.
	*
	*     georeferencing: the bounds, crs and pixel location of the map in the layout (as in the QR code)
	*     source: a description of where the map came from (the tile settings, or the input image file)
	"""
	return sha256(f"{georeferencing}|{source}".encode("utf-8")).hexdigest()[:8]


def add_marker_border(page, x0, y0, x1, y1):
	"""
	* Draw a ring of ArUco markers (at regular intervals) onto the page, inside the
	*  rectangle x0, y0, x1, y1. Each marker has a unique id, so that the extraction
	*  process knows exactly where each one is on the reference layout
	"""

	# the desired distance between markers (one marker plus a marker-sized white gap)
	pitch = MARKER_PX * 2

	def positions(start, end):
		"""
		* Get evenly spaced positions from start to end (inclusive), as close to pitch apart as possible
		"""
		n = max(int((end - start) // pitch), 1)
		return [ int(round(start + i * (end - start) / n)) for i in range(n + 1) ]

	# get the positions of the markers along each axis (top left corner of each marker, including corners)
	xs = positions(x0, x1 - MARKER_PX)
	ys = positions(y0, y1 - MARKER_PX)

	# list the top left corner of each marker, going clockwise from the top left corner of the ring
	locations = [ (x, y0) for x in xs ] \
		+ [ (x1 - MARKER_PX, y) for y in ys[1:] ] \
		+ [ (x, y1 - MARKER_PX) for x in reversed(xs[:-1]) ] \
		+ [ (x0, y) for y in reversed(ys[1:-1]) ]

	# make sure that there are enough unique ids in the dictionary
	n_ids = get_dictionary().bytesList.shape[0]
	if len(locations) > n_ids:
		raise ValueError(f"Layout needs {len(locations)} markers but the dictionary only has {n_ids}")

	# draw each marker onto the page (the marker id is its position in the list)
	for marker_id, (x, y) in enumerate(locations):
		page.paste(Image.fromarray(draw_marker(marker_id)), (x, y))

	# return the number of markers
	return len(locations)


def run_generate(blX, blY, trX, trY, epsg='3857', dpi=96, in_path=None, out_path='out.png', descriptive_text='',
				 tiles=False, fade=85, zoom=0, hillshade=False, hillshade_alpha=0.25, boundary_file=None,
				 boundary_width=8, boundary_colour='blue', boundary_alpha=0.1, verbose=False, name="", markers=True,
				 landscape=False):
	"""
	* Generate a Paper2GIS layout from an existing map, or generate one from tiles
	*
	* tiles can be 'osm' (OpenStreetMap), 'esri' (ESRI satellite) or 'google' (Google satellite) to draw
	*  the map from tiles, or False to use the map image at in_path instead. For backward compatibility,
	*  tiles=True is the same as 'osm'.
	*
	* If markers=True (default), the map is surrounded by a ring of ArUco markers, which are used
	*  by the extraction process to locate the map in the photograph. Otherwise the older random
	*  noise border is used (and the extraction relies upon features in the map itself).
	*
	* If landscape=True, the page is A3 landscape rather than A3 portrait (default).
	*
	* TODO: implement resolution options?
	* TODO: add args for page settings (presets?), tile zoom level and fade
	* ---
	* Info on QR Args:
	* 	- The qrcode version parameter is an integer from 1 to 40 that controls the size of the QR Code (the smallest, version 1, is a 21x21 matrix). 
	* 	Set to None and use the fit parameter when making the code to determine this automatically.
	* 	- The error_correction parameter controls the error correction used for the QR Code. The following four constants are made available 
	* 		on the qrcode package:
	* 			ERROR_CORRECT_L
	* 				About 7% or less errors can be corrected.
	* 			ERROR_CORRECT_M (default)
	* 				About 15% or less errors can be corrected.
	* 			ERROR_CORRECT_Q
	* 				About 25% or less errors can be corrected.
	* 			ERROR_CORRECT_H.
	* 				About 30% or less errors can be corrected.
	* 	- The box_size parameter controls how many pixels each box of the QR code is.
	* 	- The border parameter controls how many boxes thick the border should be (the default is 4, which is the minimum according to the specs).
	"""

	# Set module-level verbose flag
	global _VERBOSE
	_VERBOSE = verbose

	# work out which tiles to use, if any (tiles=True is kept for backward compatibility)
	if tiles is True:
		tiles = 'osm'

	# make sure that the requested tiles exist
	if tiles and tiles not in TILE_SOURCES:
		raise ValueError(f"Unknown tile source '{tiles}', please use one of: {', '.join(TILE_SOURCES)}")

	source = f"{tiles.upper()} tiles (zoom={zoom})" if tiles else in_path
	vprint(f"\nGenerating Paper2GIS layout: {source} -> {out_path}")
	vprint(f"Parameters: EPSG:{epsg}, bounds=[{blX}, {blY}, {trX}, {trY}]")

	# init qrcode object
	qr = QRCode(
		version=1,
		error_correction=ERROR_CORRECT_L,
		box_size=10,
		border=4,
	)


	# page dimensions in mm (A3, swapped for landscape)
	w_mm, h_mm = (420, 297) if landscape else (297, 420)
	vprint(f"Page: A3 {'landscape' if landscape else 'portrait'}")

	#  page dimensions in px
	page_w = mm2px(w_mm)
	page_h = mm2px(h_mm)

	# buffer around page in mm
	page_buffer = mm2px(3, dpi)

	# qr code size
	qr_size = mm2px(30, dpi)

	# the width of the black and white frame around the map (4px black + 2px white)
	map_frame = 6

	# the white gap (quiet zone) between the markers and the map / qr code
	marker_gap = MARKER_MODULE_PX

	# the width of the marker border (zero if not using markers)
	band = MARKER_PX + marker_gap if markers else 0

	# the top of the qr code (which sits in the bottom right corner of the page)
	qr_top = page_h - page_buffer - qr_size

	# the outer edges of the marker ring (the qr code etc sits underneath)
	ring_x0, ring_y0 = page_buffer, page_buffer
	ring_x1, ring_y1 = page_w - page_buffer, qr_top - marker_gap

	# the outer edges of the map (including its frame), inside the marker ring
	frame_x0, frame_y0 = ring_x0 + band, ring_y0 + band
	frame_x1, frame_y1 = ring_x1 - band, ring_y1 - band

	# the dimensions of the map itself (inside the frame)
	map_w = frame_x1 - frame_x0 - map_frame * 2
	map_h = frame_y1 - frame_y0 - map_frame * 2
	vprint(f"Map dimensions: {map_w} x {map_h} pixels ({'with' if markers else 'without'} marker border)")

	# scaling for the noise border
	divider = 10

	'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
	'''''''''''''''''''''''''''''''''''''' DRAWING ''''''''''''''''''''''''''''''''''''''''''
	'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

	# make new blank, page sized image
	page = Image.new('RGB', (page_w, page_h), 'white')

	# get input image or create one from tiles
	if tiles:
		# note we might need to overwrite the dimensions here as the map gets adjusted to fit the template
		c, in_map = get_osm_map(float(blX), float(blY), float(trX), float(trY), zoom, map_w, map_h, source=tiles, fade=fade, hillshade=hillshade,
						  hillshade_alpha=hillshade_alpha, boundary_file=boundary_file, boundary_width=boundary_width, 
						  boundary_colour=boundary_colour, boundary_alpha=boundary_alpha) 
		blX = str(c[0])
		blY = str(c[1])
		trX = str(c[2])
		trY = str(c[3])
	else:
		vprint(f"Loading map image: {in_path}")
		try:
			in_map = Image.open(in_path)
			vprint(f"Loaded: {in_map.size[0]}x{in_map.size[1]} pixels")
		except FileNotFoundError:
			print("ERROR: cannot open input map file, please check file path")
			exit()

		# make sure that the map fits the space available in the layout
		if in_map.size != (map_w, map_h):
			print(f"WARNING: input map is {in_map.size[0]}x{in_map.size[1]} pixels, but the layout requires " \
				f"{map_w}x{map_h} - it will be resized to fit, which may distort it if the aspect ratio is different.")
			in_map = in_map.resize((map_w, map_h), resample=Image.BILINEAR)

	# open the map and add black border
	map = expand(expand(in_map.convert('RGB'), border=4, fill='black'), border=2, fill='white')

	vprint("Compositing layout with border and map...")

	# add a ring of ArUco markers around the map
	if markers:
		n_markers = add_marker_border(page, ring_x0, ring_y0, ring_x1, ring_y1)
		vprint(f"Added {n_markers} ArUco markers to the border")

	# otherwise, add the old random noise border
	else:

		# generate random noise for border (covering the area behind the map, plus the page buffer)
		noise = rand((frame_y1 + page_buffer)//divider, page_w//divider, 3) * 255

		# turn random noise into greyscale image
		noise_im = Image.fromarray(noise.astype('uint8')).resize((noise.shape[1]*divider, noise.shape[0]*divider), Image.NEAREST).convert('L')
		page.paste(noise_im, (0, 0))

	# add the map to the image
	page.paste(map, (frame_x0, frame_y0))

	vprint("Generating QR code with georeferencing metadata...")

	# get the georeferencing information (bounds, crs, pixel coordinates of map in the layout)
	georeferencing = [str(blX), str(blY), str(trX), str(trY), str(epsg), str(frame_x0 + map_frame), str(frame_y0 + map_frame),
		str(frame_x0 + map.size[0] - map_frame), str(frame_y0 + map.size[1] - map_frame)]

	# describe where the map came from: the tile settings, or the contents of the input image file
	if tiles:
		source = f"{tiles},{zoom},{fade},{hillshade},{hillshade_alpha},{boundary_file},{boundary_width},{boundary_colour},{boundary_alpha}"
	else:
		with open(in_path, 'rb') as f:
			source = sha256(f.read()).hexdigest()

	# make the map id from these (bounds are formatted consistently, so that e.g. '1' and '1.0' give the same id)
	uid = make_uid(','.join([f"{float(v):.6f}" for v in georeferencing[:4]] + georeferencing[4:]), source)
	vprint(f"Map ID: {uid}")

	# add data to qr object, 'make' and export to image (georeferencing information and map id)
	qr.add_data(','.join(georeferencing + [uid]))
	qr.make(fit=True)
	qrcode_im = qr.make_image()

	# add qr code to the map
	page.paste(qrcode_im.resize((qr_size, qr_size)), (page_w - page_buffer - qr_size, qr_top))

	# open the north arrow and add to the page
	try:
		north = Image.open(path.join(RESOURCES, 'North.png')).resize((qr_size - page_buffer, qr_size - page_buffer))
	except FileNotFoundError:
		print("ERROR: Cannot find North Arrow file - please check installation")
		exit()
	page.paste(north, (page_w - page_buffer - (qr_size*2), qr_top + page_buffer // 2), north)

	# get drawing context for page
	draw = ImageDraw.Draw(page)

	# prepare a font
	try:
		font = ImageFont.truetype(path.join(RESOURCES, 'OpenSans-Regular.ttf'), 12)
	except OSError:
		print("ERROR: Cannot find Open Sans font file - please check installation")
		exit()

	# get the dimensions of the text and page
	bbox = draw.textbbox((0, 0), uid, font=font, anchor="la")
	th = bbox[3] - bbox[1]

	# add attribution text
	year = str(datetime.today().year)
	attribution_text_list = ["Paper2GIS Copyright", year, "Prof. Jonny Huck: https://github.com/jonnyhuck/paper2gis."]
	if tiles:
		attribution_text_list += ["\n" + TILE_SOURCES[tiles][1].format(year=year)]
	if tiles and hillshade:
		attribution_text_list += ["Hillshade data Copyright", year, "ESRI, USGS."]
	attribution_text = " ".join(attribution_text_list)

	# measure the attribution text (which may be more than one line) and place it so that its bottom
	#  lines up with the bottom of the qr code (i.e. the page buffer), so it doesn't run off the page
	attribution_bbox = draw.multiline_textbbox((0, 0), attribution_text, font=font)
	attribution_y = page_h - page_buffer - attribution_bbox[3]
	draw.multiline_text((page_buffer, attribution_y), attribution_text, fill='black', font=font)

	# add map id and description text (one line above the attribution text, with a small gap)
	draw.text((page_buffer, attribution_y - th * 2), f"{uid} | {descriptive_text}", fill='black', font=font)

	# validate out_path is a png
	if out_path[-4:] != ".png":
		out_path += ".png"

	# save the result
	try:
		page.save(out_path, 'PNG')
		vprint(f"Saved layout to {out_path}")
	except FileNotFoundError:
		print("ERROR: Cannot create output file - please check file path")
		exit()