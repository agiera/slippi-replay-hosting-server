import { useNavigate } from "react-router-dom";

import { getStoredUser, logout } from "../lib/api";

export default function Dashboard() {
  const navigate = useNavigate();
  const user = getStoredUser();

  return (
    <main className="dash-layout">
      <section className="dash-card">
        <h1>Dashboard</h1>
        <p>You are authenticated.</p>
        <pre>{JSON.stringify(user, null, 2)}</pre>
        <button
          onClick={async () => {
            await logout();
            navigate("/login", { replace: true });
          }}
        >
          Log Out
        </button>
      </section>
    </main>
  );
}
