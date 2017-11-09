"""
Working towards implementing a 1-5 'multiple choice' scale to  be used in dempster-shaffer analysis
Will be merged into the extract tool...
"""

# import the necessary packages
from imutils.perspective import four_point_transform
from imutils import contours
import numpy as np
import argparse, imutils, cv2

# open the image
img = cv2.cvtColor(cv2.imread("out.png"),cv2.COLOR_BGR2GRAY)

# crop out the bit with the circles in it
crop_img = img[636:, 719:]

# apply Otsu's thresholding method to binarize the warped piece of paper
thresh = cv2.threshold(crop_img, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
	
# find contours in the thresholded image
contours = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
contours = contours[0] if imutils.is_cv2() else contours[1]

questionCnts = []

# loop over the contours
for c in contours:

	# compute the bounding box of the contour, 
	(x, y, w, h) = cv2.boundingRect(c)
	
	# then use the bounding box to derive the aspect ratio
	ar = w / float(h)
 
	# should be sufficiently wide, sufficiently tall, and have an aspect ratio approximately equal to 1
	if w >= 20 and h >= 20 and ar >= 0.9 and ar <= 1.1:
		questionCnts.append(c)

# sort the question contours left to right
boundingBoxes = [cv2.boundingRect(c) for c in questionCnts]
(contours, boundingBoxes) = zip(*sorted(zip(questionCnts, boundingBoxes), key=lambda b:b[1][0], reverse=False))

# confidence
ds_mass = 0

# loop over the sorted contours
for c in contours:

	# construct a mask that reveals only the current "bubble" for the question
	mask = np.zeros(thresh.shape, dtype="uint8")
	cv2.drawContours(mask, [c], -1, 255, -1)
	before = cv2.countNonZero(mask)

	# apply the mask to the thresholded image, then count the number of non-zero pixels in the bubble area
	mask = cv2.bitwise_and(thresh, thresh, mask=mask)
	after = cv2.countNonZero(mask)

	# get a mass value
	ds_mass += after / before
	
print "I can see", len(contours), "bubbles, with a mass of", ds_mass

# switch back to BGR and draw contours
# crop_img = cv2.cvtColor(crop_img,cv2.COLOR_GRAY2BGR)
# cv2.drawContours(crop_img, questionCnts, -1, (0,255,0), 2)

# show the result
# cv2.imshow("cropped", crop_img)
# cv2.waitKey(0)