// RUN IN GOOGLE EARTH ENGINE CODE EDITOR, NOT ARCGIS PRO.
// Four NEW candidate vegetation exports, never replacements for existing files.
// Click Run for the four Tasks, then download the TIFFs to Downloads.
// No resistance calculation, fence/water exclusion, imputation or solver here.
//
// Means use the intersection of usable native MOD44B pixels across all four
// years, within each model cell. This fixes the subpixel spatial support for
// temporal comparisons. It is NOT a prescription to delete whole model cells.
// Coverage bands explicitly report how much native area contributes.
// No minimum-coverage threshold is imposed beyond having some valid input.
// These are candidate inputs pending local QA and separate water treatment.
//
// Sources checked 2026-09-03:
// https://developers.google.com/earth-engine/guides/resample
// https://developers.google.com/earth-engine/apidocs/ee-image-reduceresolution
// https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD44B

var YEARS = [2012, 2016, 2020, 2024];
var SOURCE = 'MODIS/061/MOD44B';
var NODATA = -9999;
var CRS = 'PROJCS["Africa_Albers_Equal_Area_Conic",' +
  'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],' +
  'PRIMEM["Greenwich",0],UNIT["Degree",0.0174532925199433]],' +
  'PROJECTION["Albers"],PARAMETER["False_Easting",0],PARAMETER["False_Northing",0],' +
  'PARAMETER["Central_Meridian",25],PARAMETER["Standard_Parallel_1",20],' +
  'PARAMETER["Standard_Parallel_2",-23],PARAMETER["Latitude_Of_Origin",0],UNIT["Meter",1]]';
var XMIN = -1443410.18670718;
var YMAX = -1744096.102480766;
var TRANSFORM = [1000, 0, XMIN, 0, -1000, YMAX];
var WIDTH = 2310;
var HEIGHT = 2200;
// Small inward inset prevents floating-point boundary expansion from adding
// an extra border row. Grid origin and pixel centers are NOT shifted.
// Native sources are NOT clipped before aggregation.
var REGION = ee.Geometry.Rectangle([
  XMIN + 0.01, YMAX - HEIGHT * 1000 + 0.01,
  XMIN + WIDTH * 1000 - 0.01, YMAX - 0.01
], CRS, false);
var SOURCE_BANDS = ['Percent_Tree_Cover', 'Percent_NonTree_Vegetation', 'Percent_NonVegetated'];
var COVER_BANDS = ['tree_pct_common_mean', 'nontree_pct_common_mean', 'bare_pct_common_mean'];
var OUTPUT_BANDS = COVER_BANDS.concat([
  'common_usable_fraction', 'annual_usable_fraction', 'annual_source_valid_fraction',
  'annual_zero_triplet_fraction', 'annual_out_of_range_fraction'
]);

var collections = YEARS.map(function(year) {
  var start = ee.Date.fromYMD(year, 1, 1);
  return ee.ImageCollection(SOURCE).filterDate(start, start.advance(1, 'year'));
});

// Native-to-model aggregation: overlap-weighted mean. bestEffort:false prevents
// silently switching to a coarser source pyramid if the native pixel cap fails.
function aggregateNative(image) {
  return image.toFloat().reduceResolution({
    reducer: ee.Reducer.mean(), bestEffort: false, maxPixels: 1024
  }).reproject({crs: CRS, crsTransform: TRANSFORM});
}

// Projection.transform() returns a WKT STRING, not six affine coefficients.
// https://developers.google.com/earth-engine/apidocs/ee-projection-transform
// Exact equality is conservative: a different representation stops the export
// for review rather than silently allowing a potentially different grid.
function nativeGridsMatch(details, years) {
  if (!Array.isArray(details) || details.length !== years.length || !details.length) {
    return false;
  }
  var first = details[0];
  if (!first || typeof first.crs !== 'string' || !first.crs.length ||
      typeof first.transform !== 'string' || !first.transform.length) {
    return false;
  }
  return details.every(function(d, i) {
    return d && typeof d.date === 'string' &&
      d.date.substring(0, 4) === String(years[i]) &&
      d.crs === first.crs && typeof d.transform === 'string' &&
      d.transform === first.transform;
  });
}

