function weatherPoint() {
  const sourceText = document.getElementById("source-text");
  const mapDiv = document.getElementById("map");
  if (sourceText && sourceText.textContent !== "not set") {
    const parts = sourceText.textContent.split(",");
    if (parts.length === 2) {
      return {
        lat: parts[0].trim(),
        lon: parts[1].trim(),
        label: "source pin",
      };
    }
  }
  return {
    lat: mapDiv ? mapDiv.dataset.lat : "",
    lon: mapDiv ? mapDiv.dataset.lon : "",
    label: "map centre",
  };
}

function formatWeather(data, label) {
  const lines = [
    "Point: " + label,
    "Time: " + (data.timestamp || "unknown"),
    "Temperature: " + data.temperature_c + " °C",
    "Feels like: " + data.apparent_temperature_c + " °C",
    "Humidity: " + data.relative_humidity_percent + " %",
    "Wind: " + data.wind_speed_kmh + " km/h",
    "Cloud cover: " + data.cloud_cover_percent + " %",
    "Precipitation: " + data.precipitation_mm + " mm",
    "Solar (shortwave): " + data.shortwave_radiation_wm2 + " W/m²",
    "Condition: " + data.weather_condition,
  ];
  return lines.join(" | ");
}

async function loadWeather() {
  const box = document.getElementById("weather-text");
  if (!box) {
    return;
  }

  const point = weatherPoint();
  box.textContent = "Loading weather...";

  try {
    const url = "/api/weather?lat=" + encodeURIComponent(point.lat) +
      "&lon=" + encodeURIComponent(point.lon);
    const response = await fetch(url);
    const data = await response.json();
    if (!response.ok || !data.ok) {
      box.textContent = data.error || "Weather request failed.";
      return;
    }
    box.textContent = formatWeather(data, point.label);
  } catch (error) {
    box.textContent = "Could not reach /api/weather. Is Flask running?";
  }
}

async function loadStatus() {
  const box = document.getElementById("status-text");
  if (!box) {
    return;
  }

  box.textContent = "Checking...";

  try {
    const response = await fetch("/api/status");
    if (!response.ok) {
      throw new Error("Status request failed");
    }
    const data = await response.json();
    box.textContent = data.ok
      ? data.message + " (" + data.time_utc + ")"
      : "Backend reported a problem.";
  } catch (error) {
    box.textContent = "Could not reach /api/status. Is Flask running?";
  }
}

async function runMlDemo() {
  const status = document.getElementById("ml-prediction-status");
  const button = document.getElementById("run-ml-demo");
  if (!status || !button) return;

  const fields = {
    air_temperature_c: "ml-air-temperature",
    relative_humidity_percent: "ml-humidity",
    solar_radiation_wm2: "ml-solar",
    wind_speed_kmh: "ml-wind",
    distance_to_centre_km: "ml-distance",
    vegetation_proxy: "ml-vegetation",
    building_density_proxy: "ml-buildings",
  };
  const features = {};
  for (const [name, id] of Object.entries(fields)) {
    const input = document.getElementById(id);
    const value = input ? Number(input.value) : NaN;
    if (!input || input.value.trim() === "" || !Number.isFinite(value)) {
      status.textContent = "Enter a valid number for every demo input.";
      return;
    }
    features[name] = value;
  }

  button.disabled = true;
  status.textContent = "Running the local synthetic-model demonstration...";
  try {
    const response = await fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ features: features }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "Prediction request failed.");
    }
    status.textContent = "Synthetic demo estimate: " +
      Number(data.estimated_heat_c).toFixed(2) + " °C; model: " + data.model_name +
      ". Data source: " + data.data_source + ". " + data.disclaimer +
      (data.history_saved
        ? " Saved in local demo history."
        : " " + (data.history_message || "Could not save to local demo history."));
    if (data.history_saved) await loadPredictionHistory();
  } catch (error) {
    status.textContent = error.message || "Could not reach /api/predict.";
  } finally {
    button.disabled = false;
  }
}

