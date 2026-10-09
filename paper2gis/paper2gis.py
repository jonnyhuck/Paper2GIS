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
* Map registration (locating the map in the photograph):
*	1. If the layout has an ArUco marker border, the markers are detected in both images and
*		matched by id, giving a homography that is independent of the map content
*	2. Otherwise (or if not enough markers are found), SIFT features are matched between the
*		(downscaled) photograph and the reference
*
* TODO:
*	- Check other versions to make sure this is up to date
* 	- Implement cleaning for raster outputs using: https://github.com/mapbox/rasterio/blob/fb93a6425c17f25141ad308cee7263d0c491a0a9/examples/rasterize_geometry.py
"""

import pillow_heif
from sys import exit
from glob import glob
from PIL import Image
from pathlib import Path
from numpy.linalg import inv
from fiona import open as fio_open
from rasterio.features import shapes
from os import remove, path, makedirs
from rasterio import open as rio_open
from rasterio.transform import from_bounds
from pyzbar.pyzbar import decode, ZBarSymbol
from paper2gis.markers import detect_markers
from numpy import float32, uint8, ones, zeros, array, concatenate, diag, dstack
from shapely.geometry import shape, mapping, LineString, Polygon
from cv2 import RANSAC, USAC_MAGSAC, COLOR_BGR2GRAY, COLOR_RGB2GRAY, COLOR_GRAY2BGR, MORPH_OPEN, THRESH_BINARY_INV, \
	INTER_AREA
from cv2 import findHomography, perspectiveTransform, warpPerspective, morphologyEx, \
	FlannBasedMatcher, threshold, imwrite, imread, cvtColor, medianBlur, SIFT_create, drawMatchesKnn, \
	resize, isContourConvex, contourArea, aruco


# Module-level verbose flag
_VERBOSE = False

# the minimum number of inliers required to accept a homography (twice the minimum possible)
MIN_INLIERS = 8

def vprint(*args, **kwargs):
	"""Print only if verbose mode is enabled"""
	if _VERBOSE:
		print(*args, **kwargs)


def estimate_homography(src_pts, dst_pts, magsac, reproj_threshold):
	"""
	* Estimate a homography from matched points, using either RANSAC or MAGSAC
	*  (MAGSAC is more tolerant of a high proportion of incorrect matches)
	"""

	# choose the robust estimation method
	method = USAC_MAGSAC if magsac else RANSAC

	# calculate the homography
	M, mask = findHomography(src_pts, dst_pts, method, reproj_threshold)

	# count the inliers (the matches that agree with the homography)
	inliers = 0 if mask is None else int(mask.sum())
	return M, inliers


def check_homography(M, inliers, reference_shape, target_shape):
	"""
	* Sanity check a homography, so that a bad one does not silently produce garbage
	"""

	# make sure that there is a homography
	if M is None:
		return "no homography could be calculated"

	# make sure that enough matches agree with it
	if inliers < MIN_INLIERS:
		return f"only {inliers} inliers (minimum required: {MIN_INLIERS})"

	# get the corners of the reference image
	h, w = reference_shape
	corners = float32([ [0,0], [0,h-1], [w-1,h-1], [w-1,0] ]).reshape(-1, 1, 2)

	# project the reference corners into the target image (i.e. where the page is in the photo)
	quad = perspectiveTransform(corners, inv(M))

	# the page should be a convex quadrilateral in the photo
	if not isContourConvex(quad):
		return "the page is not a convex shape in the photograph"

	# ...that is not mirrored (the corners should go round the same way in both images)
	if (contourArea(corners, oriented=True) > 0) != (contourArea(quad, oriented=True) > 0):
		return "the page is mirrored in the photograph"

	# ...and that is not tiny (less than 1% of the photograph)
	if contourArea(quad) < 0.01 * target_shape[0] * target_shape[1]:
		return "the page is implausibly small in the photograph"

	# all OK
	return None


def homography_from_markers(reference_img, target_img, magsac, min_markers, demo):
	"""
	* Calculate the homography between the photograph and the reference using the ArUco
	*  marker border. Each marker has a unique id, so we know exactly which corners match
	"""

	# find the markers in the reference image
	vprint("Detecting ArUco markers...")
	ref_markers = detect_markers(reference_img)

	# if there are none, this is an older layout so use SIFT instead
	if not ref_markers:
		vprint("No markers in reference image (older layout), using SIFT instead")
		return None

	# find the markers in the target image, and get the ids that appear in both
	tgt_markers = detect_markers(target_img)
	shared = sorted(set(ref_markers) & set(tgt_markers))
	vprint(f"Found {len(tgt_markers)} markers in target, {len(shared)} of which match the {len(ref_markers)} in the reference")

	# plot detected markers for demo
	if demo:
		marker_img = cvtColor(target_img, COLOR_GRAY2BGR)
		if shared:
			aruco.drawDetectedMarkers(marker_img, [ tgt_markers[i].reshape(1, 4, 2) for i in shared ], array(shared).reshape(-1, 1))
		imwrite('demo/2.markers.jpg', marker_img)

	# if there are not enough markers, use SIFT instead
	if len(shared) < min_markers:
		vprint(f"Not enough markers (minimum required: {min_markers}), using SIFT instead")
		return None

	# get the corners of each matching marker as numpy arrays (4 corners per marker, in the same order)
	src_pts = concatenate([ tgt_markers[i] for i in shared ]).astype(float32).reshape(-1, 1, 2)
	dst_pts = concatenate([ ref_markers[i] for i in shared ]).astype(float32).reshape(-1, 1, 2)

	# do some homography (the corners are accurate, so a tight reprojection threshold is OK)
	M, inliers = estimate_homography(src_pts, dst_pts, magsac, 3)
	vprint(f"Marker homography: {inliers}/{len(src_pts)} corners are inliers")

	# check the result and use SIFT instead if it is no good
	problem = check_homography(M, inliers, reference_img.shape, target_img.shape)
	if problem:
		vprint(f"Marker homography rejected ({problem}), using SIFT instead")
		return None
	return M


def homography_from_sift(reference_img, target_img, lowe_distance, homo_matches, magsac, downscale, demo,
	max_features=10000):
	"""
	* Calculate the homography between the photograph and the reference using SIFT features
	*  from the map itself (for older layouts without markers, or if the markers are not found)
	"""

	# downscale the photograph to roughly the size of the reference, as fine detail in a high resolution
	#  photo (paper grain, printer dots, noise, pen strokes) has no equivalent in the reference
	scale = 1.0
	if downscale > 0:
		scale = min(1.0, downscale * max(reference_img.shape) / max(target_img.shape))
	match_target = resize(target_img, None, fx=scale, fy=scale, interpolation=INTER_AREA) if scale < 1 else target_img
	vprint(f"Matching at {scale:.2f}x photo resolution ({match_target.shape[1]} x {match_target.shape[0]} pixels)")

	# find the keypoints and descriptors with SIFT
	vprint("Detecting keypoints with SIFT...")
	#  (keeping only the strongest max_features keypoints, as matching very large numbers is extremely slow)
	sift = SIFT_create(nfeatures=max_features)
	kp1, des1 = sift.detectAndCompute(match_target, None)
	kp2, des2 = sift.detectAndCompute(reference_img, None)
	vprint(f"Found {len(kp1)} keypoints in target, {len(kp2)} in reference")

	# make sure that there is something to match
	if des1 is None or des2 is None or len(kp2) < 2:
		raise Exception('NOT ENOUGH MATCHES', "No features found in one of the images")

	# do some FLANN matching
	flann = FlannBasedMatcher(dict(algorithm=0, trees=10), dict(checks=50))
	matches = flann.knnMatch(des1, des2, k=2)

	# store all the good matches as per Lowe's ratio test.
	good = []
	matchesMask = [[0,0] for _ in range(len(matches))]
	for i, pair in enumerate(matches):

		# skip any keypoints that did not get two matches
		if len(pair) < 2:
			continue

		# keep the match if it is much better than the second best
		m, n = pair
		if m.distance < lowe_distance * n.distance:
			good.append(m)
			matchesMask[i]=[1,0]

	vprint(f"Matched features: {len(good)} good matches (minimum required: {homo_matches})")

	# plot matches image for demo
	if demo:
		match_img = drawMatchesKnn(match_target, kp1, reference_img, kp2, matches, None, matchesMask=matchesMask)
		imwrite('demo/2.matches.jpg', match_img)

	# if there are not enough "good matches", report and exit
	if len(good) < homo_matches:
		raise Exception('NOT ENOUGH MATCHES', f"Not enough matches are found - {len(good)}/{homo_matches}")

	# get numpy arrays for each image
	src_pts = float32([ kp1[m.queryIdx].pt for m in good ]).reshape(-1,1,2)
	dst_pts = float32([ kp2[m.trainIdx].pt for m in good ]).reshape(-1,1,2)

	# do some homography
	vprint("Computing homography...")
	M, inliers = estimate_homography(src_pts, dst_pts, magsac, 10)
	vprint(f"SIFT homography: {inliers}/{len(good)} matches are inliers")

	# convert the homography from the downscaled photo to the full resolution one
	if M is not None:
		M = M @ diag([scale, scale, 1.0])

	# check the result and report if it is no good
	problem = check_homography(M, inliers, reference_img.shape, target_img.shape)
	if problem:
		raise Exception('NO HOMOGRAPHY', f"Failed to calculate Homography: {problem}")
	return M


def read_target_qr(target_img, M, qr_rect, scale=4, pad=12):
	"""
	* Read the QR code from the photograph, using the homography to rectify (and upscale) just the
	*  area around the QR code first, as it is usually too small / distorted to read in the raw photo
	"""

	# get the location of the QR code in the reference image
	left, top, width, height = qr_rect

	# make a homography that goes from the photo to an upscaled crop around the QR code (with padding for the quiet zone)
	T = array([[scale, 0, -(left - pad) * scale], [0, scale, -(top - pad) * scale], [0, 0, 1]])
	crop = warpPerspective(target_img, T @ M, ((width + 2 * pad) * scale, (height + 2 * pad) * scale))

	# read the QR code and return the uid (the last value)
	result = decode(crop, symbols=[ZBarSymbol.QRCODE])
	return result[0].data.decode("utf-8").split(",")[-1] if result else None


def find_map_homography(reference_img, target_img, lowe_distance, homo_matches, demo, magsac=False,
	downscale=1.5, min_markers=4, max_features=10000):
	"""
	* Identify one image inside another
	"""

	# first try to locate the map using the ArUco markers
	M = homography_from_markers(reference_img, target_img, magsac, min_markers, demo)

	# otherwise, fall back to SIFT
	if M is None:
		M = homography_from_sift(reference_img, target_img, lowe_distance, homo_matches, magsac, downscale, demo,
			max_features=max_features)
	return M


def extract_map(reference_img, target_img, lowe_distance, homo_matches, demo, **kwargs):
	"""
	* Identify one image inside another, extract and perspective transform
	"""

	# get the homography
	M = find_map_homography(reference_img, target_img, lowe_distance, homo_matches, demo, **kwargs)

	# apply the calculated transformation as a perspective transformation
	rows, cols = reference_img.shape
	return warpPerspective(target_img, M, (cols, rows))


def processImage(referenceImg, participantMap, lowe_distance, homo_matches, geodata, thresh, kernel, demo,
	magsac=False, downscale=1.5, max_features=10000, qr_rect=None, ignore_qr=False):
	"""
	* The image processing steps for extracting the markup data from the image
	"""

	# locate the map in the target image
	M = find_map_homography(referenceImg, participantMap, lowe_distance, homo_matches, demo,
		magsac=magsac, downscale=downscale, max_features=max_features)

	# verify that the photo matches the reference by reading the (rectified) QR code in the photo
	#  this matters most for marker layouts: the markers are the same on every layout, so a photo of
	#  one map will align perfectly with the reference for any other map, and the result will be wrong
	if qr_rect is not None:
		target_uid = read_target_qr(participantMap, M, qr_rect)

		# QR code could not be read - always warn for marker layouts (as we cannot otherwise tell whether
		#  the reference is correct), but only in verbose mode for older layouts (where it often fails)
		if target_uid is None:
			message = "the QR code in the photograph could not be read, so cannot verify that the reference image is correct"
			if detect_markers(referenceImg):
				print(f"WARNING: {message}")
			else:
				vprint(message[0].upper() + message[1:])

		# QR code does not match - this is an error unless the user has chosen to ignore it (e.g. for a
		#  map that has been regenerated with the same extent, which will have a new uid)
		elif target_uid != geodata[-1]:
			message = f"the QR code in the photograph ({target_uid}) does not match the reference image ({geodata[-1]})"
			if ignore_qr:
				print(f"WARNING: {message} - continuing anyway as --ignore_qr is set")
			else:
				raise Exception('WRONG REFERENCE', f"{message[0].upper() + message[1:]} - check that you are using the " \
					"correct reference image, or use --ignore_qr if you are sure that it is the same map")

		# QR code matches
		else:
			vprint(f"QR code in photograph matches reference ({target_uid})")

	# extract the map from the target image
	vprint("Warping image...")
	rows, cols = referenceImg.shape
	homoMap = warpPerspective(participantMap, M, (cols, rows))
	if demo:
		imwrite("./demo/3.warped.png", homoMap)

		# overlay the warped photo (magenta) on the reference (green) - misalignment shows as coloured fringes
		imwrite("./demo/3.overlay.png", dstack((homoMap, referenceImg, homoMap)))

	# crop homogrified result
	cropped_map = homoMap[int(geodata[6]):int(geodata[8]), int(geodata[5]):int(geodata[7])]
	if demo:
		imwrite("./demo/4.cropped.png", cropped_map)

	# threshold the image to extract markup
	vprint("Extracting markup with thresholding and morphology...")
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
	"""

	vprint(f"\nWriting output to GeoTIFF:")
	vprint(f"  - Dimensions: {opened_map.shape[1]} x {opened_map.shape[0]} pixels")
	vprint(f"  - CRS: EPSG:{geodata[4]}")

	# output dataset to raster
	with rio_open(output, 'w', driver='GTiff', height=opened_map.shape[0],
		width=opened_map.shape[1], count=1, dtype='uint8', crs="EPSG:" + geodata[4],
		transform=from_bounds(float(geodata[0]), float(geodata[1]), float(geodata[2]),
			float(geodata[3]), opened_map.shape[1], opened_map.shape[0])
	) as out:
		out.write(opened_map, 1)


