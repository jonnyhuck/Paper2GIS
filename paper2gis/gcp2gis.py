"""
* Extract data from marked up maps using Ground Control Points (GCPs) as part of the Paper2GIS system
*
* This is for photographs in which the map could not be located automatically. The user clicks the
*  four corners of the map (the inside corners of the black frame around the map) in the photograph
*  using the QGIS Georeferencer and saves them as a .points file. These are used to transform the
*  photograph so that the map is a rectangle that lines up with the reference image, and the markup
*  is then extracted exactly as it would be by the automatic extraction (see paper2gis.py).
*
* The georeferencing comes from the QR code on the reference image, so the map coordinates (mapX, mapY)
*  in the .points file (i.e. the real coordinates of the corners of the map) are only used to work out
*  which corner of the map each point is (so the points can be clicked in any order, and the map can be
*  at any orientation in the photograph), and to check that the reference image is the right one.
*
* All sizes in pixels unless otherwise stated with _mm in variable name
*
* @author jonnyhuck
"""

from csv import DictReader
from pathlib import Path
from numpy.linalg import norm
from numpy import float32, array, roll, argsort, arccos, degrees, dot, isnan, ptp, nan
from cv2 import getPerspectiveTransform, isContourConvex, cvtColor, COLOR_GRAY2BGR, circle, putText, \
	imwrite, FONT_HERSHEY_SIMPLEX, LINE_AA
from paper2gis.paper2gis import run_extract


# Module-level verbose flag
_VERBOSE = False

def vprint(*args, **kwargs):
	"""Print only if verbose mode is enabled"""
	if _VERBOSE:
		print(*args, **kwargs)


# the names of the corners of the map, in clockwise order (the same order as the corners from identify_corners)
CORNER_NAMES = ['top left', 'top right', 'bottom right', 'bottom left']


def to_float(value):
	"""
	* Convert a value from the .points file to a float
	* @return the float, or nan if it is missing or not a number
	"""
	try:
		return float(value)
	except (TypeError, ValueError):
		return nan


def read_points(points_file):
	"""
	* Read the GCPs from a QGIS Georeferencer .points file, which looks like:
	*
	* 	#CRS: ...
	* 	mapX,mapY,sourceX,sourceY,enable,dX,dY,residual
	* 	-251000,7075000,523.4,-456.7,1,0,0,0
	*
	* sourceY is negative in QGIS (as it is measured downwards from the top of the image)
	* @return two 4x2 numpy arrays: the pixel coordinates (x, y) and the map coordinates (x, y) of the enabled points
	"""

	# open the file, skipping any comment lines (e.g. the CRS)
	with open(points_file, encoding='utf-8-sig') as f:
		lines = [ line for line in f if line.strip() and not line.startswith('#') ]

	# read the rows and make sure that the pixel coordinates are there
	rows = list(DictReader(lines))
	if not rows or not {'sourceX', 'sourceY'} <= set(rows[0].keys()):
		raise Exception('INVALID POINTS FILE', f"{points_file} does not look like a QGIS .points file (no sourceX / sourceY columns)")

	# get the enabled points
	rows = [ r for r in rows if str(r.get('enable', '1')).strip().lower() not in ('0', 'false') ]

	# make sure that there is one point for each corner of the map
	if len(rows) != 4:
		raise Exception('WRONG NUMBER OF GCPS', f"{points_file} contains {len(rows)} enabled points, " \
			"but exactly 4 are needed (one at each corner of the map)")

	# get the pixel coordinates (QGIS stores y as negative, so use the absolute value) and the map coordinates
	pixels = array([ (float(r['sourceX']), abs(float(r['sourceY']))) for r in rows ], dtype=float32)
	map_coords = array([ (to_float(r.get('mapX')), to_float(r.get('mapY'))) for r in rows ])
	return pixels, map_coords


def identify_corners(pixels, map_coords):
	"""
	* Use the map coordinates from the .points file to work out which corner of the map each point is
	*  (the two points with the largest y are at the top, and of each pair the one with the smallest x
	*  is on the left), so that it doesn't matter which order they were clicked in
	* @return the 4x2 array of pixel coordinates in the order top left, top right, bottom right, bottom left
	"""

	# the map coordinates must be numbers that are spread out in both directions (i.e. the corners of the map)
	xs, ys = map_coords[:, 0], map_coords[:, 1]
	if isnan(map_coords).any() or ptp(xs) == 0 or ptp(ys) == 0:
		raise Exception('INVALID GCPS', "The map coordinates (mapX, mapY) in the points file are not the coordinates " \
			"of the four corners of the map - please enter these in QGIS for each point")

	# identify the corners from their map coordinates (top two by y, then left / right by x)
	order = argsort(-ys, kind='stable')
	top, bottom = order[:2], order[2:]
	tl, tr = top[argsort(xs[top], kind='stable')]
	bl, br = bottom[argsort(xs[bottom], kind='stable')]
	corners = pixels[[tl, tr, br, bl]]

	# make sure that they make a sensible shape (e.g. not a 'bow tie' due to a mis-placed point)
	if not isContourConvex(corners.reshape(-1, 1, 2)):
		raise Exception('INVALID GCPS', "The 4 points do not form a convex shape in the photograph - please check that " \
			"there is exactly one point at each corner of the map, and that each has the right map coordinates")

	# ...that goes clockwise in the photograph (otherwise the map coordinates don't match the points, e.g. top
	#  and bottom are swapped), using the shoelace formula (positive is clockwise, as y is downwards in the photo)
	nxt = roll(corners, -1, axis=0)
	if (corners[:, 0] * nxt[:, 1] - nxt[:, 0] * corners[:, 1]).sum() <= 0:
		raise Exception('INVALID GCPS', "The map coordinates in the points file do not match the positions of the " \
			"points in the photograph (e.g. top and bottom are swapped) - please check the map coordinates in QGIS")

	# ...and that is roughly rectangular, allowing for perspective (every angle between 30 and 150 degrees)
	for i in range(4):
		a, b = corners[i - 1] - corners[i], corners[(i + 1) % 4] - corners[i]
		angle = degrees(arccos(dot(a, b) / (norm(a) * norm(b))))
		if not 30 <= angle <= 150:
			raise Exception('INVALID GCPS', f"The 4 points do not look like the corners of the map (the {CORNER_NAMES[i]} " \
				f"angle is {angle:.0f} degrees) - please check that there is exactly one point at each corner of the map")

	return corners


