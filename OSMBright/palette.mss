/* ****************************************************************** */
/* OSM BRIGHT for Imposm                                              */
/* ****************************************************************** */

/* For basic style customization you can simply edit the colors and
 * fonts defined in this file. For more detailed / advanced
 * adjustments explore the other files.
 *
 * GENERAL NOTES
 *
 * There is a slight performance cost in rendering line-caps.  An
 * effort has been made to restrict line-cap definitions to styles
 * where the results will be visible (lines at least 2 pixels thick).
 */

/* ================================================================== */
/* FONTS
/* ================================================================== */

/* directory to load fonts from in addition to the system directories */
Map { font-directory: url(./fonts); }

/* set up font sets for various weights and styles */
@sans_lt:       "Open Sans Regular", "DejaVu Sans Book", "Arundina Sans Regular", "Padauk Regular", "Khmer OS Metal Chrieng Regular",
                "Mukti Narrow Regular", "gargi Medium", "TSCu_Paranar Regular", "Tibetan Machine Uni Regular", "Mallige Normal",
                "Droid Sans Fallback Regular", "Unifont Medium", "unifont Medium";


@sans_lt_italic:    "Open Sans Oblique", "DejaVu Sans Oblique", "Arundina Sans Italic", "TSCu_Paranar Italic", "Mallige NormalItalic",
                "DejaVu Sans Book", "Arundina Sans Regular", "Padauk Regular", "Khmer OS Metal Chrieng Regular",
                "Mukti Narrow Regular", "gargi Medium", "TSCu_Paranar Regular", "Tibetan Machine Uni Regular", "Mallige Normal",
                "Droid Sans Fallback Regular", "Unifont Medium", "unifont Medium";


@sans:          "Open Sans Semibold", "DejaVu Sans Book", "Arundina Sans Regular", "Padauk Regular", "Khmer OS Metal Chrieng Regular",
                "Mukti Narrow Regular", "gargi Medium", "TSCu_Paranar Regular", "Tibetan Machine Uni Regular", "Mallige Normal",
                "Droid Sans Fallback Regular", "Unifont Medium", "unifont Medium";

@sans_italic:   "Open Sans Semibold Italic",  "DejaVu Sans Oblique", "Arundina Sans Italic", "TSCu_Paranar Italic", "Mallige NormalItalic",
                "DejaVu Sans Book", "Arundina Sans Regular", "Padauk Regular", "Khmer OS Metal Chrieng Regular",
                "Mukti Narrow Regular", "gargi Medium", "TSCu_Paranar Regular", "Tibetan Machine Uni Regular", "Mallige Normal",
                "Droid Sans Fallback Regular", "Unifont Medium", "unifont Medium";


@sans_bold:  "Open Sans Bold", "DejaVu Sans Bold", "Arundina Sans Bold", "Padauk Bold", "Mukti Narrow Bold", "TSCu_Paranar Bold", "Mallige Bold",
             "DejaVu Sans Book", "Arundina Sans Regular", "Padauk Regular", "Khmer OS Metal Chrieng Regular",
             "Mukti Narrow Regular", "gargi Medium", "TSCu_Paranar Regular", "Tibetan Machine Uni Regular", "Mallige Normal",
             "Droid Sans Fallback Regular", "Unifont Medium", "unifont Medium";

@sans_bold_italic:  "Open Sans Bold Italic","DejaVu Sans Bold Oblique", "DejaVu Sans Oblique", "Arundina Sans Italic", "TSCu_Paranar Italic", "Mallige NormalItalic",
                "DejaVu Sans Book", "Arundina Sans Regular", "Padauk Regular", "Khmer OS Metal Chrieng Regular",
                "Mukti Narrow Regular", "gargi Medium", "TSCu_Paranar Regular", "Tibetan Machine Uni Regular", "Mallige Normal",
                "Droid Sans Fallback Regular", "Unifont Medium", "unifont Medium";

/* Some fonts are larger or smaller than others. Use this variable to
   globally increase or decrease the font sizes. */
/* Note this is only implemented for certain things so far */
@text_adjust: 100;

/* ================================================================== */
/* LANDUSE & LANDCOVER COLORS
/* ================================================================== */

@contour:           #ad6f69;

@land:              #FCFBE7;
@water:             #C4DFF6;
@grass:             #E6F2C1;
@beach:             #FFEEC7;
@park:              #DAF2C1;
@cemetery:          #D6DED2;
@wooded:            #C3D9AD;
@agriculture:       #F2E8B6;

/* @building:          #E4E0E0; */
@building:          #aaa;
@hospital:          rgb(229,198,195);
@school:            #FFF5CC;
@sports:            #B8E6B8;

@residential:       @land * 0.98;
@commercial:        @land * 0.97;
@industrial:        @land * 0.96;
@parking:           #EEE;

/* ================================================================== */
/* ROAD COLORS
/* ================================================================== */

/* For each class of road there are three color variables:
 * - line: for lower zoomlevels when the road is represented by a
 *         single solid line.
 * - case: for higher zoomlevels, this color is for the road's
 *         casing (outline).
 * - fill: for higher zoomlevels, this color is for the road's
 *         inner fill (inline).
 */

@motorway_line:     #E65C5C;
@motorway_fill:     lighten(@motorway_line,15%); /*10*/
@motorway_case:     @motorway_line; /* 0.9 */

@trunk_line:        #E68A5C;
@trunk_fill:        lighten(@trunk_line,15%);
@trunk_case:        @trunk_line;

@primary_line:      #FFC859;
@primary_fill:      lighten(@primary_line,15%);
@primary_case:      @primary_line;

@secondary_line:    #FFE873;
@secondary_fill:    lighten(@secondary_line,15%);
@secondary_case:    @secondary_line;

@standard_line:     @land * 0.85;
@standard_fill:     #fff;
@standard_case:     @land * 0.9;

@pedestrian_line:   @standard_line;
@pedestrian_fill:   #FAFAF5;
@pedestrian_case:   @land;

@cycle_line:        @standard_line;
@cycle_fill:        #FAFAF5;
@cycle_case:        @land;

@rail_line:         #999;
@rail_fill:         #fff;
@rail_case:         @land;

@aeroway:           #ddd;

/* ================================================================== */
/* BOUNDARY COLORS
/* ================================================================== */

@admin_2:           #324;

/* ================================================================== */
/* LABEL COLORS
/* ================================================================== */

/* We set up a default halo color for places so you can edit them all
   at once or override each individually. */
@place_halo:        fadeout(#fff,34%);

@label_color:       #bbb;

@country_text:      @label_color;  /*#435;*/
@country_halo:      @place_halo;

@state_text:        @label_color;  /*#546;*/
@state_halo:        @place_halo;

@city_text:         @label_color;  /*#888; /*444*/
@city_halo:         @place_halo;

@town_text:         @label_color;  /*#888; /*666*/
@town_halo:         @place_halo;

@poi_text:          @label_color;  /*#888;*/

@road_text:         @label_color;  /*#999; /*777*/
@road_halo:         #fff;

@other_text:        @label_color;  /*#888;*/
@other_halo:        @place_halo;

@locality_text:     @label_color;  /*#aaa;*/
@locality_halo:     @land;

/* Also used for other small places: hamlets, suburbs, localities */
@village_text:      @label_color;  /*#888;*/
@village_halo:      @place_halo;

/* ****************************************************************** */
