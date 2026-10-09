"""
* ArUco marker settings shared between layout generation (gis2paper) and
*  extraction (paper2gis), so that both always use the same dictionary
*
* All sizes in pixels unless otherwise stated with _mm in variable name
*
* @author jonnyhuck
"""

from cv2 import aruco

# the marker dictionary - 4x4 bits gives large modules (easy to detect in low-res photos)
#  and 100 ids is plenty for a ring of markers around an A3 map
MARKER_DICT = aruco.DICT_4X4_100

# the size of one marker module (bit) in pixels at 96dpi (6px ~= 1.6mm)
MARKER_MODULE_PX = 6

# the number of modules across a marker (4 data bits + 1 black border bit each side)
MARKER_MODULES = 6

# the marker size in pixels (36px ~= 9.5mm at 96dpi)
MARKER_PX = MARKER_MODULE_PX * MARKER_MODULES


def get_dictionary():
	"""
	* Get the ArUco dictionary used by Paper2GIS
	* @author jonnyhuck
	"""
	return aruco.getPredefinedDictionary(MARKER_DICT)


def draw_marker(marker_id):
	"""
	* Draw a single marker as a numpy array (black and white, MARKER_PX square)
	* @author jonnyhuck
	"""
	return aruco.generateImageMarker(get_dictionary(), marker_id, MARKER_PX, borderBits=1)


def detect_markers(img):
	"""
	* Detect Paper2GIS ArUco markers in a greyscale image
	* @author jonnyhuck
	* @return a dict of {marker id: 4x2 numpy array of corner coordinates (tl, tr, br, bl)}
	"""

	# set up the detector, refining the corners to sub-pixel accuracy
	params = aruco.DetectorParameters()
	params.cornerRefinementMethod = aruco.CORNER_REFINE_SUBPIX
	detector = aruco.ArucoDetector(get_dictionary(), params)

	# detect the markers
	corners, ids, _ = detector.detectMarkers(img)

	# return empty if nothing was found
	if ids is None:
		return {}

	# otherwise return the corners of each marker, keyed by id
	return { int(i): c.reshape(4, 2) for i, c in zip(ids.flatten(), corners) }
