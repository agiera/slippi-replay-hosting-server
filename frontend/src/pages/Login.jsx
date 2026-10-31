import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { getGoogleLoginUrl, login, signup } from "../lib/api/auth";
import { persistSession } from "../lib/api/session";

function Field({ id, label, ...inputProps }) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm/6 font-medium text-white">
        {label}
      </label>
      <Input id={id} className="mt-2" {...inputProps} />
    </div>
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
    <main className="px-4 py-16 sm:px-6 sm:py-24 lg:px-8">
      <Card className="mx-auto max-w-md sm:p-10">
        <h1 className="text-2xl/9 font-bold tracking-tight text-white">{isSignup ? "Create Account" : "Welcome Back"}</h1>
        <p className="mt-1 text-sm/6 text-gray-400">FastAPI + React starter with local + Google auth</p>

        <form className="mt-8 space-y-5" onSubmit={onSubmit}>
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
            <p className="text-sm text-red-400" role="alert">
              {error}
            </p>
          ) : null}

          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Please wait..." : isSignup ? "Sign Up" : "Log In"}
          </Button>
        </form>

        <Button
          variant="secondary"
          className="mt-4 w-full"
          onClick={() => (window.location.href = getGoogleLoginUrl())}
        >
          Continue with Google
        </Button>

        <p className="mt-8 text-center text-sm/6 text-gray-400">
          {isSignup ? "Already have an account?" : "Need an account?"}{" "}
          <button
            type="button"
            className="cursor-pointer font-semibold text-indigo-400 hover:text-indigo-300"
            onClick={() => setIsSignup(!isSignup)}
          >
            {isSignup ? "Log In" : "Sign Up"}
          </button>
        </p>
      </Card>
    </main>
  );
}
