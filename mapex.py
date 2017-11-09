import sys, cv2, osr, gdal, zbar, argparse
import numpy as np
from PIL import Image

def homogrify(img2, img1, loweDistance):
	"""
	* Aligns two images so that they can be diffed more effectively 
	"""
	
	# the number of matches required to line up the image
	MIN_MATCH_COUNT = 12 # used to be 10

	# Initiate SIFT detector
	sift = cv2.SIFT()

	# find the keypoints and descriptors with SIFT
	kp1, des1 = sift.detectAndCompute(img1, None)
	kp2, des2 = sift.detectAndCompute(img2, None)

	# do some FLANN matching nonsense...
	FLANN_INDEX_KDTREE = 0
	index_params = dict(algorithm = FLANN_INDEX_KDTREE, trees = 5)
	search_params = dict(checks = 50)
	flann = cv2.FlannBasedMatcher(index_params, search_params)
	matches = flann.knnMatch(des1,des2,k=2)

	# store all the good matches as per Lowe's ratio test.
	good = []
	for m,n in matches:
		if m.distance < loweDistance * n.distance: # used to be 0.7
			good.append(m)
	
	# if there are enough "good matches"
	if len(good)>MIN_MATCH_COUNT:
	
		# get numpy arrays for each image
		src_pts = np.float32([ kp1[m.queryIdx].pt for m in good ]).reshape(-1,1,2)
		dst_pts = np.float32([ kp2[m.trainIdx].pt for m in good ]).reshape(-1,1,2)

		# do some homography...
		M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC,5.0)
		matchesMask = mask.ravel().tolist()

		# get corner coords
		h, w = img1.shape
		pts = np.float32([ [0,0],[0,h-1],[w-1,h-1],[w-1,0] ]).reshape(-1,1,2)
		
		# calculate the transormation required to align them
		dst = cv2.perspectiveTransform(pts,M)
	
		# Apply the calculated transformation as a perspective transformation
		rows, cols = img2.shape
		return cv2.warpPerspective(img1, M, (cols, rows))

	else:
		print "Not enough matches are found - %d/%d" % (len(good),MIN_MATCH_COUNT)
		matchesMask = None
		return None


def qrToGeo(a):
	"""
	* Find and read the QR code, extracting the coordinates of the TL and BR corners
	"""
	
	# create a reader
	scanner = zbar.ImageScanner()

	# configure the reader
	scanner.parse_config('enable')
	
	# obtain image data
	pil = Image.fromarray(a).convert('L')
	width, height = pil.size
	raw = pil.tostring()

	# wrap image data
	image = zbar.Image(width, height, 'Y800', raw)

	# scan the image for barcodes
	scanner.scan(image)

	# extract results
	for symbol in image:
		data = symbol.data
		break

	# clean up
	del(image)
	
	# TODO: REMOVE THE REQUIREMENT TO DO THIS! 	
	data = data.replace('[', '')
	print data
	data = data[:-10]
	
	
	# parse and convert to numbers
	return np.array(data.split(",")).astype(np.float)


def getDiff(diffThreshold, refImg, tgtImg, demo):
	"""
	* Gets the difference between the two images (blur to denoise)
	"""

	# threshold the images
	ret1,thresh1 = cv2.threshold(refImg, diffThreshold, 255, cv2.THRESH_BINARY) #127	
	thresh2 = cv2.adaptiveThreshold(tgtImg,255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 501, 2)

	# calculate the difference between the two images
	diff = abs(thresh1 - thresh2)
	
	# write out demo files if required	  
	if demo:
		cv2.imwrite("4.png", thresh1)
		cv2.imwrite("5.png", thresh2)
		cv2.imwrite("6.png", diff)
	
	return diff


def toGeoTiff(geoData, w, h, filename):
	"""
	* Write the image to a geotiff
	"""

	# Opens source dataset
	src_ds = gdal.Open("diff.png")
	format = "PNG"
	driver = gdal.GetDriverByName(format)

	# Open destination dataset
	dst_ds = driver.CreateCopy(filename, src_ds, 0)

	# Specify raster location through geotransform array
	# (uperleftx, scalex, skewx, uperlefty, skewy, scaley)
	# Scale = size of one pixel in units of raster projection
	# this example below assumes 100x100
	# gt = [-7916400, 100, 0, 5210940, 0, -100]	# This comes from the QR code
	resolutionX = (geoData[2] - geoData[0]) / w
	resolutionY = (geoData[3] - geoData[1]) / h
	gt = [geoData[0], resolutionX, 0, geoData[1], 0, resolutionY]

	# Set location
	dst_ds.SetGeoTransform(gt)

	# Get raster projection
	epsg = int(geoData[4])
	srs = osr.SpatialReference()
	srs.ImportFromEPSG(epsg)
	dest_wkt = srs.ExportToWkt()

	# Set projection
	dst_ds.SetProjection(dest_wkt)

	# Close files
	dst_ds = None
	src_ds = None



parser = argparse.ArgumentParser(description='Extract Markup from a Paper2GIS map')
parser.add_argument('-r','--reference', help='the reference image', required = True)
parser.add_argument('-m','--map', help='the reference map', required = True)
parser.add_argument('-t','--target', help='the target image', required = True)
parser.add_argument('-o','--output', help='the name of the output file', required = False, default='out.tif')
parser.add_argument('-k','--kernel_size', help='the size of the kernel', required = False, default=7)
parser.add_argument('-b','--border_size', help='the border size', required = False, default=50)
parser.add_argument('-l','--lowe_distance', help='the lowe distance threshold', required = False, default=0.5)
parser.add_argument('-c','--diff_threshold', help='the % threshold for image differencing', required = False, default=90)
parser.add_argument('-d','--demo', help='the output data file', required = False, default=False)
args = parser.parse_args()

print "reference:" + args.reference
print "target:" + args.target
print "output:" + args.output

# open the input files and greyscale them
# TODO: REPLACE THE MAP FILE WITH A CROP OUT OF THE ORIGINAL IMAGE VIA VALUES IN THE QR CODE
referenceMap = cv2.cvtColor(cv2.imread(args.map),cv2.COLOR_BGR2GRAY)
referenceImg = cv2.cvtColor(cv2.imread(args.reference),cv2.COLOR_BGR2GRAY)
participantMap = cv2.cvtColor(cv2.imread(args.target),cv2.COLOR_BGR2GRAY)

# extract the map from the target image
homoMap = homogrify(referenceMap, participantMap, args.lowe_distance)

if args.demo:
	cv2.imwrite("1.png", referenceMap)
	cv2.imwrite("2.png", participantMap)
	cv2.imwrite("3.png", homoMap)
	
# get georeferencing data from QR code
geoData = qrToGeo(referenceImg)

if args.demo:
	print 'QR_DATA=', geoData
	
# diff the aligned maps
diffMap = getDiff(args.diff_threshold, referenceMap, homoMap, args.demo)

# erode and dilate the image to remove noise from the map alignment
kernel = np.ones((int(args.kernel_size), int(args.kernel_size)), np.uint8)
opened = cv2.morphologyEx(diffMap, cv2.MORPH_OPEN, kernel)

if args.demo:
	cv2.imwrite("7.png", opened)
	
# threshold the differenced image
ret,out = cv2.threshold(opened, 60, 255, cv2.THRESH_BINARY_INV)

# convert from numpy array to image
finalImg = Image.fromarray(out)

# write to file...
finalImg.save("diff.png")

# get the dimensions of the output image
h, w = out.shape

# georeference and write again
toGeoTiff(geoData, w, h, args.output)

# show if required
if args.demo:
	finalImg.show()