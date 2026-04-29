"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { API_BASE_URL } from "@/lib/constants";
import { useToast } from "@/components/ToastProvider";

export default function LoginPage(): React.JSX.Element {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { pushToast } = useToast();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const formData = new URLSearchParams();
      formData.append("username", email);
      formData.append("password", password);

      const res = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Login failed");
      }

      const data = await res.json();
      localStorage.setItem("access_token", data.access_token);
      pushToast("Logged in successfully!", "success");
      
      // Dispatch event so other components know auth state changed
      window.dispatchEvent(new Event("auth-change"));
      
      router.push("/");
    } catch (err: any) {
      pushToast(err.message || "An error occurred", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: "400px", margin: "4rem auto", padding: "2rem" }} className="card">
      <div style={{ textAlign: "center", marginBottom: "2rem" }}>
        <h1 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "2rem", margin: "0" }}>
          Welcome Back
        </h1>
        <p className="muted">Sign in to RealFake Console</p>
      </div>

      <form onSubmit={handleLogin} className="formGrid">
        <div>
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            placeholder="admin@realfake.com"
            style={{ marginTop: "0.5rem" }}
          />
        </div>
        <div>
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            placeholder="••••••••"
            style={{ marginTop: "0.5rem" }}
          />
        </div>

        <button type="submit" className="primaryButton" disabled={loading} style={{ width: "100%", marginTop: "1rem" }}>
          {loading ? "Signing in..." : "Sign In"}
        </button>
      </form>

      <div style={{ textAlign: "center", marginTop: "1.5rem" }}>
        <p className="muted">
          Don&apos;t have an account? <Link href="/signup" style={{ color: "var(--primary)", fontWeight: "600" }}>Sign up</Link>
        </p>
      </div>
    </div>
  );
}
