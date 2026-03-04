import * as Cesium from 'cesium'
import { clamp, hexColor } from './helpers'
import { getAirplaneBillboard } from './airplane'
import {
  getCarrierIcon, getVesselIcon, getSubmarineIcon, getMilitaryBaseIcon,
  getSatelliteIcon, getNuclearIcon, getCctvIcon, getPiracyIcon,
  getTerrorismIcon, getEarthquakeIcon, getFireIcon, getWeatherAlertIcon,
  getRefugeeIcon, getCyberIcon, getSanctionIcon,
  getThreatIntelIcon, getSignalsIcon, getMilitaryVesselIcon, getMissileIcon,
  getConflictIcon, getNewsIcon, getEventIcon, getAirportIcon,
  getTelegramIcon, getRocketAlertIcon, getGeoConfirmedIcon, getUnderseaCableIcon,
  getLiveStreamIcon, getRedditIcon,
  getEquipmentLossIcon, getInternetOutageIcon, getGPSJammingIcon,
  getNaturalEventIcon,
} from './icons'

// Build entities for a given layer from raw data items.
// Returns the count of entities created.
export function buildEntities(ds, layerKey, items, cfg) {
  ds.entities.removeAll()
  let count = 0

  for (const item of items) {
    const props = item.properties || item
    const geom = item.geometry

    // Extract coordinates from various API response formats
    let lon = props.longitude ?? props.lng ?? props.lon ?? (geom?.coordinates?.[0])
    let lat = props.latitude ?? props.lat ?? (geom?.coordinates?.[1])

    // For layers with polygon geometry (airspace), skip point coordinate validation
    if (layerKey !== 'airspace') {
      if (!isFinite(lon) || !isFinite(lat)) continue
    }
    count++

    const builder = ENTITY_BUILDERS[layerKey] || buildDefault
    builder(ds, props, geom, lon, lat, cfg)
  }
  return count
}

// ---------- Per-layer entity builder functions ----------

function buildFlight(ds, props, geom, lon, lat, cfg) {
  const alt = isFinite(props.baro_altitude ?? props.altitude)
    ? (props.baro_altitude ?? props.altitude)
    : 10000
  const callsign = (props.callsign ?? props.flight ?? 'N/A').toString().trim()
  const speed = props.velocity ?? props.speed ?? 0
  const heading = props.heading ?? props.true_track ?? 0
  const headingRad = Cesium.Math.toRadians(heading)

  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat, alt),
    billboard: {
      image: getAirplaneBillboard(props.is_military),
      width: 24,
      height: 24,
      rotation: -headingRad,  // CesiumJS rotation is counter-clockwise
      alignedAxis: Cesium.Cartesian3.UNIT_Z,
      heightReference: Cesium.HeightReference.NONE,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e3, 1.8, 1e7, 0.3),
    },
  })
  entity._tooltipData = {
    title: '\u2708 ' + callsign,
    rows: {
      Callsign: callsign,
      'ICAO24': props.icao24 || 'N/A',
      Country: props.origin_country || 'Unknown',
      'Aircraft': props.aircraft_type || 'N/A',
      'Registration': props.registration || 'N/A',
      Altitude: Math.round(alt).toLocaleString() + ' m (' + Math.round(alt * 3.281).toLocaleString() + ' ft)',
      Speed: Math.round(speed) + ' kts',
      Heading: Math.round(heading) + '\u00b0',
      'Vert Rate': (props.vertical_rate ?? 0) > 0 ? '+' + props.vertical_rate + ' ft/min' : (props.vertical_rate ?? 0) + ' ft/min',
      Squawk: props.squawk || 'N/A',
      Military: props.is_military ? 'YES \u26a0' : 'No',
      Owner: props.owner || '',
      'Mil Branch': props.mil_branch || '',
      Manufacturer: props.manufacturer || '',
      'A/C Model': props.aircraft_model || '',
      Route: props.flight_route || '',
    },
  }
  entity._flightData = {
    callsign,
    country: props.origin_country,
    altitude: alt,
    speed,
    heading,
    icao24: props.icao24,
    on_ground: props.on_ground,
    longitude: lon,
    latitude: lat,
    vertical_rate: props.vertical_rate ?? 0,
    squawk: props.squawk,
    is_military: props.is_military,
    squawk_alert: props.squawk_alert,
    aircraft_type: props.aircraft_type || '',
    registration: props.registration || '',
    flight_route: props.flight_route || '',
  }
  // Dead-reckoning motion data for real-time animation
  entity._motionData = {
    lon, lat, alt,
    heading,
    speed,      // knots
    timestamp: Date.now(),
  }
}