// Only tiny metadata requests run interactively. No full-image reduceRegion,
// map rendering or full-raster getInfo before the batch export tasks.
ee.List(collections.map(function(c) { return c.size(); })).evaluate(function(counts, error) {
  if (error || !counts || counts.some(function(n) { return n !== 1; })) {
    print('STOP: expected exactly one source image per year. No exports created.', counts, error);
    return;
  }
  var images = collections.map(function(c) { return ee.Image(c.first()); });
  var metadata = ee.List(images.map(function(image) {
    var projection = image.select(SOURCE_BANDS[0]).projection();
    return ee.Dictionary({id: image.id(), date: image.date().format('YYYY-MM-dd'),
      crs: projection.crs(), transform: projection.transform()});
  }));
  metadata.evaluate(function(details, metadataError) {
    if (metadataError || !details) {
      print('STOP: source metadata could not be checked.', metadataError);
      return;
    }
    var gridsMatch = nativeGridsMatch(details, YEARS);
    if (!gridsMatch) {
      print('STOP: native annual grids or dates differ. No exports created.', details);
      return;
    }
    print('Source IDs, dates and verified native grids (retain with project notes)', details);
    var nativeProjection = images[0].select(SOURCE_BANDS[0]).projection();
    var covers = images.map(function(image) {
      return image.select(SOURCE_BANDS, COVER_BANDS).toFloat();
    });
    var sourceValid = covers.map(function(cover) {
      return cover.mask().reduce(ee.Reducer.min()).gt(0).unmask(0, false)
        .setDefaultProjection(nativeProjection);
    });
    var zeros = covers.map(function(cover, i) {
      return cover.eq(0).reduce(ee.Reducer.min()).and(sourceValid[i])
        .unmask(0, false).setDefaultProjection(nativeProjection);
    });
    var inRange = covers.map(function(cover) {
      return cover.gte(0).and(cover.lte(100)).reduce(ee.Reducer.min())
        .unmask(0, false).setDefaultProjection(nativeProjection);
    });
    var usable = covers.map(function(cover, i) {
      return sourceValid[i].and(inRange[i]).and(zeros[i].not())
        .unmask(0, false).setDefaultProjection(nativeProjection);
    });
    var common = usable[0];
    for (var k = 1; k < usable.length; k++) { common = common.and(usable[k]); }
    common = common.setDefaultProjection(nativeProjection);
    var commonFraction = aggregateNative(common).rename('common_usable_fraction');

    YEARS.forEach(function(year, i) {
      // Actual cover values stay masked until AFTER aggregation. In particular,
      // missing cover is never changed into 0% vegetation or 0% bare cover.
      var meanCover = aggregateNative(covers[i].updateMask(common));
      var annualFraction = aggregateNative(usable[i]).rename('annual_usable_fraction');
      var sourceFraction = aggregateNative(sourceValid[i]).rename('annual_source_valid_fraction');
      var zeroFraction = aggregateNative(zeros[i]).rename('annual_zero_triplet_fraction');
      var badRange = sourceValid[i].and(inRange[i].not());
      var badRangeFraction = aggregateNative(badRange).rename('annual_out_of_range_fraction');
      var stack = meanCover.addBands(commonFraction).addBands(annualFraction)
        .addBands(sourceFraction).addBands(zeroFraction).addBands(badRangeFraction)
        .select(OUTPUT_BANDS).toFloat();
      // Sentinel only at the final target grid; explicitly declared as NoData.
      stack = stack.unmask(NODATA, false).clip(REGION);
      Export.image.toDrive({
        image: stack,
        description: 'vcf_maskpreserved_common_v2_' + year,
        folder: 'cheetah_gee_exports',
        fileNamePrefix: 'vcf_maskpreserved_common_v2_' + year,
        region: REGION, crs: CRS, crsTransform: TRANSFORM,
        maxPixels: 1e8, fileFormat: 'GeoTIFF', formatOptions: {noData: NODATA}
      });
    });
    print('Four tasks created. Start each from Tasks; download all four TIFFs.');
    print('Expected downloaded grid: 2310 x 2200; local verification still required.');
    print('Band order', OUTPUT_BANDS);
    print('Cover units: percent of the common usable native area, NOT percent of the whole 1 km cell.');
    print('Coverage units: fractions 0..1 of the model cell. A valid zero fraction is not NoData.');
    print('No-data sentinel: -9999. Zero common coverage should have NoData cover means.');
    print('No cloud/quality-bit threshold imposed. Source validity is not equivalent to ecological accuracy.');
    print('Do not overwrite old rasters, convert these masks to barriers or rerun connectivity yet.');
  });
});
