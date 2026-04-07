import { useState, useEffect, useCallback } from "react";
import { API } from "../context/AuthContext";

/**
 * useFetch — thin wrapper around fetch for authenticated API calls.
 *
 * Usage:
 *   const { data, loading, error, refetch } = useFetch("/workouts/");
 */
export function useFetch(path, options = {}) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${API}${path}`, {
        credentials: "include",
        ...options,
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.error || `Request failed (${r.status})`);
      }
      setData(await r.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}

/** One-shot POST/DELETE helper — returns { data, error } */
export async function apiCall(path, method = "GET", body = null) {
  const opts = {
    method,
    credentials: "include",
    headers: body ? { "Content-Type": "application/json" } : {},
  };
  if (body) opts.body = JSON.stringify(body);
  const r    = await fetch(`${API}${path}`, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `Request failed (${r.status})`);
  return data;
}