async function loadMlMetrics() {
  const status = document.getElementById("ml-metrics-status");
  const results = document.getElementById("ml-metrics-results");
  if (!status || !results) return;

  status.textContent = "Loading saved synthetic metrics...";
  results.replaceChildren();
  try {
    const response = await fetch("/api/ml/metrics");
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "Could not load saved model metrics.");
    }

    const heading = document.createElement("p");
    heading.textContent = "Selected model: " + data.selected_model +
      " (selection metric: " + data.selection_metric + ").";
    results.appendChild(heading);

    const validationHeading = document.createElement("h4");
    validationHeading.textContent = "Validation MAE by candidate (°C)";
    results.appendChild(validationHeading);
    const validationList = document.createElement("ul");
    validationList.className = "ml-metric-list";
    Object.entries(data.validation_results).forEach(function ([name, scores]) {
      const item = document.createElement("li");
      item.textContent = name + ": " + Number(scores.validation_mae_c).toFixed(3);
      validationList.appendChild(item);
    });
    results.appendChild(validationList);

    const test = data.test_metrics;
    const testLine = document.createElement("p");
    testLine.textContent = "Held-out test (" + test.test_rows + " rows): MAE " +
      Number(test.mae_c).toFixed(3) + " °C; RMSE " + Number(test.rmse_c).toFixed(3) +
      " °C; R² " + Number(test.r2).toFixed(3) + ".";
    results.appendChild(testLine);

    const disclaimer = document.createElement("p");
    disclaimer.className = "note";
    disclaimer.textContent = data.disclaimer;
    results.appendChild(disclaimer);
    status.textContent = "Saved evaluation reports loaded. Source: " + data.data_source + ".";
  } catch (error) {
    status.textContent = error.message || "Could not reach /api/ml/metrics.";
  }
}

async function loadPredictionHistory() {
  const status = document.getElementById("prediction-history-status");
  const list = document.getElementById("prediction-history");
  if (!status || !list) return;

  status.textContent = "Loading saved demo runs...";
  list.replaceChildren();
  try {
    const response = await fetch("/api/predictions?limit=10");
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "Could not load synthetic demo history.");
    }
    if (data.history_enabled === false) {
      status.textContent = data.message;
      return;
    }
    if (data.items.length === 0) {
      status.textContent = "No saved demo runs yet. Run the synthetic model demo to add one.";
      return;
    }

    data.items.forEach(function (prediction) {
      const card = document.createElement("article");
      card.className = "history-item";
      const heading = document.createElement("h4");
      heading.textContent = "Synthetic demo — " +
        new Date(prediction.created_at).toLocaleString();
      card.appendChild(heading);

      const summary = document.createElement("p");
      summary.textContent = "Estimate: " + Number(prediction.estimated_heat_c).toFixed(2) +
        " °C; model: " + prediction.model_name + "; source: " + prediction.data_source + ".";
      card.appendChild(summary);

      const deleteButton = document.createElement("button");
      deleteButton.type = "button";
      deleteButton.className = "secondary";
      deleteButton.textContent = "Delete this demo run";
      deleteButton.addEventListener("click", async function () {
        deleteButton.disabled = true;
        try {
          const deleteResponse = await fetch(
            "/api/predictions/" + encodeURIComponent(prediction.prediction_id),
            { method: "DELETE" }
          );
          const deleteData = await deleteResponse.json();
          if (!deleteResponse.ok || !deleteData.ok) {
            throw new Error(deleteData.error || "Could not delete demo history.");
          }
          await loadPredictionHistory();
        } catch (error) {
          status.textContent = error.message;
          deleteButton.disabled = false;
        }
      });
      card.appendChild(deleteButton);
      list.appendChild(card);
    });
    status.textContent = data.items.length + " recent synthetic demo run(s).";
  } catch (error) {
    status.textContent = error.message || "Could not reach /api/predictions.";
  }
}

function formatHistoryCoordinate(value) {
  return Number(value).toFixed(5);
}