def cleanWriteShapefile(output, opened_map, geodata, buffer, min_area, min_ratio, 
						convex_hull, centroid, representative_point, exterior, interior, uid):
	"""
	* Clean an output dataset and write to a shapefile
	"""

	vprint(f"Vectorizing and cleaning (min_area={min_area}, min_ratio={min_ratio}, buffer={buffer})...")

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
	feature_count = 0
	dropped_count = {'small': 0, 'ratio': 0, 'edge': 0}
	
	with fio_open(output, 'w', driver="ESRI Shapefile", crs=f"EPSG:{geodata[4]}",
		schema={'geometry': geom_type, 'properties': {'area':'float', 'uid':'int'}}) as out:

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
				dropped_count['small'] += 1
				continue

			# if wrong ratio between width & height of bounding box, drop
			sides = [geom.bounds[2] - geom.bounds[0], geom.bounds[3] - geom.bounds[1]]
			if min(sides) / max(sides) < min_ratio:
				dropped_count['ratio'] += 1
				continue

			# if intersects edge, clip it
			if geom.intersects(edge):
				dropped_count['edge'] += 1
				# TODO: subdivide into individual geoms
				geom = geom.difference(edge)

			# make sure that we haven't ended up with an empty geometry
			if geom.is_empty:
				continue

			# if convex hull is desired, save that
			if (convex_hull):
				out.write({'geometry': mapping(geom.convex_hull),
					'properties': {'area': geom.convex_hull.area, 'uid': uid}})
				feature_count += 1
			
			# if centroid is desired, save that
			elif (centroid):
				out.write({'geometry': mapping(geom.centroid),
					'properties': {'area': 0, 'uid': uid}})
				feature_count += 1

			# if rep point is desired, save that
			elif (representative_point):
				out.write({'geometry': mapping(geom.representative_point()),
					'properties': {'area': 0, 'uid': uid}})
				feature_count += 1
			
			# extract exterior ring from polygon
			elif (exterior):

				# handle MultiPolygons
				geoms = geom.geoms if geom.geom_type == 'MultiPolygon' else [geom]
				for g in geoms:
				
					# extract the exterior ring and convert to polygon
					polygon = Polygon(g.exterior.coords)
					out.write({'geometry': mapping(polygon),
						'properties': {'area': geom.area, 'uid': uid}})
					feature_count += 1
			
			# extract interior ring from polygon
			elif (interior):

				# handle MultiPolygons
				geoms = geom.geoms if geom.geom_type == 'MultiPolygon' else [geom]
				for g in geoms:
				
					# extract the interior ring and convert to polygon
					for int_geom in g.interiors:
						polygon = Polygon(int_geom.coords)
						out.write({'geometry': mapping(polygon),
							'properties': {'area': geom.area, 'uid': uid}})
						feature_count += 1

			# TODO: have a `holes` option that gets all polygons within each 
			# 	other polygon and adds them as holes to the constructor (or
			# 	differences them)

			# otherwise just save the raw geometry
			else:
				out.write({'geometry': mapping(geom),
					'properties': {'area': geom.area, 'uid': uid}})
				feature_count += 1
	
	vprint(f"  - Features written: {feature_count}")
	vprint(f"  - Features dropped:")
	vprint(f"    * Area too small: {dropped_count['small']}")
	vprint(f"    * Intersected edge: {dropped_count['edge']}")
	vprint(f"    * Aspect ratio too small: {dropped_count['ratio']}")
	vprint(f"  - Successfully written to {output}")