def homography_from_gcps(reference_img, target_img, corners, map_coords, geodata, demo):
	"""
	* Calculate the homography that transforms the four corners of the map in the photograph onto the
	*  corners of the map in the reference image, checking that the map coordinates in the points file
	*  match the extent of the reference image
	* @return the homography
	"""

	# make sure that all of the points are actually inside the photograph
	h, w = target_img.shape
	if (corners < 0).any() or (corners[:, 0] > w).any() or (corners[:, 1] > h).any():
		raise Exception('INVALID GCPS', f"Some of the points are outside the photograph ({w} x {h} pixels) - " \
			"please check that the .points file was made for this photograph")

	# check that the map coordinates match the extent of the reference image (to within 1% of its size)
	#  - if not, the reference image or the points file is probably wrong
	extent = array([ float(v) for v in geodata[:4] ])
	points_extent = array([ map_coords[:, 0].min(), map_coords[:, 1].min(), map_coords[:, 0].max(), map_coords[:, 1].max() ])
	tolerance = 0.01 * max(extent[2] - extent[0], extent[3] - extent[1])
	if (abs(points_extent - extent) > tolerance).any():
		print(f"WARNING: the map coordinates in the points file ({', '.join(f'{v:.0f}' for v in points_extent)}) " \
			f"do not match the extent of the reference image ({', '.join(f'{v:.0f}' for v in extent)}) - " \
			"please check that you are using the correct reference image")

	# match the corners in the photograph to the corners of the map in the reference image (from the QR code)
	x0, y0, x1, y1 = [ int(v) for v in geodata[5:9] ]
	M = getPerspectiveTransform(corners, float32([ [x0, y0], [x1, y0], [x1, y1], [x0, y1] ]))

	# plot the points on the photograph for demo, labelled with the map corner that each one is
	if demo:
		gcp_img = cvtColor(target_img, COLOR_GRAY2BGR)
		size = max(h, w) / 1000
		for (x, y), name in zip(corners, CORNER_NAMES):
			circle(gcp_img, (int(x), int(y)), int(10 * size), (0, 0, 255), int(3 * size))
			putText(gcp_img, name, (int(x + 15 * size), int(y - 15 * size)), FONT_HERSHEY_SIMPLEX, size, (0, 0, 255), int(2 * size), LINE_AA)
		imwrite('demo/2.gcps.jpg', gcp_img)

	return M


def run_gcp(reference, target, points=None, output='out.shp', thresh=100, kernel=3, min_area=1000,
	min_ratio=0.2, buffer=10, uid=None, convex_hull=False, centroid=False, representative_point=False,
	exterior=False, interior=False, ignore_qr=False, demo=False, verbose=False):
	"""
	* Main function: this runs the map extraction using GCPs, resulting in a file being written
	*  to the desired location. The options are the same as for run_extract (paper2gis.py), plus:
	*
	* 	points: the QGIS .points file containing the four corners of the map (defaults to the name
	* 		that QGIS gives it, i.e. the target file name with .points on the end)
	"""

	# Set module-level verbose flag
	global _VERBOSE
	_VERBOSE = verbose

	# use the default QGIS file name for the points if none is given
	if points is None:
		points = target + '.points'

	# read the corners of the map from the points file and put them in order
	vprint(f"\nReading GCPs from {points}")
	if not Path(points).is_file():
		raise FileNotFoundError(f"{points} does not exist")
	pixels, map_coords = read_points(points)
	corners = identify_corners(pixels, map_coords)
	vprint("Map corners in photograph: " + ', '.join(f'{n} ({x:.0f}, {y:.0f})' for n, (x, y) in zip(CORNER_NAMES, corners)))

	# HEIC photos may be rotated differently in QGIS, as their orientation is handled differently to JPEG
	if Path(target).suffix.lower() in {".heic", ".heif"}:
		print("WARNING: if the result does not line up with the map, convert the photograph to JPEG and " \
			"make the .points file from that instead")

	# run the extraction, using the GCPs to locate the map (rather than the automatic detection) and
	#  reading the photograph the same way as QGIS (without EXIF rotation) so that the GCPs line up
	run_extract(reference, target, output, thresh=thresh, kernel=kernel, min_area=min_area, min_ratio=min_ratio,
		buffer=buffer, uid=uid, convex_hull=convex_hull, centroid=centroid, representative_point=representative_point,
		exterior=exterior, interior=interior, demo=demo, verbose=verbose, ignore_qr=ignore_qr, ignore_exif=True,
		register=lambda reference_img, target_img, geodata, demo: homography_from_gcps(reference_img, target_img,
			corners, map_coords, geodata, demo))
