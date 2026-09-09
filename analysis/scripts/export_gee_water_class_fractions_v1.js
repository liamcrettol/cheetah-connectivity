// RUN IN GOOGLE EARTH ENGINE CODE EDITOR, NOT ARCGIS PRO.
// Diagnostic only. Four NEW exports. No model edits or connectivity runs.
// Fractions of native area CLASSIFIED in each category, not measured inundation
// fractions within the native 500 m pixels. LW and LC_Type1 are not independent
// validation datasets. No water/barrier threshold is applied.
// Sources checked 2026-09-04:
// https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD12Q1
// https://developers.google.com/earth-engine/apidocs/ee-image-reduceresolution
var YEARS = [2012, 2016, 2020, 2024];
var CRS = 'PROJCS["Africa_Albers_Equal_Area_Conic",' +
 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],' +
 'PRIMEM["Greenwich",0],UNIT["Degree",0.0174532925199433]],' +
 'PROJECTION["Albers"],PARAMETER["False_Easting",0],PARAMETER["False_Northing",0],' +
 'PARAMETER["Central_Meridian",25],PARAMETER["Standard_Parallel_1",20],' +
 'PARAMETER["Standard_Parallel_2",-23],PARAMETER["Latitude_Of_Origin",0],UNIT["Meter",1]]';
var XMIN = -1443410.18670718, YMAX = -1744096.102480766;
var TRANSFORM = [1000, 0, XMIN, 0, -1000, YMAX];
var REGION = ee.Geometry.Rectangle([XMIN+.01,YMAX-2200000+.01,XMIN+2310000-.01,YMAX-.01],CRS,false);
var NAMES = ['lw_water_fraction','lw_land_fraction','lw_valid_fraction',
 'lc_water_fraction','lc_wetland_fraction','lc_barren_fraction','lc_valid_fraction',
 'both_water_fraction','both_land_fraction','disagreement_fraction','both_valid_fraction'];
var collections = YEARS.map(function(year) {
 var start=ee.Date.fromYMD(year,1,1);
 return ee.ImageCollection('MODIS/061/MCD12Q1').filterDate(start,start.advance(1,'year'));
});
ee.List(collections.map(function(c){return c.size();})).evaluate(function(counts,error){
 if(error || !counts || counts.some(function(n){return n!==1;})) {
  print('STOP: expected one image per snapshot; no exports.',counts,error);return;
 }
 var images=collections.map(function(c){return ee.Image(c.first());});
 var metadata=ee.List(images.map(function(im){
  return ee.Dictionary({id:im.id(),date:im.date().format('YYYY-MM-dd'),
   lc_crs:im.select('LC_Type1').projection().crs(),lc_transform:im.select('LC_Type1').projection().transform(),
   lw_crs:im.select('LW').projection().crs(),lw_transform:im.select('LW').projection().transform()});
 }));
 metadata.evaluate(function(details,err){
  if(err || !details || details.length!==4 || details.some(function(d,i){
   return !d || typeof d.lc_transform!=='string' || !d.lc_transform.length ||
    d.lc_crs!==d.lw_crs || d.lc_transform!==d.lw_transform ||
    d.lc_crs!==details[0].lc_crs || d.lc_transform!==details[0].lc_transform ||
    d.date.substring(0,4)!==String(YEARS[i]);
  })) {print('STOP: native projection/date check failed.',details,err);return;}
  print('Verified source metadata; retain this output',details);
  images.forEach(function(im,i){
   var projection=im.select('LC_Type1').projection();
   function flag(image){return image.unmask(0,false).setDefaultProjection(projection);}
   var lc=im.select('LC_Type1'),lw=im.select('LW');
   var lv=flag(lc.mask().gt(0).and(lc.gte(1)).and(lc.lte(17)));
   var wv=flag(lw.mask().gt(0).and(lw.eq(1).or(lw.eq(2))));
   var lwater=flag(lc.eq(17).and(lv)), lland=flag(lc.neq(17).and(lv));
   var wwater=flag(lw.eq(1).and(wv)), wland=flag(lw.eq(2).and(wv));
   var both=lv.and(wv);
   var bothWater=lwater.and(wwater),bothLand=lland.and(wland);
   var disagreement=both.and(bothWater.or(bothLand).not());
   var flags=wwater.addBands(wland).addBands(wv).addBands(lwater)
    .addBands(flag(lc.eq(11).and(lv))).addBands(flag(lc.eq(16).and(lv))).addBands(lv)
    .addBands(bothWater).addBands(bothLand).addBands(disagreement).addBands(both)
    .rename(NAMES).toFloat().setDefaultProjection(projection);
   // Zero flags on invalid input are paired with explicit valid fractions.
   // Do not clip native inputs before overlap-weighted aggregation.
   var result=flags.reduceResolution({reducer:ee.Reducer.mean(),bestEffort:false,maxPixels:1024})
    .reproject({crs:CRS,crsTransform:TRANSFORM}).unmask(-9999,false).clip(REGION);
   Export.image.toDrive({image:result,description:'water_class_fractions_v1_'+YEARS[i],
    folder:'cheetah_gee_exports',fileNamePrefix:'water_class_fractions_v1_'+YEARS[i],
    region:REGION,crs:CRS,crsTransform:TRANSFORM,maxPixels:1e8,
    fileFormat:'GeoTIFF',formatOptions:{noData:-9999}});
  });
  print('Start FOUR tasks, then download water_class_fractions_v1_YEAR.tif to Downloads.');
  print('Expected grid: 2310 columns x 2200 rows; 11 Float32 fraction bands in this order:',NAMES);
  print('No-data sentinel -9999; real zero is valid. Local validation remains required.');
  print('Class 11 wetlands is reported separately, never automatically treated as a barrier.');
 });
});
