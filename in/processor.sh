#!/bin/bash

# this prevents an error for loops that match no file
shopt -s nullglob

# convert any iphone images to jpg and fix spaces in file names
#  (requires imagemagick)
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
    echo python ../allinone.py --reference ../out.png --target $FILE -o $FILENEW
    python ../allinone.py --reference ../out.png --target $FILE -o $FILENEW
    echo ""
done

# unset shell option again
shopt -u nullglob

echo "done."