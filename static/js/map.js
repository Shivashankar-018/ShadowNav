function formatCoord(value) {
  return Number(value).toFixed(5);
}

function initMap() {
  const mapDiv = document.getElementById("map");
  if (!mapDiv || typeof L === "undefined") {
    return;
  }

  const lat = Number(mapDiv.dataset.lat);
  const lon = Number(mapDiv.dataset.lon);
  const zoom = Number(mapDiv.dataset.zoom);
  const halfSize = Number(mapDiv.dataset.halfSize);

  const map = L.map("map", { maxBoundsViscosity: 1.0 }).setView([lat, lon], zoom);
  const studyBounds = L.latLngBounds(
    [lat - halfSize, lon - halfSize],
    [lat + halfSize, lon + halfSize]
  );
  map.setMaxBounds(studyBounds);
  map.fitBounds(studyBounds, { padding: [12, 12] });

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);

  let pickMode = "source";
  let sourceMarker = null;
  let destMarker = null;
  let routeLayers = [];

  const sourceText = document.getElementById("source-text");
  const destText = document.getElementById("dest-text");
  const sourceBtn = document.getElementById("pick-source");
  const destBtn = document.getElementById("pick-dest");
  const clearBtn = document.getElementById("clear-points");
  const routeButton = document.getElementById("calculate-route");
  const compareButton = document.getElementById("compare-routes");
  const routeMode = document.getElementById("route-mode");
  const routeStatus = document.getElementById("route-status");
  const routeResults = document.getElementById("route-results");
  const comparisonResults = document.getElementById("route-comparison");
  const routeColors = {
    shortest: "#60a5fa",
    balanced: "#f97316",
    cooler: "#22d3ee",
  };

  function clearRoute() {
    routeLayers.forEach(function (layer) { map.removeLayer(layer); });
    routeLayers = [];
    if (routeResults) {
      routeResults.hidden = true;
    }
    if (comparisonResults) {
      comparisonResults.hidden = true;
    }
  }

  function setRouteButtonsBusy(busy) {
    if (routeButton) routeButton.disabled = busy;
    if (compareButton) compareButton.disabled = busy;
  }

  function ensureRoutePane() {
    if (!map.getPane("routePane")) {
      map.createPane("routePane");
      map.getPane("routePane").style.zIndex = 390;
    }
  }

  function addRouteLayer(data, mode, weight, opacity) {
    ensureRoutePane();
    const layer = L.geoJSON(data, {
      pane: "routePane",
      interactive: false,
      style: {
        color: routeColors[mode],
        weight: weight,
        opacity: opacity,
      },
    }).addTo(map);
    routeLayers.push(layer);
    return layer;
  }

  function routeRequestBody() {
    const source = sourceMarker.getLatLng();
    const destination = destMarker.getLatLng();
    return {
      source_lat: source.lat,
      source_lon: source.lng,
      destination_lat: destination.lat,
      destination_lon: destination.lng,
    };
  }

  function showMetric(id, value) {
    const element = document.getElementById(id);
    if (element) {
      element.textContent = value;
    }
  }

  async function calculateRoute() {
    if (!sourceMarker || !destMarker) {
      if (routeStatus) {
        routeStatus.textContent = "Set both a source and destination on the map first.";
      }
      return;
    }

    clearRoute();
    const selectedMode = routeMode ? routeMode.value : "balanced";
    if (routeStatus) {
      routeStatus.textContent = "Calculating route. The first road-network download may take a few minutes.";
    }
    setRouteButtonsBusy(true);

    try {
      const response = await fetch("/api/route", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...routeRequestBody(), mode: selectedMode }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error || "Route request failed.");
      }

      const routeLayer = addRouteLayer(data, selectedMode, 7, 0.95);

      const props = data.properties;
      showMetric("route-distance", props.distance_km + " km");
      showMetric("route-time", props.estimated_time_min + " min");
      showMetric("route-average-heat", props.average_estimated_temp_c + " °C");
      showMetric("route-max-heat", props.maximum_estimated_temp_c + " °C");
      showMetric("route-exposure", props.heat_exposure_degree_km + " °C·km");
      showMetric("route-high-risk", props.high_risk_segment_percent + "%");
      showMetric("route-disclaimer", props.disclaimer);
      if (routeResults) {
        routeResults.hidden = false;
      }
      if (routeStatus) {
        routeStatus.textContent = selectedMode.charAt(0).toUpperCase() +
          selectedMode.slice(1) + " route calculated. Estimated walking speed: " +
          props.walking_speed_kmh_assumption + " km/h." +
          (data.history_saved === false
            ? " " + (data.history_message || "Local history could not be saved.")
            : " Saved to local history.");
      }
      if (data.history_saved !== false) loadRouteHistory();
      map.fitBounds(routeLayer.getBounds(), { padding: [28, 28] });
    } catch (error) {
      if (routeStatus) {
        routeStatus.textContent = error.message;
      }
    } finally {
      setRouteButtonsBusy(false);
    }
  }

  async function compareRoutes() {
    if (!sourceMarker || !destMarker) {
      if (routeStatus) {
        routeStatus.textContent = "Set both a source and a destination on the map first.";
      }
      return;
    }

    clearRoute();
    if (routeStatus) {
      routeStatus.textContent = "Calculating three route options. The first request may take a few minutes.";
    }
    setRouteButtonsBusy(true);

    try {
      const response = await fetch("/api/routes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(routeRequestBody()),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error || "Route comparison failed.");
      }

      // Draw the shared paths first so each differently coloured route remains
      // visible where it takes a different street.
      const modes = ["shortest", "balanced", "cooler"];
      ["balanced", "cooler", "shortest"].forEach(function (mode) {
        const route = data.routes[mode];
        if (!route) throw new Error("The server did not return the " + mode + " route.");
        addRouteLayer(route, mode, mode === "shortest" ? 6 : 5, 0.82);
        const props = route.properties;
        const prefix = "compare-" + mode + "-";
        showMetric(prefix + "distance", props.distance_km + " km");
        showMetric(prefix + "time", props.estimated_time_min + " min");
        showMetric(prefix + "average", props.average_estimated_temp_c + " °C");
        showMetric(prefix + "maximum", props.maximum_estimated_temp_c + " °C");
        showMetric(prefix + "exposure", props.heat_exposure_degree_km + " °C·km");
        showMetric(prefix + "risk", props.high_risk_segment_percent + "%");
      });

      const distinctPaths = new Set(
        modes.map(function (mode) {
          return JSON.stringify(data.routes[mode].geometry.coordinates);
        })
      ).size;
      showMetric(
        "route-comparison-note",
        distinctPaths === 1
          ? "All three preferences chose the same streets for these points, so their coloured lines overlap. Try a longer trip to explore other tradeoffs."
          : distinctPaths + " distinct paths were found. Some route sections may overlap."
      );

      if (comparisonResults) comparisonResults.hidden = false;
      const combinedRoutes = L.featureGroup(routeLayers);
      map.fitBounds(combinedRoutes.getBounds(), { padding: [28, 28] });
      if (routeStatus) {
        routeStatus.textContent = "Shortest, balanced, and cooler candidate routes are shown with their metrics." +
          (data.history_saved === false
            ? " " + (data.history_message || "Local history could not be saved.")
            : " Saved to local history.");
      }
      if (data.history_saved !== false) loadRouteHistory();
    } catch (error) {
      clearRoute();
      if (routeStatus) routeStatus.textContent = error.message;
    } finally {
      setRouteButtonsBusy(false);
    }
  }

  function setActiveButtons() {
    if (!sourceBtn || !destBtn) {
      return;
    }
    sourceBtn.classList.toggle("active", pickMode === "source");
    destBtn.classList.toggle("active", pickMode === "destination");
  }

  function placeSource(latlng) {
    clearRoute();
    if (routeStatus) {
      routeStatus.textContent = "Source set. Now set a destination.";
    }
    if (sourceMarker) {
      sourceMarker.setLatLng(latlng);
    } else {
      sourceMarker = L.circleMarker(latlng, {
        radius: 10,
        color: "#166534",
        fillColor: "#22c55e",
        fillOpacity: 0.9,
        weight: 2,
      }).addTo(map);
    }
    sourceMarker.bindPopup("Source (start)").openPopup();
    if (sourceText) {
      sourceText.textContent =
        formatCoord(latlng.lat) + ", " + formatCoord(latlng.lng);
    }
  }

  function placeDest(latlng) {
    clearRoute();
    if (routeStatus) {
      routeStatus.textContent = "Destination set. Choose a preference and calculate the route.";
    }
    if (destMarker) {
      destMarker.setLatLng(latlng);
    } else {
      destMarker = L.circleMarker(latlng, {
        radius: 10,
        color: "#991b1b",
        fillColor: "#ef4444",
        fillOpacity: 0.9,
        weight: 2,
      }).addTo(map);
    }
    destMarker.bindPopup("Destination (end)").openPopup();
    if (destText) {
      destText.textContent =
        formatCoord(latlng.lat) + ", " + formatCoord(latlng.lng);
    }
  }

  function handlePointClick(event) {
    if (pickMode === "source") {
      placeSource(event.latlng);
      pickMode = "destination";
    } else {
      placeDest(event.latlng);
      pickMode = "source";
    }
    setActiveButtons();
  }

  function handleOverlayPointClick(event) {
    // GeoJSON feature events also propagate to Leaflet's map. Mark the
    // original browser event so the map handler does not process it twice.
    if (event.originalEvent) {
      event.originalEvent._shadowNavPointHandled = true;
    }
    handlePointClick(event);
  }

  map.on("click", function (event) {
    if (event.originalEvent && event.originalEvent._shadowNavPointHandled) {
      return;
    }
    handlePointClick(event);
  });

  if (sourceBtn) {
    sourceBtn.addEventListener("click", function () {
      pickMode = "source";
      setActiveButtons();
    });
  }

  if (destBtn) {
    destBtn.addEventListener("click", function () {
      pickMode = "destination";
      setActiveButtons();
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", function () {
      if (sourceMarker) {
        map.removeLayer(sourceMarker);
        sourceMarker = null;
      }
      if (destMarker) {
        map.removeLayer(destMarker);
        destMarker = null;
      }
      if (sourceText) {
        sourceText.textContent = "not set";
      }
      if (destText) {
        destText.textContent = "not set";
      }
      clearRoute();
      if (routeStatus) {
        routeStatus.textContent = "Pins cleared. Choose source and destination points to calculate a route.";
      }
      pickMode = "source";
      setActiveButtons();
    });
  }

  if (routeButton) {
    routeButton.addEventListener("click", calculateRoute);
  }
  if (compareButton) {
    compareButton.addEventListener("click", compareRoutes);
  }

  setActiveButtons();
  loadHeatLayer(map, lat, lon, handleOverlayPointClick);
}

