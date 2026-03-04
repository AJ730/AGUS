import React, { useEffect, useRef, useState, useCallback } from 'react'
import * as Cesium from 'cesium'
import 'cesium/Build/Cesium/Widgets/widgets.css'

import { LAYERS, DEFAULT_VISIBLE_LAYERS } from './config/layers'
import { clamp, escapeHtml } from './utils/helpers'
import { buildEntities } from './utils/entityBuilders'
import { buildArcs, extractArcsFromEvents, extractCyberArcs } from './utils/arcBuilder'
import { createCRTStage, createNVGStage, createFLIRStage, createAnimeStage, createReticleStage, removeAllFilters } from './utils/visualFilters'
import { updateEntityMotion } from './utils/motionTracker'
import { GIBS_LAYERS, addGIBSOverlay, removeGIBSOverlay } from './utils/gibsLayers'
import { StreetTrafficController } from './utils/streetTraffic'
import Sidebar from './components/Sidebar'
import TopBar from './components/TopBar'
import FlightPanel from './components/FlightPanel'
import VideoPanel from './components/VideoPanel'
import AnalysisPanel from './components/AnalysisPanel'
import RadioPanel from './components/RadioPanel'
import BottomBar from './components/BottomBar'
import AnalyticsCards from './components/AnalyticsCards'
import NewsTicker from './components/NewsTicker'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

// Analytics layer keys -- layers tracked in the analytics cards
const ANALYTICS_KEYS = ['flights', 'conflicts', 'earthquakes', 'fires', 'news', 'threat_intel', 'missile_tests', 'telegram_osint', 'rocket_alerts', 'reddit_osint', 'equipment_losses', 'gps_jamming']

