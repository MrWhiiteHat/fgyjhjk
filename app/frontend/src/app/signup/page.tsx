"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { API_BASE_URL } from "@/lib/constants";
import { useToast } from "@/components/ToastProvider";

export default function SignupPage(): React.JSX.Element {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { pushToast } = useToast();

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/auth/signup`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          password,
          full_name: name
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Signup failed");
      }

      pushToast("Account created successfully! Please log in.", "success");
      router.push("/login");
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
          Create Account
        </h1>
        <p className="muted">Join RealFake Console</p>
      </div>

      <form onSubmit={handleSignup} className="formGrid">
        <div>
          <label htmlFor="name">Full Name</label>
          <input
            id="name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder="John Doe"
            style={{ marginTop: "0.5rem" }}
          />
        </div>
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
            minLength={6}
          />
        </div>

        <button type="submit" className="primaryButton" disabled={loading} style={{ width: "100%", marginTop: "1rem" }}>
          {loading ? "Creating account..." : "Sign Up"}
        </button>
      </form>

      <div style={{ textAlign: "center", marginTop: "1.5rem" }}>
        <p className="muted">
          Already have an account? <Link href="/login" style={{ color: "var(--primary)", fontWeight: "600" }}>Log in</Link>
        </p>
      </div>
    </div>
  );
}
