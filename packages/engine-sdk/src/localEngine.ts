import type { RouteEngine } from "./types";

export class LocalEngine implements RouteEngine {
  private unsupported(op: string): never {
    throw new Error(`LocalEngine not implemented yet: ${op}`);
  }

  async generateRoutes() {
    this.unsupported("generateRoutes");
  }

  async fetchNearbyPois() {
    this.unsupported("fetchNearbyPois");
  }

  async fetchWeather() {
    this.unsupported("fetchWeather");
  }

  async exportRouteGpx() {
    this.unsupported("exportRouteGpx");
  }
}
