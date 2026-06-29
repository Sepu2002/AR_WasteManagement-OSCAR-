import cv2
import numpy as np
import requests
import threading
import time
from pygrabber.dshow_graph import FilterGraph

# --- CONFIGURATION ---
ESP32_IP = "http://192.168.0.199"  # <--- CHANGE THIS TO YOUR ESP32 IP
TAG_SIZE = 0.165                  # 16.5 cm (Tag size)
TAG_FAMILY = cv2.aruco.DICT_APRILTAG_36h11

# Trash Can Physical Dimensions (in meters)
CAN_WIDTH = 0.26   # 26 cm
CAN_DEPTH = 0.26   # 26 cm
CAN_HEIGHT = 0.78  # 18 cm

# Since the tag is centered on the front face:
# X axis: -0.13 to +0.13 (Width)
# Y axis: -0.09 (Top) to +0.09 (Bottom) (Note: Y is down in OpenCV)
# Z axis: 0 (Front Face) to -0.26 (Back Face)

# Global variables for data sharing between thread and main loop
trash_data = {"percent": 0, "distance": 0}
running = True

def get_available_cameras():
    graph = FilterGraph()
    devices = graph.get_input_devices()
    print("\n--- Available Cameras ---")
    for i, name in enumerate(devices):
        print(f"[{i}] {name}")
    
    # Auto-select 0 if only one cam, else ask
    if len(devices) == 1: return 0
    
    while True:
        try:
            selection = input("\nEnter camera index number: ")
            index = int(selection)
            if 0 <= index < len(devices): return index
        except ValueError: pass

def data_fetcher():
    """Background thread to fetch data from ESP32"""
    global trash_data
    while running:
        try:
            # Add timeout so we don't hang forever
            r = requests.get(f"{ESP32_IP}/data", timeout=2)
            if r.status_code == 200:
                trash_data = r.json()
                #print(f"Update: {trash_data['percent']}%")
        except Exception as e:
            print(f"Connection Error: {e}")
        time.sleep(0.5)

def get_camera_matrix(width, height):
    # Approximating camera intrinsics
    focal_length = width 
    center_x = width / 2
    center_y = height / 2
    return np.array([[focal_length, 0, center_x], 
                     [0, focal_length, center_y], 
                     [0, 0, 1]], dtype=np.float32), np.zeros((4, 1))

