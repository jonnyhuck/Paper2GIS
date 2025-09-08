"""
* Extract data from marked up maps as part of the Paper2GIS system
*
* All sizes in pixels unless otherwise stated with _mm in variable name
*
* @author jonnyhuck
*
* References:
* 	https://opencv-python-tutroals.readthedocs.io/en/latest/py_tutorials/py_feature2d/py_feature_homography/py_feature_homography.html
* 	https://docs.opencv.org/master/dc/dc3/tutorial_py_matcher.html
*
* NB: Need to install Open CV via PIP (not conda) using
* 	pip install opencv-contrib-python
*
* Settings used:
* python paper2gis.py --reference ./_template/the-used-one.png --target ./timnadata/IMG_9441.jpg -o ./out/path.tif --threshold 100 --kernel 0
* python paper2gis.py --reference ./_template/the-used-one.png --target ./timna/IMG_9423.jpg -o ./out/wind.tif --threshold 100 --kernel 0
*
* TODO:
*	- Need to implement frame option
*	- Check other versions to make sure this is up to date
* 	- Implement cleaning for raster outputs using: https://github.com/mapbox/rasterio/blob/fb93a6425c17f25141ad308cee7263d0c491a0a9/examples/rasterize_geometry.py
"""

import pillow_heif
from sys import exit
from glob import glob
from PIL import Image
from pathlib import Path
from fiona import open as fio_open
from rasterio.features import shapes
from os import remove, path, makedirs
from rasterio import open as rio_open
from rasterio.transform import from_bounds
from pyzbar.pyzbar import decode, ZBarSymbol
from numpy import float32, uint8, ones, zeros, array
from shapely.geometry import shape, mapping, LineString, Polygon
from cv2 import RANSAC, COLOR_BGR2GRAY, MORPH_OPEN, THRESH_BINARY_INV
from cv2 import findHomography, perspectiveTransform, warpPerspective, morphologyEx, \
	FlannBasedMatcher, threshold, imwrite, imread, cvtColor, medianBlur, SIFT_create


def extract_map(reference_img, target_img, lowe_distance, homo_matches):
	"""
	* Identify one image inside another, extract and perspective transform
	* @author jonnyhuck
	* @return a numpy array representing the extracted and rectified map
	"""

	# find the keypoints and descriptors with SIFT
	sift = SIFT_create()
	kp1, des1 = sift.detectAndCompute(target_img, None)
	kp2, des2 = sift.detectAndCompute(reference_img, None)

	# do some FLANN matching
	flann = FlannBasedMatcher(dict(algorithm=0, trees=10), dict(checks=50))
	matches = flann.knnMatch(des1, des2, k=2)

	# store all the good matches as per Lowe's ratio test.
	good = []
	for m,n in matches:
		if m.distance < lowe_distance * n.distance:
			good.append(m)

	# if there are not enough "good matches", report and exit
	if len(good) < homo_matches:
		raise Exception('NOT ENOUGH MATCHES', f"Not enough matches are found - {len(good)}/{homo_matches}")

	# get numpy arrays for each image
	src_pts = float32([ kp1[m.queryIdx].pt for m in good ]).reshape(-1,1,2)
	dst_pts = float32([ kp2[m.trainIdx].pt for m in good ]).reshape(-1,1,2)

	# do some homography
	M, mask = findHomography(src_pts, dst_pts, RANSAC, 10)
	if M is None:
		raise Exception('NO HOMOGRAPHY', "Failed to calculate Homography")

	# get corner coords
	h, w = target_img.shape
	pts = float32([ [0,0], [0,h-1], [w-1,h-1], [w-1,0] ]).reshape(-1, 1, 2)

	# calculate the transormation required to align them
	dst = perspectiveTransform(pts, M)

	# Apply the calculated transformation as a perspective transformation
	rows, cols = reference_img.shape
	return warpPerspective(target_img, M, (cols, rows))


def processImage(referenceImg, participantMap, lowe_distance,
	homo_matches, geodata, thresh, kernel, demo):
	"""
	* The image processing steps for extracting the markup data from the image
	* @author jonnyhuck
	* @return a binary numpy array of (255) markup and (0) background
	"""

	# extract the map from the target image
	homoMap = extract_map(referenceImg, participantMap, lowe_distance, homo_matches)
	if demo:
		imwrite("./demo/3.warped.png", homoMap)

	# crop homogrified result
	cropped_map = homoMap[int(geodata[6]):int(geodata[8]), int(geodata[5]):int(geodata[7])]
	if demo:
		imwrite("./demo/4.cropped.png", cropped_map)

	# threshold the image to extract markup
	_, thresh_map = threshold(medianBlur(cropped_map, 7), thresh, 255, THRESH_BINARY_INV)
	if demo:
		imwrite("./demo/5.thresholded.png", thresh_map)

	# if kernel is 0 then skip this step
	if kernel > 0:
		# erode and dilate the image to remove noise from the map alignment
		opened_map = morphologyEx(thresh_map, MORPH_OPEN, ones((kernel, kernel), uint8))
		if demo:
			imwrite("./demo/6.opened.png", opened_map)
	else:
		opened_map = thresh_map

	# return the resulting dataset
	return opened_map


