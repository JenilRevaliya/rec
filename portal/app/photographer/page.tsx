"use client";
import React, { useState, useEffect } from "react";
import { UploadCloud, QrCode, Image as ImageIcon, CalendarPlus, FolderOpen, Send, LogOut } from "lucide-react";
import LoginForm from "../../components/LoginForm";

export default function PhotographerPortal() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [username, setUsername] = useState("");
  const [isClient, setIsClient] = useState(false);
  
  const [activeEvent, setActiveEvent] = useState<string | null>("EVT-892");
  const [queue, setQueue] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [processedPhotos, setProcessedPhotos] = useState<any[]>([]);
  const [pastPhotos, setPastPhotos] = useState<any[]>([]);
  const [linkCopied, setLinkCopied] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [sortMode, setSortMode] = useState<"newest" | "oldest">("newest");
  const [generatedTokens, setGeneratedTokens] = useState<string[]>([]);
  const [generatingLinks, setGeneratingLinks] = useState(false);
  const [shareBaseUrl, setShareBaseUrl] = useState<string>("");

  React.useEffect(() => {
    if (!activeEvent) return;
    
    const fetchPhotos = () => {
      fetch(`${window.location.protocol}//${window.location.hostname}:8001/photos/${activeEvent}`)
        .then(res => res.json())
        .then(data => {
          if (Array.isArray(data)) setPastPhotos(data);
        })
        .catch(console.error);
    };

    fetchPhotos();
    const interval = setInterval(fetchPhotos, 5000); // Poll for edge uploads
    return () => clearInterval(interval);
  }, [activeEvent]);

  useEffect(() => {
    setIsClient(true);
    if (typeof window !== 'undefined') {
      const currentOrigin = window.location.origin;
      setShareBaseUrl(currentOrigin);
      // Initial auto-detect attempt
      detectNetworkIp();
    }
    const storedUser = localStorage.getItem("rec_username_photographer");
    const storedToken = localStorage.getItem("rec_token_photographer");
    if (storedUser && storedToken) {
      setUsername(storedUser);
      setLoggedIn(true);
    }
  }, []);

  const detectNetworkIp = () => {
    if (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')) {
      fetch(`${window.location.protocol}//${window.location.hostname}:8001/network-ip`)
        .then(res => res.json())
        .then(data => {
          if (data.ip && data.ip !== '127.0.0.1') {
            setShareBaseUrl(`${window.location.protocol}//${data.ip}:${window.location.port}`);
          }
        })
        .catch(console.error);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("rec_token_photographer");
    localStorage.removeItem("rec_role_photographer");
    localStorage.removeItem("rec_username_photographer");
    setLoggedIn(false);
    setUsername("");
  };

  const handleLoginSuccess = (user: string) => {
    setUsername(user);
    setLoggedIn(true);
  };

  const handleNewEvent = () => {
    const eventName = prompt("Enter a unique Event ID (e.g., EVT-999):");
    if (eventName && eventName.trim().length > 0) {
      setActiveEvent(eventName.trim().toUpperCase());
      setPastPhotos([]);
    }
  };

  const shareUrl = shareBaseUrl ? `${shareBaseUrl}/user?event=${activeEvent}` : "";

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setLinkCopied(true);
    setTimeout(() => setLinkCopied(false), 2000);
  };

  const handleGeneratePrivateLinks = async () => {
    setGeneratingLinks(true);
    try {
      const res = await fetch(`${window.location.protocol}//${window.location.hostname}:8001/links/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_id: activeEvent, count: 5, max_opens: 2 })
      });
      const data = await res.json();
      if (data.tokens) {
        setGeneratedTokens(data.tokens);
        alert(`Successfully generated ${data.tokens.length} private links!`);
      }
    } catch (err) {
      console.error(err);
      alert("Failed to generate private links");
    } finally {
      setGeneratingLinks(false);
    }
  };

  const handleSelectFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    console.log("File selection triggered!", e.target.files);
    if (e.target.files && e.target.files.length > 0) {
      const filesArray = Array.from(e.target.files);
      console.log("Adding to queue:", filesArray);
      setQueue(prev => [...prev, ...filesArray]);
    } else {
      console.warn("No files detected in selection.");
    }
    
    // Clear safely using explicit DOM reference to prevent React synthetic event nullification
    const input = document.getElementById("file-upload") as HTMLInputElement;
    if (input) input.value = '';
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.items) {
      const newFiles: File[] = [];
      
      const traverseFileTree = (item: any, path?: string) => {
        return new Promise<void>((resolve) => {
          path = path || "";
          if (item.isFile) {
            item.file((file: File) => {
              if (file.type.startsWith('image/') || file.name.match(/\.(jpg|jpeg|png|webp|cr2|nef|arw)$/i)) {
                newFiles.push(file);
              }
              resolve();
            });
          } else if (item.isDirectory) {
            const dirReader = item.createReader();
            dirReader.readEntries((entries: any[]) => {
              const promises = entries.map(entry => traverseFileTree(entry, path + item.name + "/"));
              Promise.all(promises).then(() => resolve());
            });
          } else {
             resolve();
          }
        });
      };
      
      const promises = Array.from(e.dataTransfer.items).map(item => {
        const entry = item.webkitGetAsEntry();
        if (entry) {
          return traverseFileTree(entry);
        }
        return Promise.resolve();
      });
      
      Promise.all(promises).then(() => {
        setQueue(prev => [...prev, ...newFiles]);
      });
    } else if (e.dataTransfer.files) {
      const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
      setQueue(prev => [...prev, ...files]);
    }
  };

  const handleProcessQueue = async () => {
    if (queue.length === 0) return;
    setUploading(true);
    
    // Upload all concurrently
    await Promise.all(queue.map(async (file) => {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("event", activeEvent || "EVT-UNKNOWN");
      formData.append("photographer", username);
      
      try {
        const res = await fetch(`${window.location.protocol}//${window.location.hostname}:8001/upload`, {
          method: "POST",
          body: formData,
        });
        const data = await res.json();
        if (data.error || typeof data.faces_detected !== 'number') {
          console.warn(`Could not process ${file.name}: ${data.error}`);
        } else {
          setProcessedPhotos(prev => [...prev, { ...data, localUrl: URL.createObjectURL(file) }]);
        }
      } catch (err) {
        console.error("Upload failed", err);
      }
    }));
    
    setQueue([]);
    setUploading(false);
    alert("Batch processed successfully by AI pipeline!");
    
    // Refresh past photos
    fetch(`${window.location.protocol}//${window.location.hostname}:8001/photos/${activeEvent}`)
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) setPastPhotos(data);
      });
  };

  const sortedPastPhotos = [...pastPhotos].sort((a, b) => {
    return sortMode === "newest" ? b.id.localeCompare(a.id) : a.id.localeCompare(b.id);
  });
  
  if (!isClient) return null; // Prevent hydration mismatch

  if (!loggedIn) {
    return <LoginForm expectedRole="photographer" onLoginSuccess={handleLoginSuccess} title="Studio Login" />;
  }
  
  return (
    <div className="min-h-screen bg-neo-green bg-grain p-8 font-mono">
      <div className="max-w-6xl mx-auto space-y-8">
        
        <div className="bg-white border-4 border-black p-6 shadow-neo flex justify-between items-center">
          <div>
            <h1 className="text-4xl font-bold uppercase tracking-tight">Photographer Studio</h1>
            <p className="text-gray-600 font-bold mt-2">Welcome back, {username}</p>
          </div>
          <div className="flex gap-4">
            <button onClick={handleNewEvent} className="bg-neo-yellow font-bold px-6 py-3 border-4 border-black hover:-translate-y-1 hover:-translate-x-1 hover:shadow-neo transition-all flex items-center">
              <CalendarPlus className="mr-2" /> New Event
            </button>
            <button onClick={handleLogout} className="bg-white font-bold px-6 py-3 border-4 border-black hover:-translate-y-1 hover:-translate-x-1 hover:shadow-neo transition-all flex items-center">
              <LogOut className="mr-2" /> Exit
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Sidebar / Event List */}
          <div className="col-span-1 space-y-6">
            <div className="bg-white border-4 border-black p-6 shadow-neo">
              <h2 className="text-2xl font-bold uppercase border-b-4 border-black pb-4 mb-4">Your Events</h2>
              <div className="space-y-4">
                <div 
                  className={`border-4 border-black p-4 cursor-pointer transition-all ${activeEvent === "EVT-892" ? 'bg-black text-white' : 'bg-neo-blue hover:-translate-y-1 hover:-translate-x-1 hover:shadow-neo'}`}
                  onClick={() => setActiveEvent("EVT-892")}
                >
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-bold">Music Festival 2026</span>
                    <span className="text-xs font-bold px-2 py-1 bg-white text-black border-2 border-black">LIVE</span>
                  </div>
                  <p className="text-sm opacity-80 flex items-center"><ImageIcon className="w-4 h-4 mr-2" /> 1,204 Photos</p>
                </div>
                
                <div 
                  className={`border-4 border-black p-4 cursor-pointer transition-all ${activeEvent === "EVT-441" ? 'bg-black text-white' : 'bg-white hover:-translate-y-1 hover:-translate-x-1 hover:shadow-neo'}`}
                  onClick={() => setActiveEvent("EVT-441")}
                >
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-bold">Tech Conference</span>
                    <span className="text-xs font-bold px-2 py-1 bg-gray-200 text-black border-2 border-black">ENDED</span>
                  </div>
                  <p className="text-sm opacity-80 flex items-center"><ImageIcon className="w-4 h-4 mr-2" /> 450 Photos</p>
                </div>
              </div>
            </div>
            
            <div className="bg-neo-orange border-4 border-black p-6 shadow-neo text-center">
              <div className="bg-white border-4 border-black inline-block p-2 mb-4">
                {shareUrl ? (
                  <img 
                    src={`https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(shareUrl)}`} 
                    alt="Share QR" 
                    className="w-32 h-32"
                  />
                ) : (
                  <div className="w-32 h-32 bg-gray-200 animate-pulse"></div>
                )}
              </div>
              <h3 className="text-xl font-bold uppercase mb-2">Share Portal</h3>
              <p className="text-sm mb-4 font-bold">Print this QR code or send the link to attendees so they can find their photos.</p>
              
              <div className="mb-4 text-left">
                <label className="text-[10px] font-bold text-black uppercase mb-1 flex justify-between items-center">
                  <span>Public Domain / Network IP</span>
                  <button onClick={detectNetworkIp} className="text-neo-blue hover:underline">Auto-Detect</button>
                </label>
                <input 
                  type="text" 
                  value={shareBaseUrl} 
                  onChange={e => setShareBaseUrl(e.target.value)} 
                  className="w-full text-xs p-2 border-4 border-black bg-white font-bold outline-none focus:bg-neo-yellow transition-colors"
                  placeholder="e.g. http://192.168.1.5:3000"
                />
              </div>
              
              <button 
                onClick={() => shareUrl && copyToClipboard(shareUrl)}
                className={`w-full font-bold py-3 border-4 border-black transition-all flex justify-center items-center mb-4 ${linkCopied ? 'bg-neo-green text-black translate-y-1 translate-x-1 shadow-none' : 'bg-white hover:-translate-y-1 hover:-translate-x-1 hover:shadow-neo'}`}
              >
                <Send className="mr-2 w-5 h-5" /> {linkCopied ? 'Copied!' : 'Copy Public Link'}
              </button>

              <hr className="border-2 border-black my-4" />
              
              <h3 className="text-xl font-bold uppercase mb-2">Private Mode</h3>
              <p className="text-sm mb-4 font-bold">Generate unique, single-use links for VIPs.</p>
              
              <button 
                onClick={handleGeneratePrivateLinks}
                disabled={generatingLinks}
                className="w-full font-bold py-3 border-4 border-black transition-all flex justify-center items-center bg-black text-white hover:bg-neo-blue hover:text-black uppercase"
              >
                {generatingLinks ? 'Generating...' : 'Generate 5 Private Links'}
              </button>

              {generatedTokens.length > 0 && (
                <div className="mt-4 text-left border-4 border-black bg-white p-2 h-32 overflow-y-auto">
                  <p className="text-xs font-bold uppercase mb-2 text-gray-500">New Links (Max 2 Opens Each)</p>
                  {generatedTokens.map((t, i) => (
                    <div key={i} className="flex justify-between items-center border-b-2 border-black pb-1 mb-1">
                      <code className="text-xs">{t.substring(0,6)}...</code>
                      <button onClick={() => copyToClipboard(`${shareUrl}&token=${t}`)} className="text-xs font-bold bg-neo-yellow px-2 border-2 border-black">Copy</button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Main Workspace */}
          <div className="col-span-1 lg:col-span-2 space-y-6">
            <div className="bg-white border-4 border-black p-8 shadow-neo min-h-[400px] flex flex-col">
              <div className="border-b-4 border-black pb-4 mb-6">
                <h2 className="text-3xl font-bold uppercase">Batch Upload ({activeEvent})</h2>
                <p className="font-bold text-gray-600 mt-2">Images will be automatically processed by the AI pipeline for face extraction.</p>
              </div>
              
              <label 
                htmlFor="file-upload"
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                className={`flex-grow flex flex-col items-center justify-center border-4 border-dashed border-black cursor-pointer transition-all relative group ${dragActive ? 'bg-neo-yellow border-solid scale-[1.02]' : 'bg-gray-50 hover:bg-neo-yellow'}`}
              >
                <UploadCloud className="w-20 h-20 mb-4 group-hover:scale-110 transition-transform duration-300" />
                <span className="text-2xl font-bold uppercase">Drop Folders Here</span>
                <span className="font-bold text-gray-500 mt-2">or click to browse RAW/JPG/PNG</span>
                <input id="file-upload" type="file" multiple className="sr-only" onChange={handleSelectFiles} />
              </label>
              
              {/* Queue Previews */}
              {queue.length > 0 && (
                <div className="mt-6 border-4 border-black p-4 bg-gray-50 max-h-64 overflow-y-auto">
                  <h3 className="font-bold uppercase mb-4 border-b-2 border-black pb-2">Upload Queue ({queue.length})</h3>
                  <div className="grid grid-cols-4 sm:grid-cols-6 gap-2">
                    {queue.map((f, i) => (
                      <div key={i} className="relative border-2 border-black aspect-square bg-gray-200">
                        <img src={URL.createObjectURL(f)} className="w-full h-full object-cover" alt="preview" />
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              <div className="mt-6 flex justify-between items-center">
                <span className="font-bold flex items-center"><FolderOpen className="mr-2" /> Upload Queue: {queue.length} files</span>
                <button 
                  onClick={handleProcessQueue}
                  disabled={uploading || queue.length === 0}
                  className={`font-bold px-8 py-4 border-4 border-black uppercase transition-colors ${uploading ? 'bg-gray-400 text-black' : 'bg-black text-white hover:bg-neo-blue'}`}
                >
                  {uploading ? 'Processing...' : 'Start Processing'}
                </button>
              </div>
            </div>

            {/* Past Photos Library */}
            <div className="bg-white border-4 border-black p-8 shadow-neo">
              <div className="flex justify-between items-end border-b-4 border-black pb-4 mb-6">
                <div>
                  <h2 className="text-2xl font-bold uppercase">Event Library</h2>
                  <p className="font-bold text-gray-600 mt-1">{pastPhotos.length} Total Processed Captures</p>
                </div>
                
                <div className="flex space-x-2">
                  <select 
                    value={sortMode} 
                    onChange={e => setSortMode(e.target.value as any)}
                    className="border-4 border-black font-bold p-2 bg-white"
                  >
                    <option value="newest">Newest First</option>
                    <option value="oldest">Oldest First</option>
                  </select>
                  
                  <div className="flex border-4 border-black">
                    <button onClick={() => setViewMode("grid")} className={`p-2 ${viewMode === 'grid' ? 'bg-black text-white' : 'bg-white text-black'}`}>Grid</button>
                    <button onClick={() => setViewMode("list")} className={`p-2 border-l-4 border-black ${viewMode === 'list' ? 'bg-black text-white' : 'bg-white text-black'}`}>List</button>
                  </div>
                </div>
              </div>
              
              {pastPhotos.length === 0 ? (
                <div className="text-center py-12 border-4 border-dashed border-gray-300">
                  <p className="font-bold text-gray-400 uppercase">No photos uploaded for this event yet.</p>
                </div>
              ) : viewMode === 'grid' ? (
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
                  {sortedPastPhotos.map((photo, i) => (
                    <div key={i} className="border-4 border-black bg-gray-100 overflow-hidden relative group aspect-square">
                      <img src={photo.url} alt="Processed" className="w-full h-full object-cover" />
                      <div className="absolute top-2 right-2 bg-neo-yellow font-bold px-2 py-1 border-2 border-black text-xs">
                        {photo.faces_detected} Faces
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="space-y-4">
                  {sortedPastPhotos.map((photo, i) => (
                    <div key={i} className="flex border-4 border-black p-2 items-center bg-gray-50 hover:bg-neo-yellow transition-colors cursor-pointer">
                      <img src={photo.url} alt="Processed" className="w-16 h-16 object-cover border-2 border-black mr-4" />
                      <div className="flex-grow">
                        <p className="font-bold uppercase text-sm">Image ID: {photo.id.substring(0, 8)}...</p>
                        <p className="text-xs font-bold text-gray-500">Faces detected: {photo.faces_detected}</p>
                      </div>
                      <a href={photo.url} target="_blank" rel="noreferrer" className="bg-white border-2 border-black font-bold px-4 py-2 text-xs uppercase hover:bg-black hover:text-white transition-colors">
                        View Original
                      </a>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
          
        </div>
      </div>
    </div>
  );
}
