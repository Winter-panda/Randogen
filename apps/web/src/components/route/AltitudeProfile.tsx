import type { RoutePoint } from "../../types/route";

interface AltitudeProfileProps {
  points: RoutePoint[];
}

const VIEW_W = 600;
const VIEW_H = 120;
const PAD = { top: 12, right: 12, bottom: 24, left: 48 };

function haversineKm(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const R = 6371;
  const toRad = (v: number) => (v * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export default function AltitudeProfile({ points }: AltitudeProfileProps) {
  const elevated = points.filter((p) => (p.elevation_m ?? 0) !== 0);

  if (elevated.length < 2) return null;

  const distances: number[] = [0];
  for (let i = 1; i < elevated.length; i++) {
    const prev = elevated[i - 1];
    const curr = elevated[i];
    distances.push(
      distances[i - 1] +
        haversineKm(prev.latitude, prev.longitude, curr.latitude, curr.longitude)
    );
  }

  const totalKm = distances[distances.length - 1];
  const elevations = elevated.map((p) => p.elevation_m ?? 0);
  const minEle = Math.min(...elevations);
  const maxEle = Math.max(...elevations);
  const eleRange = maxEle - minEle || 1;

  const innerW = VIEW_W - PAD.left - PAD.right;
  const innerH = VIEW_H - PAD.top - PAD.bottom;
  const toX = (km: number) => PAD.left + (km / totalKm) * innerW;
  const toY = (ele: number) =>
    PAD.top + innerH - ((ele - minEle) / eleRange) * innerH;

  const coordPairs = elevated
    .map(
      (p, i) =>
        `${toX(distances[i]).toFixed(1)},${toY(p.elevation_m ?? 0).toFixed(1)}`
    )
    .join(" L");

  const baseY = (PAD.top + innerH).toFixed(1);
  const fillPath = `M${toX(0).toFixed(1)},${baseY} L${coordPairs} L${toX(totalKm).toFixed(1)},${baseY} Z`;
  const linePath = `M${coordPairs}`;

  return (
    <div className="altitude-profile">
      <p className="altitude-profile-title">Profil altimétrique</p>
      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        className="altitude-profile-svg"
        aria-label="Profil altimétrique du parcours"
      >
        <path d={fillPath} className="altitude-fill" />
        <path d={linePath} className="altitude-line" />
        <text
          x={PAD.left - 6}
          y={PAD.top + 4}
          className="altitude-label"
          textAnchor="end"
        >
          {Math.round(maxEle)} m
        </text>
        <text
          x={PAD.left - 6}
          y={PAD.top + innerH}
          className="altitude-label"
          textAnchor="end"
        >
          {Math.round(minEle)} m
        </text>
        <text
          x={PAD.left}
          y={VIEW_H - 6}
          className="altitude-label"
          textAnchor="start"
        >
          0 km
        </text>
        <text
          x={VIEW_W - PAD.right}
          y={VIEW_H - 6}
          className="altitude-label"
          textAnchor="end"
        >
          {totalKm.toFixed(1)} km
        </text>
      </svg>
    </div>
  );
}
