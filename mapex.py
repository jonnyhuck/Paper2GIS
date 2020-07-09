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
* python mapex.py --reference "out.png"  --target samples/jonny6.jpg --demo True
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


def extract_map(reference_img, target_img):
	"""
	* Ideentify one image inside another, extract and transform
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
		if m.distance < args.lowe_distance * n.distance:
			good.append(m)

	# if there are not enough "good matches", report and exit
	if len(good) < int(args.homo_matches):
		print(f"Not enough matches are found - {len(good)}/{args.homo_matches}")
		exit()

	# get numpy arrays for each image
	src_pts = float32([ kp1[m.queryIdx].pt for m in good ]).reshape(-1,1,2)
	dst_pts = float32([ kp2[m.trainIdx].pt for m in good ]).reshape(-1,1,2)

	# do some homography
	M, mask = findHomography(src_pts, dst_pts, RANSAC, 10)
	if M is None:
		print("Failed to calculate Homography")
		exit()

	# get corner coords
	h, w = target_img.shape
	pts = float32([ [0,0], [0,h-1], [w-1,h-1], [w-1,0] ]).reshape(-1, 1, 2)

	# calculate the transormation required to align them
	dst = perspectiveTransform(pts, M)

	# Apply the calculated transformation as a perspective transformation
	rows, cols = reference_img.shape
	return warpPerspective(target_img, M, (cols, rows))


# init argument parser
parser = ArgumentParser(description='Extract Markup from a Paper2GIS map')
parser.add_argument('-r','--reference', help='the reference image', required = True)
parser.add_argument('-t','--target', help='the target image', required = True)
parser.add_argument('-o','--output', help='the name of the output file', required = False, default='out.tif')
parser.add_argument('-l','--lowe_distance', help='the lowe distance threshold', required = False, default=0.5)
parser.add_argument('-i','--threshold', help='the threshold the target image', required = False, default=100)
parser.add_argument('-m','--homo_matches', help='the number of matches required for homography', required = False, default=12)
parser.add_argument('-d','--demo', help='the output data file', required = False, default=False)

# parse args
args = parser.parse_args()
if args.demo:
	print("reference:" + args.reference)
	print("target:" + args.target)
	print("output:" + args.output)

# read in reference image and greyscale
referenceImg = cvtColor(imread(args.reference), COLOR_BGR2GRAY)
if args.demo:
	imwrite("./demo/1.png", referenceImg)

# get metadata from QR code
geodata = decode(referenceImg)[0].data.decode("utf-8").split(",")
if args.demo:
	print('QR_DATA=', geodata)

# crop reference image
referenceImg = referenceImg[int(geodata[6]):int(geodata[8]), int(geodata[5]):int(geodata[7])]
if args.demo:
	imwrite("./demo/2.png", referenceImg)

# read in participant map
participantMap = cvtColor(imread(args.target), COLOR_BGR2GRAY)
if args.demo:
	imwrite("./demo/3.png", participantMap)

# extract the map from the target image
homoMap = extract_map(referenceImg, participantMap)
if args.demo:
	imwrite("./demo/4.png", homoMap)

# threshold the image to extract markup
_, thresh_map = threshold(homoMap, int(args.threshold), 255, THRESH_BINARY_INV)
if args.demo:
# 	imwrite("./demo/4.png", thresh1)
	imwrite("./demo/5.png", thresh_map)

# output dataset to raster (hardcoded crs as was causing error)
with rio_open(args.output, 'w', driver='GTiff', height=thresh_map.shape[0],
	width=thresh_map.shape[1], count=1, dtype='uint8', crs="EPSG:" + geodata[4],
	transform=from_bounds(float(geodata[0]), float(geodata[1]), float(geodata[2]),
		float(geodata[3]), thresh_map.shape[1], thresh_map.shape[0])
) as output:
	output.write(thresh_map, 1)

print('done!')