def writeTiff(output, opened_map, geodata):
	"""
	* Write a numpy array to a GeoTiff - this is mostly here for backward compatibility,
	*  expected behaviour is to output to shapefile as this has data cleaning steps to
	*  improve the output
	* @author jonnyhuck
	"""

	# output dataset to raster
	with rio_open(output, 'w', driver='GTiff', height=opened_map.shape[0],
		width=opened_map.shape[1], count=1, dtype='uint8', crs="EPSG:" + geodata[4],
		transform=from_bounds(float(geodata[0]), float(geodata[1]), float(geodata[2]),
			float(geodata[3]), opened_map.shape[1], opened_map.shape[0])
	) as out:
		out.write(opened_map, 1)


def cleanWriteShapefile(output, opened_map, geodata, buffer, min_area, min_ratio, convex_hull, centroid, representative_point, exterior, interior):
	"""
	* Clean an output dataset and write to a shapefile
	* @author jonnyhuck
	"""

	# make a mask of which cells we want to extract
	mask = opened_map == 255

	# extract the masked cells as georeferenced vector shapes
	results = ({'properties': {'raster_val': v}, 'geometry': s} for i, (s, v) in
		enumerate(shapes(opened_map, mask=mask, transform=from_bounds(float(geodata[0]),
		float(geodata[1]), float(geodata[2]), float(geodata[3]), opened_map.shape[1],
		opened_map.shape[0]))))

	# set geometry type for shapefile
	geom_type = 'Point' if any([centroid, representative_point]) else 'Polygon'

	# open shapefile for writing
	with fio_open(output, 'w', driver="ESRI Shapefile", crs=f"EPSG:{geodata[4]}",
		schema={'geometry': geom_type, 'properties': {'area':'float'}}) as out:

		#  this would write the raw records - the equivalent of what you would get in the raster output
		# out.writerecords(results)

		# construct aoi boundary zone
		envelope = [ float(x) for x in geodata[:4] ]
		edge = LineString([
			(envelope[0], envelope[1]), # bl
			(envelope[2], envelope[1]), # br
			(envelope[2], envelope[3]), # tr
			(envelope[0], envelope[3]), # tl
			(envelope[0], envelope[1])  # bl
			]).buffer(buffer)

		# access the variable (loop through each feature in this case)
		for feature in results:

			# convert the geometry to shapely format
			geom = shape(feature['geometry'])

			# if too small, drop (either convex hull or regular geom)
			the_area = geom.convex_hull.area if convex_hull else geom.area
			if the_area < min_area:
				continue

			# if wrong ratio between width & height of bounding box, drop
			sides = [geom.bounds[2] - geom.bounds[0], geom.bounds[3] - geom.bounds[1]]
			if min(sides) / max(sides) < min_ratio:
				continue

			# if intersects edge, clip it
			if geom.intersects(edge):
				# TODO: subdivide into individual geoms
				geom = geom.difference(edge)

			# make sure that we haven't ended up with an empty geometry
			if geom.is_empty:
				continue

			# if convex hull is desired, save that
			if (convex_hull):
				out.write({'geometry': mapping(geom.convex_hull),
					'properties': {'area': geom.convex_hull.area}})
			
			# if centroid is desired, save that
			elif (centroid):
				out.write({'geometry': mapping(geom.centroid),
					'properties': {'area': 0}})

			# if rep point is desired, save that
			elif (representative_point):
				out.write({'geometry': mapping(geom.representative_point()),
					'properties': {'area': 0}})
			
			# extract exterior ring from polygon
			elif (exterior):

				# handle MultiPolygons
				geoms = geom.geoms if geom.geom_type == 'MultiPolygon' else [geom]
				for g in geoms:
				
					# extract the exterior ring and convert to polygon
					polygon = Polygon(g.exterior.coords)
					out.write({'geometry': mapping(polygon),
						'properties': {'area': geom.area}})
			
			# extract interior ring from polygon
			elif (interior):

				# handle MultiPolygons
				geoms = geom.geoms if geom.geom_type == 'MultiPolygon' else [geom]
				for g in geoms:
				
					# extract the interior ring and convert to polygon
					for int_geom in geom.interiors:
						polygon = Polygon(int_geom.coords)
						out.write({'geometry': mapping(polygon),
							'properties': {'area': geom.area}})

			# TODO: have a `holes` option that gets all polygons within each 
			# 	other polygon and adds them as holes to the constructor (or
			# 	differences them)

			# otherwise just save the raw geometry
			else:
				out.write({'geometry': mapping(geom),
					'properties': {'area': geom.area}})


