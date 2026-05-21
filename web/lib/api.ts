const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status} ${path}`);
  return res.json();
}

export const api = {
  clubs: {
    list: (params?: { campus?: string; category?: string }) =>
      apiFetch<import("./types").Club[]>(
        "/clubs" + (params ? "?" + new URLSearchParams(params as Record<string, string>) : "")
      ),
    get: (id: string) => apiFetch<import("./types").Club>(`/clubs/${id}`),
  },
  events: {
    search: (body: object) =>
      apiFetch<import("./types").Event[]>("/events/search", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    get: (id: string) => apiFetch<import("./types").Event>(`/events/${id}`),
  },
  users: {
    getPreferences: (discordId: string) =>
      apiFetch<import("./types").UserPreferences>(`/users/${discordId}`),
    savePreferences: (prefs: import("./types").UserPreferences) =>
      apiFetch<void>("/users/preferences", {
        method: "POST",
        body: JSON.stringify(prefs),
      }),
    getDigest: (discordId: string) =>
      apiFetch<import("./types").Event[]>(`/users/${discordId}/digest`),
  },
  recommend: (profile: object) =>
    apiFetch<import("./types").Recommendation[]>("/recommend", {
      method: "POST",
      body: JSON.stringify(profile),
    }),
};
