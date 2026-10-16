import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

import { SLIPPILAB_URL } from "../config/env";
import { logout } from "../lib/api/auth";
import { getAccessToken } from "../lib/api/session";
import { cn } from "../lib/cn";

const LINK_CLASS = "cursor-pointer rounded-md px-3 py-2 text-sm font-medium text-gray-300 hover:bg-white/5 hover:text-white";

// Route links are highlighted while their page is open.
function navLinkClass({ isActive }) {
  return cn(LINK_CLASS, isActive && "bg-white/10 text-white");
}

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
    <header className="sticky top-0 z-30 border-b border-white/10 bg-gray-950/80 backdrop-blur">
      <nav className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-1">
          <NavLink className={navLinkClass} to="/" end>
            Replays
          </NavLink>
          <a className={LINK_CLASS} href={SLIPPILAB_URL} target="_blank" rel="noreferrer">
            SlippiLab
          </a>
        </div>
        <div className="flex items-center gap-1">
          {isAuthenticated ? (
            <>
              <NavLink className={navLinkClass} to="/settings">
                Settings
              </NavLink>
              <button
                className={LINK_CLASS}
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
            <NavLink className={navLinkClass} to="/login">
              Login
            </NavLink>
          )}
        </div>
      </nav>
    </header>
  );
}