async function loadRouteHistory() {
  const status = document.getElementById("history-status");
  const list = document.getElementById("route-history");
  if (!status || !list) return;

  status.textContent = "Loading saved routes...";
  list.replaceChildren();

  try {
    const response = await fetch("/api/history?limit=30");
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "Could not load route history.");
    }
    if (data.history_enabled === false) {
      status.textContent = data.message;
      return;
    }

    const searches = new Map();
    data.items.forEach(function (item) {
      if (!searches.has(item.search_id)) {
        searches.set(item.search_id, {
          id: item.search_id,
          created_at: item.created_at,
          source_lat: item.source_lat,
          source_lon: item.source_lon,
          destination_lat: item.destination_lat,
          destination_lon: item.destination_lon,
          routes: [],
        });
      }
      searches.get(item.search_id).routes.push(item);
    });

    if (searches.size === 0) {
      status.textContent = "No saved routes yet. Calculate or compare a route to add history.";
      return;
    }

    const modeOrder = { shortest: 0, balanced: 1, cooler: 2 };
    searches.forEach(function (search) {
      const card = document.createElement("article");
      card.className = "history-item";

      const heading = document.createElement("h3");
      heading.textContent = "Route search — " + new Date(search.created_at).toLocaleString();
      card.appendChild(heading);

      const points = document.createElement("p");
      points.textContent = "From " +
        formatHistoryCoordinate(search.source_lat) + ", " +
        formatHistoryCoordinate(search.source_lon) + " to " +
        formatHistoryCoordinate(search.destination_lat) + ", " +
        formatHistoryCoordinate(search.destination_lon);
      card.appendChild(points);

      const routeList = document.createElement("ul");
      routeList.className = "history-routes";
      search.routes.sort(function (a, b) {
        return modeOrder[a.mode] - modeOrder[b.mode];
      }).forEach(function (route) {
        const item = document.createElement("li");
        item.textContent = route.mode.charAt(0).toUpperCase() + route.mode.slice(1) +
          ": " + route.distance_km + " km, " + route.estimated_time_min +
          " min, average heat " + route.average_estimated_temp_c +
          " °C, exposure " + route.heat_exposure_degree_km + " °C·km";
        routeList.appendChild(item);
      });
      card.appendChild(routeList);

      const deleteButton = document.createElement("button");
      deleteButton.type = "button";
      deleteButton.className = "secondary";
      deleteButton.textContent = "Delete this history item";
      deleteButton.addEventListener("click", async function () {
        deleteButton.disabled = true;
        try {
          const deleteResponse = await fetch(
            "/api/history/" + encodeURIComponent(search.id),
            { method: "DELETE" }
          );
          const deleteData = await deleteResponse.json();
          if (!deleteResponse.ok || !deleteData.ok) {
            throw new Error(deleteData.error || "Could not delete route history.");
          }
          await loadRouteHistory();
        } catch (error) {
          status.textContent = error.message;
          deleteButton.disabled = false;
        }
      });
      card.appendChild(deleteButton);
      list.appendChild(card);
    });

    status.textContent = searches.size + " saved route search(es).";
  } catch (error) {
    status.textContent = error.message;
  }
}

document.addEventListener("DOMContentLoaded", function () {
  loadStatus();
  loadWeather();
  loadRouteHistory();
  loadMlMetrics();
  loadPredictionHistory();
  const statusButton = document.getElementById("status-btn");
  if (statusButton) {
    statusButton.addEventListener("click", loadStatus);
  }
  const weatherButton = document.getElementById("weather-btn");
  if (weatherButton) {
    weatherButton.addEventListener("click", loadWeather);
  }
  const mlDemoButton = document.getElementById("run-ml-demo");
  if (mlDemoButton) {
    mlDemoButton.addEventListener("click", runMlDemo);
  }
  const predictionHistoryButton = document.getElementById("refresh-prediction-history");
  if (predictionHistoryButton) {
    predictionHistoryButton.addEventListener("click", loadPredictionHistory);
  }
  const historyButton = document.getElementById("refresh-history");
  if (historyButton) {
    historyButton.addEventListener("click", loadRouteHistory);
  }
});
