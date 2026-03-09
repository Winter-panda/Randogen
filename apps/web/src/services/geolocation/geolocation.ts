import type { UserPosition } from "../../types/route";

type NativeGeolocation = typeof import("@capacitor/geolocation").Geolocation;

function hasBrowserGeolocation(): boolean {
  return typeof navigator !== "undefined" && typeof navigator.geolocation !== "undefined";
}

async function getNativeGeolocation(): Promise<NativeGeolocation | null> {
  const maybeCapacitor = (globalThis as { Capacitor?: { isNativePlatform?: () => boolean } }).Capacitor;
  if (!maybeCapacitor?.isNativePlatform?.()) {
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

function getBrowserPositionInternal(): Promise<UserPosition> {
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
        enableHighAccuracy: true,
        timeout: 10_000,
        maximumAge: 0,
      }
    );
  });
}

export async function getCurrentPosition(): Promise<UserPosition> {
  const nativeGeolocation = await getNativeGeolocation();
  if (nativeGeolocation) {
    try {
      await ensureNativeLocationPermission(nativeGeolocation);
      const position = await nativeGeolocation.getCurrentPosition({
        enableHighAccuracy: true,
        timeout: 10_000,
        maximumAge: 0,
      });
      return {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
      };
    } catch (error) {
      throw new Error(normalizeNativeError(error));
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
        const watchId = await nativeGeolocation.watchPosition(
          {
            enableHighAccuracy: true,
            timeout: 10_000,
            maximumAge: 1_000,
          },
          (position, err) => {
            if (err) {
              onError?.(normalizeNativeError(err));
              return;
            }
            if (!position?.coords) {
              return;
            }
            onPosition({
              latitude: position.coords.latitude,
              longitude: position.coords.longitude,
            });
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
        onPosition({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        });
      },
      (error) => {
        onError?.(getGeolocationErrorMessage(error));
      },
      {
        enableHighAccuracy: true,
        timeout: 10_000,
        maximumAge: 1_000,
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
