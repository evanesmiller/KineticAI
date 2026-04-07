import { createContext, useContext, useState, useEffect } from "react";

const API = "";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true);

  // Check if already logged in on mount
  useEffect(() => {
    fetch(`${API}/auth/me`, { credentials: "include" })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setUser(data); })
      .finally(() => setLoading(false));
  }, []);

  async function login(username, password) {
    const r = await fetch(`${API}/auth/login`, {
      method:      "POST",
      credentials: "include",
      headers:     { "Content-Type": "application/json" },
      body:        JSON.stringify({ username, password }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || "Login failed.");
    setUser(data);
    return data;
  }

  async function register(username, password) {
    const r = await fetch(`${API}/auth/register`, {
      method:      "POST",
      credentials: "include",
      headers:     { "Content-Type": "application/json" },
      body:        JSON.stringify({ username, password }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || "Registration failed.");
    setUser(data);
    return data;
  }

  async function logout() {
    await fetch(`${API}/auth/logout`, { method: "POST", credentials: "include" });
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

export { API };
