import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

import { SLIPPILAB_URL } from "../config/env";
import { logout } from "../lib/api/auth";
import { getAccessToken } from "../lib/api/session";
import { cn } from "../lib/cn";

const LINK_CLASS = "cursor-pointer text-[0.92rem] font-semibold text-muted no-underline hover:text-accent-strong";

// Route links are highlighted while their page is open.
function navLinkClass({ isActive }) {
  return cn(LINK_CLASS, isActive && "text-fg");
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
    <header className="sticky top-0 z-10 border-b border-accent/35 bg-black/72 backdrop-blur-[6px]">
      <nav className="mx-auto flex min-h-(--top-nav-height) max-w-[1080px] items-center justify-between px-4">
        <div className="flex items-center gap-3">
          <NavLink className={navLinkClass} to="/" end>
            Replays
          </NavLink>
          <a className={LINK_CLASS} href={SLIPPILAB_URL} target="_blank" rel="noreferrer">
            SlippiLab
          </a>
        </div>
        <div className="flex items-center gap-3">
          {isAuthenticated ? (
            <>
              <NavLink className={navLinkClass} to="/settings">
                Settings
              </NavLink>
              <button
                className={cn(LINK_CLASS, "bg-transparent p-0")}
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
