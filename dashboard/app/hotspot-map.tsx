"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import MapLegend from "./map-legend";
import { buildingPosition, formatLevel, type BuildingListItem } from "../lib/analysis";

const countyBounds: L.LatLngBoundsExpression = [[33.65, -118.95], [34.83, -117.63]];

function resetView(map: L.Map) {
  map.fitBounds(countyBounds, { padding: [16, 16], animate: false });
}

function markerIcon(building: BuildingListItem, selected = false) {
  const style = building.approximate_location
    ? " hotspot-approximate"
    : building.verified_location ? " hotspot-verified" : "";
  return L.divIcon({
    className: `hotspot-marker hotspot-${building.review_level}${style}${selected ? " is-selected" : ""}`,
    iconSize: [24, 24],
    popupAnchor: [0, -7],
  });
}

function popupContent(building: BuildingListItem) {
  const content = document.createElement("div");
  content.className = "hotspot-popup";
  const address = document.createElement("strong");
  address.textContent = building.building_key;
  const details = document.createElement("p");
  const score = Number.isFinite(building.total_score) ? Math.round(building.total_score) : "Unavailable";
  details.textContent = `${building.hospice_count} hospices · ${formatLevel(building.review_level)} · Review score ${score}`;
  content.append(address, details);
  if (building.coordinate_source) {
    const source = document.createElement("small");
    const verified = building.verified_location;
    const approximate = building.approximate_location;
    const precision = approximate?.precision === "parcel_interior"
      ? "Parcel location"
      : "Census street interpolation";
    source.textContent = approximate
      ? `Approximate location · ${precision} · ${approximate.county} County · Building position unconfirmed`
      : verified
      ? `${building.coordinate_source} · ${verified.confidence === "verified" ? "Reviewed address point" : `${verified.confidence} match · Address point`}`
      : building.coordinate_source;
    content.append(source);
  }
  const link = document.createElement("a");
  link.href = "#building-evidence";
  link.textContent = "View building evidence";
  content.append(link);
  return content;
}

