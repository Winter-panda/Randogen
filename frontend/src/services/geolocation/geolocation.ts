import type { UserPosition } from "../../types/route";

export function getCurrentPosition(): Promise<UserPosition> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("La géolocalisation n'est pas prise en charge par ce navigateur."));
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude
        });
      },
      (error) => {
        reject(new Error(getGeolocationErrorMessage(error)));
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0
      }
    );
  });
}

export function startPositionWatch(
  onPosition: (position: UserPosition) => void,
  onError?: (message: string) => void
): () => void {
  if (!navigator.geolocation) {
    onError?.("La géolocalisation n'est pas prise en charge par ce navigateur.");
    return () => undefined;
  }

  const watchId = navigator.geolocation.watchPosition(
    (position) => {
      onPosition({
        latitude: position.coords.latitude,
        longitude: position.coords.longitude
      });
    },
    (error) => {
      onError?.(getGeolocationErrorMessage(error));
    },
    {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 1000
    }
  );

  return () => {
    navigator.geolocation.clearWatch(watchId);
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