def run_extract(reference, target, output='out.shp', lowe_distance=0.5, thresh=100,
	kernel=3, homo_matches=12, frame=0, min_area=1000, min_ratio=0.2, buffer=10, convex_hull=False,
	centroid=False, representative_point=False, exterior=False, interior=False, demo=False):
	"""
	* Main function: this runs the map extraction, resulting in a file being written
	*  to the desired location
	* @author jonnyhuck
	"""

	# make sure there are not any conflicting output options specified
	if sum([convex_hull, centroid, representative_point, exterior, interior]) > 1:
		raise AttributeError(f"you have requested more than one type of output - please select only one of convex_hull, centroid, representative_point or boundary")

	# check input files exist (cv2.imread does not raise FileNotFoundError)
	if not path.isfile(reference):
		raise FileNotFoundError(f"{reference} does not exist")
	if not path.isfile(target):
		raise FileNotFoundError(f"{target} does not exist")

	# make sure that the output file extension is suitable
	if output[-4:] not in [".tif", ".shp"]:
		print(f"output data file must be .tif (for a raster output) or .shp (for vector output). You used {output[-4:]}")
		exit()

	# output demo info & empty demo directory
	if demo:

		# make sure demo folder exists
		if not path.exists('./demo'):
			makedirs('./demo')

		# make sure demo folder is empty
		for f in glob("./demo/*.png"):
			remove(f)

		# print initial demo information
		print(f"reference: {reference}")
		print(f"target: {target}")
		print(f"output: {output}")

	# read in reference image and greyscale
	reference_img = cvtColor(imread(reference), COLOR_BGR2GRAY)
	if demo:
		imwrite("./demo/1.reference.png", reference_img)

	# catch HEIC/heif input file
	if Path(target).suffix.lower() in {".heic", ".heif"}:
		if demo:
			print("converting HEIC...")
		
		# register HEIF opener with Pillow and open the file
		pillow_heif.register_heif_opener()
		pil_img = Image.open(target)

		# convert to NumPy array
		ref_np = array(pil_img)
	else:

		# read into numpy array
		ref_np = imread(target)

	# read in participant map and greyscale
	participant_map = cvtColor(ref_np, COLOR_BGR2GRAY)
	if frame > 0:
		# make a white background
		h, w = participant_map.shape
		
		# make a white background that is 2 * frame larger then the image in each dimension
		frame_multiplier = 1 + frame * 2
		frame_background = zeros([int(h * frame_multiplier), int(w * frame_multiplier)], dtype=uint8)
		frame_background.fill(127)

		# paste the original image onto the new background, leaving a frame
		y_offset, x_offset = int(frame * h), int(frame * w)
		y_end, x_end = h + y_offset, w + x_offset
		frame_background[y_offset:y_end, x_offset:x_end] = participant_map
		
		# overwrite the participant map
		participant_map = frame_background
	if demo:
		imwrite("./demo/2.target.png", participant_map)

	# get metadata from QR code
	try:
		geodata = decode(reference_img, symbols=[ZBarSymbol.QRCODE])[0].data.decode("utf-8").split(",")
		if demo:
			print('QR_DATA=', geodata)
	except IndexError:
		raise Exception('NOT A PAPER2GIS MAP', "Reference image is not a Paper2GIS map")

	# verify that the target image matches the reference
	try:
		tmp_geodata = decode(participant_map, symbols=[ZBarSymbol.QRCODE])[0].data.decode("utf-8").split(",")
		if geodata[-1] != tmp_geodata[-1]:
			raise Exception('WRONG REFERENCE', "Target image does not match reference image")
	except IndexError:
		# print("WARNING - can't read QR code in target image")
		pass	# never seems to manage to read it!

	# run the imageb processing to get binary result array
	opened_map = processImage(reference_img, participant_map, lowe_distance,
		homo_matches, geodata, thresh, kernel, demo)

	# output to a raster if the output file extension is .tif (no cleaning)
	if output[-4:] == ".tif":
		# TODO: convert to vector, clean then rasterise
		writeTiff(output, opened_map, geodata)

	# clean the dataset and output to a vector if the output file extension is .shp
	elif output[-4:] == ".shp":
		cleanWriteShapefile(output, opened_map, geodata, buffer, min_area, min_ratio, 
		      convex_hull, centroid, representative_point, exterior, interior)