export default function App() {
  const containerRef = useRef(null)
  const viewerRef = useRef(null)
  const dataSourcesRef = useRef({})
  const intervalsRef = useRef({})
  const retryCountRef = useRef({})

  const [loading, setLoading] = useState(true)
  const [loadingStatus, setLoadingStatus] = useState('CONNECTING TO BACKEND...')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [layerState, setLayerState] = useState(() => {
    const s = {}
    for (const key of Object.keys(LAYERS)) {
      s[key] = {
        visible: DEFAULT_VISIBLE_LAYERS.includes(key),
        count: 0,
        opacity: 1.0,
      }
    }
    return s
  })
  const [flightPanel, setFlightPanel] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [collapsedGroups, setCollapsedGroups] = useState({})
  const [analytics, setAnalytics] = useState({ flights: 0, conflicts: 0, earthquakes: 0, fires: 0, news: 0, threat_intel: 0, missile_tests: 0, telegram_osint: 0, rocket_alerts: 0, reddit_osint: 0, equipment_losses: 0, gps_jamming: 0 })
  const [squawkAlerts, setSquawkAlerts] = useState([])
  const [cameraAlt, setCameraAlt] = useState(0)
  const [newsItems, setNewsItems] = useState([])
  const [mapStyle, setMapStyle] = useState('hybrid') // 'satellite', 'dark', 'hybrid'
  const [videoPanel, setVideoPanel] = useState(null)
  const [analysisPanel, setAnalysisPanel] = useState(null)
  const [radioPanel, setRadioPanel] = useState(null)
  const [dismissedSquawk, setDismissedSquawk] = useState(false)
  const [visualFilter, setVisualFilter] = useState('crt')   // 'crt' | 'nvg' | 'flir' | 'none'
  const [gibsActive, setGibsActive] = useState({})          // { viirs_thermal: true, ... }
  const gibsLayerRefs = useRef({})                           // { viirs_thermal: ImageryLayer, ... }
  const tiles3dRef = useRef(null)                            // Google 3D tileset ref
  const streetTrafficRef = useRef(null)                      // StreetTrafficController
  const trafficTilesRef = useRef(null)                       // Google traffic tile layer
  const [trafficOverlay, setTrafficOverlay] = useState(false) // Google traffic tiles toggle
  const imageryLayersRef = useRef({ esri: null, labels: null, darkStreets: null, nightlightsOverlay: null })

  // Initialize CesiumJS
  useEffect(() => {
    Cesium.Ion.defaultAccessToken = undefined

    const viewer = new Cesium.Viewer(containerRef.current, {
      animation: false,
      timeline: false,
      fullscreenButton: false,
      vrButton: false,
      geocoder: false,
      homeButton: false,
      infoBox: false,
      selectionIndicator: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      baseLayerPicker: false,
      creditContainer: document.createElement('div'),
      imageryProvider: false,
      requestRenderMode: true,
      maximumRenderTimeChange: 0.5,
    })

    viewerRef.current = viewer
    const scene = viewer.scene
    const globe = scene.globe

    // HIGH-RES SATELLITE IMAGERY (ESRI -- free, no API key)
    const esriLayer = viewer.imageryLayers.addImageryProvider(
      new Cesium.UrlTemplateImageryProvider({
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        credit: new Cesium.Credit('Esri, Maxar, Earthstar Geographics'),
        maximumLevel: 19,
      })
    )

    // LABELS OVERLAY (borders, cities, roads)
    const labelsLayer = viewer.imageryLayers.addImageryProvider(
      new Cesium.UrlTemplateImageryProvider({
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
        credit: new Cesium.Credit('Esri'),
        maximumLevel: 15,
      })
    )
    labelsLayer.alpha = 0.6

    // DARK STREET MAP (CartoDB Dark Matter -- free, detailed at street level)
    const darkStreetsLayer = viewer.imageryLayers.addImageryProvider(
      new Cesium.UrlTemplateImageryProvider({
        url: 'https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
        credit: new Cesium.Credit('CartoDB, OpenStreetMap'),
        maximumLevel: 20,
      })
    )
    darkStreetsLayer.alpha = 0.7 // Blended in hybrid mode

    imageryLayersRef.current = { esri: esriLayer, labels: labelsLayer, darkStreets: darkStreetsLayer }

    // Globe settings -- NO LIGHTING (keeps globe stable and fully visible)
    globe.enableLighting = false
    globe.showGroundAtmosphere = true
    scene.backgroundColor = Cesium.Color.fromCssColorString('#000008')
    scene.fog.enabled = true
    scene.fog.density = 2.0e-4

    if (scene.skyAtmosphere) {
      scene.skyAtmosphere.show = true
    }

    // Star skybox
    scene.skyBox = new Cesium.SkyBox({
      sources: {
        positiveX: Cesium.buildModuleUrl('Assets/Textures/SkyBox/tycho2t3_80_px.jpg'),
        negativeX: Cesium.buildModuleUrl('Assets/Textures/SkyBox/tycho2t3_80_mx.jpg'),
        positiveY: Cesium.buildModuleUrl('Assets/Textures/SkyBox/tycho2t3_80_py.jpg'),
        negativeY: Cesium.buildModuleUrl('Assets/Textures/SkyBox/tycho2t3_80_my.jpg'),
        positiveZ: Cesium.buildModuleUrl('Assets/Textures/SkyBox/tycho2t3_80_pz.jpg'),
        negativeZ: Cesium.buildModuleUrl('Assets/Textures/SkyBox/tycho2t3_80_mz.jpg'),
      },
    })

    // FXAA anti-aliasing (GPU-powered)
    scene.postProcessStages.fxaa.enabled = true

    // CRT filter applied by default (replaces old CSS scanlines)
    scene.postProcessStages.add(createCRTStage())

    // High-DPI rendering -- use full device resolution
    viewer.resolutionScale = window.devicePixelRatio || 1.0

    // Clock -- do NOT animate
    viewer.clock.shouldAnimate = false

    // Camera controls
    scene.screenSpaceCameraController.minimumZoomDistance = 250
    scene.screenSpaceCameraController.maximumZoomDistance = 50000000

    // Initial view -- Middle East overview
    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(30, 25, 15000000),
    })

    // Create data sources for each layer
    for (const key of Object.keys(LAYERS)) {
      const ds = new Cesium.CustomDataSource(key)
      dataSourcesRef.current[key] = ds
      viewer.dataSources.add(ds)
    }

    // Street traffic controller (animated vehicles on roads below 5km)
    const trafficCtrl = new StreetTrafficController(viewer)
    streetTrafficRef.current = trafficCtrl

    // Real-time entity motion: dead-reckoning for flights, vessels, carriers
    // Extrapolates positions based on heading + speed between API refreshes
    const motionInterval = setInterval(() => {
      const ds = dataSourcesRef.current
      const moved =
        updateEntityMotion(ds.flights) +
        updateEntityMotion(ds.vessels) +
        updateEntityMotion(ds.carriers)
      if (moved > 0) scene.requestRender()
    }, 200) // 5fps smooth dead reckoning

    // Camera altitude tracking + altitude-based street/satellite crossfade (throttled)
    let lastAltUpdate = 0
    let lastVpFetch = 0
    let lastVpLat = null
    let lastVpLon = null
    scene.postRender.addEventListener(() => {
      const now = Date.now()
      if (now - lastAltUpdate < 500) return
      lastAltUpdate = now
      const cart = viewer.camera.positionCartographic
      if (!cart) return
      const altKm = cart.height / 1000
      const camLat = Cesium.Math.toDegrees(cart.latitude)
      const camLon = Cesium.Math.toDegrees(cart.longitude)
      setCameraAlt(Math.round(altKm))

      // Procedural street traffic (animated vehicles on roads)
      trafficCtrl.update(altKm, camLat, camLon)

      // Altitude-based crossfade: only in hybrid mode (dark/darksat keep full alpha)
      const layers = imageryLayersRef.current
      if (layers.darkStreets && layers.esri && layers.esri.show) {
        const streetAlpha = altKm < 50 ? 0.85
          : altKm > 200 ? 0.0
          : 0.85 * (1 - (altKm - 50) / 150)
        layers.darkStreets.alpha = streetAlpha
      }

      // Viewport-based flight fetch: when user zooms in (<500km alt), fetch flights for current view
      // Throttle to once per 15s and only if camera moved significantly
      if (altKm < 500 && now - lastVpFetch > 15000) {
        const vpLat = Cesium.Math.toDegrees(cart.latitude)
        const vpLon = Cesium.Math.toDegrees(cart.longitude)
        const moved = lastVpLat === null || Math.abs(vpLat - lastVpLat) > 1 || Math.abs(vpLon - lastVpLon) > 1
        if (moved) {
          lastVpFetch = now
          lastVpLat = vpLat
          lastVpLon = vpLon
          const dist = Math.min(250, Math.max(50, Math.round(altKm * 0.8)))
          fetch(`${API_BASE}/flights_viewport?lat=${vpLat.toFixed(2)}&lon=${vpLon.toFixed(2)}&dist=${dist}`)
            .then(r => r.ok ? r.json() : null)
            .then(data => {
              if (!data || !Array.isArray(data)) return
              const ds = dataSourcesRef.current.flights
              if (!ds || !ds.show) return
              // Only update if we got more flights than currently cached
              if (data.length > (ds.entities.values.length || 0)) {
                const cfg = LAYERS.flights
                buildEntities(ds, 'flights', data, cfg)
                scene.requestRender()
              }
            })
            .catch(() => {})
        }
      }
    })

    // HOVER TOOLTIP
    const tooltip = document.createElement('div')
    tooltip.className = 'globe-tooltip'
    tooltip.style.display = 'none'
    containerRef.current.appendChild(tooltip)

    const handler = new Cesium.ScreenSpaceEventHandler(scene.canvas)
    handler.setInputAction((movement) => {
      const picked = scene.pick(movement.endPosition)
      if (picked && picked.id && picked.id._tooltipData) {
        const data = picked.id._tooltipData
        let html = `<div class="tooltip-title">${escapeHtml(data.title)}</div>`
        for (const [k, v] of Object.entries(data.rows || {})) {
          if (v !== undefined && v !== null && v !== '') {
            html += `<div class="tooltip-row"><span class="tooltip-label">${escapeHtml(k)}:</span> <span>${escapeHtml(v)}</span></div>`
          }
        }
        tooltip.innerHTML = html
        tooltip.style.display = 'block'
        const x = clamp(movement.endPosition.x + 15, 0, containerRef.current.clientWidth - 320)
        const y = clamp(movement.endPosition.y - 10, 0, containerRef.current.clientHeight - 200)
        tooltip.style.left = x + 'px'
        tooltip.style.top = y + 'px'
      } else {
        tooltip.style.display = 'none'
      }
    }, Cesium.ScreenSpaceEventType.MOUSE_MOVE)

    // CLICK -- flight detail, video panel, radio panel, or stream open
    handler.setInputAction((click) => {
      const picked = scene.pick(click.position)
      if (picked && picked.id) {
        if (picked.id._flightData) {
          setFlightPanel(picked.id._flightData)
        } else if (picked.id._radioData) {
          setRadioPanel(picked.id._radioData)
        } else if (picked.id._videoData) {
          searchVideos(picked.id._videoData.query)
        } else if (picked.id._cctvData) {
          const cctv = picked.id._cctvData
          if (cctv.stream_url) {
            window.open(cctv.stream_url, '_blank', 'width=800,height=600')
          } else if (isFinite(cctv.lat) && isFinite(cctv.lon)) {
            viewerRef.current.camera.flyTo({
              destination: Cesium.Cartesian3.fromDegrees(cctv.lon, cctv.lat, 500),
              orientation: { heading: 0, pitch: Cesium.Math.toRadians(-45), roll: 0 },
              duration: 1.5,
            })
          }
        }
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK)

    // Poll backend health until it's ready, then hide loading screen
    let loadingDismissed = false
    const pollHealth = async () => {
      while (!loadingDismissed) {
        try {
          const resp = await fetch(`${API_BASE}/health`)
          if (resp.ok) {
            const health = await resp.json()
            const sources = health.sources || {}
            const ready = Object.values(sources).filter(s => s.record_count > 0).length
            const total = Object.keys(sources).length
            if (ready > 0) {
              setLoadingStatus(`LOADING OSINT FEEDS... ${ready}/${total} SOURCES`)
            }
            if (ready >= 18) {
              loadingDismissed = true
              setLoading(false)
              return
            }
          }
        } catch { /* backend not up yet */ }
        setLoadingStatus(prev => prev.includes('CONNECTING') ? 'WAITING FOR BACKEND STARTUP...' : prev)
        await new Promise(r => setTimeout(r, 2000))
      }
    }
    pollHealth()

    return () => {
      loadingDismissed = true
      clearInterval(motionInterval)
      trafficCtrl.destroy()
      handler.destroy()
      viewer.destroy()
    }
  }, [])

  // DATA FETCHING
  const fetchData = useCallback(async (layerKey) => {
    try {
      const resp = await fetch(`${API_BASE}/${layerKey}`)
      if (!resp.ok) return null
      return await resp.json()
    } catch { return null }
  }, [])

  // LOAD LAYER -- fetch data and build entities via buildEntities()
  const loadLayer = useCallback(async (layerKey) => {
    const ds = dataSourcesRef.current[layerKey]
    if (!ds) return

    const data = await fetchData(layerKey)
    if (!data) return

    // Extract items from various response formats
    let items
    if (Array.isArray(data)) {
      items = data
    } else if (data.type === 'FeatureCollection') {
      items = data.features || []
    } else {
      items = data.states || data.data || data.results || data.features ||
              data.flights || data.events || data.fires || data.vessels ||
              data.submarines || data.satellites || data.earthquakes ||
              data.alerts || data.threats || data.incidents || data.bases ||
              data.sanctions || data.zones || data.webcams ||
              data.cameras || data.airports || data.notams || []
    }

    const cfg = LAYERS[layerKey]
    const count = buildEntities(ds, layerKey, items, cfg)

    // Build animated arcs for attack/cyber layers
    if (layerKey === 'missile_tests' || layerKey === 'conflicts') {
      const arcs = extractArcsFromEvents(items)
      if (arcs.length > 0) buildArcs(ds, arcs)
    } else if (layerKey === 'threat_intel' || layerKey === 'cyber') {
      const arcs = extractCyberArcs(items)
      if (arcs.length > 0) buildArcs(ds, arcs)
    }

    // Request render after entity changes (needed for requestRenderMode)
    if (viewerRef.current) viewerRef.current.scene.requestRender()

    // If backend is still prefetching (0 items), retry with backoff (up to ~5 min)
    if (items.length === 0) {
      const retries = retryCountRef.current[layerKey] || 0
      if (retries < 18) {
        retryCountRef.current[layerKey] = retries + 1
        const delay = retries < 6 ? 10000 : 20000
        setTimeout(() => loadLayer(layerKey), delay)
      }
      return
    }
    retryCountRef.current[layerKey] = 0

    // Update layer count in state
    setLayerState(prev => ({
      ...prev,
      [layerKey]: { ...prev[layerKey], count }
    }))

    // Update analytics cards if this is a tracked layer
    if (ANALYTICS_KEYS.includes(layerKey)) {
      setAnalytics(prev => ({ ...prev, [layerKey]: count }))
    }

    // Scan flights for emergency squawk alerts
    if (layerKey === 'flights') {
      const emergencies = items
        .map(it => it.properties || it)
        .filter(p => p.squawk_alert && ['HIJACK', 'RADIO_FAILURE', 'EMERGENCY'].includes(p.squawk_alert))
        .map(p => ({
          callsign: (p.callsign || p.flight || 'UNKNOWN').trim(),
          squawk: p.squawk || '????',
          alert: p.squawk_alert,
        }))
      // Reset dismiss if new/different alerts appear
      setSquawkAlerts(prev => {
        const prevKey = prev.map(a => a.callsign + a.squawk).sort().join(',')
        const newKey = emergencies.map(a => a.callsign + a.squawk).sort().join(',')
        if (newKey !== prevKey) setDismissedSquawk(false)
        return emergencies
      })
    }

    // Extract headlines for news ticker
    if (layerKey === 'news' || layerKey === 'events' || layerKey === 'telegram_osint' || layerKey === 'reddit_osint') {
      const headlines = items
        .filter(it => {
          const p = it.properties || it
          return p.title || p.headline || p.name
        })
        .slice(0, 50)
        .map(it => {
          const p = it.properties || it
          return {
            title: String(p.title || p.headline || p.name || '').substring(0, 120),
            source: p.source || p.domain || (layerKey === 'news' ? 'GDELT' : 'Event'),
            url: p.url || '#',
            country: p.country || '',
          }
        })
      if (headlines.length > 0) {
        setNewsItems(prev => {
          // Merge: keep other layer's items, replace this layer's
          const otherKey = layerKey === 'news' ? 'events' : 'news'
          const other = prev.filter(h => h._layer === otherKey)
          const tagged = headlines.map(h => ({ ...h, _layer: layerKey }))
          return [...tagged, ...other].slice(0, 80)
        })
      }
    }
  }, [fetchData])

  // Map style switching (satellite, hybrid, dark, darksat, 3d)
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) return
    const layers = imageryLayersRef.current
    if (!layers.esri) return
    const scene = viewer.scene

    // Remove 3D tileset if switching away from 3D mode
    if (mapStyle !== '3d' && tiles3dRef.current) {
      scene.primitives.remove(tiles3dRef.current)
      tiles3dRef.current = null
      scene.globe.show = true
      scene.globe.showGroundAtmosphere = true
      scene.globe.depthTestAgainstTerrain = false
    }
    // Remove darksat nightlights overlay when switching away
    if (mapStyle !== 'darksat' && layers.nightlightsOverlay) {
      viewer.imageryLayers.remove(layers.nightlightsOverlay)
      layers.nightlightsOverlay = null
    }

    switch (mapStyle) {
      case 'satellite':
        layers.esri.show = true
        layers.labels.show = true
        layers.darkStreets.show = false
        break
      case 'dark':
        layers.esri.show = false
        layers.labels.show = false
        layers.darkStreets.show = true
        layers.darkStreets.alpha = 1.0
        break
      case 'darksat':
        // Dark basemap + VIIRS nightlights overlay
        layers.esri.show = false
        layers.labels.show = false
        layers.darkStreets.show = true
        layers.darkStreets.alpha = 1.0
        if (!layers.nightlightsOverlay) {
          layers.nightlightsOverlay = addGIBSOverlay(viewer, 'nightlights')
          layers.nightlightsOverlay.alpha = 0.4
        }
        break
      case '3d': {
        if (!tiles3dRef.current) {
          // Keep globe visible until tileset actually loads
          layers.esri.show = true
          layers.labels.show = false
          layers.darkStreets.show = false
          const googleKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY
          const ionToken = import.meta.env.VITE_CESIUM_ION_TOKEN
          const loadTileset = googleKey
            ? Cesium.Cesium3DTileset.fromUrl(
                `https://tile.googleapis.com/v1/3dtiles/root.json?key=${googleKey}`
              )
            : ionToken
              ? Cesium.Cesium3DTileset.fromIonAssetId(2275207, {
                  accessToken: ionToken,
                })
              : null
          if (loadTileset) {
            loadTileset.then(tileset => {
              tiles3dRef.current = scene.primitives.add(tileset)
              // Keep globe visible for CLAMP_TO_GROUND entity positioning
              // but hide imagery so it doesn't z-fight with 3D tiles
              scene.globe.show = true
              scene.globe.baseColor = Cesium.Color.fromCssColorString('#000008')
              scene.globe.showGroundAtmosphere = false
              scene.globe.depthTestAgainstTerrain = false
              layers.esri.show = false
              layers.labels.show = false
              layers.darkStreets.show = false
              scene.requestRender()
            }).catch(() => {
              setMapStyle('hybrid')
            })
          } else {
            // No API key — fall back to hybrid
            setMapStyle('hybrid')
          }
        }
        break
      }
      case 'hybrid':
      default:
        layers.esri.show = true
        layers.labels.show = true
        layers.darkStreets.show = true
        break
    }
    scene.requestRender()
  }, [mapStyle])

  // Visual filter switching
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) return
    removeAllFilters(viewer)
    const creators = { crt: createCRTStage, nvg: createNVGStage, flir: createFLIRStage, anime: createAnimeStage, reticle: createReticleStage }
    if (creators[visualFilter]) {
      viewer.scene.postProcessStages.add(creators[visualFilter]())
    }
    viewer.scene.requestRender()
  }, [visualFilter])

  // GIBS overlay toggling
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) return
    for (const key of Object.keys(GIBS_LAYERS)) {
      if (gibsActive[key] && !gibsLayerRefs.current[key]) {
        gibsLayerRefs.current[key] = addGIBSOverlay(viewer, key)
      } else if (!gibsActive[key] && gibsLayerRefs.current[key]) {
        removeGIBSOverlay(viewer, gibsLayerRefs.current[key])
        delete gibsLayerRefs.current[key]
      }
    }
    viewer.scene.requestRender()
  }, [gibsActive])

  // Google traffic tiles overlay
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) return
    if (trafficOverlay && !trafficTilesRef.current) {
      const provider = new Cesium.UrlTemplateImageryProvider({
        url: 'https://mt0.google.com/vt?lyrs=h,traffic&x={x}&y={y}&z={z}',
        maximumLevel: 18,
        credit: new Cesium.Credit('Google Traffic'),
      })
      trafficTilesRef.current = viewer.imageryLayers.addImageryProvider(provider)
      trafficTilesRef.current.alpha = 0.7
    } else if (!trafficOverlay && trafficTilesRef.current) {
      viewer.imageryLayers.remove(trafficTilesRef.current)
      trafficTilesRef.current = null
    }
    viewer.scene.requestRender()
  }, [trafficOverlay])

  // Load visible layers and set up refresh intervals
  useEffect(() => {
    for (const [key, state] of Object.entries(layerState)) {
      const ds = dataSourcesRef.current[key]
      if (ds) ds.show = state.visible

      if (state.visible) {
        if (!intervalsRef.current[key]) {
          const ms = LAYERS[key].refreshMs
          intervalsRef.current[key] = setInterval(() => loadLayer(key), ms)
          loadLayer(key) // Single initial fetch when enabling layer
        }
      } else {
        if (intervalsRef.current[key]) {
          clearInterval(intervalsRef.current[key])
          delete intervalsRef.current[key]
        }
      }
    }
  }, [layerState, loadLayer])

  // Toggle layer visibility
  const toggleLayer = useCallback((key) => {
    setLayerState(prev => ({
      ...prev,
      [key]: { ...prev[key], visible: !prev[key].visible }
    }))
  }, [])

  // Toggle group collapse in sidebar
  const toggleGroup = useCallback((group) => {
    setCollapsedGroups(prev => ({ ...prev, [group]: !prev[group] }))
  }, [])

  // Stable callbacks for child components (avoids breaking React.memo)
  const toggleSidebar = useCallback(() => setSidebarOpen(prev => !prev), [])
  const closeFlightPanel = useCallback(() => setFlightPanel(null), [])
  const closeVideoPanel = useCallback(() => setVideoPanel(null), [])
  const closeAnalysisPanel = useCallback(() => setAnalysisPanel(null), [])
  const closeRadioPanel = useCallback(() => setRadioPanel(null), [])
  const flyToLocation = useCallback((lon, lat) => {
    viewerRef.current?.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(lon, lat, 500000),
      duration: 1.5,
    })
  }, [])

  // Open analysis panel for a region/entity
  const openAnalysis = useCallback(async (context) => {
    setAnalysisPanel({ loading: true, briefing: '', threat_level: '', predictions: [], ...context })
    try {
      const resp = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(context),
      })
      if (resp.ok) {
        const data = await resp.json()
        setAnalysisPanel(prev => prev ? { ...prev, ...data, loading: false } : null)
      } else {
        setAnalysisPanel(prev => prev ? { ...prev, loading: false, briefing: 'Analysis unavailable. Configure AZURE_OPENAI_ENDPOINT.' } : null)
      }
    } catch {
      setAnalysisPanel(prev => prev ? { ...prev, loading: false, briefing: 'Analysis service unavailable.' } : null)
    }
  }, [])

  // Search YouTube videos for a topic
  const searchVideos = useCallback(async (query) => {
    setVideoPanel({ loading: true, query, videos: [] })
    try {
      const resp = await fetch(`${API_BASE}/youtube_search?q=${encodeURIComponent(query)}`)
      if (resp.ok) {
        const data = await resp.json()
        setVideoPanel(prev => prev ? { ...prev, ...data, loading: false } : null)
      } else {
        setVideoPanel(prev => prev ? { ...prev, loading: false } : null)
      }
    } catch {
      setVideoPanel(prev => prev ? { ...prev, loading: false } : null)
    }
  }, [])

  // Fly to preset location (with cinematic heading/pitch)
  const flyToPreset = useCallback((preset) => {
    const heading = Cesium.Math.toRadians(preset.heading ?? 0)
    const pitch = Cesium.Math.toRadians(preset.pitch ?? -90)
    viewerRef.current?.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(preset.lon, preset.lat, preset.alt),
      orientation: { heading, pitch, roll: 0 },
      duration: 1.5,
    })
  }, [])

  // Search location via OpenStreetMap Nominatim
  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) return
    try {
      const resp = await fetch(
        'https://nominatim.openstreetmap.org/search?q=' +
        encodeURIComponent(searchQuery) +
        '&format=json&limit=1'
      )
      const results = await resp.json()
      if (results[0]) {
        const { lon, lat } = results[0]
        viewerRef.current?.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(parseFloat(lon), parseFloat(lat), 500000),
          duration: 1.5,
        })
      }
    } catch { /* ignore search errors */ }
  }, [searchQuery])

  // Flight tracking -- fly to aircraft and show detail info
  const trackFlight = useCallback(async (icao24) => {
    if (!icao24 || !viewerRef.current) return
    try {
      const resp = await fetch(API_BASE + '/flight_detail/' + icao24)
      if (!resp.ok) return
      const detail = await resp.json()

      // Fly camera to the aircraft position
      const state = detail.state
      if (state && isFinite(state.longitude) && isFinite(state.latitude)) {
        viewerRef.current.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(
            state.longitude, state.latitude,
            Math.max((state.baro_altitude || 10000) * 3, 50000)
          ),
          duration: 1.5,
        })
      }

      // Draw track polyline if waypoints available
      const waypoints = detail.track || detail.path || detail.route || detail.waypoints || []
      if (waypoints.length > 1) {
        const positions = []
        for (const wp of waypoints) {
          const wlon = wp.longitude ?? wp.lon ?? wp[0]
          const wlat = wp.latitude ?? wp.lat ?? wp[1]
          const walt = wp.altitude ?? wp.alt ?? wp[2] ?? 10000
          if (isFinite(wlon) && isFinite(wlat)) {
            positions.push(Cesium.Cartesian3.fromDegrees(wlon, wlat, isFinite(walt) ? walt : 10000))
          }
        }
        if (positions.length > 1) {
          viewerRef.current.entities.add({
            polyline: {
              positions,
              width: 4,
              material: new Cesium.PolylineGlowMaterialProperty({
                glowPower: 0.25,
                color: Cesium.Color.CYAN.withAlpha(0.8),
              }),
              clampToGround: false,
            },
          })
          viewerRef.current.scene.requestRender()
        }
      }

      // Update flight panel with latest detail
      if (state) {
        setFlightPanel(prev => prev ? { ...prev, ...state } : state)
      }
    } catch { /* ignore tracking errors */ }
  }, [])

  return (
    <>
      {/* Loading Screen */}
      {loading && (
        <div className="loading-screen">
          <div className="loading-spinner" />
          <h1>AGUS</h1>
          <p>{loadingStatus}</p>
        </div>
      )}

      {/* Emergency Squawk Alert Banner */}
      {squawkAlerts.length > 0 && !dismissedSquawk && (
        <div className="squawk-alert-banner">
          <span className="squawk-alert-icon">WARNING</span>
          {squawkAlerts.map((a, i) => (
            <span key={i} className="squawk-alert-item">
              {a.callsign} SQUAWK {a.squawk} — {a.alert}
            </span>
          ))}
          <button className="squawk-dismiss" onClick={() => setDismissedSquawk(true)} title="Dismiss">&times;</button>
        </div>
      )}

      <div className={'app-container' + (sidebarOpen ? '' : ' sidebar-collapsed')}>
        <TopBar
          onMenuToggle={toggleSidebar}
          onFlyToPreset={flyToPreset}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          onSearch={handleSearch}
          cameraAlt={cameraAlt}
          mapStyle={mapStyle}
          onMapStyleChange={setMapStyle}
          onAnalyze={openAnalysis}
          visualFilter={visualFilter}
          onVisualFilterChange={setVisualFilter}
          gibsActive={gibsActive}
          onGibsToggle={setGibsActive}
          trafficOverlay={trafficOverlay}
          onTrafficToggle={setTrafficOverlay}
        />

        <Sidebar
          layers={LAYERS}
          layerState={layerState}
          onToggle={toggleLayer}
          collapsedGroups={collapsedGroups}
          onToggleGroup={toggleGroup}
          isOpen={sidebarOpen}
        />

        {/* Globe */}
        <div className="globe-container" ref={containerRef} />

        <FlightPanel
          flight={flightPanel}
          onClose={closeFlightPanel}
          onTrack={trackFlight}
        />

        <VideoPanel
          data={videoPanel}
          onClose={closeVideoPanel}
        />

        <AnalysisPanel
          data={analysisPanel}
          onClose={closeAnalysisPanel}
          onFlyTo={flyToLocation}
        />

        <RadioPanel
          data={radioPanel}
          onClose={closeRadioPanel}
        />

        <AnalyticsCards analytics={analytics} />

        <NewsTicker items={newsItems} />

        <BottomBar cameraAlt={cameraAlt} />
      </div>
    </>
  )
}
