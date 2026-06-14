import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { clearSession, persistSession } from "../lib/api";

export default function OauthSuccess() {
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const query = new URLSearchParams(location.search);
    const accessToken = query.get("token");
    const refreshToken = query.get("refresh_token");
    if (accessToken && refreshToken) {
      persistSession({ access_token: accessToken, refresh_token: refreshToken, user: null });
      navigate("/dashboard", { replace: true });
      return;
    }
    clearSession();
    navigate("/login", { replace: true });
  }, [location.search, navigate]);

  return <p style={{ padding: 24 }}>Signing you in...</p>;
}
