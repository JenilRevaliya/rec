import os
import time
import json
import redis
from .mock import MockCameraDriver
from .dslr import DSLRDriver

def main():
    print("Initializing Camera Controller...")
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    use_mock = os.environ.get("USE_MOCK_CAMERA", "1") == "1"
    
    r = redis.from_url(redis_url)
    pubsub = r.pubsub()
    pubsub.subscribe('camera_commands')
    
    if use_mock:
        print("Using MockCameraDriver")
        driver = MockCameraDriver("MOCK_CAM_01")
    else:
        print("Using DSLRDriver")
        driver = DSLRDriver("DSLR_01")
        
    if not driver.connect():
        print("Failed to connect to camera. Exiting...")
        return
        
    print("Camera connected. Listening for commands on 'camera_commands' channel...")
    
    # Send an initial ping to say we are ready
    r.publish('camera_events', json.dumps({"event": "connected", "camera_id": driver.camera_id}))
    
    while True:
        message = pubsub.get_message()
        if message and message['type'] == 'message':
            try:
                data = json.loads(message['data'].decode('utf-8'))
                command = data.get("command")
                
                if command == "CAPTURE":
                    print("Received CAPTURE command")
                    driver.trigger_autofocus()
                    img_data = driver.capture_image()
                    
                    # Push result to Redis queue for detection engine or orchestrator
                    r.rpush("raw_images", json.dumps({
                        "filepath": img_data.filepath,
                        "timestamp": img_data.timestamp,
                        "camera_id": img_data.camera_id
                    }))
                    print(f"Pushed {img_data.filepath} to raw_images queue")
                    
            except Exception as e:
                print(f"Error processing command: {e}")
                
        time.sleep(0.1)

if __name__ == "__main__":
    main()
