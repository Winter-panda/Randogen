import type { UserPosition } from "../../types/route";

type NativeGeolocation = typeof import("@capacitor/geolocation").Geolocation;
type NativeCoords = { latitude: number; longitude: number };

const CACHED_POSITION_TTL_MS = 45_000;
const PERSISTED_POSITION_TTL_MS = 24 * 60 * 60 * 1000;
const LAST_POSITION_STORAGE_KEY = "randogen_last_position_v1";
let cachedPosition: { position: UserPosition; capturedAt: number } | null = null;

function hasBrowserGeolocation(): boolean {
  return typeof navigator !== "undefined" && typeof navigator.geolocation !== "undefined";
}

function isLikelyAndroidRuntime(): boolean {
  return typeof navigator !== "undefined" && /Android/i.test(navigator.userAgent);
}

function updateCachedPosition(coords: NativeCoords): UserPosition {
  const next = {
    latitude: coords.latitude,
    longitude: coords.longitude,
  };
  const capturedAt = Date.now();
  cachedPosition = {
    position: next,
    capturedAt,
  };
  try {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(
        LAST_POSITION_STORAGE_KEY,
        JSON.stringify({
          latitude: next.latitude,
          longitude: next.longitude,
          capturedAt,
        })
      );
    }
  } catch {
    // Ignore storage errors (private mode, quota, etc.)
  }
  return next;
}

function getFreshCachedPosition(maxAgeMs: number = CACHED_POSITION_TTL_MS): UserPosition | null {
  if (cachedPosition && Date.now() - cachedPosition.capturedAt <= maxAgeMs) {
    return cachedPosition.position;
  }

  try {
    if (typeof window === "undefined") {
      return null;
    }
    const raw = window.localStorage.getItem(LAST_POSITION_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as {
      latitude?: number;
      longitude?: number;
      capturedAt?: number;
    };
    if (
      typeof parsed.latitude !== "number"
      || typeof parsed.longitude !== "number"
      || typeof parsed.capturedAt !== "number"
    ) {
      return null;
    }
    if (Date.now() - parsed.capturedAt > maxAgeMs) {
      return null;
    }
    const restored = {
      latitude: parsed.latitude,
      longitude: parsed.longitude,
    };
    cachedPosition = {
      position: restored,
      capturedAt: parsed.capturedAt,
    };
    return restored;
  } catch {
    return null;
  }
}

async function getNativeGeolocation(): Promise<NativeGeolocation | null> {
  let isNativePlatform = false;
  try {
    const core = await import("@capacitor/core");
    isNativePlatform = core.Capacitor.isNativePlatform();
  } catch {
    const maybeCapacitor = (globalThis as { Capacitor?: { isNativePlatform?: () => boolean } }).Capacitor;
    isNativePlatform = Boolean(maybeCapacitor?.isNativePlatform?.());
  }
  if (!isNativePlatform) {
    return null;
  }

  try {
    const plugin = await import("@capacitor/geolocation");
    return plugin.Geolocation;
  } catch {
    return null;
  }
}

async function ensureNativeLocationPermission(geolocation: NativeGeolocation): Promise<void> {
  const current = await geolocation.checkPermissions();
  const hasCurrentPermission = current.location === "granted" || current.coarseLocation === "granted";
  if (hasCurrentPermission) {
    return;
  }

  await geolocation.requestPermissions();
  const requested = await geolocation.checkPermissions();
  const granted = requested.location === "granted" || requested.coarseLocation === "granted";
  if (!granted) {
    throw new Error("permission_denied");
  }
}

function normalizeNativeError(error: unknown): string {
  const raw = error instanceof Error ? error.message : String(error ?? "");
  const message = raw.toLowerCase();

  if (message.includes("permission") || message.includes("denied")) {
    return "Accès à la géolocalisation refusé.";
  }
  if (message.includes("timeout")) {
    return "Délai dépassé pour récupérer la position.";
  }
  if (message.includes("unavailable") || message.includes("location")) {
    return "Position indisponible. Vérifie la position de l'émulateur Android.";
  }
  return "Erreur inconnue de géolocalisation.";
}

async function firstSuccessfulPosition(candidates: Array<Promise<UserPosition>>): Promise<UserPosition> {
  return await new Promise<UserPosition>((resolve, reject) => {
    let rejected = 0;
    let lastError: unknown = null;
    for (const candidate of candidates) {
      candidate
        .then((position) => {
          resolve(position);
        })
        .catch((error) => {
          rejected += 1;
          lastError = error;
          if (rejected >= candidates.length) {
            reject(lastError);
          }
        });
    }
  });
}

function getBrowserPosition(options: PositionOptions): Promise<UserPosition> {
  return new Promise((resolve, reject) => {
    if (!hasBrowserGeolocation()) {
      reject(new Error("La géolocalisation n'est pas prise en charge par ce navigateur."));
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        });
      },
      (error) => {
        reject(new Error(getGeolocationErrorMessage(error)));
      },
      {
        enableHighAccuracy: options.enableHighAccuracy ?? false,
        timeout: options.timeout ?? 8_000,
        maximumAge: options.maximumAge ?? 0,
      }
    );
  });
}