function buildConflict(ds, props, geom, lon, lat, cfg) {
  const fatalities = props.fatalities ?? 0
  const iconSize = Math.round(clamp(18 + fatalities * 2, 18, 36))

  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getConflictIcon('#ef4444', 32),
      width: iconSize,
      height: iconSize,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.5),
    },
  })
  entity._tooltipData = {
    title: '\u2694 ' + (props.event_type || 'Conflict'),
    rows: {
      Type: props.event_type || props.sub_event_type || 'Unknown',
      'Sub-Type': props.sub_event_type || '',
      Location: props.location || props.admin1 || '',
      Country: props.country || '',
      Date: props.event_date || '',
      Fatalities: fatalities > 0 ? fatalities + ' reported' : '0',
      Actor1: props.actor1 || '',
      Actor2: props.actor2 || '',
      Source: props.source || 'ACLED/GDELT',
      Coords: lat.toFixed(3) + ', ' + lon.toFixed(3),
      Notes: (props.notes || '').substring(0, 150),
    },
  }
}

function buildEvent(ds, props, geom, lon, lat, cfg) {
  const headline = props.title ?? props.headline ?? 'Event'
  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getEventIcon('#f97316', 32),
      width: 20,
      height: 20,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.5),
    },
  })
  entity._tooltipData = {
    title: String(headline).substring(0, 80),
    rows: {
      Source: props.source || props.domain || 'GDELT',
      Type: props.type || 'Event',
      Country: props.country || '',
      URL: props.url ? String(props.url).substring(0, 60) + '...' : '',
      Coords: lat.toFixed(3) + ', ' + lon.toFixed(3),
    },
  }
  if (props.url) {
    entity._cctvData = { name: headline, stream_url: props.url }
  }
}

function buildNews(ds, props, geom, lon, lat, cfg) {
  const title = props.title ?? props.name ?? props.headline ?? 'News'
  const articleCount = props.article_count ?? props.count ?? 0
  const iconSize = Math.round(clamp(16 + Math.log10(Math.max(articleCount, 1)) * 4, 16, 28))

  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getNewsIcon('#10b981', 32),
      width: iconSize,
      height: iconSize,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.5),
    },
  })
  entity._tooltipData = {
    title: '\ud83d\udcf0 ' + String(title).substring(0, 100),
    rows: {
      Location: props.country || props.name || '',
      Articles: articleCount > 0 ? articleCount.toLocaleString() + ' articles' : '',
      Source: props.source || 'GDELT',
      'More Headlines': props.more_headlines ? props.more_headlines.substring(0, 150) : '',
      'Click': props.url ? 'Click to read article' : '',
    },
  }
  // Open article in new tab on click
  if (props.url) {
    entity._cctvData = { name: title, stream_url: props.url }
  }
}

function buildCctv(ds, props, geom, lon, lat, cfg) {
  const camName = props.name ?? props.title ?? 'CCTV Camera'
  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getCctvIcon('#22c55e', 32),
      width: 24,
      height: 24,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.6),
    },
  })
  entity._tooltipData = {
    title: '\ud83d\udcf9 ' + camName,
    rows: {
      Name: camName,
      Type: props.type || 'surveillance',
      City: props.city || '',
      Country: props.country || '',
      Operator: props.operator || '',
      Source: props.source || 'OSM',
      Stream: (props.stream_url || props.url) ? 'Click to view' : 'Click for Street View',
      Coords: lat.toFixed(4) + ', ' + lon.toFixed(4),
    },
  }
  entity._cctvData = { name: camName, stream_url: props.stream_url || props.url, lat, lon }
}

function buildFire(ds, props, geom, lon, lat, cfg) {
  const brightness = props.brightness ?? 300
  const norm = clamp((brightness - 300) / 200, 0, 1)
  const fireSize = Math.round(clamp(14 + norm * 18, 14, 32))
  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getFireIcon('#f97316', fireSize),
      width: fireSize,
      height: fireSize,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.5, 1e7, 0.5),
    },
  })
  entity._tooltipData = {
    title: '\ud83d\udd25 Fire Hotspot',
    rows: {
      Brightness: Math.round(brightness) + ' K',
      'FRP': props.frp ? props.frp + ' MW' : '',
      Confidence: props.confidence || 'N/A',
      Satellite: props.satellite || '',
      Date: props.acq_date || 'N/A',
      Time: props.acq_time || '',
      Coords: lat.toFixed(3) + ', ' + lon.toFixed(3),
    },
  }
}

function buildEarthquake(ds, props, geom, lon, lat, cfg) {
  const mag = props.magnitude ?? props.mag ?? 0
  const depth = props.depth ?? 0
  const markerColor = mag >= 7 ? '#ff0000'
    : mag >= 5.5 ? '#ff6600'
    : mag >= 4 ? '#ffd700'
    : '#22c55e'
  const quakeSize = Math.round(clamp(20 + (mag - 2.5) * 4, 20, 32))

  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getEarthquakeIcon(markerColor, quakeSize),
      width: quakeSize,
      height: quakeSize,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.5),
    },
  })
  entity._tooltipData = {
    title: '\ud83c\udf0d Earthquake M' + mag.toFixed(1),
    rows: {
      Magnitude: mag.toFixed(1) + (mag >= 6 ? ' \u26a0 MAJOR' : ''),
      Place: props.place || 'Unknown',
      Depth: depth + ' km',
      Time: props.time ? new Date(props.time).toUTCString() : '',
      Tsunami: props.tsunami_warning ? 'YES \u26a0' : 'No',
      'Felt Reports': props.felt || '',
      Significance: props.sig || '',
      Status: props.status || '',
      Coords: lat.toFixed(3) + ', ' + lon.toFixed(3),
    },
  }
}

