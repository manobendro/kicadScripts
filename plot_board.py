'''
	A python script to create Nice looking board previews.

	These can be used for textures in MCAD tools to cever up the bland STEP board model.
'''

import sys
import os
import pcbnew
import time

import re
import logging
import shutil
import subprocess

import xml.etree.ElementTree as ET

from pcbnew import *
from datetime import datetime
from shutil import copy

def unique_prefix():
	unique_prefix.counter += 1
	return "pref_" + str(unique_prefix.counter)
unique_prefix.counter = 0

def ki2dmil(val):
	return val / 2540

def kiColour(val):
	return (val & 0xFF0000 >> 24) / 255


class BBox:
	def __init__(self, xl=None, yl=None, xh=None, yh=None):
		self.xl = xl
		self.xh = xh
		self.yl = yl
		self.yh = yh

	def __str__(self):
		return "({},{} {},{})".format(self.xl, self.yl, self.xh, self.yh)
		
	def addPoint(self, pt):
		self.xl = mymin(self.xl, pt.x)
		self.xh = mymax(self.xh, pt.x)
		self.yl = mymin(self.yl, pt.y)
		self.yh = mymax(self.yh, pt.y)

	def addPointBloatXY(self, pt, x, y):
		self.xl = mymin(self.xl, pt.x-x)
		self.xh = mymax(self.xh, pt.x+x)
		self.yl = mymin(self.yl, pt.y-y)
		self.yh = mymax(self.yh, pt.y+y)

class svgObject(object):
	# Open an SVG file
	def openSVG(self, filename):
		prefix = unique_prefix() + "_"
		root = ET.parse(filename)
		self.bbox = BBox()
		
		# We have to ensure all Ids in SVG are unique. Let's make it nasty by
		# collecting all ids and doing search & replace
		# Potentially dangerous (can break user text)
		ids = []
		for el in root.getiterator():
			if "id" in el.attrib and el.attrib["id"] != "origin":
				ids.append(el.attrib["id"])
		with open(filename) as f:
			content = f.read()
		for i in ids:
			content = content.replace("#"+i, "#" + prefix + i)

		root = ET.fromstring(content)
		# Remove SVG namespace to ease our lifes and change ids
		for el in root.getiterator():
			if "id" in el.attrib and el.attrib["id"] != "origin":
				el.attrib["id"] = prefix + el.attrib["id"]
			if '}' in str(el.tag):
				el.tag = el.tag.split('}', 1)[1]
		self.svg = root

		# parse all polyline points into a BBox
		for el in root.getiterator():
			if el.tag == 'polyline':
				points = el.attrib['points'];
				# use re to parse through points

				#add them to the BBox


		

	# Create a Blank SVG
	def createSVG(self):
		self.et = ET.ElementTree(ET.fromstring("""<svg width="29.7002cm" height="21.0007cm" viewBox="0 0 116930 82680 ">
<title>Picutre generated by pcb2svg</title>
<desc>Picture generated by pcb2svg</desc>
<defs> </defs>
</svg>"""))
		self.svg = self.et.getroot()

	# Wrap all image data into a group and return that group
	def extractImageAsGroup(self):
		wrapper = ET.Element('g')
		wrapper.extend(self.svg.iter('g'))
		return wrapper

