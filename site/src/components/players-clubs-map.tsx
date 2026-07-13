import { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import type { LatLngBoundsExpression } from "leaflet";
import "leaflet/dist/leaflet.css";
import type { City } from "@/lib/data";

const WORLD_CENTER: [number, number] = [24, 10];
const WORLD_ZOOM = 2;
// Below this zoom the map shows one bubble per country; at or above it the
// individual city dots appear.
const CITY_ZOOM_THRESHOLD = 4;
const ACTIVE_COLOR = "#b3541e";
const DEFAULT_COLOR = "#c96f33";
const COUNTRY_COLOR = "#1f6f43";

export interface MapFocus {
  /** Monotonic id so the same bounds can be re-applied. */
  id: number;
  bounds: LatLngBoundsExpression | null; // null = world view
}

interface CountryBubble {
  country: string;
  lat: number;
  lon: number;
  clubCount: number;
  cityCount: number;
  bounds: LatLngBoundsExpression;
}

interface PlayersClubsMapProps {
  cities: City[];
  selectedCityKey: string | null;
  onSelectCity: (cityKey: string) => void;
  focus: MapFocus;
}

export function boundsForCities(cities: City[]): LatLngBoundsExpression | null {
  if (cities.length === 0) {
    return null;
  }
  return [
    [Math.min(...cities.map((c) => c.city_lat)), Math.min(...cities.map((c) => c.city_lon))],
    [Math.max(...cities.map((c) => c.city_lat)), Math.max(...cities.map((c) => c.city_lon))],
  ];
}

function buildCountryBubbles(cities: City[]): CountryBubble[] {
  const grouped = new Map<string, City[]>();
  for (const city of cities) {
    const bucket = grouped.get(city.country);
    if (bucket) {
      bucket.push(city);
    } else {
      grouped.set(city.country, [city]);
    }
  }
  return Array.from(grouped.entries()).map(([country, group]) => {
    const clubCount = group.reduce((sum, city) => sum + city.club_count, 0);
    // Weight the bubble position by club count so a country's bubble sits
    // near its football center of gravity rather than its geographic middle.
    const lat = group.reduce((sum, city) => sum + city.city_lat * city.club_count, 0) / clubCount;
    const lon = group.reduce((sum, city) => sum + city.city_lon * city.club_count, 0) / clubCount;
    return {
      country,
      lat,
      lon,
      clubCount,
      cityCount: group.length,
      bounds: boundsForCities(group) as LatLngBoundsExpression,
    };
  });
}

function ZoomTracker({ onZoom }: { onZoom: (zoom: number) => void }) {
  useMapEvents({
    zoomend: (event) => onZoom(event.target.getZoom()),
  });
  return null;
}

function ResetViewControl({ onReset }: { onReset: () => void }) {
  const map = useMap();
  return (
    <div className="map-reset-control leaflet-top leaflet-right">
      <button
        type="button"
        className="map-reset-button leaflet-control"
        onClick={() => {
          map.setView(WORLD_CENTER, WORLD_ZOOM);
          onReset();
        }}
      >
        World view
      </button>
    </div>
  );
}

function FocusController({ focus }: { focus: MapFocus }) {
  const map = useMap();
  useEffect(() => {
    if (focus.id === 0) {
      return; // initial mount, leave the world view alone
    }
    if (focus.bounds) {
      map.fitBounds(focus.bounds, { padding: [32, 32], maxZoom: 6 });
    } else {
      map.setView(WORLD_CENTER, WORLD_ZOOM);
    }
  }, [focus, map]);
  return null;
}

function CountryZoom({ bounds }: { bounds: LatLngBoundsExpression | null }) {
  const map = useMap();
  useEffect(() => {
    if (bounds) {
      map.fitBounds(bounds, { padding: [32, 32], maxZoom: 6 });
    }
  }, [bounds, map]);
  return null;
}

export function PlayersClubsMap({ cities, selectedCityKey, onSelectCity, focus }: PlayersClubsMapProps) {
  const [zoom, setZoom] = useState(WORLD_ZOOM);
  const [pendingBounds, setPendingBounds] = useState<LatLngBoundsExpression | null>(null);

  const countryBubbles = useMemo(() => buildCountryBubbles(cities), [cities]);
  const showCities = zoom >= CITY_ZOOM_THRESHOLD;

  return (
    <MapContainer
      center={WORLD_CENTER}
      zoom={WORLD_ZOOM}
      minZoom={WORLD_ZOOM}
      dragging={false}
      scrollWheelZoom
      worldCopyJump
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ZoomTracker onZoom={(next) => { setZoom(next); setPendingBounds(null); }} />
      <FocusController focus={focus} />
      <CountryZoom bounds={pendingBounds} />
      <ResetViewControl onReset={() => setPendingBounds(null)} />

      {!showCities &&
        countryBubbles.map((bubble) => (
          <CircleMarker
            key={bubble.country}
            center={[bubble.lat, bubble.lon]}
            radius={Math.min(8 + Math.sqrt(bubble.clubCount) * 2.4, 26)}
            pathOptions={{
              color: COUNTRY_COLOR,
              fillColor: COUNTRY_COLOR,
              fillOpacity: 0.55,
              weight: 1,
            }}
            eventHandlers={{
              click: () => setPendingBounds(bubble.bounds),
            }}
          >
            <Tooltip direction="top" offset={[0, -4]} opacity={1}>
              {bubble.country} &middot; {bubble.clubCount} club{bubble.clubCount === 1 ? "" : "s"} in{" "}
              {bubble.cityCount} cit{bubble.cityCount === 1 ? "y" : "ies"} — click to zoom in
            </Tooltip>
          </CircleMarker>
        ))}

      {showCities &&
        cities.map((city) => {
          const isSelected = city.city_key === selectedCityKey;
          const radius = Math.min(6 + city.club_count * 1.5, 16);
          return (
            <CircleMarker
              key={city.city_key}
              center={[city.city_lat, city.city_lon]}
              radius={radius}
              pathOptions={{
                color: isSelected ? ACTIVE_COLOR : DEFAULT_COLOR,
                fillColor: isSelected ? ACTIVE_COLOR : DEFAULT_COLOR,
                fillOpacity: isSelected ? 0.9 : 0.55,
                weight: isSelected ? 2 : 1,
              }}
              eventHandlers={{
                click: () => onSelectCity(city.city_key),
              }}
            >
              <Tooltip direction="top" offset={[0, -4]} opacity={1}>
                {city.city}, {city.country} &middot; {city.club_count} club{city.club_count === 1 ? "" : "s"}
              </Tooltip>
            </CircleMarker>
          );
        })}
    </MapContainer>
  );
}