function buildWeatherAlert(ds, props, geom, lon, lat, cfg) {
  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getWeatherAlertIcon('#a855f7', 32),
      width: 22,
      height: 22,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.5),
    },
  })
  entity._tooltipData = {
    title: '\u26c8 ' + (props.title || 'Weather Alert').substring(0, 60),
    rows: {
      Severity: props.severity || 'Unknown',
      Type: props.type || props.alert_type || 'Alert',
      Country: props.country || '',
      Source: props.source || 'GDACS',
      Description: (props.description || '').substring(0, 100),
      Issued: props.issued || props.pub_date || '',
      Coords: lat.toFixed(3) + ', ' + lon.toFixed(3),
    },
  }
}

function buildNuclear(ds, props, geom, lon, lat, cfg) {
  const level = props.radiation_level ?? props.radiation ?? props.level ?? 0
  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getNuclearIcon('#84cc16', 32),
      width: 22,
      height: 22,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.5),
    },
  })
  entity._tooltipData = {
    title: '\u2622 ' + (props.station_name || props.name || 'Station'),
    rows: {
      Level: level + ' ' + (props.unit || 'uSv/h'),
      Country: props.country || 'Unknown',
    },
  }
}

function buildVessel(ds, props, geom, lon, lat, cfg) {
  const heading = props.heading ?? 0
  const isMil = props.is_military || props.ship_type === 35
  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: isMil ? getMilitaryVesselIcon('#ef4444', 32) : getVesselIcon('#3b82f6', 32),
      width: isMil ? 22 : 18,
      height: isMil ? 22 : 18,
      rotation: -Cesium.Math.toRadians(heading),
      alignedAxis: Cesium.Cartesian3.UNIT_Z,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.4),
    },
  })
  entity._tooltipData = {
    title: (isMil ? '\u2693 MILITARY ' : '\ud83d\udea2 ') + (props.name || 'Vessel'),
    rows: {
      MMSI: props.mmsi || 'N/A',
      Classification: isMil ? 'MILITARY' : 'Civilian',
      Navy: props.navy || '',
      'Hull #': props.hull_number || '',
      Class: props.vessel_class || '',
      Type: props.ship_type || props.vessel_type || '',
      Speed: (props.speed || 0) + ' kn',
      Heading: (props.heading || 0) + '\u00b0',
      'Nav Status': props.nav_status || props.navigational_status || '',
      Destination: props.destination || '',
      Callsign: props.callsign || '',
      Country: props.country || '',
      Coords: lat.toFixed(4) + ', ' + lon.toFixed(4),
    },
  }
  // Dead-reckoning motion data for real-time animation
  entity._motionData = {
    lon, lat, alt: 0,
    heading,
    speed: props.speed || 0,  // knots
    timestamp: Date.now(),
  }
}

function buildSubmarine(ds, props, geom, lon, lat, cfg) {
  // Color by type: SSBN=red, SSN=orange, SSK/other=blue
  const subType = (props.type || '').toUpperCase()
  const color = subType.includes('SSBN') ? '#ef4444'
    : subType.includes('SSN') ? '#f97316'
    : '#0ea5e9'

  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getSubmarineIcon(color, 32),
      width: 24,
      height: 24,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.5),
    },
  })
  entity._tooltipData = {
    title: '\ud83d\udd31 ' + (props.name || 'Submarine'),
    rows: {
      Class: props.class || 'Unknown',
      Type: props.type || 'N/A',
      Operator: props.operator || 'Unknown',
      'Home Port': props.home_port || 'N/A',
      Status: props.status || 'N/A',
    },
  }
}

function buildPiracy(ds, props, geom, lon, lat, cfg) {
  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getPiracyIcon('#1e293b', 32),
      width: 24,
      height: 24,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.5),
    },
  })
  entity._tooltipData = {
    title: '\ud83c\udff4\u200d\u2620\ufe0f ' + (props.title || 'Piracy Zone').substring(0, 50),
    rows: {
      Region: props.region || 'Unknown',
      Severity: props.severity || 'Unknown',
    },
  }
}

function buildTerrorism(ds, props, geom, lon, lat, cfg) {
  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getTerrorismIcon('#b91c1c', 32),
      width: 22,
      height: 22,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.5),
    },
  })
  entity._tooltipData = {
    title: '\ud83d\udd12 ' + (props.title || 'Security Event').substring(0, 50),
    rows: {
      Country: props.country || 'Unknown',
      Date: props.date || 'N/A',
    },
  }
}

