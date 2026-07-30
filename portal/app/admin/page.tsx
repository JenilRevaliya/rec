"use client";
import React, { useState, useEffect } from "react";
import { Users, Database, Camera, Plus, Power, BarChart, Settings, Aperture, LogOut } from "lucide-react";
import LoginForm from "../../components/LoginForm";

export default function AdminPortal() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [username, setUsername] = useState("");
  const [isClient, setIsClient] = useState(false);
  
  const [dbStats, setDbStats] = useState({
    users: 0,
    photographers: 0,
    events: 0,
    images: 0,
    storage: "42.8 GB",
  });
  
  const [users, setUsers] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [autoCaptureActive, setAutoCaptureActive] = useState(false);

  useEffect(() => {
    setIsClient(true);
    const storedUser = localStorage.getItem("rec_username_admin");
    const storedToken = localStorage.getItem("rec_token_admin");
    if (storedUser && storedToken) {
      setUsername(storedUser);
      setLoggedIn(true);
      fetchData();
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("rec_token_admin");
    localStorage.removeItem("rec_role_admin");
    localStorage.removeItem("rec_username_admin");
    setLoggedIn(false);
    setUsername("");
  };

  const handleLoginSuccess = (user: string) => {
    setUsername(user);
    setLoggedIn(true);
    fetchData();
  };

  const fetchData = async () => {
    const statsRes = await fetch("http://localhost:8001/admin/stats");
    const statsData = await statsRes.json();
    setDbStats(prev => ({ ...prev, users: statsData.users, images: statsData.photos, storage: statsData.storage || "0 KB" }));
    
    const usersRes = await fetch("http://localhost:8001/admin/users");
    const usersData = await usersRes.json();
    setUsers(usersData);
    
    const eventsRes = await fetch("http://localhost:8001/admin/events");
    const eventsData = await eventsRes.json();
    setEvents(eventsData);
  };
  
  const handleAddPhotographer = async () => {
    const pUsername = prompt("Enter new photographer username:");
    if (!pUsername) return;
    const pPassword = prompt("Enter new photographer password:");
    if (!pPassword) return;
    
    await fetch("http://localhost:8001/admin/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: pUsername, password: pPassword, role: "photographer" })
    });
    fetchData();
  };

  if (!isClient) return null; // Prevent hydration mismatch

  if (!loggedIn) {
    return <LoginForm expectedRole="admin" onLoginSuccess={handleLoginSuccess} title="Admin Login" />;
  }

  return (
    <div className="min-h-screen bg-neo-yellow bg-grain p-8 font-mono">
      <div className="max-w-6xl mx-auto space-y-8">
        
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center bg-white border-4 border-black p-6 shadow-neo">
          <div>
            <h1 className="text-4xl font-bold uppercase tracking-tight">Admin Terminal</h1>
            <p className="text-gray-600 font-bold mt-2">REC Global Control Center</p>
          </div>
          <div className="mt-4 md:mt-0 flex gap-4">
            <button className="bg-neo-blue text-white font-bold px-6 py-3 border-4 border-black hover:-translate-y-1 hover:-translate-x-1 hover:shadow-neo transition-all flex items-center">
              <Camera className="mr-2" /> Enter Photographer Mode
            </button>
            <button onClick={handleLogout} className="bg-white font-bold px-6 py-3 border-4 border-black hover:-translate-y-1 hover:-translate-x-1 hover:shadow-neo transition-all flex items-center">
              <LogOut className="mr-2" /> Exit
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          
          {/* Stats Dashboard */}
          <div className="col-span-1 md:col-span-3 grid grid-cols-2 md:grid-cols-3 gap-6">
            <div className="bg-white border-4 border-black p-6 shadow-neo group hover:bg-neo-green transition-colors">
              <Database className="w-8 h-8 mb-4 group-hover:animate-bounce" />
              <p className="text-sm font-bold uppercase">Total Storage</p>
              <p className="text-4xl font-bold">{dbStats.storage}</p>
            </div>
            
            <div className="bg-white border-4 border-black p-6 shadow-neo group hover:bg-neo-orange transition-colors">
              <Aperture className="w-8 h-8 mb-4 group-hover:animate-bounce" />
              <p className="text-sm font-bold uppercase">Images Processed</p>
              <p className="text-4xl font-bold">{dbStats.images.toLocaleString()}</p>
            </div>
            
            <div className="bg-white border-4 border-black p-6 shadow-neo group hover:bg-neo-blue hover:text-white transition-colors">
              <Users className="w-8 h-8 mb-4 group-hover:animate-bounce" />
              <p className="text-sm font-bold uppercase">Registered Users</p>
              <p className="text-4xl font-bold">{dbStats.users}</p>
            </div>
          </div>

          {/* Core Controls */}
          <div className="col-span-1 space-y-6">
            <div className={`border-4 border-black p-6 shadow-neo transition-colors ${autoCaptureActive ? 'bg-neo-green' : 'bg-white'}`}>
              <h2 className="text-xl font-bold uppercase mb-4">Edge Node Link</h2>
              <button 
                onClick={() => setAutoCaptureActive(!autoCaptureActive)}
                className={`w-full font-bold py-4 border-4 border-black flex items-center justify-center transition-all ${autoCaptureActive ? 'bg-black text-white' : 'bg-neo-yellow hover:-translate-y-1 hover:-translate-x-1 hover:shadow-neo'}`}
              >
                <Power className="mr-2" />
                {autoCaptureActive ? 'HALT DAEMON' : 'START AUTO-CAPTURE'}
              </button>
              <p className="text-xs font-bold mt-4 text-center">
                {autoCaptureActive ? 'DSLR/PTZ Cameras are actively tracking.' : 'Edge nodes are sleeping.'}
              </p>
            </div>
          </div>
        </div>

        {/* Management Area */}
        <div className="bg-white border-4 border-black p-8 shadow-neo">
          <div className="flex justify-between items-center mb-8 border-b-4 border-black pb-4">
            <h2 className="text-3xl font-bold uppercase">User & Photographer Management</h2>
            <button onClick={handleAddPhotographer} className="bg-neo-green font-bold px-4 py-2 border-4 border-black hover:-translate-y-1 hover:-translate-x-1 hover:shadow-neo transition-all flex items-center">
              <Plus className="mr-2" /> Provision New
            </button>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-black text-white">
                  <th className="p-4 border-4 border-black font-bold uppercase">ID</th>
                  <th className="p-4 border-4 border-black font-bold uppercase">Username</th>
                  <th className="p-4 border-4 border-black font-bold uppercase">Role</th>
                  <th className="p-4 border-4 border-black font-bold uppercase">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.id} className="hover:bg-neo-yellow transition-colors cursor-pointer">
                    <td className="p-4 border-4 border-black font-bold">USR-{u.id}</td>
                    <td className="p-4 border-4 border-black font-bold">{u.username}</td>
                    <td className="p-4 border-4 border-black"><span className="bg-neo-green px-2 py-1 border-2 border-black font-bold text-xs uppercase">{u.role}</span></td>
                    <td className="p-4 border-4 border-black">
                      <button className="bg-white px-3 py-1 border-2 border-black font-bold text-xs uppercase hover:bg-black hover:text-white transition-colors">Manage</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Events Area */}
        <div className="bg-white border-4 border-black p-8 shadow-neo">
          <div className="flex justify-between items-center mb-8 border-b-4 border-black pb-4">
            <h2 className="text-3xl font-bold uppercase">Live Events & Links</h2>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-black text-white">
                  <th className="p-4 border-4 border-black font-bold uppercase">Event ID</th>
                  <th className="p-4 border-4 border-black font-bold uppercase">Name</th>
                  <th className="p-4 border-4 border-black font-bold uppercase">Photographer</th>
                  <th className="p-4 border-4 border-black font-bold uppercase">Live Link</th>
                </tr>
              </thead>
              <tbody>
                {events.length === 0 && (
                  <tr><td colSpan={4} className="p-4 border-4 border-black text-center font-bold">No active events yet</td></tr>
                )}
                {events.map((evt: any) => (
                  <tr key={evt.id} className="hover:bg-neo-yellow transition-colors cursor-pointer">
                    <td className="p-4 border-4 border-black font-bold">{evt.id}</td>
                    <td className="p-4 border-4 border-black font-bold">{evt.name}</td>
                    <td className="p-4 border-4 border-black font-bold">{evt.photographer_id}</td>
                    <td className="p-4 border-4 border-black font-bold text-neo-blue">
                      <a href={`http://localhost:3000/user?event=${evt.id}`} target="_blank" rel="noreferrer">
                        http://localhost:3000/user?event={evt.id}
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        
      </div>
    </div>
  );
}