def run_extract(reference, target, output='out.shp', lowe_distance=0.5, thresh=100,
	kernel=3, homo_matches=12, frame=0, min_area=1000, min_ratio=0.2, buffer=10, uid=None, convex_hull=False,
	centroid=False, representative_point=False, exterior=False, interior=False, demo=False, verbose=False,
	magsac=False, downscale=1.5, max_features=10000, ignore_qr=False):
	"""
	* Main function: this runs the map extraction, resulting in a file being written
	*  to the desired location
	*
	* Registration options:
	* 	magsac: use MAGSAC rather than RANSAC to calculate the homography
	* 	downscale: shrink the photo to this multiple of the reference size for SIFT matching (0 to disable)
	* 	max_features: the maximum number of SIFT keypoints to use in each image (0 for no limit)
	*
	* 	ignore_qr: continue (with a warning) if the QR code in the photo does not match the reference
	"""

	# Set module-level verbose flag
	global _VERBOSE
	_VERBOSE = verbose

	vprint(f"\nExtracting markup: {target} -> {output}")
	vprint(f"Parameters: threshold={thresh}, kernel={kernel}, lowe_distance={lowe_distance}, min_matches={homo_matches}")
	vprint(f"Registration: method={'MAGSAC' if magsac else 'RANSAC'}, downscale={downscale}, max_features={max_features}")

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
		for f in glob("./demo/*.png") + glob("./demo/*.jpg"):
			remove(f)

		# print initial demo information
		print(f"reference: {reference}")
		print(f"target: {target}")
		print(f"output: {output}")

	# read in reference image and greyscale
	reference_np = imread(reference)
	if reference_np is None:
		raise Exception('UNREADABLE IMAGE', f"Cannot read reference image {reference}")
	reference_img = cvtColor(reference_np, COLOR_BGR2GRAY)
	if demo:
		imwrite("./demo/1.reference.png", reference_img)

	# catch HEIC/heif input file
	if Path(target).suffix.lower() in {".heic", ".heif"}:
		vprint("Converting HEIC/HEIF format...")
		if demo and not _VERBOSE:
			print("Converting HEIC/HEIF format...")
		
		# register HEIF opener with Pillow and open the file
		pillow_heif.register_heif_opener()
		pil_img = Image.open(target)

		# convert to NumPy array and greyscale (Pillow gives RGB rather than OpenCV's BGR)
		participant_map = cvtColor(array(pil_img.convert('RGB')), COLOR_RGB2GRAY)
	else:

		# read into numpy array
		ref_np = imread(target)
		if ref_np is None:
			raise Exception('UNREADABLE IMAGE', f"Cannot read target image {target}")

		# greyscale
		participant_map = cvtColor(ref_np, COLOR_BGR2GRAY)

	# add a frame around the participant map if requested
	if frame > 0:
		vprint(f"Adding frame (multiplier: {frame})")
		h, w = participant_map.shape

		# make a grey background that is 2 * frame larger then the image in each dimension
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

	# get metadata from QR code (and its location, which is used to find & read the QR code in the photo)
	try:
		qr = decode(reference_img, symbols=[ZBarSymbol.QRCODE])[0]
		geodata = qr.data.decode("utf-8").split(",")
		vprint(f"Map CRS: EPSG:{geodata[4]}, UUID: {geodata[-1]}")
		if demo and not _VERBOSE:
			print(f"Map CRS: EPSG:{geodata[4]}, UUID: {geodata[-1]}")
	except IndexError:
		raise Exception('NOT A PAPER2GIS MAP', "Reference image is not a Paper2GIS map")

	# run the image processing to get binary result array (this also checks the QR code in the photo matches)
	opened_map = processImage(reference_img, participant_map, lowe_distance, homo_matches, geodata, thresh, kernel, demo,
		magsac=magsac, downscale=downscale, max_features=max_features, qr_rect=qr.rect, ignore_qr=ignore_qr)

	# output to a raster if the output file extension is .tif (no cleaning)
	if output[-4:] == ".tif":
		# TODO: convert to vector, clean then rasterise
		writeTiff(output, opened_map, geodata)

	# clean the dataset and output to a vector if the output file extension is .shp
	elif output[-4:] == ".shp":
		cleanWriteShapefile(output, opened_map, geodata, buffer, min_area, min_ratio, 
		      convex_hull, centroid, representative_point, exterior, interior, uid)
	
	vprint("Extraction complete!")