function buildCyber(ds, props, geom, lon, lat, cfg) {
  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getCyberIcon('#8b5cf6', 32),
      width: 20,
      height: 20,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.5),
    },
  })
  entity._tooltipData = {
    title: '\ud83d\udcbb ' + (props.title || 'Cyber Threat').substring(0, 50),
    rows: {
      Type: props.type || 'APT',
      Severity: props.severity || 'Unknown',
      Target: props.target_country || 'Global',
    },
  }
}

function buildMilitaryBase(ds, props, geom, lon, lat, cfg) {
  const operator = (props.operator || '').toLowerCase()
  const color = operator.includes('united states') || operator.includes('us') ? '#3b82f6'
    : operator.includes('russia') ? '#ef4444'
    : operator.includes('china') ? '#eab308'
    : operator.includes('nato') ? '#06b6d4'
    : '#16a34a'

  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getMilitaryBaseIcon(color, 32),
      width: 22,
      height: 22,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.5),
    },
  })
  entity._tooltipData = {
    title: '\ud83c\udfdb ' + (props.name || 'Military Base'),
    rows: {
      Country: props.country || 'Unknown',
      Operator: props.operator || 'Unknown',
      Type: props.type || 'Base',
      Branch: props.branch || 'N/A',
    },
  }
}

function buildAirspace(ds, props, geom, lon, lat, cfg) {
  // Support polygon geometry (GeoJSON format)
  if (geom && geom.type === 'Polygon' && geom.coordinates && geom.coordinates[0]) {
    const ring = geom.coordinates[0]
    const positions = []
    let valid = true
    for (const coord of ring) {
      if (!isFinite(coord[0]) || !isFinite(coord[1])) { valid = false; break }
      positions.push(coord[0], coord[1])
    }
    if (valid && positions.length >= 6) {
      const entity = ds.entities.add({
        polygon: {
          hierarchy: Cesium.Cartesian3.fromDegreesArray(positions),
          material: hexColor('#dc2626', 0.15),
          outline: true,
          outlineColor: hexColor('#dc2626', 0.6),
          outlineWidth: 2,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        },
      })
      entity._tooltipData = {
        title: '\u2708 Airspace: ' + (props.name || 'Restricted'),
        rows: { Type: props.type || 'Restricted', Status: props.status || 'Active' },
      }
    }
  } else if (props.coordinates) {
    // Backend format: coordinates as [[lat, lon], [lat, lon], ...] array
    const coords = props.coordinates
    if (Array.isArray(coords) && coords.length >= 3) {
      const positions = []
      let valid = true
      for (const c of coords) {
        if (!Array.isArray(c) || c.length < 2 || !isFinite(c[0]) || !isFinite(c[1])) {
          valid = false
          break
        }
        // Backend sends [lat, lon], fromDegreesArray expects [lon, lat, lon, lat, ...]
        positions.push(c[1], c[0])
      }
      if (valid && positions.length >= 6) {
        const entity = ds.entities.add({
          polygon: {
            hierarchy: Cesium.Cartesian3.fromDegreesArray(positions),
            material: hexColor('#dc2626', 0.15),
            outline: true,
            outlineColor: hexColor('#dc2626', 0.6),
            outlineWidth: 2,
            heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          },
        })
        entity._tooltipData = {
          title: '\u2708 Airspace: ' + (props.name || 'Restricted'),
          rows: { Type: props.type || 'Restricted', Status: props.status || 'Active' },
        }
      }
    }
  } else if (isFinite(lon) && isFinite(lat)) {
    // Fallback to ellipse for point-only airspace data
    const entity = ds.entities.add({
      position: Cesium.Cartesian3.fromDegrees(lon, lat),
      ellipse: {
        semiMinorAxis: 50000,
        semiMajorAxis: 50000,
        material: hexColor('#dc2626', 0.15),
        outline: true,
        outlineColor: hexColor('#dc2626', 0.6),
        outlineWidth: 2,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      },
    })
    entity._tooltipData = {
      title: '\u2708 Airspace: ' + (props.name || 'Restricted'),
      rows: { Type: props.type || 'Restricted' },
    }
  }
}

function buildRefugee(ds, props, geom, lon, lat, cfg) {
  const pop = props.population_affected
  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getRefugeeIcon('#06b6d4', 32),
      width: 22,
      height: 22,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.5),
    },
  })
  entity._tooltipData = {
    title: '\ud83d\udc65 ' + (props.title || 'Displacement').substring(0, 50),
    rows: {
      Country: props.country || 'Unknown',
      Affected: pop ? Number(pop).toLocaleString() : 'N/A',
    },
  }
}

function buildSanction(ds, props, geom, lon, lat, cfg) {
  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getSanctionIcon('#d97706', 32),
      width: 24,
      height: 24,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.5),
    },
  })
  entity._tooltipData = {
    title: '\u2696 Sanction: ' + (props.country || 'Unknown'),
    rows: {
      Type: props.sanction_type || 'N/A',
      'Imposed By': props.imposed_by || 'N/A',
    },
  }
}

