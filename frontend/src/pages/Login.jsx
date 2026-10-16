import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { getGoogleLoginUrl, login, signup } from "../lib/api/auth";
import { persistSession } from "../lib/api/session";

function Field({ id, label, ...inputProps }) {
  return (
    <>
      <label htmlFor={id}>{label}</label>
      <Input id={id} {...inputProps} />
    </>
  );
}

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
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-[calc(100vh-46px)] place-items-center p-6">
      <Card className="max-w-[520px]">
        <h1 className="mb-4 text-[2rem] leading-tight font-bold">{isSignup ? "Create Account" : "Welcome Back"}</h1>
        <p className="mb-4 text-muted">FastAPI + React starter with local + Google auth</p>

        <form className="grid gap-2" onSubmit={onSubmit}>
          <Field
            id="login-username"
            label="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />

          {isSignup ? (
            <Field
              id="login-email"
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          ) : null}

          <Field
            id="login-password"
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={isSignup ? "new-password" : "current-password"}
            required
          />

          {error ? (
            <p className="my-2 text-danger" role="alert">
              {error}
            </p>
          ) : null}

          <Button type="submit" size="lg" className="w-full" disabled={loading}>
            {loading ? "Please wait..." : isSignup ? "Sign Up" : "Log In"}
          </Button>
        </form>

        <Button
          variant="ghost"
          size="lg"
          className="mt-3 w-full"
          onClick={() => (window.location.href = getGoogleLoginUrl())}
        >
          Continue with Google
        </Button>

        <p className="mt-3">
          {isSignup ? "Already have an account?" : "Need an account?"}{" "}
          <button
            type="button"
            className="cursor-pointer bg-transparent p-0 font-semibold text-accent-strong hover:underline"
            onClick={() => setIsSignup(!isSignup)}
          >
            {isSignup ? "Log In" : "Sign Up"}
          </button>
        </p>
      </Card>
    </main>
  );
}
