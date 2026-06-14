import { useEffect, useState } from "react";
import { Navigate, Outlet } from "react-router-dom";

import { fetchMe, getAccessToken } from "../lib/api";

export default function ProtectedRoute() {
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    async function checkAuth() {
      if (!getAccessToken()) {
        setAuthenticated(false);
        setLoading(false);
        return;
      }

      try {
        await fetchMe();
        setAuthenticated(true);
      } catch {
        setAuthenticated(false);
      } finally {
        setLoading(false);
      }
    }

    checkAuth();
  }, []);

  if (loading) {
    return <p style={{ padding: 24 }}>Loading session...</p>;
  }

  if (!authenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}