function buildSatellite(ds, props, geom, lon, lat, cfg) {
  const rawAlt = props.altitude ?? props.alt ?? 400
  const alt = isFinite(rawAlt) ? rawAlt * 1000 : 400000
  const isISS = (props.name || '').toUpperCase().includes('ISS')

  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat, alt),
    billboard: {
      image: getSatelliteIcon(isISS ? '#ffffff' : '#c0c0c0', isISS ? 48 : 32),
      width: isISS ? 24 : 16,
      height: isISS ? 24 : 16,
      heightReference: Cesium.HeightReference.NONE,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.5, 2e7, 0.4),
    },
  })
  if (isISS) {
    entity.label = {
      text: 'ISS',
      font: '12px monospace',
      fillColor: Cesium.Color.WHITE,
      outlineColor: Cesium.Color.BLACK,
      outlineWidth: 2,
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      pixelOffset: new Cesium.Cartesian2(0, -18),
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 2e7, 0.4),
    }
  }
  entity._tooltipData = {
    title: '\ud83d\udef0 ' + (props.name || 'Satellite'),
    rows: {
      'NORAD ID': props.norad_id || 'N/A',
      Altitude: Math.round(alt / 1000) + ' km',
    },
  }
}

function buildAirport(ds, props, geom, lon, lat, cfg) {
  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getAirportIcon('#64748b', 32),
      width: 16,
      height: 16,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 5e6, 0.4),
    },
  })
  entity._tooltipData = {
    title: '\ud83d\udeec ' + (props.name || 'Airport'),
    rows: {
      ICAO: props.icao_code || 'N/A',
      IATA: props.iata_code || 'N/A',
      City: props.city || 'Unknown',
      LiveATC: props.liveatc_url ? 'Click to listen' : '',
    },
  }
  if (props.liveatc_url) {
    entity._cctvData = { name: props.name || 'Airport ATC', stream_url: props.liveatc_url }
  }
}

function buildNotam(ds, props, geom, lon, lat, cfg) {
  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    ellipse: {
      semiMinorAxis: (props.radius_nm || 50) * 1852,
      semiMajorAxis: (props.radius_nm || 50) * 1852,
      material: hexColor('#f43f5e', 0.1),
      outline: true,
      outlineColor: hexColor('#f43f5e', 0.5),
      outlineWidth: 1,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
    },
  })
  entity._tooltipData = {
    title: '\ud83d\udccb ' + (props.title || 'NOTAM').substring(0, 50),
    rows: {
      Region: props.region || 'Unknown',
      Type: props.type || 'N/A',
    },
  }
}

function buildCarrier(ds, props, geom, lon, lat, cfg) {
  const operator = (props.operator || '').toLowerCase()
  const status = (props.status || '').toLowerCase()
  const isDeployed = status.includes('deployed') || status.includes('detected')
  const color = operator.includes('united states') || operator.includes('us navy') ? '#3b82f6'
    : operator.includes('russia') || operator.includes('soviet') ? '#ef4444'
    : operator.includes('china') || operator.includes('people') ? '#eab308'
    : operator.includes('india') ? '#f97316'
    : operator.includes('france') ? '#06b6d4'
    : operator.includes('united kingdom') || operator.includes('royal navy') ? '#22c55e'
    : '#6366f1'

  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getCarrierIcon(color, 32),
      width: isDeployed ? 32 : 24,
      height: isDeployed ? 32 : 24,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.5, 1e7, 0.7),
    },
  })

  const rows = {
    Operator: props.operator || 'Unknown',
    Status: props.status || 'N/A',
  }
  if (props.class) rows.Class = props.class
  if (props.home_port) rows['Home Port'] = props.home_port
  if (props.confidence) rows.Confidence = props.confidence.toUpperCase()
  if (props.corroborating_sources) rows.Sources = props.corroborating_sources + ' independent'
  if (props.source) rows['Intel Source'] = props.source
  if (props.headline) rows.Headline = props.headline.substring(0, 100)

  const statusIcon = isDeployed ? '\u{1F6A2}' : '\u2693'
  entity._tooltipData = {
    title: statusIcon + ' ' + (props.name || 'Warship'),
    rows,
  }
  if (props.headline && props.url) {
    entity._cctvData = { name: props.name, stream_url: props.url }
  }
  // Dead-reckoning motion data for real-time animation
  entity._motionData = {
    lon, lat, alt: 0,
    heading: props.heading || 0,
    speed: props.speed || 0,
    timestamp: Date.now(),
  }
}

