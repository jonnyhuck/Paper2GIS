#!/bin/bash

# fix any spaces in file names
for f in *.jpg; do mv "$f" "${f// /_}"; done
 
# extract tifs and contours
for FILE in *.jpg
do
    FILENEW=`echo $FILE | sed "s/.jpg/.tif/"`
    echo python mapex.py -r reference_img.png -m reference_map.png -t $FILE -o $FILENEW -k 5 -b 30 -l 0.1 -c 90
    python mapex.py -r holly50k.png -m holly_50kmap.png -t $FILE -o $FILENEW -k 5 -b 30 -l 0.1 -c 90

    FILE2=`echo $FILENEW | sed "s/.tif/_tmp.shp/"`  # tmp file to be reprojected then deleted
    FILE3=`echo $FILENEW | sed "s/.tif/.shp/"`      # result file

    # make polygons from the raster
    echo gdal_polygonize.py -q $FILENEW -f "ESRI Shapefile" $FILE2
    gdal_polygonize.py -q $FILENEW -f "ESRI Shapefile" $FILE2

    # fix the projection problem (not sure why this happens...)
    echo ogr2ogr -f "ESRI Shapefile" -s_srs "EPSG:3857" -t_srs "EPSG:54004" -overwrite  -where "DN = 0" $FILE3 $FILE2
    ogr2ogr -f "ESRI Shapefile" -s_srs "EPSG:3857" -t_srs "EPSG:54004" -overwrite -where "DN = 0" $FILE3 $FILE2

    # clean up the unwanted files
    echo "cleaning..."
    rm $FILE2
    rm `echo $FILE2| sed "s/.shp/.dbf/"`
    rm `echo $FILE2| sed "s/.shp/.shx/"`
    rm `echo $FILE2| sed "s/.shp/.prj/"`
    echo ""
done

echo "done."