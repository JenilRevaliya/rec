"use client";
import React, { useState, useRef } from "react";
import { Upload, Camera, CheckCircle2, User, HelpCircle, Trash2 } from "lucide-react";

export default function LabPage() {
  const [photos, setPhotos] = useState<any[]>([]);
  const [matchingPhotos, setMatchingPhotos] = useState<string[] | null>(null);
  const [webcamActive, setWebcamActive] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const files = Array.from(e.target.files);
    
    // Upload all concurrently
    await Promise.all(files.map(async (file) => {
      const formData = new FormData();
      formData.append("file", file);
      const localUrl = URL.createObjectURL(file);
      
      try {
        const res = await fetch(`${window.location.protocol}//${window.location.hostname}:8001/upload`, {
          method: "POST",
          body: formData,
        });
        const data = await res.json();
        
        if (data.error || !Array.isArray(data.faces)) {
          alert(`Could not process ${file.name}: ${data.error || 'Server error'}.`);
          return;
        }
        
        setPhotos(prev => [...prev, { ...data, localUrl, file }]);
      } catch (err) {
        console.error("Upload failed", err);
      }
    }));
    
    // Reset file input
    e.target.value = '';
  };

  const resetLab = async () => {
    try {
      await fetch(`${window.location.protocol}//${window.location.hostname}:8001/reset`, { method: "POST" });
    } catch(e) {
      console.error(e);
    }
    setPhotos([]);
    setMatchingPhotos(null);
  };

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

  const executeMatch = async (fileOrBlob: Blob | File) => {
    setAnalyzing(true);
    const formData = new FormData();
    formData.append("file", fileOrBlob, "subject.jpg");
    
    try {
      const res = await fetch(`${window.location.protocol}//${window.location.hostname}:8001/match`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      
      if (data.error) {
        alert(`Search failed: ${data.error}`);
        setMatchingPhotos(null);
        return;
      }
      
      if (data.matches) {
        setMatchingPhotos(data.matches.map((m: any) => m.photo_id));
      } else {
        setMatchingPhotos([]);
      }
    } catch (err) {
      console.error("Match failed", err);
      alert("Search failed due to server error.");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleSubjectUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    executeMatch(file);
    e.target.value = '';
  };

  const captureAndMatch = async () => {
    if (!videoRef.current || !canvasRef.current) return;
    const context = canvasRef.current.getContext('2d');
    if (context) {
      context.drawImage(videoRef.current, 0, 0, 640, 480);
      canvasRef.current.toBlob(async (blob) => {
        if (!blob) return;
        await executeMatch(blob);
      }, 'image/jpeg');
    }
  };

  return (
    <div className="min-h-screen bg-neo-yellow bg-grain p-8 font-mono">
      <div className="max-w-6xl mx-auto space-y-8">
        <h1 className="text-4xl md:text-6xl font-bold uppercase tracking-tight shadow-neo bg-white border-4 border-black p-4 inline-block">
          Face Search Lab
        </h1>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          
          {/* Controls Panel */}
          <div className="col-span-1 space-y-8">
            <div className="bg-neo-blue border-4 border-black shadow-neo p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-2xl font-bold bg-white inline-block px-2 border-2 border-black">1. Upload Database</h2>
                <button onClick={resetLab} className="bg-red-500 text-white font-bold px-2 py-1 border-2 border-black hover:bg-red-600 flex items-center">
                  <Trash2 className="w-4 h-4 mr-1"/> Reset
                </button>
              </div>
              <label className="flex items-center justify-center w-full h-32 bg-white border-4 border-dashed border-black cursor-pointer hover:bg-gray-100 transition-colors">
                <div className="flex flex-col items-center text-center p-2">
                  <Upload className="w-8 h-8 mb-2" />
                  <span className="font-bold">Upload Target Photos</span>
                  <span className="text-xs text-gray-500">(JPG/PNG only)</span>
                </div>
                <input type="file" multiple accept="image/jpeg, image/png, image/webp" className="hidden" onChange={handleFileUpload} />
              </label>
            </div>

            <div className="bg-neo-orange border-4 border-black shadow-neo p-6">
              <h2 className="text-2xl font-bold mb-4 bg-white inline-block px-2 border-2 border-black">2. Find Subject</h2>
              
              <div className="flex gap-2 mb-4">
                <button 
                  onClick={startWebcam}
                  className="flex-1 bg-white border-4 border-black font-bold py-2 hover:shadow-none hover:translate-y-1 hover:translate-x-1 shadow-neo transition-all flex items-center justify-center text-sm"
                >
                  <Camera className="w-4 h-4 mr-2" /> Webcam
                </button>
                <label className="flex-1 bg-white border-4 border-black font-bold py-2 hover:shadow-none hover:translate-y-1 hover:translate-x-1 shadow-neo transition-all flex items-center justify-center cursor-pointer text-sm">
                  <Upload className="w-4 h-4 mr-2" /> Upload
                  <input type="file" accept="image/jpeg, image/png, image/webp" className="hidden" onChange={handleSubjectUpload} />
                </label>
              </div>

              {webcamActive && (
                <div className="space-y-4">
                  <div className="border-4 border-black overflow-hidden bg-black">
                    <video ref={videoRef} autoPlay playsInline muted className="w-full h-auto transform scale-x-[-1]" />
                    <canvas ref={canvasRef} width="640" height="480" className="hidden" />
                  </div>
                  <button 
                    onClick={captureAndMatch}
                    disabled={analyzing}
                    className="w-full bg-neo-green border-4 border-black font-bold py-4 hover:shadow-none hover:translate-y-1 hover:translate-x-1 shadow-neo transition-all flex items-center justify-center text-lg uppercase"
                  >
                    {analyzing ? "Analyzing..." : "Search This Face"}
                  </button>
                </div>
              )}
              
              {analyzing && (
                 <div className="mt-4 text-center font-bold animate-pulse bg-neo-yellow border-4 border-black p-4 shadow-neo">
                    Analyzing Subject...
                 </div>
              )}
            </div>
          </div>

          {/* Results Grid */}
          <div className="col-span-1 md:col-span-2">
            <div className="bg-white border-4 border-black shadow-neo p-6 min-h-[600px]">
              <div className="flex justify-between items-center mb-6 border-b-4 border-black pb-4">
                <h2 className="text-3xl font-bold">Image Database</h2>
                {matchingPhotos && (
                  <span className="bg-neo-green font-bold border-2 border-black px-3 py-1">
                    Found: {matchingPhotos.length} Match(es)
                  </span>
                )}
              </div>
              
              {photos.length === 0 ? (
                <div className="h-64 flex flex-col items-center justify-center text-gray-500 border-4 border-dashed border-gray-300">
                  <HelpCircle className="w-12 h-12 mb-4" />
                  <p className="font-bold text-xl">Upload images to populate database</p>
                </div>
              ) : (
                <div className="grid grid-cols-2 lg:grid-cols-3 gap-6">
                  {photos.map((photo) => {
                    const isMatch = matchingPhotos ? matchingPhotos.includes(photo.photo_id) : true;
                    
                    if (!isMatch) return null;

                    return (
                      <div key={photo.photo_id} className="group relative border-4 border-black shadow-neo bg-gray-100 overflow-hidden">
                        <img 
                          src={photo.localUrl} 
                          alt="Uploaded" 
                          className="w-full h-48 object-cover object-center"
                        />
                        
                        {/* Hover Overlay */}
                        <div className="absolute inset-0 bg-black/80 flex flex-col p-4 opacity-0 group-hover:opacity-100 transition-opacity text-white overflow-y-auto">
                          <p className="font-bold border-b-2 border-neo-green pb-1 mb-2 uppercase">Analysis Data</p>
                          <p className="text-sm text-neo-yellow mb-2">Faces Found: {photo.faces_detected || 0}</p>
                          {(photo.faces || []).map((f: any, i: number) => (
                            <div key={i} className="text-xs mb-2 border-l-2 border-white pl-2">
                              <p className="flex items-center"><User className="w-3 h-3 mr-1"/> Person {i+1}</p>
                              <p>Age: {f.age}</p>
                              <p>Gender: {f.gender}</p>
                              <p className="truncate text-gray-400">Box: {f.bbox ? f.bbox.map((n:number)=>Math.round(n)).join(',') : 'N/A'}</p>
                            </div>
                          ))}
                        </div>
                        
                        {matchingPhotos && matchingPhotos.includes(photo.photo_id) && (
                          <div className="absolute top-2 right-2 bg-neo-green text-black border-2 border-black p-1 rounded-full animate-bounce">
                            <CheckCircle2 className="w-6 h-6" />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