export default function HotspotMap({
  buildings, total, status, warning, selectedId, focusOnSelection, onSelect,
}: {
  buildings: BuildingListItem[];
  total: number;
  status: "loading" | "ready" | "error";
  warning: string;
  selectedId: string | null;
  focusOnSelection: { buildingId: string } | null;
  onSelect: (buildingId: string, focus?: boolean) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const markerLayer = useRef<L.LayerGroup | null>(null);
  const markers = useRef(new Map<string, { marker: L.Marker; building: BuildingListItem }>());
  const highlighted = useRef<string | null>(null);
  const select = useRef(onSelect);
  const [tiles, setTiles] = useState<"loading" | "ready" | "error">("loading");
  const points = useMemo(() => warning ? [] : buildings.flatMap((building) => {
    const position = buildingPosition(building);
    return position ? [{ building, position }] : [];
  }), [buildings, warning]);
  const verifiedCount = points.filter(({ building }) => building.verified_location).length;
  const approximateCount = points.filter(({ building }) => building.approximate_location).length;

  useEffect(() => { select.current = onSelect; }, [onSelect]);

  useEffect(() => {
    if (!container.current) return;
    const instance = L.map(container.current, { maxZoom: 19, scrollWheelZoom: true });
    map.current = instance;
    resetView(instance);
    const layer = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      className: "hotspot-tiles",
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
    });
    let tileFailed = false;
    layer.on("loading", () => { tileFailed = false; });
    layer.on("tileerror", () => {
      tileFailed = true;
      setTiles("error");
    });
    layer.on("load", () => setTiles(tileFailed ? "error" : "ready"));
    layer.addTo(instance);
    instance.attributionControl?.setPrefix(false);
    markerLayer.current = L.layerGroup().addTo(instance);

    const resize = new ResizeObserver(() => instance.invalidateSize({ animate: false, debounceMoveend: true }));
    resize.observe(container.current);
    return () => {
      resize.disconnect();
      layer.off();
      instance.remove();
      map.current = null;
      markerLayer.current = null;
    };
  }, []);

  useEffect(() => {
    const group = markerLayer.current;
    const instance = map.current;
    if (!group || !instance) return;
    const entries = markers.current;
    entries.clear();
    for (const { building, position } of points) {
      const marker = L.marker(position, {
        icon: markerIcon(building),
        title: building.building_key,
        autoPanOnFocus: false,
      });
      marker.on("click", () => select.current(building.building_id));
      marker.on("keypress", (event: L.LeafletKeyboardEvent) => {
        if (event.originalEvent.key === "Enter") select.current(building.building_id);
      });
      marker.bindPopup(() => {
        const content = popupContent(building);
        const origin = instance.latLngToLayerPoint(marker.getLatLng());
        const nearby = [...entries.values()].filter((entry) =>
          entry.marker !== marker &&
          instance.latLngToLayerPoint(entry.marker.getLatLng()).distanceTo(origin) <= 24,
        );
        if (nearby.length) {
          const choices = document.createElement("details");
          choices.className = "hotspot-nearby";
          const heading = document.createElement("summary");
          heading.textContent = "Other buildings at or near this point";
          const list = document.createElement("ul");
          L.DomEvent.disableScrollPropagation(list);
          for (const entry of nearby) {
            const item = document.createElement("li");
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = entry.building.building_key;
            button.addEventListener("click", () => {
              select.current(entry.building.building_id);
              entry.marker.openPopup();
              entry.marker.getPopup()?.getElement()?.querySelector<HTMLElement>("a")?.focus();
            });
            item.append(button);
            list.append(item);
          }
          choices.append(heading, list);
          content.append(choices);
        }
        return content;
      }, { maxWidth: 280 });
      entries.set(building.building_id, { marker, building });
    }
    for (const { marker } of entries.values()) group.addLayer(marker);
    return () => { group.clearLayers(); entries.clear(); };
  }, [points]);

  useEffect(() => {
    const previous = highlighted.current ? markers.current.get(highlighted.current) : undefined;
    previous?.marker.setIcon(markerIcon(previous.building));
    previous?.marker.setZIndexOffset(0);
    highlighted.current = selectedId;
    const current = selectedId ? markers.current.get(selectedId) : undefined;
    if (current) {
      current.marker.setIcon(markerIcon(current.building, true));
      current.marker.setZIndexOffset(1000);
      const position = current.marker.getLatLng();
      const animate = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (focusOnSelection && map.current && map.current.getZoom() < 15) {
        map.current.setView(position, 15, { animate: false });
      } else {
        map.current?.panTo(position, { animate });
      }
    }
  }, [focusOnSelection, points, selectedId]);

  return (
    <section className="map-panel" aria-label="Los Angeles County map">
      <div className="hotspot-frame">
        <div ref={container} className="hotspot-map" aria-label="Interactive LA County street map" role="region" />
        <button className="hotspot-reset" type="button" onClick={() => map.current && resetView(map.current)}>
          Reset view
        </button>
        {tiles !== "ready" && <p role="status" className="hotspot-status">
          {tiles === "loading" ? "Loading street tiles…" : "Some street tiles are unavailable. Building locations remain available."}
        </p>}
      </div>
      <MapLegend buildings={buildings} selectedId={selectedId} onSelect={(id) => onSelect(id, true)} />
      {warning && <p className="map-warning" role="alert">{warning}</p>}
      <details className="map-data" open={selectedId === null}>
      <summary>Map coverage and location data</summary>
      <div className="location-overview">
        <section aria-labelledby="coverage-title">
          <h2 id="coverage-title">Coverage</h2>
          <dl className="coverage-metrics">
            <div><dt>Total buildings</dt><dd>{status === "ready" ? total.toLocaleString() : "—"}</dd></div>
            <div><dt>Mapped buildings</dt><dd>{status === "ready" && !warning ? points.length.toLocaleString() : "—"}</dd></div>
            <div><dt>Geocoding coverage</dt><dd>{status === "ready" && !warning && total > 0 ? `${(100 * points.length / total).toFixed(1)}%` : "—"}</dd></div>
          </dl>
        </section>
        <section aria-labelledby="location-title">
          <h2 id="location-title">Location Data</h2>
          <dl className="location-breakdown">
            <div>
              <dt>Verified locations</dt>
              <dd className="location-count">{status === "ready" && !warning ? verifiedCount.toLocaleString() : "—"}</dd>
              <dd>Address points from <a href="https://cams-lacounty.hub.arcgis.com/">LA County CAMS</a> and municipal GIS.</dd>
            </div>
            <div>
              <dt>Approximate locations</dt>
              <dd className="location-count">{status === "ready" && !warning ? approximateCount.toLocaleString() : "—"}</dd>
              <dd>Supplemental geocoding from <a href="https://www.census.gov/data/developers/data-sets/Geocoding-services.html">Census street estimates</a> and parcel records.</dd>
            </div>
            <div>
              <dt>Unmapped buildings</dt>
              <dd className="location-count">{status === "ready" && !warning ? (total - points.length).toLocaleString() : "—"}</dd>
              <dd>Available for investigation in the <a href="#buildings">building queue</a>.</dd>
            </div>
          </dl>
        </section>
      </div>
      </details>
    </section>
  );
}
