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
* python allinone.py --reference ./_template/the-used-one.png --target ./timnadata/IMG_9441.jpg -o ./out/path.tif --threshold 100 --kernel 0
* python allinone.py --reference ./_template/the-used-one.png --target ./timna/IMG_9423.jpg -o ./out/wind.tif --threshold 100 --kernel 0
*
* TODO:
*	- Need to implement frame option
* 	- Implement cleaning for raster outputs using: https://github.com/mapbox/rasterio/blob/fb93a6425c17f25141ad308cee7263d0c491a0a9/examples/rasterize_geometry.py
"""

from sys import exit
from glob import glob
from affine import Affine
from pyzbar.pyzbar import decode
from fiona import open as fio_open
from argparse import ArgumentParser
from rasterio.features import shapes
from os import remove, path, makedirs
from rasterio import open as rio_open
from cv2.xfeatures2d import SIFT_create
from rasterio.transform import from_bounds
from numpy import float32, array, ones, uint8
from shapely.geometry import shape, mapping, LineString
from cv2 import findHomography, perspectiveTransform, warpPerspective, morphologyEx, \
	FlannBasedMatcher, threshold, adaptiveThreshold, imwrite, imread, cvtColor, medianBlur
from cv2 import THRESH_BINARY, RANSAC, ADAPTIVE_THRESH_GAUSSIAN_C, COLOR_BGR2GRAY, \
	MORPH_OPEN, THRESH_BINARY_INV


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


def cleanWriteShapefile(output, opened_map, geodata, buffer, min_area, min_ratio, convex_hull):
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

	# write to shapefile
	with fio_open(output, 'w', driver="ESRI Shapefile", crs=f"EPSG:{geodata[4]}",
		schema={'geometry': 'Polygon', 'properties': {'area':'float'}}) as out:

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

			# if too small, drop (eitehr convex hull or regular geom)
			the_area = geom.convex_hull.area if convex_hull else geom.area
			if the_area < min_area:
				continue

			# if wrong ratio between width & height of bounding box, drop
			sides = [geom.bounds[2] - geom.bounds[0], geom.bounds[3] - geom.bounds[1]]
			if min(sides) / max(sides) < min_ratio:
				continue

			# if intersects edge, drop
			if geom.intersects(edge):
				continue

			# if convex hull is desired, save that
			if (convex_hull) :
				out.write({'geometry': mapping(geom.convex_hull),
					'properties': {'area': geom.convex_hull.area}})

			# otherwise just save the raw geometry
			else:
				out.write({'geometry': mapping(geom),
					'properties': {'area': geom.area}})

def run_map_extract(reference, target, output='out.shp', lowe_distance=0.5, thresh=100,
	kernel=3, homo_matches=12, min_area=1000, min_ratio=0.2, buffer=10, convex_hull=False,
	demo=False):
	"""
	* Main function: this runs the map extraction, resulting in a file being written
	*  to the desired location
	* @author jonnyhuck
	"""

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
	if args.demo:

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
	referenceImg = cvtColor(imread(reference), COLOR_BGR2GRAY)
	if demo:
		imwrite("./demo/1.reference.png", referenceImg)

	# read in participant map and greyscale
	participantMap = cvtColor(imread(target), COLOR_BGR2GRAY)
	if demo:
		imwrite("./demo/2.target.png", participantMap)

	# get metadata from QR code
	geodata = decode(referenceImg)[0].data.decode("utf-8").split(",")
	if demo:
		print('QR_DATA=', geodata)

	# verify that the target image matches the reference
	try:
		tmp_geodata = decode(participantMap)[0].data.decode("utf-8").split(",")
		if geodata[-1] != tmp_geodata[-1]:
			raise Exception('WRONG REFERENCE', "Target image does not match reference image")
	except IndexError:
		print("WARNING - can't read QR code in target image")

	# run the imageb processing to get binary result array
	opened_map = processImage(referenceImg, participantMap, lowe_distance,
		homo_matches, geodata, thresh, kernel, demo)

	# output to a raster if the output file extension is .tif (no cleaning)
	if output[-4:] == ".tif":
		writeTiff(output, opened_map, geodata)

	# clean the dataset and output to a vector if the output file extension is .shp
	elif output[-4:] == ".shp":
		cleanWriteShapefile(output, opened_map, geodata, buffer, min_area, min_ratio, convex_hull)



"""
* If this is run as a script, parse CLIs and call the main function
* @author jonnyhuck
"""
if __name__ == "__main__":

	# init argument parser
	parser = ArgumentParser(description='Extract Markup from a Paper2GIS map')

	# for the extraction
	parser.add_argument('-r','--reference', help='the reference image', required = True)
	parser.add_argument('-t','--target', help='the target image', required = True)
	parser.add_argument('-o','--output', help='the name of the output file', required = False, default='out.shp')
	parser.add_argument('-l','--lowe_distance', help='the lowe distance threshold', required = False, default=0.5)
	parser.add_argument('-k','--kernel', help='the size of the kernel used for opening the image', required = False, default=3)
	parser.add_argument('-i','--threshold', help='the threshold the target image', required = False, default=100)
	parser.add_argument('-m','--homo_matches', help='the number of matches required for homography', required = False, default=12)

	# TODO: Needs implementing
	parser.add_argument('-f','--frame', help='a frame to add round the image if the map is too close to the edge', required = False, default=0)

	# for vector data cleaning
	parser.add_argument('-a','--min_area', help='the area below which features will be rejected', required = False, default = 1000)
	parser.add_argument('-x','--min_ratio', help='the ratio (long/short) below which features will be rejected', required = False, default = 0.2)
	parser.add_argument('-b','--buffer', help='buffer around the edge used for data cleaning', required = False, default = 10)

	# for vector output - do you want a convex hull or not?
	parser.add_argument('-c','--convex_hull', help='do you want the raw output or a convex hull (vector only)?', required = False, default = False)

	# environment settings
	parser.add_argument('-d','--demo', help='the output data file', required = False, default = False)
	parser.add_argument('-e','--error_messages', help='suppress error messages', required = False, default = False)

	# parse args
	args = parser.parse_args()

	# extract the map and store the result in the tif file
	try:
		run_map_extract(args.reference, args.target, args.output, args.lowe_distance,
			int(args.threshold), int(args.kernel), int(args.homo_matches), int(args.min_area),
			float(args.min_ratio), int(args.buffer), args.convex_hull, args.demo)
	except Exception as e:
		print(f"ERROR: {e}")
		exit()