function buildThreatIntel(ds, props, geom, lon, lat, cfg) {
  const severity = (props.severity || 'low').toLowerCase()
  const color = severity === 'critical' ? '#ef4444'
    : severity === 'high' ? '#f43f5e'
    : severity === 'medium' ? '#f97316'
    : '#eab308'
  const iconSize = severity === 'critical' ? 28 : 24

  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getThreatIntelIcon(color, 32),
      width: iconSize,
      height: iconSize,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.5),
    },
  })
  entity._tooltipData = {
    title: '\ud83c\udfaf ' + (props.title || 'Threat Intel').substring(0, 60),
    rows: {
      Indicator: props.indicator || 'N/A',
      Type: props.indicator_type || 'Unknown',
      Severity: (props.severity || 'Unknown').toUpperCase(),
      Source: props.source || 'OTX',
      Country: props.country || '',
      CVEs: (props.cves || []).slice(0, 3).join(', ') || '',
      Ports: (props.open_ports || []).slice(0, 5).join(', ') || '',
    },
  }
}

function buildSignals(ds, props, geom, lon, lat, cfg) {
  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getSignalsIcon('#a78bfa', 32),
      width: 20,
      height: 20,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e3, 1.5, 1e7, 0.3),
    },
  })
  entity._tooltipData = {
    title: '\ud83d\udce1 ' + (props.name || 'SDR Receiver'),
    rows: {
      Location: props.location || '',
      Frequency: props.frequency_range || '',
      Antenna: props.antenna || '',
      Users: props.users_max ? `${props.users || 0}/${props.users_max}` : '',
      Source: props.source || 'KiwiSDR',
      Click: props.url ? 'Click to connect to radio' : '',
    },
  }
  // Attach radio data for RadioPanel instead of opening in new tab
  entity._radioData = {
    name: props.name || 'SDR Receiver',
    url: props.url || '',
    location: props.location || '',
    frequency_range: props.frequency_range || '',
    antenna: props.antenna || '',
    users: props.users || 0,
    users_max: props.users_max || 0,
  }
}

function buildMissileTest(ds, props, geom, lon, lat, cfg) {
  const etype = (props.type || '').toLowerCase()
  const color = etype === 'airstrike' || etype === 'drone_strike' ? '#ef4444'
    : etype === 'missile_strike' || etype === 'missile_test' ? '#dc2626'
    : etype === 'nuclear_test' ? '#f59e0b'
    : etype === 'shelling' ? '#f97316'
    : etype === 'bombing' || etype === 'suicide_bombing' ? '#b91c1c'
    : '#dc2626'
  const fatalities = props.fatalities || 0
  const iconSize = fatalities > 10 ? 32 : fatalities > 0 ? 28 : 24

  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getMissileIcon(color, 32),
      width: iconSize,
      height: iconSize,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.5, 1e7, 0.7),
    },
  })

  const typeLabel = (props.sub_type || props.type || 'Strike').replace(/_/g, ' ')
  const rows = {
    Type: typeLabel.charAt(0).toUpperCase() + typeLabel.slice(1),
    Date: props.date || 'N/A',
    Country: props.country || '',
    Region: props.region || '',
    Actor: props.actor || '',
    Target: props.target || '',
  }
  if (fatalities > 0) rows.Fatalities = fatalities.toString()
  rows.Source = props.source || 'OSINT'
  if (props.url) rows.Article = 'Click to read'

  if (props.origin_latitude && props.origin_longitude) {
    rows['Launch Site'] = props.launch_site || 'Unknown'
    rows['Origin'] = props.origin_confidence === 'confirmed' ? 'CONFIRMED' : 'Inferred'
  }

  entity._tooltipData = {
    title: '\uD83D\uDCA5 ' + (props.name || typeLabel || 'Strike Event').slice(0, 80),
    rows,
  }
  // Video search on click for missile/strike events
  entity._videoData = {
    query: (props.country || '') + ' ' + (typeLabel || 'strike') + ' ' + (props.actor || ''),
    title: props.name || typeLabel,
  }
  if (props.url) {
    entity._cctvData = { name: props.name, stream_url: props.url }
  }
}

function buildTelegramOsint(ds, props, geom, lon, lat, cfg) {
  const severity = (props.severity || 'medium').toLowerCase()
  const color = severity === 'high' ? '#ef4444' : severity === 'critical' ? '#dc2626' : '#0088cc'
  const iconSize = severity === 'high' || severity === 'critical' ? 26 : 22

  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getTelegramIcon(color, 32),
      width: iconSize,
      height: iconSize,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.5),
    },
  })
  entity._tooltipData = {
    title: '\u{1F4E8} ' + (props.title || 'OSINT Report').substring(0, 100),
    rows: {
      Channel: props.channel || 'Telegram',
      Category: props.category || '',
      Location: props.location || '',
      Severity: (props.severity || 'medium').toUpperCase(),
      Date: props.date || '',
      Source: props.source || 'Telegram',
    },
  }
  if (props.url) {
    entity._cctvData = { name: props.title, stream_url: props.url }
  }
}

