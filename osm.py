from PIL import Image
from io import BytesIO
from matplotlib import pyplot as plt
from cartopy.io.img_tiles import OSM
from numpy import reshape, frombuffer, uint8

def get_osm_map(bl_x, bl_y, tr_x, tr_y, zoom, w, h, dpi=96, crs=None):
    """
    * Return an OSM map as a PIL image
    * 
    * Parameters:
    *     bl_x, bl_y, tr_x, tr_y: desired map bounds (overidden by the desired map dimensions)
    *     zoom: zoom level of the map tiles
    *     w, h: desired dimensions of the output image (overides the map bounds)
    *     dpi: resolution of the output image (default 96)
    *     crs: the crs of the input coordinates (default Web Mercator)
    """

    # get OSM tile interface
    tiler = OSM()

    # if no CRS is specified, assume Web Mercator
    if crs is None:
        crs = tiler.crs

    # enforce dimensions, preserving the width of the original dimensions
    map_w = tr_x - bl_x
    map_h = tr_y - bl_y

    # here the map is too wide so preserve the width (add height)
    if (map_w / map_h) < (w / h):
        half_map_height = (map_w * h / w) / 2
        mid_point = bl_y + map_h / 2
        bl_y = mid_point - half_map_height
        tr_y = mid_point + half_map_height

    # otherwise it is too tall, so preserve height (add width)
    else:               
        half_map_width = (map_h * w / h) / 2
        mid_point = bl_x + map_w / 2
        bl_x = mid_point - half_map_width
        tr_x = mid_point + half_map_width

    # create a figure and axis
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1, projection=tiler.crs)

    # set the desired map extent on the axis
    ax.set_extent([bl_x, tr_x, bl_y, tr_y], crs=crs)

    # add the map tiles to the axis
    # TODO: Can I set zoom level automatically...?
    ax.add_image(tiler, zoom)
    b = ax.get_window_extent()

    # load map into buffer then array
    # TODO: This seems to be dependent on screen resolution - I think that the problem is actually
    #   ax.get_window_extent
    io_buf = BytesIO()
    fig.savefig(io_buf, format='raw', bbox_inches='tight', pad_inches=0) # dont set dpi?
    io_buf.seek(0)
    img_arr = reshape(frombuffer(io_buf.getvalue(), dtype=uint8), newshape=(int(b.height), int(b.width), -1))
    io_buf.close()

    # convert array to image, fade and return
    map = Image.fromarray(img_arr)
    map.putalpha(200)
    return map
    

# TEST
map = get_osm_map(-2462672.600, 9330748.585, -2393838.600, 9421934.585, 10, 1084, 1436, 96)
map.save('test.png', 'PNG')