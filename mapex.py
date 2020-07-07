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
* Jonathans-MBP:barra jonnyhuck$ python mapex.py --reference "out copy.png" --map "map.png"  --target samples/jonny.jpg --demo True --diff_threshold 218
"""

from sys import exit
from affine import Affine
from pyzbar.pyzbar import decode
from argparse import ArgumentParser
from rasterio import open as rio_open
from cv2.xfeatures2d import SIFT_create
from rasterio.transform import from_bounds
from numpy import float32, array, ones, uint8
from cv2 import findHomography, perspectiveTransform, warpPerspective, morphologyEx, \
	FlannBasedMatcher, threshold, adaptiveThreshold, imwrite, imread, cvtColor
from cv2 import THRESH_BINARY, RANSAC, ADAPTIVE_THRESH_GAUSSIAN_C, COLOR_BGR2GRAY, \
	MORPH_OPEN, THRESH_BINARY_INV


def homogrify(img2, img1, loweDistance):
	"""
	* Aligns two images so that they can be diffed more effectively
	"""

	# find the keypoints and descriptors with SIFT
	sift = SIFT_create()
	kp1, des1 = sift.detectAndCompute(img1, None)
	kp2, des2 = sift.detectAndCompute(img2, None)

	# do some FLANN matching
	flann = FlannBasedMatcher(dict(algorithm=0, trees=10), dict(checks=50))
	matches = flann.knnMatch(des1,des2,k=2)

	# store all the good matches as per Lowe's ratio test.
	good = []
	for m,n in matches:
		if m.distance < loweDistance * n.distance:
			good.append(m)

	# if there are not enough "good matches", report and exit
	# TODO: THIS SHOULD BE A USER ARGUMENT
	if len(good) < 12:
		print(f"Not enough matches are found - {len(good)}/{MIN_MATCH_COUNT}")
		exit()

	# get numpy arrays for each image
	src_pts = float32([ kp1[m.queryIdx].pt for m in good ]).reshape(-1,1,2)
	dst_pts = float32([ kp2[m.trainIdx].pt for m in good ]).reshape(-1,1,2)

	# do some homography
	M, mask = findHomography(src_pts, dst_pts, RANSAC,5.0)
	matchesMask = mask.ravel().tolist()

	# get corner coords
	h, w = img1.shape
	pts = float32([ [0,0], [0,h-1], [w-1,h-1], [w-1,0] ]).reshape(-1, 1, 2)

	# calculate the transormation required to align them
	dst = perspectiveTransform(pts, M)

	# Apply the calculated transformation as a perspective transformation
	rows, cols = img2.shape
	return warpPerspective(img1, M, (cols, rows))


# init and extract argument parser
parser = ArgumentParser(description='Extract Markup from a Paper2GIS map')
parser.add_argument('-r','--reference', help='the reference image', required = True)
parser.add_argument('-m','--map', help='the reference map', required = True)
parser.add_argument('-t','--target', help='the target image', required = True)
parser.add_argument('-o','--output', help='the name of the output file', required = False, default='out.tif')
parser.add_argument('-k','--kernel_size', help='the size of the kernel', required = False, default=5)
parser.add_argument('-b','--border_size', help='the border size', required = False, default=50)
parser.add_argument('-l','--lowe_distance', help='the lowe distance threshold', required = False, default=0.5)
parser.add_argument('-c','--diff_threshold', help='the % threshold for image differencing', required = False, default=90)
parser.add_argument('-d','--demo', help='the output data file', required = False, default=False)
args = parser.parse_args()

# output parameters just for user info
print("reference:" + args.reference)
print("target:" + args.target)
print("output:" + args.output)

# open the input files and greyscale them
# TODO: REPLACE THE MAP FILE WITH A CROP OUT OF THE ORIGINAL IMAGE VIA VALUES IN THE QR CODE
referenceMap = cvtColor(imread(args.map), COLOR_BGR2GRAY)
referenceImg = cvtColor(imread(args.reference), COLOR_BGR2GRAY)
participantMap = cvtColor(imread(args.target), COLOR_BGR2GRAY)
if args.demo:
	imwrite("./demo/1.png", referenceMap)
	imwrite("./demo/2.png", participantMap)

# extract the map from the target image
homoMap = homogrify(referenceMap, participantMap, args.lowe_distance)
if args.demo:
	imwrite("./demo/3.png", homoMap)

# get georeferencing data from QR code
geodata = decode(referenceImg)[0].data.decode("utf-8").split(",")
if args.demo:
	print('QR_DATA=', geodata)

# threshold the images to compare
ret1, thresh1 = threshold(referenceMap, int(args.diff_threshold), 255, THRESH_BINARY)
thresh2 = adaptiveThreshold(homoMap, 255, ADAPTIVE_THRESH_GAUSSIAN_C, THRESH_BINARY, 501, 2)
if args.demo:
	imwrite("./demo/4.png", thresh1)
	imwrite("./demo/5.png", thresh2)

# calculate the difference between the two images
diff = abs(thresh1 - thresh2)
if args.demo:
	imwrite("./demo/6.png", diff)

# 'open' the image to remove small gaps in markup coused by map features
opened = morphologyEx(diff, MORPH_OPEN, ones((int(args.kernel_size), int(args.kernel_size)), uint8))
if args.demo:
	imwrite("./demo/7.png", opened)

# threshold the differenced image
ret, out = threshold(opened, 60, 255, THRESH_BINARY_INV)
if args.demo:
	imwrite("./demo/8.png", out)

# output dataset to raster (hardcoded crs as was causing error)
with rio_open(args.output, 'w', driver='GTiff', height=out.shape[0],
	width=out.shape[1], count=1, dtype='uint8', crs="EPSG:" + geodata[4],
	transform=from_bounds(float(geodata[0]), float(geodata[1]),
		float(geodata[2]), float(geodata[3]), out.shape[1], out.shape[0])
) as output:
	output.write(out, 1)

print('done!')
