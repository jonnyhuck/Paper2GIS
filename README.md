# Paper2GIS

Paper2GIS is a participatory GIS / mapping platform that allows participants to draw markup onto a paper map (using a **thick black marker pen**), which can then be automatically extracted into georeferenced Shapefile or GeoTiff datasets. THis is intended to reduce the impact of *digital divides* on the collection of participatory map data. Paper2GIS was created in 2016 for students to use on a field course in the Indian Himalaya. It has since been used for a range of teaching research applications, some of which are listed in the [References](#references) section of this document. 

The figure below (reproduced from [Denwood et al., 2022](https://link.springer.com/article/10.1007/s10109-022-00386-6)) briefly describes the process: A) take an image of a Paper2GIS layout with markup. The software then identifies B) the layout in the photograph, C) the map in the layout, D) the markup on the map, and extracts it either to a Shapefile or a GeoTiff.

![Paper2GIS Workflow](https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Fs10109-022-00386-6/MediaObjects/10109_2022_386_Fig4_HTML.jpg?as=webp)

Paper2GIS no longer supports map production via Mapnik Stylesheets, as the Mapnik [Python Bindings](https://github.com/mapnik/python-mapnik)  are challenging for people to build and appear to have very limited support / development at the moment. Instead, you now must provide a map image that will be used instead. For now, I would recommend making your map **1084 x 1436 @ 96dpi**, and ensuring that there are no very rark areas (e.g. prominent black labels), which may be misinterpreted as markup. 

It is always good to thoroughly test the extractor before using a Paper2GIS layout 'in the wild', and remember that the extract software has loads of settings to help make sure that you get a nice result!

## Contents:

* [Usage](#usage)
* [Installation](#installation)
* [Bulk Extraction of Shapefiles](#bulk-extraction-of-shapefiles)
* [Future Development](#future-development)
* [Licensing](#licensing)
* [References](#references)

## Usage

Paper2GIS accessed via a Python-based CLI package (`p2g.py`) that can be used to: 

### Create a Paper2GIS layout from a map image (`p2g.py generate`)

Example call with a pre-existing map (`1084 x 1436px @ 96dpi`):

```
python p2g.py generate -a -2462672.600 -b 9330748.585 -c -2393838.600 -d 9421934.585
```

Example call with a map drawn using OSM tiles:

```
python p2g.py generate -a -2462672.600 -b 9330748.585 -c -2393838.600 -d 9421934.585 -i test.png -o test2.png -t True -z 10
```

Full details:

```
usage: Paper2GIS generate [-h] -a BL_X -b BL_Y -c TR_X -d TR_Y [-e EPSG] [-r RESOLUTION] [-i INPUT] [-o OUTPUT] [-t {True,False}]
                          [-f FADE] [-z ZOOM]

options:
  -h, --help            show this help message and exit
  -a BL_X, --bl_x BL_X  bottom left x coord
  -b BL_Y, --bl_y BL_Y  bottom left y coord
  -c TR_X, --tr_x TR_X  top right x coord
  -d TR_Y, --tr_y TR_Y  top right y coord
  -e EPSG, --epsg EPSG  EPSG code for the map CRS
  -r RESOLUTION, --resolution RESOLUTION
                        Resolution of the input map image (dpi)
  -i INPUT, --input INPUT
                        the input map image (file path) - this is ignored if --tiles=True
  -o OUTPUT, --output OUTPUT
                        the output data file (file path)
  -t {True,False}, --tiles {True,False}
                        create a OSM map (ignores --input)
  -f FADE, --fade FADE  intensity of the white filter over the tiles (0-255)
  -z ZOOM, --zoom ZOOM  requested zoom level of OSM tiles (necessary if using tiles)
```

### Extract markup from an image of a used Paper2GIS layout (`p2g.py extract`)

Example call:

```
python p2g.py extract --reference map.png --target in.jpg -o out.shp --threshold 100 --kernel 0
```

Full details:

```
usage: Paper2GIS extract [-h] -r REFERENCE -t TARGET [-o OUTPUT] [-l LOWE_DISTANCE] [-k KERNEL] [-i THRESHOLD] [-m HOMO_MATCHES] [-f FRAME] [-a MIN_AREA]
                         [-x MIN_RATIO] [-b BUFFER] [-c {True,False}] [-d {True,False}] [-e {True,False}]

options:
  -h, --help            show this help message and exit
  -r REFERENCE, --reference REFERENCE
                        the reference image
  -t TARGET, --target TARGET
                        the target image
  -o OUTPUT, --output OUTPUT
                        the name of the output file
  -l LOWE_DISTANCE, --lowe_distance LOWE_DISTANCE
                        the lowe distance threshold
  -k KERNEL, --kernel KERNEL
                        the size of the kernel used for opening the image
  -i THRESHOLD, --threshold THRESHOLD
                        the threshold the target image
  -m HOMO_MATCHES, --homo_matches HOMO_MATCHES
                        the number of matches required for homography
  -f FRAME, --frame FRAME
                        a frame to add round the image if the map is too close to the edge
  -a MIN_AREA, --min_area MIN_AREA
                        the area below which features will be rejected
  -x MIN_RATIO, --min_ratio MIN_RATIO
                        the ratio (long/short) below which features will be rejected
  -b BUFFER, --buffer BUFFER
                        buffer around the edge used for data cleaning
  -c {True,False}, --convex_hull {True,False}
                        do you want the raw output or a convex hull (vector only)?
  -d {True,False}, --demo {True,False}
                        the output data file
  -e {True,False}, --error_messages {True,False}
                        suppress error messages
```

## Installation

The below examples use conda to manage the Python installations, but there is no reason that you could not do this with `pip` and `vitrualenv`, or any other similar package management / virtual environment system.

### Mac

* Install X Code tools:

```bash
xcode-select --install
```

* Install Homebrew:

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

* Install C library dependencies:

```bash
brew install zbar opencv gdal geos imagemagick
```

* [Install Miniconda / Anaconda](https://docs.conda.io/projects/continuumio-conda/en/latest/user-guide/install/macos.html)

* Set up conda environment (note the need to use `pip` for `opencv-contrib-python`):

```bash
conda create -n paper2gis -c conda-forge -y python=3 fiona rasterio pyzbar qrcode pillow cartopy 
conda activate paper2gis
pip install opencv-contrib-python
```

* Get Paper2GIS:

```bash
git clone git@github.com:jonnyhuck/Paper2GIS.git
cd paper2gis-master
```

### Linux (Ubuntu)

* Install C library dependencies:

```bash
sudo apt install libopencv-dev python3-opencv libgdal-dev gdal-bin libzbar0 libgeos3.10.2
```

* [Install Miniconda / Anaconda](https://docs.conda.io/projects/continuumio-conda/en/latest/user-guide/install/linux.html)

* Set up conda environment (note the need to use `pip` for `opencv-contrib-python`):

```bash
conda create -n paper2gis -c conda-forge -y python=3 fiona rasterio pyzbar qrcode pillow cartopy
conda activate paper2gis
pip install opencv-contrib-python
```

* Get Paper2GIS:

```bash
git clone git@github.com:jonnyhuck/Paper2GIS.git
cd paper2gis-master
```

### Windows

I have never attempted to install Paper2GIS on Windows, but I can't see any reason why this should not be possible. Please do contact me if you either need this, and would like some advice, or have done this and would like to contribute some instructions. 

## Bulk Extraction and Shapefiles

Paper2GIS does not currently have any specific bulk data processing functionality. This can be achieved using a simple shell script, and example of which is given in [processor.sh](./in/processor.sh) and below:

```bash
#!/bin/bash

# this prevents an error for loops that match no file
shopt -s nullglob

# convert any iphone images to jpg and fix spaces in file names
for FILE in *.HEIC 
do 
    FILEJPG=`echo $FILE | sed "s/.HEIC/.jpg/"`
    convert -quality 100% $FILE $FILEJPG
    rm $FILE
done
 
# extract shapefiles
for FILE in *.jpg 
do

    # print name of current file
    echo $FILE

    # run the extractor
    FILENEW=`echo $FILE | sed "s/.jpg/.shp/"`
    echo python ../p2g.py extract --reference ../out.png --target $FILE -o $FILENEW
    python ../p2g.py extract --reference ../out.png --target $FILE -o $FILENEW
    echo ""
done

# unset shell option again
shopt -u nullglob

echo "done."
```

## Future Development:

I am planning to add the following features to Paper2GIS:

#### High Priority:

* Restore support for landscape Paper2GIS layouts
* Implement better support for layouts of different sizes and resolutions
* Implement batch processing for extraction
* Improved output cleaning for GeoTiff outputs (so that it is the same as for the Shapefile outputs)
* Centroid / representative point extraction (enabling the collection of point data)
* The ability to add an artificial frame to pictures of layouts that are too close to the edge of the photograph

#### Lower Priority:

* Implement alpha-shape (Concave Hull) extraction
* Implement the ability to interpret markup outlines as solid polygons (dependent upon the above)
* The ability to draw maps from a range of tile sources, not just OSM
* A QGIS Plugin to interface with Paper2GIS

If you would like to request a feature, you can do so by opening an [Issue](https://github.com/jonnyhuck/Paper2GIS/issues).

## Licensing

The software is licensed under the [GNU General Public License v3](LICENSE). Bundled with it is the Open Sans font, which is licensed under the [Apache License v2](resources/Apache_License.txt).

## References

Paper2GIS has been described in the academic literature (all are open access).

### Journal Articles

[Denwood, T., Huck, J. J., & Lindley, S. (2022). Paper2GIS: improving accessibility without limiting analytical potential in Participatory  Mapping. *Journal of Geographical Systems*, 1-21.](https://link.springer.com/article/10.1007/s10109-022-00386-6)

### Conference Papers

[Huck, J. J., Dunning, I., Lee, P., Lowe, T., Quek, E., Weerasinghe, S.,  & Wintie, D. (2017). Paper2GIS: a self-digitising,  paper-based PPGIS. In *Geocomp 2017: Proceedings of the 14th International Conference on Geocomputation*.](https://www.geog.leeds.ac.uk/groups/geocomp/2017/papers/80.pdf)

[Denwood, T., Huck, J.J., & Lindley, S. (2021). Paper2GIS: Going postal in the midst of a pandemic. In *Proceedings of the 29th Geographical Information Science UK Conference*.](https://zenodo.org/record/4665392)