#	def addAttributesToElement(self,element, attrs):
#		for k,v in attrs.items():
#			element.setAttribute(k,v)

	def reColour(self, transform_function):
		# Set fill and stroke on all groups
		for group in self.svg.findall('g'):
			svgObject._apply_transform(group, {
				'fill': transform_function,
				'stroke': transform_function,
			})

	@staticmethod
	def _apply_transform(node, values):
		original_style = node.attrib['style']
		for (k,v) in values.items():
			escaped_key = re.escape(k)
			m = re.search(r'\b' + escaped_key + r':(?P<value>[^;]*);', original_style)
			if m:
				transformed_value = v(m.group('value'))
				original_style = re.sub(
					r'\b' + escaped_key + r':[^;]*;',
					k + ':' + transformed_value + ';',
					original_style)
		node.attrib['style'] = original_style

	def addSvgImage(self, svgImage):
		imageGroup = svgImage.extractImageAsGroup()
		self.svg.append(imageGroup)
		if bMirrorMode:
			imageGroup.attrib['transform'] = "scale(-1,1)"
	
	def addholes(self, holeData):
		defs = self.svg.find('defs')
		self.svg.append(holeData)
		if bMirrorMode:
			holeData.attrib['transform'] = "scale(-1,1)"

	def addSvgImageInvert(self, svgImage, colour):
		defs = self.svg.find('defs')
		newMask = ET.SubElement(defs,'mask', id="test-a", 
		width="{}".format(ki2dmil(bb.GetWidth())),
		height="{}".format(ki2dmil(bb.GetHeight())),
		x="{}".format(ki2dmil(bb.GetX())),
		y="{}".format(ki2dmil(bb.GetY())))
		if bMirrorMode:
			newMask.attrib['transform'] = "scale(-1,1)"
		
		
		imageGroup = svgImage.extractImageAsGroup()
		newMask.append(imageGroup)

		rect = ET.SubElement(newMask, 'rect',  
		width="{}".format(ki2dmil(bb.GetWidth())),
		height="{}".format(ki2dmil(bb.GetHeight())),
		x="{}".format(ki2dmil(bb.GetX())),
		y="{}".format(ki2dmil(bb.GetY())),
		style="fill:#FFFFFF; fill-opacity:1.0;")


		#create a rectangle to mask through
		wrapper = ET.SubElement(self.svg, 'g',
		style="fill:{}; fill-opacity:0.8; mask:url(#test-a);".format(colour))
		rect = ET.SubElement(wrapper, 'rect', 
		width="{}".format(ki2dmil(bb.GetWidth())),
		height="{}".format(ki2dmil(bb.GetHeight())),
		x="{}".format(ki2dmil(bb.GetX())),
		y="{}".format(ki2dmil(bb.GetY())))


		if bMirrorMode:
			wrapper.attrib['transform'] = "scale(-1,1)"

	def write(self, filename):
		with open(filename, 'wb') as output_file:
			self.et.write(output_file)




def get_hole_mask(board):
	mask = ET.Element( "g", id="hole-mask")
	container = ET.SubElement(mask, "g", style="opacity:0.8;")

	# Print all Drills
	for mod in board.GetModules():
		for pad in mod.Pads():
			pos = pad.GetPosition()
			pos.x = ki2dmil(pos.x)
			pos.y = ki2dmil(pos.y)
			size = ki2dmil(pad.GetDrillSize()[0]) # Tracks will fail with Get Drill Value

			stroke = size
			length = 0.1
			points = "{} {} {} {}".format(0, -length / 2, 0, length / 2)
			el = ET.SubElement(container, "polyline")
			el.attrib["stroke-linecap"] = "round"
			el.attrib["stroke"] = "black"
			el.attrib["stroke-width"] = str(stroke)
			el.attrib["points"] = points
			el.attrib["transform"] = "translate({} {})".format(
				pos.x, pos.y)	

	# Print all Vias
	for track in board.GetTracks():
		try:
			pos = track.GetPosition()
			pos.x = ki2dmil(pos.x)
			pos.y = ki2dmil(pos.y)
			size = ki2dmil(track.GetDrillValue()) # Tracks will fail with Get Drill Value
		except:
			continue
		stroke = size
		length = 0.1
		points = "{} {} {} {}".format(0, -length / 2, 0, length / 2)
		el = ET.SubElement(container, "polyline")
		el.attrib["stroke-linecap"] = "round"
		el.attrib["stroke"] = "black"
		el.attrib["stroke-width"] = str(stroke)
		el.attrib["points"] = points
		el.attrib["transform"] = "translate({} {})".format(
			pos.x, pos.y)
		
		

	return mask


def plot_layer(layer_info):
	pctl.SetLayer(layer_info[1])
	pctl.OpenPlotfile(layer_info[0], PLOT_FORMAT_SVG, layer_info[2])
	pctl.PlotLayer()
	time.sleep(0.01)
	pctl.ClosePlot()
	return pctl.GetPlotFileName()