function riskPopup(props) {
  return (
    "<strong>" + props.heat_risk + "</strong><br>" +
    "Estimated: " + props.estimated_temp_c + " °C<br>" +
    "Open-Meteo base: " + props.base_temp_c + " °C<br>" +
    "Prototype UHI offset: +" + props.uhi_proxy_c + " °C<br>" +
    "Time: " + props.timestamp
  );
}

async function loadHeatLayer(map, lat, lon, onPointClick) {
  const status = document.getElementById("heat-status");
  const legendBox = document.getElementById("heat-legend");
  const toggle = document.getElementById("toggle-heat");

  if (!map.getPane("heatPane")) {
    map.createPane("heatPane");
  }
  map.getPane("heatPane").style.zIndex = 350;

  try {
    const response = await fetch(
      "/api/heatmap?lat=" + encodeURIComponent(lat) +
      "&lon=" + encodeURIComponent(lon)
    );
    const data = await response.json();
    if (!response.ok || !data.ok) {
      if (status) {
        status.textContent = data.error || "Heat layer failed to load.";
      }
      return;
    }

    const heatLayer = L.geoJSON(data, {
      pane: "heatPane",
      style: function (feature) {
        return {
          color: "#0f172a",
          weight: 1,
          fillColor: feature.properties.color,
          fillOpacity: 0.45,
          bubblingMouseEvents: false,
        };
      },
      onEachFeature: function (feature, layer) {
        layer.bindPopup(riskPopup(feature.properties));
      },
    }).addTo(map);
    heatLayer.on("click", onPointClick);

    if (legendBox && data.legend) {
      legendBox.innerHTML = data.legend.map(function (item) {
        return (
          '<span class="legend-item">' +
          '<span class="legend-swatch" style="background:' + item.color + '"></span>' +
          item.label + " (" + item.rule + ")" +
          "</span>"
        );
      }).join("");
    }

    if (toggle) {
      toggle.addEventListener("change", function () {
        if (toggle.checked) {
          if (!map.hasLayer(heatLayer)) {
            heatLayer.addTo(map);
          }
        } else {
          map.removeLayer(heatLayer);
        }
      });
    }

    if (status) {
      status.textContent =
        data.cell_count + " prototype cells. " + data.disclaimer;
    }
  } catch (error) {
    if (status) {
      status.textContent = "Could not reach /api/heatmap.";
    }
  }

  loadRoadLayer(map, lat, lon, onPointClick);
}