async function getBrowserPositionInternal(): Promise<UserPosition> {
  const cached = getFreshCachedPosition();
  if (cached) {
    return cached;
  }

  const quickOptions: PositionOptions = {
    enableHighAccuracy: false,
    timeout: 2_500,
    maximumAge: 60_000,
  };
  const preciseOptions: PositionOptions = {
    enableHighAccuracy: true,
    timeout: 10_000,
    maximumAge: 2_000,
  };

  const position = await firstSuccessfulPosition([
    getBrowserPosition(quickOptions),
    getBrowserPosition(preciseOptions),
  ]);
  return updateCachedPosition(position);
}

async function getNativePositionInternal(geolocation: NativeGeolocation): Promise<UserPosition> {
  const cached = getFreshCachedPosition();
  if (cached) {
    return cached;
  }

  const isAndroid = isLikelyAndroidRuntime();
  const quickTimeoutMs = isAndroid ? 2_000 : 2_500;
  const preciseTimeoutMs = isAndroid ? 7_000 : 9_000;

  const position = await firstSuccessfulPosition([
    geolocation.getCurrentPosition({
      enableHighAccuracy: false,
      timeout: quickTimeoutMs,
      maximumAge: 10 * 60_000,
    }).then((quick) => ({
      latitude: quick.coords.latitude,
      longitude: quick.coords.longitude,
    })),
    geolocation.getCurrentPosition({
      enableHighAccuracy: true,
      timeout: preciseTimeoutMs,
      maximumAge: 2_000,
    }).then((precise) => ({
      latitude: precise.coords.latitude,
      longitude: precise.coords.longitude,
    })),
  ]);
  return updateCachedPosition(position);
}

export async function getCurrentPosition(): Promise<UserPosition> {
  const nativeGeolocation = await getNativeGeolocation();
  if (nativeGeolocation) {
    try {
      await ensureNativeLocationPermission(nativeGeolocation);
      return await getNativePositionInternal(nativeGeolocation);
    } catch (error) {
      const cachedFallback = getFreshCachedPosition(PERSISTED_POSITION_TTL_MS);
      if (cachedFallback) {
        return cachedFallback;
      }
      try {
        return await getBrowserPositionInternal();
      } catch {
        throw new Error(normalizeNativeError(error));
      }
    }
  }

  return await getBrowserPositionInternal();
}

export function startPositionWatch(
  onPosition: (position: UserPosition) => void,
  onError?: (message: string) => void
): () => void {
  let stopImpl: () => void = () => undefined;
  let cancelled = false;

  void (async () => {
    const nativeGeolocation = await getNativeGeolocation();
    if (cancelled) return;

    if (nativeGeolocation) {
      try {
        await ensureNativeLocationPermission(nativeGeolocation);
        const isAndroid = isLikelyAndroidRuntime();
        const watchId = await nativeGeolocation.watchPosition(
          {
            enableHighAccuracy: !isAndroid,
            timeout: isAndroid ? 15_000 : 10_000,
            maximumAge: 5_000,
            minimumUpdateInterval: 2_000,
          },
          (position, err) => {
            if (err) {
              onError?.(normalizeNativeError(err));
              return;
            }
            if (!position?.coords) {
              return;
            }
            const nextPosition = updateCachedPosition({
              latitude: position.coords.latitude,
              longitude: position.coords.longitude,
            });
            onPosition(nextPosition);
          }
        );

        stopImpl = () => {
          void nativeGeolocation.clearWatch({ id: watchId });
        };
        return;
      } catch (error) {
        onError?.(normalizeNativeError(error));
      }
    }

    if (!hasBrowserGeolocation()) {
      onError?.("La géolocalisation n'est pas prise en charge par ce navigateur.");
      return;
    }

    const watchId = navigator.geolocation.watchPosition(
      (position) => {
        const nextPosition = updateCachedPosition({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        });
        onPosition(nextPosition);
      },
      (error) => {
        onError?.(getGeolocationErrorMessage(error));
      },
      {
        enableHighAccuracy: !isLikelyAndroidRuntime(),
        timeout: 10_000,
        maximumAge: 3_000,
      }
    );

    stopImpl = () => {
      navigator.geolocation.clearWatch(watchId);
    };
  })();

  return () => {
    cancelled = true;
    stopImpl();
  };
}

function getGeolocationErrorMessage(error: GeolocationPositionError): string {
  switch (error.code) {
    case error.PERMISSION_DENIED:
      return "Accès à la géolocalisation refusé.";
    case error.POSITION_UNAVAILABLE:
      return "Position indisponible.";
    case error.TIMEOUT:
      return "Délai dépassé pour récupérer la position.";
    default:
      return "Erreur inconnue de géolocalisation.";
  }
}
