// Run in GOOGLE EARTH ENGINE CODE EDITOR, not ArcGIS Pro.
// Diagnostic only: four five-band Byte GeoTIFFs. No resistance calculations.
// Default nearest-neighbor sampling of native flags at the model grid.
// These are center-sample flags, NOT water/valid-data fractions of 1 km cells,
// NOT a final habitat mask, and NOT replacements for existing cover exports.
// https://developers.google.com/earth-engine/apidocs/export-image-todrive
// https://developers.google.com/earth-engine/apidocs/ee-image-unmask
// https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD44B
// https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD12Q1

var crs = 'PROJCS["Africa_Albers_Equal_Area_Conic",' +
  'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],' +
  'PRIMEM["Greenwich",0],UNIT["Degree",0.0174532925199433]],' +
  'PROJECTION["Albers"],PARAMETER["False_Easting",0],PARAMETER["False_Northing",0],' +
  'PARAMETER["Central_Meridian",25],PARAMETER["Standard_Parallel_1",20],' +
  'PARAMETER["Standard_Parallel_2",-23],PARAMETER["Latitude_Of_Origin",0],UNIT["Meter",1]]';
var xmin = -1443410.18670718;
var ymax = -1744096.102480766;
var transform = [1000, 0, xmin, 0, -1000, ymax];
var region = ee.Geometry.Rectangle(
  [xmin, ymax - 2200 * 1000, xmin + 2310 * 1000, ymax], crs, false);
var bands = ['vcf_triplet_valid', 'vcf_allzero_when_valid',
             'lc_type1', 'lc_type1_valid', 'land_water'];

print('Expected grid: 2310 columns x 2200 rows, 1000 m; verify again after download.');
print('Band order', bands);
print('255 = NoData. Validity bands: 0 = unavailable, 1 = available.');
print('LC_Type1: 17 water bodies, 11 wetlands. LW: 1 water, 2 land.');
print('Do NOT treat every missing VCF pixel or wetland as an impermeable barrier.');

[2012, 2016, 2020, 2024].forEach(function(year) {
  var start = ee.Date.fromYMD(year, 1, 1);
  var end = start.advance(1, 'year');
  var vc = ee.ImageCollection('MODIS/061/MOD44B').filterDate(start, end);
  var lc = ee.ImageCollection('MODIS/061/MCD12Q1').filterDate(start, end);
  // Small metadata request only; no full-image getInfo or synchronous reducer.
  ee.Dictionary({vcf_count: vc.size(), lc_count: lc.size()}).evaluate(function(info, error) {
    if (error || !info || info.vcf_count !== 1 || info.lc_count !== 1) {
      print('STOP: no task created for ' + year + '; unexpected source count/error', info, error);
      return;
    }
    var vcf = ee.Image(vc.first());
    var land = ee.Image(lc.first());
    var cover = vcf.select(['Percent_Tree_Cover', 'Percent_NonTree_Vegetation', 'Percent_NonVegetated']);
    var valid = cover.mask().reduce(ee.Reducer.min()).gt(0).unmask(0, false)
      .rename('vcf_triplet_valid');
    var allzero = cover.eq(0).reduce(ee.Reducer.min()).updateMask(valid)
      .unmask(255, false).rename('vcf_allzero_when_valid');
    var lcValue = land.select('LC_Type1').unmask(255, false).rename('lc_type1');
    var lcValid = land.select('LC_Type1').mask().gt(0).unmask(0, false).rename('lc_type1_valid');
    var lw = land.select('LW').unmask(255, false).rename('land_water');
    // Compute flags on each product's native grid before nearest-neighbor
    // export. Do not infer validity from coarser cover-value pyramid levels.
    var vcfFlags = valid.addBands(allzero).reproject({
      crs: vcf.select('Percent_Tree_Cover').projection()
    });
    var lcFlags = lcValue.addBands(lcValid).addBands(lw).reproject({
      crs: land.select('LC_Type1').projection()
    });
    var output = vcfFlags.addBands(lcFlags).select(bands).toByte().clip(region);
    print(year + ' sources', vcf.id(), land.id());
    Export.image.toDrive({
      image: output,
      description: 'cheetah_source_validity_audit_v1_' + year,
      folder: 'cheetah_gee_exports',
      fileNamePrefix: 'cheetah_source_validity_audit_v1_' + year,
      region: region,
      crs: crs,
      crsTransform: transform,
      maxPixels: 1e8,
      fileFormat: 'GeoTIFF',
      formatOptions: {noData: 255}
    });
    print('Task created for ' + year + '. Start it from Tasks.');
  });
});

// Download the four completed files to Downloads for local comparison.
// This script intentionally does not create resistance or connectivity outputs.