async function loadRoadLayer(map, lat, lon, onPointClick) {
  const status = document.getElementById("road-status");
  const toggle = document.getElementById("toggle-roads");

  if (!map.getPane("roadPane")) {
    map.createPane("roadPane");
  }
  map.getPane("roadPane").style.zIndex = 380;

  try {
    const response = await fetch(
      "/api/roads?lat=" + encodeURIComponent(lat) +
      "&lon=" + encodeURIComponent(lon)
    );
    const data = await response.json();
    if (!response.ok || !data.ok) {
      if (status) {
        status.textContent = data.error || "Walking streets failed to load.";
      }
      return;
    }

    const roadLayer = L.geoJSON(data, {
      pane: "roadPane",
      style: function (feature) {
        return {
          color: feature.properties.color,
          weight: 3,
          opacity: 0.9,
          bubblingMouseEvents: false,
        };
      },
      onEachFeature: function (feature, layer) {
        const props = feature.properties;
        layer.bindPopup(
          "<strong>" + props.name + "</strong><br>" +
          "Type: " + props.highway + "<br>" +
          "Length: " + props.length_m + " m<br>" +
          "Heat risk: " + props.heat_risk + " (" + props.estimated_temp_c + " °C)"
        );
      },
    }).addTo(map);
    roadLayer.on("click", onPointClick);

    if (toggle) {
      toggle.addEventListener("change", function () {
        if (toggle.checked) {
          if (!map.hasLayer(roadLayer)) {
            roadLayer.addTo(map);
          }
        } else {
          map.removeLayer(roadLayer);
        }
      });
    }

    if (status) {
      status.textContent =
        data.edge_count + " walking segments, " +
        data.node_count + " junctions. " + data.disclaimer;
    }
  } catch (error) {
    if (status) {
      status.textContent = "Could not reach /api/roads.";
    }
  }
}

document.addEventListener("DOMContentLoaded", initMap);
