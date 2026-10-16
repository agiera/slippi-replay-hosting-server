import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { clearSession, persistSession } from "../lib/api/session";

export default function OauthSuccess() {
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const query = new URLSearchParams(location.search);
    const accessToken = query.get("token");
    const refreshToken = query.get("refresh_token");
    if (accessToken && refreshToken) {
      persistSession({ access_token: accessToken, refresh_token: refreshToken, user: null });
      navigate("/", { replace: true });
      return;
    }
    clearSession();
    navigate("/login", { replace: true });
  }, [location.search, navigate]);

  return <p className="p-6 text-sm text-gray-400">Signing you in...</p>;
}
