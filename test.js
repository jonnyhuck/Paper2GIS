/**
 * Simple Node.js Mapnik renderer
 *
 * NB: neeed to deactivate conda to be able to run it
 *
 * TODO: add CL args so this can be called from within mapgen.py
 **/

function mm2px(mm, dpi) {
  // 1 inch = 25.4mm 96dpi is therefore...
	return parseInt((mm * dpi / 25.4) + 0.5)
}

//load libraries
var mapnik = require('mapnik');
var fs = require('fs');

// register fonts and datasource plugins
mapnik.register_default_fonts();
mapnik.register_default_input_plugins();

// width =   3508;
// height =  4961;
width =   parseInt(3508 / 300 * 96 - mm2px(10, 96));
height =  parseInt(4961 / 300 * 96 - mm2px(40, 96));
console.log(width, "x", height);  // 1084 x 1436

//create a map
var map = new mapnik.Map(width, height);

// load the required stylesheet
map.load('./OSMBright/style.xml', function(err,map) {
    if (err) throw err;

    // set the zoom and dimensions
    map.zoomToBox([1920835.627, 6375494.894, 1921741.171, 6376788.906]);
    var im = new mapnik.Image(width, height);

    // render the map
    map.render(im, function(err,im) {
      if (err) throw err;

      // encode to png
      im.encode('png', function(err,buffer) {
          if (err) throw err;

          // write to file
          fs.writeFile('map.png',buffer, function(err) {
              if (err) throw err;

              // log to user
              console.log('saved map image to map.png');
          });
      });
    });
});
