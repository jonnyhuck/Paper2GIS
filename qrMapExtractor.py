import sys
import cv2
import osr
import gdal
import zbar
import math
import getopt
import numpy as np
from PIL import Image

##
# Aligns two images so that they can be diffed more effectively 
# @author jonnyhuck
##
def homogrify(img2, img1, loweDistance):

# Had a vague notion that this might be better as it will only compare the QR an ARUco codes,
#  possibly a slight improvement, but not massive, and certainly not perfect. A better 
# approach than this would be a blank versio of the map anyway
#     ret1, img1 = cv2.threshold(img1, 90, 255, cv2.THRESH_BINARY)
#     img2 = cv2.adaptiveThreshold(img2,255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 501, 2)

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



##
# Find and read the QR code, extracting the coordinates of the TL and BR corners
# @author jonnyhuck
##
def qrToGeo(a):
       
    # create a reader
    scanner = zbar.ImageScanner()

    # configure the reader
    scanner.parse_config('enable')
    
    # obtain image data
    pil = Image.fromarray(a).convert('L')
    width, height = pil.size
    raw = pil.tobytes()

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
    
    # parse and convert to numbers
    return np.array(data.split(",")).astype(np.float)



##
# Gets the difference between the two images (blur to denoise)
# @author jonnyhuck
##
def getDiff(diffThreshold, refImg, tgtImg, demo):

    ret1,thresh1 = cv2.threshold(refImg, diffThreshold, 255, cv2.THRESH_BINARY) #127
#     ret2,thresh2 = cv2.threshold(tgtImg, diffThreshold, 255, cv2.THRESH_BINARY) #127
    
    thresh2 = cv2.adaptiveThreshold(tgtImg,255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 501, 2)

    # calculate the difference between the two images
    diff = abs(thresh1 - thresh2)
    
    # write out demo files if required    
    if demo:
        cv2.imwrite("4.png", thresh1)
        cv2.imwrite("5.png", thresh2)
        cv2.imwrite("6.png", diff)
    
    # run through a harsh denoising filter and return
#     return cv2.fastNlMeansDenoising(diff, None, 100, 21, 7)
    return diff



##
# Write the image to a geotiff
# @author jonnyhuck
##
def toGeoTiff(geoData, w, h, filename):

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
    #gt = [-7916400, 100, 0, 5210940, 0, -100]  # This comes from the QR code
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


##
# Mask the QR Code, arUco tags and North Arrow (all likely to cause noise)
# Works because outputs are the same size as inputs...
# This takes in a CV Numpy Array Image and returns a PIL Image for saving, therefore is the
#  final step in the process.
# @author jonnyhuck
##
def doMasking(map, size, borderMask):

    # calculate sizes
    size = int(size)
    size2 = int(size / 2)
    size3 = int(size * 0.75)
    pil = Image.fromarray(map)
    w,h = pil.size

    # make a mask
    m1 = Image.new("RGB", (size,size), "white")
    m2 = Image.new("RGB", (size2,size2), "white")
    m3 = Image.new("RGB", (size3,size3), "white")
    m4 = Image.new("RGB", (w,borderMask), "white")
    m5 = Image.new("RGB", (borderMask,h), "white")

    # cover QR
    pil.paste(m1,(0,0))
    
    # cover arUco tags    
    pil.paste(m2,(w-size2,0))
    pil.paste(m2,(w-size2, h-size2))
    pil.paste(m2,(0, h-size2))
    
    # cover north arrow
    pil.paste(m3,(w-(size3+10), h-(size2+10+size3)))
    
    # cover border
    pil.paste(m4,(0,0))
    pil.paste(m4,(0,h-borderMask))
    pil.paste(m5,(0,0))
    pil.paste(m5,(w-borderMask,0))
    
    # clean up
    del(m1)
    del(m2)
    del(m3)
    del(m4)
    del(m5)
    
    return pil


##
# Main Function
# @author jonnyhuck
##
def main(argv):
   
    try:
        opts, args = getopt.getopt(argv, "hdsr:t:o:k:b:l:c:")
    except getopt.GetoptError:
        print 'python getMapQr.py -r reference.JPG -t participant.JPG -o out.tif'
        sys.exit(2)
    
    refFileName = '' # the reference image file path (produced with qrMapGenerator.py)
    tarFileName = '' # the target image file path (photograph / scan)
    outFileName = '' # the output GeoTiff file path
    kernelSize = 7 # the size of the noise reducing kernel
    borderSize = 50 # the size of the border mask
    loweDistance = 0.5 # the distance used in Lowes ration to filter control points in the homography
    diffThreshold = 90 # the threshold (0-255) for differencing
    demo = False # this is whether or not to make an image for every stage of the process (for testing)
    showMap = False # this is whether or not the map should be displayed on screen at the end

    # read in all of the arguments
    for opt, arg in opts:
        if opt == '-h':
            print 'python getMapQr.py -r reference.JPG -t participant.JPG -o out.tif'
            sys.exit()
        elif opt == '-r':
            refFileName = arg
        elif opt == '-t':
            tarFileName = arg
        elif opt == '-o':
            outFileName = arg
        elif opt == '-k':
            kernelSize = int(arg)
        elif opt == '-b':
            borderSize = int(arg)
        elif opt == '-l':
            loewDistance = float(arg)
        elif opt == '-c':
            diffThreshold = float(arg)
        elif opt == '-d':
            demo = True
        elif opt == '-s':
            showMap = True
            
    print "reference:" + refFileName
    print "target:" + tarFileName
    print "output:" + outFileName

    # open the input files and greyscale them
    referenceMap = cv2.cvtColor(cv2.imread(refFileName),cv2.COLOR_BGR2GRAY)
    participantMap = cv2.cvtColor(cv2.imread(tarFileName),cv2.COLOR_BGR2GRAY)

    # extract the map from the target image
    homoMap = homogrify(referenceMap, participantMap, loweDistance)
    
    if demo:
        cv2.imwrite("1.png", referenceMap)
        cv2.imwrite("2.png", participantMap)
        cv2.imwrite("3.png", homoMap)

    # get georeferencing data from QR code
    geoData = qrToGeo(referenceMap)

    # diff the aligned maps
    diffMap = getDiff(diffThreshold, referenceMap, homoMap, demo)
    
    
    
    # erode and dilate the image to remove noise from the map alignment
    kernel = np.ones((kernelSize,kernelSize), np.uint8) # was 3,3
#     kernel2 = np.ones((17,14), np.uint8)
    opened = cv2.morphologyEx(diffMap, cv2.MORPH_OPEN, kernel)
#     eroded = cv2.erode(diffMap, kernel)
#     opened = cv2.dilate(diffMap, kernel2)

    
    
    # threshold the differenced image
    ret,out = cv2.threshold(opened, 60, 255, cv2.THRESH_BINARY_INV)
#     ret,out = cv2.threshold(diffMap, 60, 255, cv2.THRESH_BINARY_INV)
    
    # mask out the QR code, arUco tags and north arrow, return as image
    finalImg = doMasking(out, geoData[5], borderSize)

    # write to file...
    finalImg.save("diff.png")

    # get the dimensions of the output image
    h, w = out.shape

    # georeference and write again
    toGeoTiff(geoData, w, h, outFileName)
    
    # show if required
    if(showMap):
        finalImg.show()


##
# Python nonsense...
# @author jonnyhuck
##
if __name__ == "__main__":
    main(sys.argv[1:])