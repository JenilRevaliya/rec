"use client";
import React, { useState } from "react";

interface LoginFormProps {
  expectedRole: "admin" | "photographer" | "user";
  onLoginSuccess: (username: string) => void;
  title: string;
}

export default function LoginForm({ expectedRole, onLoginSuccess, title }: LoginFormProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    
    try {
      const res = await fetch(`${window.location.protocol}//${window.location.hostname}:8001/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();
      
      if (data.token) {
        if (data.role === expectedRole || (expectedRole === "photographer" && data.role === "admin")) {
          // Admin can access photographer portal too
          localStorage.setItem(`rec_token_${expectedRole}`, data.token);
          localStorage.setItem(`rec_role_${expectedRole}`, data.role);
          localStorage.setItem(`rec_username_${expectedRole}`, data.username);
          onLoginSuccess(data.username);
        } else {
          setError(`Access Denied: Requires ${expectedRole} privileges.`);
        }
      } else {
        setError(data.error || "Invalid credentials");
      }
    } catch (err) {
      setError("Failed to connect to backend");
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-neo-green bg-grain p-8 font-mono flex items-center justify-center">
      <form onSubmit={handleLogin} className="bg-white border-4 border-black p-8 shadow-neo max-w-sm w-full space-y-4">
        <h1 className="text-3xl font-bold uppercase text-center mb-6">{title}</h1>
        
        {error && (
          <div className="bg-red-500 text-white font-bold p-3 border-4 border-black text-center text-sm uppercase">
            {error}
          </div>
        )}
        
        <input 
          className="w-full border-4 border-black p-3 font-bold" 
          type="text" 
          placeholder="Username" 
          value={username} 
          onChange={e => setUsername(e.target.value)} 
          required 
        />
        <input 
          className="w-full border-4 border-black p-3 font-bold" 
          type="password" 
          placeholder="Password" 
          value={password} 
          onChange={e => setPassword(e.target.value)} 
          required 
        />
        <button 
          type="submit"
          disabled={loading}
          className={`w-full font-bold py-4 uppercase border-4 border-black transition-all ${loading ? 'bg-gray-400 text-black' : 'bg-black text-white hover:bg-neo-blue hover:-translate-y-1 hover:-translate-x-1 hover:shadow-neo'}`}
        >
          {loading ? 'Authenticating...' : 'Enter System'}
        </button>
      </form>
    </div>
  );
}
