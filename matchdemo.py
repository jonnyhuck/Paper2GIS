import sys, cv2, osr, gdal, zbar, getopt
import numpy as np
from PIL import Image

def drawMatches(img1, kp1, img2, kp2, matches):
    """
    My own implementation of cv2.drawMatches as OpenCV 2.4.9
    does not have this function available but it's supported in
    OpenCV 3.0.0

    This function takes in two images with their associated 
    keypoints, as well as a list of DMatch data structure (matches) 
    that contains which keypoints matched in which images.

    An image will be produced where a montage is shown with
    the first image followed by the second image beside it.

    Keypoints are delineated with circles, while lines are connected
    between matching keypoints.

    img1,img2 - Grayscale images
    kp1,kp2 - Detected list of keypoints through any of the OpenCV keypoint 
              detection algorithms
    matches - A list of matches of corresponding keypoints through any
              OpenCV keypoint matching algorithm
    """

    # Create a new output image that concatenates the two images together
    # (a.k.a) a montage
    rows1 = img1.shape[0]
    cols1 = img1.shape[1]
    rows2 = img2.shape[0]
    cols2 = img2.shape[1]

    # Create the output image
    # The rows of the output are the largest between the two images
    # and the columns are simply the sum of the two together
    # The intent is to make this a colour image, so make this 3 channels
    out = np.zeros((max([rows1,rows2]),cols1+cols2,3), dtype='uint8')

    # Place the first image to the left
    out[:rows1,:cols1] = np.dstack([img1, img1, img1])

    # Place the next image to the right of it
    out[:rows2,cols1:] = np.dstack([img2, img2, img2])

    # For each pair of points we have between both images
    # draw circles, then connect a line between them
    for mat in matches:

        # Get the matching keypoints for each of the images
        img1_idx = mat.queryIdx
        img2_idx = mat.trainIdx

        # x - columns
        # y - rows
        (x1,y1) = kp1[img1_idx].pt
        (x2,y2) = kp2[img2_idx].pt

        # Draw a small circle at both co-ordinates
        # radius 4
        # colour blue
        # thickness = 1
        cv2.circle(out, (int(x1),int(y1)), 4, (255, 0, 0), 1)   
        cv2.circle(out, (int(x2)+cols1,int(y2)), 4, (255, 0, 0), 1)

        # Draw a line in between the two points
        # thickness = 1
        # colour blue
        cv2.line(out, (int(x1),int(y1)), (int(x2)+cols1,int(y2)), (255,0,0), 1)


    # Show the image
    cv2.imshow('Matched Features', out)
    cv2.waitKey(0)
    cv2.destroyWindow('Matched Features')

    # Also return the image if you'd like a copy
    return out

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

		img3 = drawMatches(img1,kp1,img2,kp2,good)
# 		img3.save('matches.png')
		im = Image.fromarray(img3)
		im.save("matches.png")
		
		
		# calculate the transormation required to align them
		dst = cv2.perspectiveTransform(pts,M)
	
		# Apply the calculated transformation as a perspective transformation
		rows, cols = img2.shape
		return cv2.warpPerspective(img1, M, (cols, rows))

	else:
		print "Not enough matches are found - %d/%d" % (len(good),MIN_MATCH_COUNT)
		matchesMask = None
		return None
		

# open the input files and greyscale them
referenceMap = cv2.cvtColor(cv2.imread('Leh.png'),cv2.COLOR_BGR2GRAY)
participantMap = cv2.cvtColor(cv2.imread('99_walk.jpg'),cv2.COLOR_BGR2GRAY)

# extract the map from the target image
homoMap = homogrify(referenceMap, participantMap, 0.5)