import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getAccessToken, logout } from "../lib/api";

export default function TopNav() {
  const [isAuthenticated, setIsAuthenticated] = useState(Boolean(getAccessToken()));

  useEffect(() => {
    const syncAuthState = () => setIsAuthenticated(Boolean(getAccessToken()));

    window.addEventListener("storage", syncAuthState);
    window.addEventListener("auth:changed", syncAuthState);

    return () => {
      window.removeEventListener("storage", syncAuthState);
      window.removeEventListener("auth:changed", syncAuthState);
    };
  }, []);

  return (
    <header className="top-nav">
      <nav className="top-nav-inner">
        <div className="top-nav-left">
          <Link className="top-nav-link" to="/">
            Replays
          </Link>
          {isAuthenticated && (
            <Link className="top-nav-link" to="/dashboard">
              Dashboard
            </Link>
          )}
        </div>
        <div className="top-nav-right">
          {isAuthenticated ? (
            <>
              <Link className="top-nav-link" to="/settings">
                Settings
              </Link>
              <button
                className="top-nav-link top-nav-button"
                onClick={async () => {
                  await logout();
                  window.location.href = "/login";
                }}
                type="button"
              >
                Logout
              </button>
            </>
          ) : (
            <Link className="top-nav-link login-link" to="/login">
              Login
            </Link>
          )}
        </div>
      </nav>
    </header>
  );
}
