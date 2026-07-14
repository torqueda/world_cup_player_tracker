import { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import type { LatLngBoundsExpression } from "leaflet";
import "leaflet/dist/leaflet.css";
import type { City } from "@/lib/data";

const WORLD_CENTER: [number, number] = [24, 10];
const WORLD_ZOOM = 2;
// Latitude clamped to the Web-Mercator limits; longitude spans many world
// copies so horizontal looping (worldCopyJump) stays effectively unbounded
// while vertical panning is walled in. Used on mobile only.
const VERTICAL_MAX_BOUNDS: LatLngBoundsExpression = [
  [-85, -100000],
  [85, 100000],
];
// Below this zoom the map shows one bubble per country; at or above it the
// individual city dots appear.
const CITY_ZOOM_THRESHOLD = 4;
// Kept in sync with the map legend on the Club Map route.
export const MAP_ACTIVE_COLOR = "#8a3f1e";
export const MAP_CITY_COLOR = "#b0542b";
export const MAP_COUNTRY_COLOR = "#145b3d";
const ACTIVE_COLOR = MAP_ACTIVE_COLOR;
const DEFAULT_COLOR = MAP_CITY_COLOR;
const COUNTRY_COLOR = MAP_COUNTRY_COLOR;

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

// Toggle the map's interaction model imperatively rather than by remounting the
// MapContainer. Remounting on the mobile/desktop switch both reset the user's
// view and could crash Leaflet's drag handler mid-cleanup; driving the handlers
// on the live map instance avoids all of that.
//   Mobile: pan (drag) + pinch-zoom on, mouse-wheel zoom off, and a
//   latitude-only maxBounds so up/down panning can't drift into empty space
//   (longitude stays unbounded, so worldCopyJump still loops left/right).
//   Desktop: panning off (page scroll isn't hijacked; navigation stays on the
//   zoom buttons / country bubbles), mouse-wheel zoom on, no bounds.
// Shape of the Leaflet internals we defensively touch (not in the public types).
type DraggableHandler = (this: unknown, ...args: unknown[]) => unknown;

// The drag lifecycle methods that read the (possibly detached) drag target via
// Leaflet's className helpers. Wrapping these makes teardown crash-proof.
const GUARDED_DRAG_METHODS = ["finishDrag", "_onMove", "_onUp"];

function MapInteractionMode({ isMobile }: { isMobile: boolean }) {
  const map = useMap();
  useEffect(() => {
    if (isMobile) {
      map.dragging.enable();
      map.touchZoom.enable();
      map.scrollWheelZoom.disable();
      map.options.maxBoundsViscosity = 1;
      map.setMaxBounds(VERTICAL_MAX_BOUNDS);
    } else {
      map.dragging.disable();
      map.touchZoom.disable();
      map.scrollWheelZoom.enable();
      map.options.maxBoundsViscosity = 0;
      map.setMaxBounds(null as unknown as LatLngBoundsExpression);
    }

    // Enabling dragging means Leaflet holds an internal Draggable with document
    // -level mouse/touch handlers. When the map unmounts after the user has
    // panned (e.g. they drag the map, then tap a nav link), Leaflet's teardown
    // and any late pointer event run those handlers against a now-detached drag
    // target, and its className helpers throw "Cannot read properties of
    // undefined (reading 'baseVal')" — enough to trip React Router's error
    // boundary and blank the app. Wrap the drag lifecycle methods so a
    // mid-teardown failure is swallowed instead of crashing. This only guards
    // cleanup; a live, on-screen drag has a stable target and never throws.
    const draggable = (map.dragging as unknown as { _draggable?: Record<string, unknown> })._draggable;
    if (draggable && !draggable.__safeFinish) {
      for (const name of GUARDED_DRAG_METHODS) {
        const original = draggable[name];
        if (typeof original === "function") {
          const originalFn = original as DraggableHandler;
          draggable[name] = function guardedDragHandler(this: unknown, ...args: unknown[]) {
            try {
              return originalFn.apply(this, args);
            } catch {
              return undefined; // torn down mid-gesture; nothing to clean up
            }
          };
        }
      }
      draggable.__safeFinish = true;
    }
  }, [isMobile, map]);

  return null;
}

// Touch devices (phones) can't lean on the mouse-wheel zoom or the hover
// tooltips the desktop layout relies on, so there we make the map pannable and
// let it wrap continuously — see `MapInteractionMode` above.
function useIsMobile(query = "(max-width: 767px)"): boolean {
  const [isMobile, setIsMobile] = useState(
    () => typeof window !== "undefined" && window.matchMedia(query).matches,
  );
  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = () => setIsMobile(mql.matches);
    onChange();
    mql.addEventListener("change", onChange);
    // `resize` is a belt-and-suspenders fallback: some environments don't fire
    // the media-query `change` event on a viewport change, but always fire
    // `resize`, so this keeps the mobile/desktop switch reliable.
    window.addEventListener("resize", onChange);
    return () => {
      mql.removeEventListener("change", onChange);
      window.removeEventListener("resize", onChange);
    };
  }, [query]);
  return isMobile;
}

export function PlayersClubsMap({ cities, selectedCityKey, onSelectCity, focus }: PlayersClubsMapProps) {
  const [zoom, setZoom] = useState(WORLD_ZOOM);
  const [pendingBounds, setPendingBounds] = useState<LatLngBoundsExpression | null>(null);
  const isMobile = useIsMobile();

  const countryBubbles = useMemo(() => buildCountryBubbles(cities), [cities]);
  const showCities = zoom >= CITY_ZOOM_THRESHOLD;

  return (
    <MapContainer
      center={WORLD_CENTER}
      zoom={WORLD_ZOOM}
      minZoom={WORLD_ZOOM}
      // Interaction defaults here are the desktop model; MapInteractionMode
      // below switches the live map to the mobile model when needed, without a
      // remount. worldCopyJump is an init-only option, so it stays here — it
      // makes markers reappear on the copy of the world nearest the view, so
      // panning all the way left/right keeps showing them.
      dragging={false}
      scrollWheelZoom
      worldCopyJump
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <MapInteractionMode isMobile={isMobile} />
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