def draw_ar_prism(img, rvec, tvec, K, D, percent):
    """Draws a 3D prism representing the trash level"""
    
    # 1. Determine Color
    if percent > 80:
        color = (0, 0, 255) # Red (BGR)
    elif percent > 50:
        color = (0, 215, 255) # Gold/Yellow
    else:
        color = (0, 255, 0) # Green

    # 2. Calculate Fill Height in meters
    # Percent 0   -> fill_height_m = 0
    # Percent 100 -> fill_height_m = 0.18
    fill_height_m = (percent / 100.0) * CAN_HEIGHT
    
    # 3. Define the 8 Corners of the Prism relative to Tag Center
    # Tag is at (0,0,0)
    # Bottom of Can (Y positive) = CAN_HEIGHT / 2
    # Top of Trash Level = Bottom - fill_height_m
    
    half_w = CAN_WIDTH / 2
    bottom_y = CAN_HEIGHT / 2
    current_top_y = bottom_y - fill_height_m
    
    # Define corners (X, Y, Z)
    # Z goes from 0 (Front) to -CAN_DEPTH (Back)
    
    # Front Face (Z=0)
    p1 = [-half_w, bottom_y, 0]      # Bottom Left Front
    p2 = [half_w, bottom_y, 0]       # Bottom Right Front
    p3 = [half_w, current_top_y, 0]  # Top Right Front
    p4 = [-half_w, current_top_y, 0] # Top Left Front
    
    # Back Face (Z = -CAN_DEPTH)
    p5 = [-half_w, bottom_y, -CAN_DEPTH]
    p6 = [half_w, bottom_y, -CAN_DEPTH]
    p7 = [half_w, current_top_y, -CAN_DEPTH]
    p8 = [-half_w, current_top_y, -CAN_DEPTH]

    points_3d = np.array([p1, p2, p3, p4, p5, p6, p7, p8], dtype=np.float32)

    # 4. Project 3D points to 2D image
    img_points, _ = cv2.projectPoints(points_3d, rvec, tvec, K, D)
    pts = np.int32(img_points).reshape(-1, 2)

    # 5. Draw Faces
    # Helper to draw filled polygons with transparency
    overlay = img.copy()
    
    # Front Face
    cv2.fillPoly(overlay, [pts[:4]], color)
    # Back Face
    cv2.fillPoly(overlay, [pts[4:]], color)
    # Top Face (p4, p3, p7, p8)
    cv2.fillPoly(overlay, [np.array([pts[3], pts[2], pts[6], pts[7]])], color)
    # Bottom Face (p1, p2, p6, p5)
    cv2.fillPoly(overlay, [np.array([pts[0], pts[1], pts[5], pts[4]])], color)
    # Left Face (p1, p4, p8, p5)
    cv2.fillPoly(overlay, [np.array([pts[0], pts[3], pts[7], pts[4]])], color)
    # Right Face (p2, p3, p7, p6)
    cv2.fillPoly(overlay, [np.array([pts[1], pts[2], pts[6], pts[5]])], color)

    # Apply transparency
    alpha = 0.4
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

    # 6. Draw Wireframe Outline (Solid lines for clarity)
    # Front
    cv2.polylines(img, [pts[:4]], True, color, 2)
    # Back
    cv2.polylines(img, [pts[4:]], True, color, 2)
    # Connecting Lines
    for i in range(4):
        cv2.line(img, tuple(pts[i]), tuple(pts[i+4]), color, 2)
        
    # 7. Draw Label floating above
    label_pos_3d = np.array([[0, -CAN_HEIGHT/2 - 0.05, -CAN_DEPTH/2]], dtype=np.float32) # 5cm above center
    label_pos_2d, _ = cv2.projectPoints(label_pos_3d, rvec, tvec, K, D)
    lbl = tuple(np.int32(label_pos_2d).reshape(2))
    
    text = f"{percent}%"
    cv2.putText(img, text, lbl, cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)


def main():
    global running
    
    # Start Data Thread
    t = threading.Thread(target=data_fetcher)
    t.start()
    
    cam_idx = get_available_cameras()
    cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
    
    # Setup Detection
    aruco_dict = cv2.aruco.getPredefinedDictionary(TAG_FAMILY)
    params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, params)

    # 3D object points for the Tag itself (for pose estimation)
    half_tag = TAG_SIZE / 2
    # Standard planar tag definition
    obj_points = np.array([
        [-half_tag, half_tag, 0], 
        [half_tag, half_tag, 0], 
        [half_tag, -half_tag, 0], 
        [-half_tag, -half_tag, 0]
    ], dtype=np.float32)

    print("Starting AR Stream... Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret: break
        
        h, w = frame.shape[:2]
        K, D = get_camera_matrix(w, h)
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, rejected = detector.detectMarkers(gray)
        
        if ids is not None:
            cv2.aruco.drawDetectedMarkers(frame, corners)
            
            for i, tag_id in enumerate(ids.flatten()):
                if tag_id == 1: # We only care about ID 1
                    success, rvec, tvec = cv2.solvePnP(obj_points, corners[i], K, D)
                    
                    if success:
                        # Draw the trash Prism!
                        draw_ar_prism(frame, rvec, tvec, K, D, trash_data['percent'])

        # UI Info
        cv2.putText(frame, f"WiFi Data: {trash_data['percent']}% ({trash_data['distance']}cm)", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.imshow('Smart Trash AR', frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    running = False
    t.join()
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()