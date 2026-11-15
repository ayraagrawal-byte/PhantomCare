"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet.markercluster";
import { buildingPosition, formatLevel, type BuildingListItem } from "../lib/analysis";

const countyBounds: L.LatLngBoundsExpression = [[33.65, -118.95], [34.83, -117.63]];

function resetView(map: L.Map) {
  map.fitBounds(countyBounds, { padding: [16, 16], animate: false });
}

function markerIcon(building: BuildingListItem, selected = false) {
  const size = Math.min(30, 14 + building.hospice_count);
  const style = building.approximate_location ? " hotspot-approximate" : "";
  return L.divIcon({
    className: `hotspot-marker hotspot-${building.review_level}${style}${selected ? " is-selected" : ""}`,
    iconSize: [size, size],
    popupAnchor: [0, -size / 2],
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
  buildings, total, status, warning, selectedId, onSelect,
}: {
  buildings: BuildingListItem[];
  total: number;
  status: "loading" | "ready" | "error";
  warning: string;
  selectedId: string | null;
  onSelect: (buildingId: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const clusters = useRef<L.MarkerClusterGroup | null>(null);
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
    const group = L.markerClusterGroup({
      maxClusterRadius: 38,
      showCoverageOnHover: false,
      iconCreateFunction: (cluster) => L.divIcon({
        className: "hotspot-cluster",
        html: String(cluster.getChildCount()),
        iconSize: [34, 34],
      }),
    }).addTo(instance);
    clusters.current = group;

    const resize = new ResizeObserver(() => instance.invalidateSize({ pan: false }));
    resize.observe(container.current);
    return () => {
      resize.disconnect();
      layer.off();
      instance.remove();
      map.current = null;
      clusters.current = null;
    };
  }, []);

  useEffect(() => {
    const group = clusters.current;
    if (!group) return;
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
      marker.bindPopup(() => popupContent(building), { maxWidth: 260 });
      entries.set(building.building_id, { marker, building });
    }
    group.addLayers(Array.from(entries.values(), ({ marker }) => marker));
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
      if (!map.current?.hasLayer(current.marker)) {
        clusters.current?.zoomToShowLayer(current.marker, () => {});
      }
    }
  }, [points, selectedId]);

  return (
    <section className="map-panel" aria-labelledby="map-title">
      <div className="map-copy">
        <h2 id="map-title">LA County hotspots</h2>
        <p>Select a building to review its evidence. Buildings without coordinates are still available in the review queue.</p>
        <div className="map-legend">
          <span><i className="legend-hot" />High priority</span>
          <span><i className="legend-watch" />Worth a look</span>
          <span><i className="legend-neutral" />No indicators found</span>
          <span><i className="legend-verified" />Verified address point</span>
          <span><i className="legend-approximate" />Approximate street or parcel position</span>
        </div>
        <p className="hotspot-count" aria-live="polite">
          {status === "ready" && !warning ? <><strong>{points.length}</strong> mapped of {total} analyzed buildings</>
            : status === "loading" ? "Loading building locations…" : "Building locations unavailable"}
        </p>
        {warning && <p role="alert">{warning}</p>}
        {status === "ready" && !warning && (verifiedCount > 0 || approximateCount > 0) && (
          <p className="hotspot-breakdown">
            {verifiedCount} verified · {approximateCount} approximate · {total - points.length} unmapped
          </p>
        )}
        {status === "ready" && !warning && points.length === 0 && <p>No building coordinates in this analysis.</p>}
        {points.some(({ building }) => building.verified_location) && (
          <p className="hotspot-provenance">
            Address points from <a href="https://cams-lacounty.hub.arcgis.com/">LA County CAMS</a>.
          </p>
        )}
        {approximateCount > 0 && (
          <p className="hotspot-provenance">
            Street estimates from the <a href="https://www.census.gov/data/developers/data-sets/Geocoding-services.html">U.S. Census Bureau</a>.
          </p>
        )}
      </div>
      <div className="hotspot-frame">
        <div ref={container} className="hotspot-map" aria-label="Interactive LA County street map" role="region" />
        <button className="hotspot-reset" type="button" onClick={() => map.current && resetView(map.current)}>
          Reset view
        </button>
        {tiles !== "ready" && <p role="status" className="hotspot-status">
          {tiles === "loading" ? "Loading street tiles…" : "Some street tiles are unavailable. Building locations remain available."}
        </p>}
      </div>
    </section>
  );
}
