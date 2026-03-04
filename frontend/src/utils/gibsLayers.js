// NASA GIBS (Global Imagery Browse Services) satellite overlay helpers.
// Free WMTS imagery — no API key required, data ~1 day behind real-time.

import * as Cesium from 'cesium'

// ---- Layer definitions ----

export const GIBS_LAYERS = {
  viirs_thermal: {
    id: 'VIIRS_SNPP_Thermal_Anomalies_375m_All',
    label: 'Thermal Hotspots',
    maxZoom: 8,
    format: 'image/png',
  },
  nightlights: {
    id: 'VIIRS_SNPP_DayNightBand_At_Sensor_Radiance',
    label: 'Night Lights',
    maxZoom: 8,
    format: 'image/png',
  },
  aerosol: {
    id: 'MODIS_Terra_Aerosol_Optical_Depth_3km',
    label: 'Aerosol/Smoke',
    maxZoom: 6,
    format: 'image/png',
  },
  truecolor: {
    id: 'MODIS_Terra_CorrectedReflectance_TrueColor',
    label: 'True Color',
    maxZoom: 9,
    format: 'image/jpeg',
  },
}

// ---- Helpers ----

/**
 * Return yesterday's date in UTC as YYYY-MM-DD.
 * GIBS imagery is typically ~1 day behind real-time.
 */
function getYesterdayUTC() {
  return new Date(Date.now() - 86400000).toISOString().slice(0, 10)
}

/**
 * Map MIME format to file extension for the GIBS tile URL.
 */
function formatToExt(format) {
  return format === 'image/jpeg' ? 'jpg' : 'png'
}

// ---- Public API ----

/**
 * Create a Cesium UrlTemplateImageryProvider for the given GIBS layer key.
 *
 * @param {string} layerKey — one of the keys in GIBS_LAYERS
 * @returns {Cesium.UrlTemplateImageryProvider}
 */
export function createGIBSProvider(layerKey) {
  const cfg = GIBS_LAYERS[layerKey]
  if (!cfg) {
    throw new Error(`Unknown GIBS layer key: "${layerKey}"`)
  }

  const date = getYesterdayUTC()
  const ext = formatToExt(cfg.format)

  return new Cesium.UrlTemplateImageryProvider({
    url:
      `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/` +
      `${cfg.id}/default/${date}/GoogleMapsCompatible_Level${cfg.maxZoom}/{z}/{y}/{x}.${ext}`,
    maximumLevel: cfg.maxZoom,
    credit: new Cesium.Credit('NASA GIBS'),
  })
}

/**
 * Add a GIBS imagery overlay to the viewer at 60 % opacity.
 *
 * @param {Cesium.Viewer} viewer — active CesiumJS viewer instance
 * @param {string} layerKey — one of the keys in GIBS_LAYERS
 * @returns {Cesium.ImageryLayer} the newly added imagery layer
 */
export function addGIBSOverlay(viewer, layerKey) {
  const provider = createGIBSProvider(layerKey)
  const layer = viewer.imageryLayers.addImageryProvider(provider)
  layer.alpha = 0.6
  return layer
}

/**
 * Remove a previously added GIBS imagery layer from the viewer.
 *
 * @param {Cesium.Viewer} viewer — active CesiumJS viewer instance
 * @param {Cesium.ImageryLayer} layer — the layer reference returned by addGIBSOverlay
 */
export function removeGIBSOverlay(viewer, layer) {
  viewer.imageryLayers.remove(layer)
}