def render(plot_plan, output_filename):
	canvas = svgObject()
	canvas.createSVG()
	for layer_info in plot_plan:

		plot_layer(layer_info)
		
		svgData = svgObject()
		svgData.openSVG(pctl.GetPlotFileName())

		if layer_info[4] == "Invert":
			canvas.addSvgImageInvert(svgData, layer_info[5]);
		else:
			def colorize(original):
				# For invert to work we need to invert default colours. 
				if original.lower() == '#000000':
					return layer_info[5]
				return original
			svgData.reColour(colorize)
			
			canvas.addSvgImage(svgData)

	# Drills are seperate from Board layers. Need to be handled differently
	canvas.addholes(get_hole_mask(board))
	
	print 'Merging layers...'
	final_svg = os.path.join(temp_dir, project_name + '-merged.svg')
	canvas.write(final_svg)

	print 'Rasterizing...'
	final_png = os.path.join(output_directory, output_filename)

	subprocess.check_call([
		'C:\Program Files\Inkscape\inkscape',
		'--export-area-drawing',
		'--export-dpi=600',
		'--export-png', final_png,
		'--export-background', plot_bg,
		final_svg,
	])


#Slight hack for etree. to remove 'ns0:' from output
ET.register_namespace('', "http://www.w3.org/2000/svg")


filename=sys.argv[1]
project_name = os.path.splitext(os.path.split(filename)[1])[0]
project_path = os.path.abspath(os.path.split(filename)[0])

output_directory = os.path.join(project_path,'plot')

temp_dir = os.path.join(output_directory, 'temp')
shutil.rmtree(temp_dir, ignore_errors=True)
try:
	os.makedirs(temp_dir)
except:
	print 'folder exists'

today = datetime.now().strftime('%Y%m%d_%H%M%S')

board = LoadBoard(filename)

pctl = PLOT_CONTROLLER(board)

popt = pctl.GetPlotOptions()

popt.SetOutputDirectory(temp_dir)

# Set some important plot options:
popt.SetPlotFrameRef(False)
popt.SetLineWidth(FromMM(0.35))

popt.SetAutoScale(False)
popt.SetScale(1)
popt.SetMirror(False)
popt.SetUseGerberAttributes(False)
popt.SetExcludeEdgeLayer(True);
popt.SetScale(1)
popt.SetUseAuxOrigin(False)
popt.SetNegative(False)
popt.SetPlotReference(False)
popt.SetPlotValue(False)
popt.SetPlotInvisibleText(False)
popt.SetDrillMarksType(PCB_PLOT_PARAMS.FULL_DRILL_SHAPE)
pctl.SetColorMode(False)

# This by gerbers only (also the name is truly horrid!)
popt.SetSubtractMaskFromSilk(False) #remove solder mask from silk to be sure there is no silk on pads
bb = board.ComputeBoundingBox()





bMirrorMode = False
plot_bg = '#064A00'
# Once the defaults are set it become pretty easy...
# I have a Turing-complete programming language here: I'll use it...
# param 0 is a string added to the file base name to identify the drawing
# param 1 is the layer ID
plot_plan = [
	( "CuTop", F_Cu, "Top layer", ".gtl", "",'#E8D959',0.85 ),
	( "MaskTop", F_Mask, "Mask top", ".gts", "Invert" ,'#1D5D17',0.8 ),
	( "PasteTop", F_Paste, "Paste Top", ".gtp", "" ,'#9E9E9E',0.95 ),
	( "SilkTop", F_SilkS, "Silk Top", ".gto", "" ,'#fefefe',1.0 ),
	( "EdgeCuts", Edge_Cuts, "Edges", ".gml", ""  ,'#000000',0.2 ),
]
#renderPNG(plot_plan, project_name + '-Front.png')
render(plot_plan, project_name + '-Front.png')

bMirrorMode = True
plot_plan = [
	( "CuBottom", B_Cu, "Bottom layer", ".gbl", "",'#E8D959',0.85 ),
	( "MaskBottom", B_Mask, "Mask Bottom", ".gbs", "Invert" ,'#1D5D17',0.8 ),
	( "PasteBottom", B_Paste, "Paste Bottom", ".gbp", "" ,'#9E9E9E',0.95 ),
	( "SilkTop", B_SilkS, "Silk Bottom", ".gbo", "" ,'#fefefe',1.0 ),
	( "EdgeCuts", Edge_Cuts, "Edges", ".gml", ""  ,'#000000',0.2 ),
]
#renderPNG(plot_plan, project_name + '-Back.png')


render(plot_plan, project_name + '-Back.png')

shutil.rmtree(temp_dir, ignore_errors=True)
# We have just generated your plotfiles with a single script
