// Cheetah input provenance check. Run in Earth Engine Code Editor, NOT ArcGIS.
// 32 diagnostic points only. No raster exports or resistance changes.
// Sources:
// https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD44B
// https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD12Q1
//
// Native-pixel checks at model-cell centers are diagnostic. They do not
// reproduce an unknown 1 km export aggregation/resampling operation.
// Missing native values are -9999, never converted to measured zero.
// gee_*_valid flags preserve the original native data masks.

var samples = [
  {
    "sample_id": "2012_zero_water_1",
    "year": 2012,
    "group": "zero_water",
    "row": 93,
    "col": 2024,
    "longitude": 30.648280715812547,
    "latitude": -15.598099333304319,
    "local_lc": 17,
    "aligned_tree": 0,
    "aligned_nontree": 0,
    "aligned_bare": 0,
    "raw_tree": 0,
    "raw_nontree": 0,
    "raw_bare": 0
  },
  {
    "sample_id": "2012_zero_water_2",
    "year": 2012,
    "group": "zero_water",
    "row": 2173,
    "col": 915,
    "longitude": 19.82409496943683,
    "latitude": -34.76946572438394,
    "local_lc": 17,
    "aligned_tree": 0,
    "aligned_nontree": 0,
    "aligned_bare": 0,
    "raw_tree": 0,
    "raw_nontree": 0,
    "raw_bare": 0
  },
  {
    "sample_id": "2012_zero_other_3",
    "year": 2012,
    "group": "zero_other",
    "row": 96,
    "col": 1935,
    "longitude": 29.783249247510696,
    "latitude": -15.625821146819938,
    "local_lc": 16,
    "aligned_tree": 0,
    "aligned_nontree": 0,
    "aligned_bare": 0,
    "raw_tree": 0,
    "raw_nontree": 0,
    "raw_bare": 0
  },
  {
    "sample_id": "2012_zero_other_4",
    "year": 2012,
    "group": "zero_other",
    "row": 2024,
    "col": 1033,
    "longitude": 20.9835227305507,
    "latitude": -33.287776062683825,
    "local_lc": 16,
    "aligned_tree": 0,
    "aligned_nontree": 0,
    "aligned_bare": 0,
    "raw_tree": 0,
    "raw_nontree": 0,
    "raw_bare": 0
  },
  {
    "sample_id": "2012_nonzero_water_5",
    "year": 2012,
    "group": "nonzero_water",
    "row": 96,
    "col": 1936,
    "longitude": 29.792969497479287,
    "latitude": -15.625803478792406,
    "local_lc": 17,
    "aligned_tree": 4,
    "aligned_nontree": 32,
    "aligned_bare": 65,
    "raw_tree": 4,
    "raw_nontree": 32,
    "raw_bare": 65
  },
  {
    "sample_id": "2012_nonzero_water_6",
    "year": 2012,
    "group": "nonzero_water",
    "row": 2179,
    "col": 934,
    "longitude": 20.010255319438137,
    "latitude": -34.83015883335908,
    "local_lc": 17,
    "aligned_tree": 15,
    "aligned_nontree": 58,
    "aligned_bare": 27,
    "raw_tree": 15,
    "raw_nontree": 58,
    "raw_bare": 27
  },
  {
    "sample_id": "2012_nonzero_other_7",
    "year": 2012,
    "group": "nonzero_other",
    "row": 0,
    "col": 1891,
    "longitude": 29.353829009138273,
    "latitude": -14.795671319491294,
    "local_lc": 9,
    "aligned_tree": 15,
    "aligned_nontree": 73,
    "aligned_bare": 13,
    "raw_tree": 15,
    "raw_nontree": 73,
    "raw_bare": 13
  },
  {
    "sample_id": "2012_nonzero_other_8",
    "year": 2012,
    "group": "nonzero_other",
    "row": 2179,
    "col": 933,
    "longitude": 20.000450584211357,
    "latitude": -34.8301374697246,
    "local_lc": 9,
    "aligned_tree": 27,
    "aligned_nontree": 57,
    "aligned_bare": 17,
    "raw_tree": 27,
    "raw_nontree": 57,
    "raw_bare": 17
  },
  {
    "sample_id": "2016_zero_water_1",
    "year": 2016,
    "group": "zero_water",
    "row": 97,
    "col": 1928,
    "longitude": 29.715226999493,
    "latitude": -15.634614174184655,
    "local_lc": 17,
    "aligned_tree": 0,
    "aligned_nontree": 0,
    "aligned_bare": 0,
    "raw_tree": 0,
    "raw_nontree": 0,
    "raw_bare": 0
  },
  {
    "sample_id": "2016_zero_water_2",
    "year": 2016,
    "group": "zero_water",
    "row": 2173,
    "col": 915,
    "longitude": 19.82409496943683,
    "latitude": -34.76946572438394,
    "local_lc": 17,
    "aligned_tree": 0,
    "aligned_nontree": 0,
    "aligned_bare": 0,
    "raw_tree": 0,
    "raw_nontree": 0,
    "raw_bare": 0
  },
  {
    "sample_id": "2016_zero_other_3",
    "year": 2016,
    "group": "zero_other",
    "row": 93,
    "col": 2024,
    "longitude": 30.648280715812547,
    "latitude": -15.598099333304319,
    "local_lc": 11,
    "aligned_tree": 0,
    "aligned_nontree": 0,
    "aligned_bare": 0,
    "raw_tree": 0,
    "raw_nontree": 0,
    "raw_bare": 0
  },
  {
    "sample_id": "2016_zero_other_4",
    "year": 2016,
    "group": "zero_other",
    "row": 2099,
    "col": 859,
    "longitude": 19.276811236314643,
    "latitude": -34.02809867814917,
    "local_lc": 16,
    "aligned_tree": 0,
    "aligned_nontree": 0,
    "aligned_bare": 0,
    "raw_tree": 0,
    "raw_nontree": 0,
    "raw_bare": 0
  },
  {
    "sample_id": "2016_nonzero_water_5",
    "year": 2016,
    "group": "nonzero_water",
    "row": 96,
    "col": 1936,
    "longitude": 29.792969497479287,
    "latitude": -15.625803478792406,
    "local_lc": 17,
    "aligned_tree": 4,
    "aligned_nontree": 20,
    "aligned_bare": 77,
    "raw_tree": 4,
    "raw_nontree": 20,
    "raw_bare": 77
  },
  {
    "sample_id": "2016_nonzero_water_6",
    "year": 2016,
    "group": "nonzero_water",
    "row": 2179,
    "col": 934,
    "longitude": 20.010255319438137,
    "latitude": -34.83015883335908,
    "local_lc": 17,
    "aligned_tree": 19,
    "aligned_nontree": 59,
    "aligned_bare": 23,
    "raw_tree": 19,
    "raw_nontree": 59,
    "raw_bare": 23
  },
  {
    "sample_id": "2016_nonzero_other_7",
    "year": 2016,
    "group": "nonzero_other",
    "row": 0,
    "col": 1891,
    "longitude": 29.353829009138273,
    "latitude": -14.795671319491294,
    "local_lc": 9,
    "aligned_tree": 18,
    "aligned_nontree": 81,
    "aligned_bare": 2,
    "raw_tree": 18,
    "raw_nontree": 81,
    "raw_bare": 2
  },
  {
    "sample_id": "2016_nonzero_other_8",
    "year": 2016,
    "group": "nonzero_other",
    "row": 2179,
    "col": 933,
    "longitude": 20.000450584211357,
    "latitude": -34.8301374697246,
    "local_lc": 9,
    "aligned_tree": 29,
    "aligned_nontree": 57,
    "aligned_bare": 14,
    "raw_tree": 29,
    "raw_nontree": 57,
    "raw_bare": 14
  },
  {
    "sample_id": "2020_zero_water_1",
    "year": 2020,
    "group": "zero_water",
    "row": 97,
    "col": 1928,
    "longitude": 29.715226999493,
    "latitude": -15.634614174184655,
    "local_lc": 17,
    "aligned_tree": 0,
    "aligned_nontree": 0,
    "aligned_bare": 0,
    "raw_tree": 0,
    "raw_nontree": 0,
    "raw_bare": 0
  },
  {
    "sample_id": "2020_zero_water_2",
    "year": 2020,
    "group": "zero_water",
    "row": 2173,
    "col": 915,
    "longitude": 19.82409496943683,
    "latitude": -34.76946572438394,
    "local_lc": 17,
    "aligned_tree": 0,
    "aligned_nontree": 0,
    "aligned_bare": 0,
    "raw_tree": 0,
    "raw_nontree": 0,
    "raw_bare": 0
  },
  {
    "sample_id": "2020_zero_other_3",
    "year": 2020,
    "group": "zero_other",
    "row": 93,
    "col": 2024,
    "longitude": 30.648280715812547,
    "latitude": -15.598099333304319,
    "local_lc": 11,
    "aligned_tree": 0,
    "aligned_nontree": 0,
    "aligned_bare": 0,
    "raw_tree": 0,
    "raw_nontree": 0,
    "raw_bare": 0
  },
  {
    "sample_id": "2020_zero_other_4",
    "year": 2020,
    "group": "zero_other",
    "row": 2103,
    "col": 859,
    "longitude": 19.276715738966438,
    "latitude": -34.067944707579834,
    "local_lc": 11,
    "aligned_tree": 0,
    "aligned_nontree": 0,
    "aligned_bare": 0,
    "raw_tree": 0,
    "raw_nontree": 0,
    "raw_bare": 0
  },
  {
    "sample_id": "2020_nonzero_water_5",
    "year": 2020,
    "group": "nonzero_water",
    "row": 96,
    "col": 1936,
    "longitude": 29.792969497479287,
    "latitude": -15.625803478792406,
    "local_lc": 17,
    "aligned_tree": 8,
    "aligned_nontree": 24,
    "aligned_bare": 68,
    "raw_tree": 8,
    "raw_nontree": 24,
    "raw_bare": 68
  },
  {
    "sample_id": "2020_nonzero_water_6",
    "year": 2020,
    "group": "nonzero_water",
    "row": 2179,
    "col": 934,
    "longitude": 20.010255319438137,
    "latitude": -34.83015883335908,
    "local_lc": 17,
    "aligned_tree": 12,
    "aligned_nontree": 60,
    "aligned_bare": 29,
    "raw_tree": 12,
    "raw_nontree": 60,
    "raw_bare": 29
  },
  {
    "sample_id": "2020_nonzero_other_7",
    "year": 2020,
    "group": "nonzero_other",
    "row": 0,
    "col": 1891,
    "longitude": 29.353829009138273,
    "latitude": -14.795671319491294,
    "local_lc": 9,
    "aligned_tree": 20,
    "aligned_nontree": 59,
    "aligned_bare": 22,
    "raw_tree": 20,
    "raw_nontree": 59,
    "raw_bare": 22
  },
  {
    "sample_id": "2020_nonzero_other_8",
    "year": 2020,
    "group": "nonzero_other",
    "row": 2179,
    "col": 933,
    "longitude": 20.000450584211357,
    "latitude": -34.8301374697246,
    "local_lc": 9,
    "aligned_tree": 26,
    "aligned_nontree": 55,
    "aligned_bare": 20,
    "raw_tree": 26,
    "raw_nontree": 55,
    "raw_bare": 20
  },
  {
    "sample_id": "2024_zero_water_1",
    "year": 2024,
    "group": "zero_water",
    "row": 97,
    "col": 2030,
    "longitude": 30.706695823873545,
    "latitude": -15.632652817658448,
    "local_lc": 17,
    "aligned_tree": 0,
    "aligned_nontree": 0,
    "aligned_bare": 0,
    "raw_tree": 0,
    "raw_nontree": 0,
    "raw_bare": 0
  },
  {
    "sample_id": "2024_zero_water_2",
    "year": 2024,
    "group": "zero_water",
    "row": 2173,
    "col": 919,
    "longitude": 19.863312916783208,
    "latitude": -34.769553883131245,
    "local_lc": 17,
    "aligned_tree": 0,
    "aligned_nontree": 0,
    "aligned_bare": 0,
    "raw_tree": 0,
    "raw_nontree": 0,
    "raw_bare": 0
  },
  {
    "sample_id": "2024_zero_other_3",
    "year": 2024,
    "group": "zero_other",
    "row": 93,
    "col": 2024,
    "longitude": 30.648280715812547,
    "latitude": -15.598099333304319,
    "local_lc": 11,
    "aligned_tree": 0,
    "aligned_nontree": 0,
    "aligned_bare": 0,
    "raw_tree": 0,
    "raw_nontree": 0,
    "raw_bare": 0
  },
  {
    "sample_id": "2024_zero_other_4",
    "year": 2024,
    "group": "zero_other",
    "row": 2174,
    "col": 923,
    "longitude": 19.902509596532788,
    "latitude": -34.779685164514554,
    "local_lc": 10,
    "aligned_tree": 0,
    "aligned_nontree": 0,
    "aligned_bare": 0,
    "raw_tree": 0,
    "raw_nontree": 0,
    "raw_bare": 0
  },
  {
    "sample_id": "2024_nonzero_water_5",
    "year": 2024,
    "group": "nonzero_water",
    "row": 96,
    "col": 1936,
    "longitude": 29.792969497479287,
    "latitude": -15.625803478792406,
    "local_lc": 17,
    "aligned_tree": 3,
    "aligned_nontree": 18,
    "aligned_bare": 80,
    "raw_tree": 3,
    "raw_nontree": 18,
    "raw_bare": 80
  },
  {
    "sample_id": "2024_nonzero_water_6",
    "year": 2024,
    "group": "nonzero_water",
    "row": 2179,
    "col": 934,
    "longitude": 20.010255319438137,
    "latitude": -34.83015883335908,
    "local_lc": 17,
    "aligned_tree": 12,
    "aligned_nontree": 63,
    "aligned_bare": 26,
    "raw_tree": 12,
    "raw_nontree": 63,
    "raw_bare": 26
  },
  {
    "sample_id": "2024_nonzero_other_7",
    "year": 2024,
    "group": "nonzero_other",
    "row": 0,
    "col": 1891,
    "longitude": 29.353829009138273,
    "latitude": -14.795671319491294,
    "local_lc": 9,
    "aligned_tree": 15,
    "aligned_nontree": 67,
    "aligned_bare": 19,
    "raw_tree": 15,
    "raw_nontree": 67,
    "raw_bare": 19
  },
  {
    "sample_id": "2024_nonzero_other_8",
    "year": 2024,
    "group": "nonzero_other",
    "row": 2179,
    "col": 933,
    "longitude": 20.000450584211357,
    "latitude": -34.8301374697246,
    "local_lc": 9,
    "aligned_tree": 29,
    "aligned_nontree": 62,
    "aligned_bare": 10,
    "raw_tree": 29,
    "raw_nontree": 62,
    "raw_bare": 10
  }
];
var points = ee.FeatureCollection(samples.map(function(s) {
  return ee.Feature(ee.Geometry.Point([s.longitude, s.latitude]), s);
}));
var result = ee.FeatureCollection([]);
[2012, 2016, 2020, 2024].forEach(function(year) {
  var start = ee.Date.fromYMD(year, 1, 1);
  var end = start.advance(1, 'year');
  var vcfCollection = ee.ImageCollection('MODIS/061/MOD44B').filterDate(start, end);
  var lcCollection = ee.ImageCollection('MODIS/061/MCD12Q1').filterDate(start, end);
  print(year + ' source image counts (expect one of each)', vcfCollection.size(), lcCollection.size());
  var vcf = ee.Image(vcfCollection.first());
  var lc = ee.Image(lcCollection.first());
  var cover = vcf.select(['Percent_Tree_Cover', 'Percent_NonTree_Vegetation',
                          'Percent_NonVegetated'], ['gee_tree', 'gee_nontree', 'gee_bare']);
  var originalMasks = cover.mask().rename(['gee_tree_valid','gee_nontree_valid','gee_bare_valid']);
  var lcBands = lc.select(['LC_Type1','QC','LW'], ['gee_lc_type1','gee_lc_qc','gee_land_water']);
  var lcValid = lc.select('LC_Type1').mask().rename('gee_lc_valid');
  var stack = cover.toFloat().unmask(-9999, false)
    .addBands(originalMasks.unmask(0, false))
    .addBands(vcf.select(['Quality', 'Cloud'], ['gee_vcf_quality', 'gee_vcf_cloud'])
      .toFloat().unmask(-9999, false))
    .addBands(lcBands.toFloat().unmask(-9999, false))
    .addBands(lcValid.unmask(0, false));
  var sampled = stack.sampleRegions({
    collection: points.filter(ee.Filter.eq('year', year)),
    projection: vcf.select('Percent_Tree_Cover').projection(),
    scale: vcf.select('Percent_Tree_Cover').projection().nominalScale(),
    geometries: false,
    tileScale: 2
  }).map(function(f) {
    return f.set({
      gee_vcf_image: vcf.id(), gee_lc_image: lc.id(),
      gee_vcf_date: vcf.date().format('YYYY-MM-dd'),
      gee_lc_date: lc.date().format('YYYY-MM-dd'),
      sampling_note: 'Native VCF pixel at model cell center; not a reconstruction of the original 1 km export'
    });
  });
  result = result.merge(sampled);
});
print('Expected records', samples.length);
print('Actual records', result.size());
print('Source QA records', result);
Map.centerObject(points, 5);
Map.addLayer(points, {color: 'ff00ff'}, 'Diagnostic sample locations');

// This creates one SMALL CSV export task. Click Run in Tasks to export it.
Export.table.toDrive({
  collection: result,
  description: 'cheetah_input_source_qa_20260903',
  folder: 'cheetah_gee_exports',
  fileNamePrefix: 'cheetah_input_source_qa_20260903',
  fileFormat: 'CSV'
});