function buildRocketAlert(ds, props, geom, lon, lat, cfg) {
  const alertType = (props.alert_type || 'rocket_alert').toLowerCase()
  const isActive = true // OREF alerts are always active/recent
  const iconSize = isActive ? 30 : 24

  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getRocketAlertIcon('#ff0000', 32),
      width: iconSize,
      height: iconSize,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.5, 1e7, 0.7),
    },
  })

  const typeLabel = alertType === 'uav_intrusion' ? 'UAV Intrusion'
    : alertType === 'hostile_aircraft' ? 'Hostile Aircraft'
    : alertType === 'earthquake' ? 'Earthquake Alert'
    : 'Rocket/Missile Alert'

  entity._tooltipData = {
    title: '\u{1F6A8} ' + typeLabel,
    rows: {
      Location: props.location || props.title || '',
      Type: typeLabel,
      Severity: 'CRITICAL',
      Time: props.date || 'Recent',
      Source: props.source || 'OREF',
    },
  }
}

function buildGeoConfirmed(ds, props, geom, lon, lat, cfg) {
  const isVerified = props.verified !== false
  const color = isVerified ? '#14b8a6' : '#f97316'

  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getGeoConfirmedIcon(color, 32),
      width: 24,
      height: 24,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.6),
    },
  })
  entity._tooltipData = {
    title: (isVerified ? '\u2705 ' : '\u{1F50D} ') + (props.title || 'Verified Event').substring(0, 100),
    rows: {
      Status: isVerified ? 'VERIFIED' : 'Unverified',
      Date: props.date || '',
      Description: (props.description || '').substring(0, 150),
      Source: props.source || 'GeoConfirmed',
      Media: (props.media_urls || []).length > 0 ? (props.media_urls || []).length + ' source(s)' : '',
    },
  }
  if (props.url || (props.media_urls && props.media_urls[0])) {
    entity._cctvData = { name: props.title, stream_url: props.url || props.media_urls[0] }
  }
}

function buildUnderseaCable(ds, props, geom, lon, lat, cfg) {
  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getUnderseaCableIcon('#06b6d4', 32),
      width: 20,
      height: 20,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.5),
    },
  })
  entity._tooltipData = {
    title: '\u{1F30A} ' + (props.title || 'Submarine Cable'),
    rows: {
      Country: props.country || '',
      Cables: props.cable_count ? props.cable_count + ' cable(s)' : '',
      Length: props.cable_length || '',
      RFS: props.rfs || '',
      Owners: (props.owners || '').substring(0, 100),
      Source: 'TeleGeography',
    },
  }
}

function buildLiveStream(ds, props, geom, lon, lat, cfg) {
  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getLiveStreamIcon('#ec4899', 32),
      width: 26,
      height: 26,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.6),
    },
  })
  entity._tooltipData = {
    title: '\u{1F4FA} ' + (props.name || 'Live Stream'),
    rows: {
      City: props.city || '',
      Country: props.country || '',
      Language: props.language || '',
      Type: props.type || '24/7 Live',
      Stream: 'Click to watch LIVE',
    },
  }
  if (props.stream_url) {
    entity._cctvData = { name: props.name || 'Live TV', stream_url: props.stream_url }
  }
}

function buildRedditOsint(ds, props, geom, lon, lat, cfg) {
  const severity = (props.severity || 'medium').toLowerCase()
  const color = severity === 'critical' ? '#dc2626'
    : severity === 'high' ? '#ef4444'
    : severity === 'medium' ? '#f97316'
    : '#ff4500'
  const iconSize = severity === 'critical' || severity === 'high' ? 26 : 22

  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getRedditIcon(color, 32),
      width: iconSize,
      height: iconSize,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.5),
    },
  })
  entity._tooltipData = {
    title: '\u{1F4E2} ' + (props.title || 'Reddit OSINT').substring(0, 100),
    rows: {
      Subreddit: props.channel || '',
      Category: props.category || '',
      Location: props.location || '',
      Severity: (props.severity || 'medium').toUpperCase(),
      Score: props.score ? props.score.toLocaleString() + ' upvotes' : '',
      Comments: props.comments ? props.comments.toLocaleString() : '',
      Flair: props.flair || '',
      Source: props.source || 'Reddit',
    },
  }
  if (props.url) {
    entity._cctvData = { name: props.title, stream_url: props.url }
  }
}

function buildEquipmentLoss(ds, props, geom, lon, lat, cfg) {
  const status = (props.status || 'destroyed').toLowerCase()
  const color = status === 'destroyed' ? '#dc2626'
    : status === 'captured' ? '#f97316'
    : status === 'damaged' ? '#eab308'
    : '#92400e'
  const verified = props.verified
  const iconSize = verified ? 26 : 22

  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getEquipmentLossIcon(color, 32),
      width: iconSize,
      height: iconSize,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.6),
    },
  })
  entity._tooltipData = {
    title: '\u{1F4A5} ' + (props.name || 'Equipment Loss').substring(0, 80),
    rows: {
      Equipment: props.equipment_type || 'Unknown',
      Status: (props.status || 'destroyed').toUpperCase(),
      Country: props.country || '',
      Operator: props.operator || '',
      Date: props.date || '',
      Verified: verified ? 'PHOTO VERIFIED' : 'Reported',
      Category: props.category || '',
      Source: props.source || 'WarSpotting',
    },
  }
  if (props.url || props.photo_url) {
    entity._cctvData = { name: props.name, stream_url: props.url || props.photo_url }
  }
}

