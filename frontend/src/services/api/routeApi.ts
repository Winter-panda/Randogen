import type {
  GenerateRoutesRequest,
  GenerateRoutesResponse
} from "../../types/route";

const API_BASE_URL = "http://127.0.0.1:8000/api";

export async function generateRoutes(
  payload: GenerateRoutesRequest
): Promise<GenerateRoutesResponse> {
  const response = await fetch(`${API_BASE_URL}/routes/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`Erreur API (${response.status})`);
  }

  return (await response.json()) as GenerateRoutesResponse;
}
