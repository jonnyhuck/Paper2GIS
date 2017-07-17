"""
Draw a quick and dirty scale bar onto a mapnik map

This is a slightly different version to the GitHub version, as it uses the PIL image
 dimensions to draw the scalebar, not the mapnik object (meaning that you can draw outside 
 of the map window)

@author jonnyhuck
"""

import mapnik
from math import floor, log10, ceil
from PIL import Image, ImageDraw, ImageFont

def mm2px(mm, dpi=96):
	"""
	1 inch = 25.4mm 96dpi is therefore...
	"""
	return int(ceil(mm * dpi / 25.4))
	

def addScaleBar(m, mapImg, left=False):
	"""
	* Add a scalebar to a map, at a sensible width of approx 20% the width of the map
	*
	* Parameters:
	*  - m: 		mapnik Map object
	*  - mapImg:	PIL Image object for the exported mapnik map
	*  - left:	boolean value describing whether it should be drawn on the left (True) or right (False)
	"""

	# get the m per pixel on the map
	mPerPx = m.scale()

	# how many metres is 20% of the width of the map?
	twentyPc = m.width * 0.2 * mPerPx

	# get the order of magnitude
	oom = 10 ** floor(log10(twentyPc))

	# get the desired width of the scalebar in m
	mScaleBar = round(twentyPc / oom) * oom

	# get the desired width of the scalebar in px
	pxScaleBar = round(mScaleBar/mPerPx)

	# make some text for the scalebar (sort units)
	if oom >= 1000:
		scaleText = str(int(mScaleBar/1000)) + "km"
	else:
		scaleText = str(int(mScaleBar)) + "m"
	
	# get PIL context to draw on
	draw = ImageDraw.Draw(mapImg)
	
	# dimensions of the PIL image (replaces use of m.width and m.height in the GitHub version)
	width, height = mapImg.size

	# prepare a font
	font = ImageFont.truetype('./open-sans/OpenSans-Regular.ttf', 12)
	
	# get the dimensions of the text
	tw, th = draw.textsize(scaleText, font=font)
	
	# set scale bar positioning parameters
	barBuffer  = mm2px(5)	# distance from scale bar to edge of image
	lBuffer    = 5	# distance from the line to the end of the background
	tickHeight = 12	# height of the tick marks
	
	# draw scale bar on bottom left...
	if left:
	
		# add background
		draw.rectangle([(pxScaleBar+lBuffer+lBuffer+barBuffer, 
			height-barBuffer-lBuffer-lBuffer-tickHeight),
			(barBuffer,height-barBuffer)], 
			outline=(0,0,0), fill=(255,255,255))
	
		# add lines
		draw.line([
			(lBuffer+pxScaleBar+barBuffer, height-tickHeight-barBuffer), 
			(lBuffer+pxScaleBar+barBuffer, height-lBuffer-barBuffer), 
			(lBuffer+barBuffer, height-lBuffer-barBuffer), 
			(lBuffer+barBuffer, height-tickHeight-barBuffer)], 
			fill=(0, 0, 0), width=1)
	
		# add label
		draw.text(( ((lBuffer+pxScaleBar+barBuffer+lBuffer)/2)-tw/2, 
			height-barBuffer-lBuffer-lBuffer-th), 
			scaleText, fill=(0,0,0), font=font)
	
	# ...or bottom right
	else:
			
		# add background
		draw.rectangle([(width-pxScaleBar-lBuffer-lBuffer-barBuffer, 
			height-barBuffer-lBuffer-lBuffer-tickHeight),
			(width-barBuffer,height-barBuffer)], 
			outline=(0,0,0), fill=(255,255,255))
	
		# add lines
		draw.line([
			(width-lBuffer-pxScaleBar-barBuffer, height-tickHeight-barBuffer), 
			(width-lBuffer-pxScaleBar-barBuffer, height-lBuffer-barBuffer), 
			(width-lBuffer-barBuffer, height-lBuffer-barBuffer), 
			(width-lBuffer-barBuffer, height-tickHeight-barBuffer)], 
			fill=(0, 0, 0), width=1)
	
		# add label
		draw.text(( 
			(width-lBuffer-pxScaleBar/2) - tw/2, 
			height-barBuffer-lBuffer-lBuffer-th), 
			scaleText, fill=(0,0,0), font=font)