function buildInternetOutage(ds, props, geom, lon, lat, cfg) {
  const severity = (props.severity || 'medium').toLowerCase()
  const color = severity === 'critical' ? '#dc2626'
    : severity === 'high' ? '#ef4444'
    : '#7c3aed'
  const iconSize = severity === 'critical' ? 30 : severity === 'high' ? 26 : 22

  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getInternetOutageIcon(color, 32),
      width: iconSize,
      height: iconSize,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.6),
    },
  })
  entity._tooltipData = {
    title: '\u{1F4E1} ' + (props.name || 'Internet Outage'),
    rows: {
      Country: props.country || '',
      Severity: (props.severity || 'medium').toUpperCase(),
      Level: props.level || '',
      Description: (props.description || '').substring(0, 150),
      Score: props.score ? props.score + '% drop' : '',
      Date: props.date || '',
      Source: props.source || 'IODA',
    },
  }
}

function buildGPSJamming(ds, props, geom, lon, lat, cfg) {
  const severity = (props.severity || 'medium').toLowerCase()
  const color = severity === 'critical' ? '#dc2626'
    : severity === 'high' ? '#ef4444'
    : '#e11d48'
  const radius = (props.radius_km || 100) * 1000  // km to meters

  // Zone circle
  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    ellipse: {
      semiMinorAxis: radius,
      semiMajorAxis: radius,
      material: hexColor(color, 0.12),
      outline: true,
      outlineColor: hexColor(color, 0.5),
      outlineWidth: 2,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
    },
  })
  entity._tooltipData = {
    title: '\u{1F6F0} ' + (props.name || 'GPS Jamming Zone'),
    rows: {
      Type: (props.type || 'jamming').toUpperCase(),
      Severity: (props.severity || 'medium').toUpperCase(),
      Radius: (props.radius_km || 100) + ' km',
      Description: (props.description || '').substring(0, 150),
      Status: props.date === 'ongoing' ? 'ACTIVE (ongoing)' : props.date || '',
      Verified: props.verified ? 'CONFIRMED' : 'Reported',
      Source: props.source || 'OPSGROUP',
    },
  }

  // Center marker icon
  ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getGPSJammingIcon(color, 32),
      width: 24,
      height: 24,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.6),
    },
  })
}

function buildNaturalEvent(ds, props, geom, lon, lat, cfg) {
  const name = props.name || 'Natural Event'
  const category = props.category || 'Unknown'
  const entity = ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    billboard: {
      image: getNaturalEventIcon(cfg.color),
      width: 28,
      height: 28,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: 1e5,
      scaleByDistance: new Cesium.NearFarScalar(1e2, 2.0, 1e7, 0.6),
    },
  })
  entity._tooltipData = {
    title: name,
    rows: {
      Category: category,
      Date: props.date || '',
      Magnitude: props.magnitude || '',
      Source: props.source || 'NASA EONET',
    },
  }
}

function buildDefault(ds, props, geom, lon, lat, cfg) {
  if (!isFinite(lon) || !isFinite(lat)) return
  ds.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    point: {
      pixelSize: 8,
      color: hexColor(cfg.color, 0.85),
      outlineWidth: 1,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
    },
  })
}

// Map of layer keys to their builder functions
const ENTITY_BUILDERS = {
  flights: buildFlight,
  conflicts: buildConflict,
  events: buildEvent,
  news: buildNews,
  cctv: buildCctv,
  fires: buildFire,
  earthquakes: buildEarthquake,
  weather_alerts: buildWeatherAlert,
  nuclear: buildNuclear,
  vessels: buildVessel,
  submarines: buildSubmarine,
  piracy: buildPiracy,
  terrorism: buildTerrorism,
  cyber: buildCyber,
  military_bases: buildMilitaryBase,
  airspace: buildAirspace,
  refugees: buildRefugee,
  sanctions: buildSanction,
  satellites: buildSatellite,
  airports: buildAirport,
  notams: buildNotam,
  carriers: buildCarrier,
  threat_intel: buildThreatIntel,
  signals: buildSignals,
  missile_tests: buildMissileTest,
  telegram_osint: buildTelegramOsint,
  rocket_alerts: buildRocketAlert,
  geo_confirmed: buildGeoConfirmed,
  undersea_cables: buildUnderseaCable,
  live_streams: buildLiveStream,
  reddit_osint: buildRedditOsint,
  equipment_losses: buildEquipmentLoss,
  internet_outages: buildInternetOutage,
  gps_jamming: buildGPSJamming,
  natural_events: buildNaturalEvent,
}
