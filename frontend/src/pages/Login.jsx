import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { getGoogleLoginUrl, login, persistSession, signup } from "../lib/api";

export default function Login() {
  const [isSignup, setIsSignup] = useState(false);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = isSignup
        ? await signup({ username, email, password })
        : await login({ username, password });
      persistSession(data);
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-layout">
      <section className="auth-card">
        <h1>{isSignup ? "Create Account" : "Welcome Back"}</h1>
        <p className="subtitle">FastAPI + React starter with local + Google auth</p>

        <form onSubmit={onSubmit}>
          <label>Username</label>
          <input value={username} onChange={(e) => setUsername(e.target.value)} required />

          {isSignup && (
            <>
              <label>Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </>
          )}

          <label>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />

          {error && <p className="error">{error}</p>}

          <button disabled={loading} type="submit">
            {loading ? "Please wait..." : isSignup ? "Sign Up" : "Log In"}
          </button>
        </form>

        <button className="ghost" onClick={() => (window.location.href = getGoogleLoginUrl())}>
          Continue with Google
        </button>

        <p className="toggle">
          {isSignup ? "Already have an account?" : "Need an account?"} {" "}
          <button className="link" onClick={() => setIsSignup(!isSignup)}>
            {isSignup ? "Log In" : "Sign Up"}
          </button>
        </p>
      </section>
    </main>
  );
}
