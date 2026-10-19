import { createContext, useContext, useEffect, useState } from "react";
import { getCurrentUser, logout } from "../lib/api.js";
import { removeToken } from "../utils/auth.js";

const AuthContext = createContext({ user: null, loading: false });

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  async function refresh() {
    try {
      const current = await getCurrentUser();
      setUser(current);
      return current;
    } catch (error) {
      setUser(null);
      if (error?.response?.status !== 401) throw error;
      return null;
    }
  }
  useEffect(() => {
    removeToken();
    const expired = () => setUser(null);
    window.addEventListener("paper:session-expired", expired);
    refresh().catch(() => {}).finally(() => setLoading(false));
    return () => window.removeEventListener("paper:session-expired", expired);
  }, []);
  async function signOut() {
    await logout();
    setUser(null);
  }
  return <AuthContext.Provider value={{ user, loading, refresh, signOut }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
