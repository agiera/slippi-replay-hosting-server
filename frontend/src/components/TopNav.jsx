import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { SLIPPILAB_URL } from "../config/env";
import { logout } from "../lib/api/auth";
import { getAccessToken } from "../lib/api/session";

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
          <a className="top-nav-link" href={SLIPPILAB_URL} target="_blank" rel="noreferrer">
            SlippiLab
          </a>
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
