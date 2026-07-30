"use client";
import React, { useState, useRef, useEffect, Suspense } from "react";
import { Camera, Download, Lock, CheckCircle2, LogOut, AlertTriangle } from "lucide-react";
import { useSearchParams } from "next/navigation";
import LoginForm from "../../components/LoginForm";

function UserPortalContent() {
  const searchParams = useSearchParams();
  const token = searchParams?.get("token");
  const eventId = searchParams?.get("event");
  const [tokenValid, setTokenValid] = useState<boolean | null>(null);
  const [tokenError, setTokenError] = useState("");

  const [loggedIn, setLoggedIn] = useState(false);
  const [username, setUsername] = useState("");
  const [isClient, setIsClient] = useState(false);

  const [authenticated, setAuthenticated] = useState(false);
  const [webcamActive, setWebcamActive] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  
  useEffect(() => {
    setIsClient(true);
    const storedUser = localStorage.getItem("rec_username_user");
    const storedToken = localStorage.getItem("rec_token_user");
    if (storedUser && storedToken) {
      setUsername(storedUser);
      setLoggedIn(true);
    }
    
    // Validate private link token if present
    if (token) {
      fetch(`http://localhost:8001/links/validate/${token}`)
        .then(res => res.json())
        .then(data => {
          if (data.valid) {
            setTokenValid(true);
          } else {
            setTokenValid(false);
            setTokenError(data.error || "Invalid private link");
          }
        })
        .catch(() => {
          setTokenValid(false);
          setTokenError("Could not validate private link");
        });
    } else {
      // If no token is provided, assume public mode or standard access
      setTokenValid(true); 
    }
  }, [token]);

  const handleLogout = () => {
    localStorage.removeItem("rec_token_user");
    localStorage.removeItem("rec_role_user");
    localStorage.removeItem("rec_username_user");
    setLoggedIn(false);
    setUsername("");
    setAuthenticated(false);
    setMatchedPhotos([]);
  };

  const handleLoginSuccess = (user: string) => {
    setUsername(user);
    setLoggedIn(true);
  };

  const [matchedPhotos, setMatchedPhotos] = useState<any[]>([]);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const uniqueEventsCount = new Set(matchedPhotos.map(p => p.event)).size;

  const startWebcam = async () => {
    setWebcamActive(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch (err) {
      console.error("Webcam error", err);
    }
  };

  const authenticateFace = async () => {
    if (!videoRef.current || !canvasRef.current) return;
    setAnalyzing(true);
    
    const context = canvasRef.current.getContext('2d');
    if (context) {
      context.drawImage(videoRef.current, 0, 0, 640, 480);
      
      canvasRef.current.toBlob(async (blob) => {
        if (!blob) return;
        const formData = new FormData();
        formData.append("file", blob, "webcam.jpg");
        
        try {
          const res = await fetch("http://localhost:8001/match", {
            method: "POST",
            body: formData,
          });
          const data = await res.json();
          if (data.matches) {
            setMatchedPhotos(data.matches);
            // Consume token if present
            if (token) {
              fetch(`http://localhost:8001/links/consume/${token}`, { method: "POST" });
            }
          }
        } catch (err) {
          console.error("Match failed", err);
          alert("Could not connect to AI Engine.");
        } finally {
          setAnalyzing(false);
          setAuthenticated(true);
          if (videoRef.current && videoRef.current.srcObject) {
            const stream = videoRef.current.srcObject as MediaStream;
            stream.getTracks().forEach(track => track.stop());
          }
        }
      }, 'image/jpeg');
    }
  };

  if (!isClient) return null;

  if (!loggedIn) {
    return <LoginForm expectedRole="user" onLoginSuccess={handleLoginSuccess} title="User Login" />;
  }

  if (!authenticated) {
    return (
      <div className="min-h-screen bg-neo-blue bg-grain p-4 md:p-8 flex items-center justify-center font-mono">
        <div className="bg-white border-4 border-black p-8 md:p-12 shadow-neo max-w-xl w-full text-center">
          {tokenValid === false ? (
            <>
              <AlertTriangle className="w-16 h-16 mx-auto mb-6 text-red-500" />
              <h1 className="text-4xl font-bold uppercase tracking-tight mb-2 text-red-500">Access Denied</h1>
              <p className="font-bold text-gray-600 mb-8">{tokenError}</p>
              <p className="text-sm font-bold bg-gray-100 p-4 border-2 border-black">This event is set to Private. Please request a new link from the photographer.</p>
            </>
          ) : (
            <>
              <Lock className="w-16 h-16 mx-auto mb-6" />
              <h1 className="text-4xl font-bold uppercase tracking-tight mb-2">Find Your Photos, {username}</h1>
              <p className="font-bold text-gray-600 mb-8">Take a quick selfie to unlock and instantly find every photo of you across all events.</p>
              
              {!webcamActive ? (
            <button 
              onClick={startWebcam}
              className="w-full bg-neo-yellow font-bold py-6 border-4 border-black hover:-translate-y-1 hover:-translate-x-1 hover:shadow-neo transition-all flex items-center justify-center text-xl uppercase"
            >
              <Camera className="mr-3 w-6 h-6" /> Open Camera
            </button>
          ) : (
            <div className="space-y-4">
              <div className="border-4 border-black overflow-hidden bg-black max-w-sm mx-auto">
                <video ref={videoRef} autoPlay playsInline muted className="w-full h-auto transform scale-x-[-1]" />
                <canvas ref={canvasRef} width="640" height="480" className="hidden" />
              </div>
              <button 
                onClick={authenticateFace}
                disabled={analyzing}
                className="w-full bg-neo-green text-black font-bold py-4 border-4 border-black hover:-translate-y-1 hover:-translate-x-1 hover:shadow-neo transition-all flex items-center justify-center text-lg uppercase"
              >
                {analyzing ? 'Scanning Face Data...' : 'Authenticate & Search'}
              </button>
            </div>
          )}
          </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100 bg-grain p-4 md:p-8 font-mono">
      <div className="max-w-6xl mx-auto space-y-8">
        
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center bg-white border-4 border-black p-6 shadow-neo">
          <div className="flex items-center">
            <CheckCircle2 className="w-10 h-10 text-neo-green mr-4" />
            <div>
              <h1 className="text-3xl font-bold uppercase tracking-tight">Identity Verified</h1>
              <p className="font-bold text-gray-600">Found {matchedPhotos.length} photos of you across {uniqueEventsCount} event{uniqueEventsCount === 1 ? '' : 's'}.</p>
            </div>
          </div>
          <button onClick={handleLogout} className="mt-4 md:mt-0 bg-white font-bold px-6 py-3 border-4 border-black hover:-translate-y-1 hover:-translate-x-1 hover:shadow-neo transition-all flex items-center">
            <LogOut className="mr-2" /> Exit
          </button>
        </div>

        {/* Gallery */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
          {matchedPhotos.map((photo, index) => (
            <div key={photo.photo_id || index} className="bg-white border-4 border-black shadow-neo flex flex-col group">
              {/* Lower quality thumbnail for preview */}
              <div className="border-b-4 border-black relative overflow-hidden h-64 bg-gray-200">
                <img 
                  src={photo.url} 
                  alt="Matched Photo" 
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                />
              </div>
              
              <div className="p-4 flex-grow flex flex-col justify-between">
                <div>
                  <h3 className="font-bold text-xl uppercase mb-1">{photo.event}</h3>
                  <p className="text-sm font-bold text-gray-500 mb-4">By: {photo.photographer}</p>
                </div>
                
                <a href={photo.url} download target="_blank" rel="noreferrer" className="w-full bg-black text-white font-bold py-3 border-2 border-black hover:bg-neo-green hover:text-black transition-colors flex items-center justify-center uppercase">
                  <Download className="mr-2 w-5 h-5" /> Full Quality
                </a>
              </div>
            </div>
          ))}
        </div>

      </div>
    </div>
  );
}

export default function UserPortal() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center font-bold font-mono">Loading Portal...</div>}>
      <UserPortalContent />
    </Suspense>
  );
}
