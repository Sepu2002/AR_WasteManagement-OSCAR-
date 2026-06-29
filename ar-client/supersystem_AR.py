import cv2
import numpy as np
import requests
import threading
import time
import random
from pygrabber.dshow_graph import FilterGraph

# --- CONFIGURATION ---
ESP32_IP = "http://192.168.0.199"  # <--- CHANGE THIS TO YOUR ESP32 IP
TAG_SIZE = 0.165                  
TAG_FAMILY = cv2.aruco.DICT_APRILTAG_36h11
CAN_WIDTH = 0.26   
CAN_DEPTH = 0.26   
CAN_HEIGHT = 0.78 

# Global variables
trash_data = {"percent": 0, "distance": 0}
running = True

# --- SUPERSYSTEM SIMULATION VARIABLES ---
city_grid_id = f"NODE-{random.randint(1000, 9999)}"
dispatch_status = "IDLE"
truck_eta = "N/A"

def get_available_cameras():
    try:
        graph = FilterGraph()
        devices = graph.get_input_devices()
        print("\n--- Available Cameras ---")
        for i, name in enumerate(devices):
            print(f"[{i}] {name}")
        
        # Auto-select 0 if only one cam, else ask
        if len(devices) == 1: 
            print("Auto-selecting single camera.")
            return 0
        
        while True:
            try:
                selection = input("\nEnter camera index number: ")
                index = int(selection)
                if 0 <= index < len(devices): return index
            except ValueError: pass
    except Exception as e:
        print(f"Could not list cameras using pygrabber: {e}")
        return 0 # Default to 0 if listing fails

def data_fetcher():
    """Background thread to fetch data and simulate Supersystem Logic"""
    global trash_data, dispatch_status, truck_eta
    while running:
        try:
            r = requests.get(f"{ESP32_IP}/data", timeout=2)
            if r.status_code == 200:
                trash_data = r.json()
                
                # --- SUPERSYSTEM LOGIC ---
                # If bin is > 90% full, the "City Grid" takes over
                if trash_data['percent'] > 90:
                    dispatch_status = "DISPATCHED"
                    truck_eta = "14 MINS"
                elif trash_data['percent'] > 75:
                    dispatch_status = "QUEUED"
                    truck_eta = "PENDING"
                else:
                    dispatch_status = "IDLE"
                    truck_eta = "N/A"
                    
        except: pass 
        time.sleep(0.5)

def get_camera_matrix(width, height):
    focal_length = width 
    center_x = width / 2
    center_y = height / 2
    return np.array([[focal_length, 0, center_x], [0, focal_length, center_y], [0, 0, 1]], dtype=np.float32), np.zeros((4, 1))

def draw_supersystem_ui(img, percent):
    """Draws the Smart City Supersystem Interface"""
    h, w = img.shape[:2]
    
    # 1. Draw Sidebar Background
    cv2.rectangle(img, (w-250, 0), (w, 180), (0, 0, 0), -1)
    
    # 2. Header
    cv2.putText(img, "CITY GRID CONNECT", (w-240, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    
    # 3. Node ID
    cv2.putText(img, f"ID: {city_grid_id}", (w-240, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    
    # 4. Status Logic
    status_color = (0, 255, 0) # Green
    if dispatch_status == "DISPATCHED": status_color = (0, 0, 255) # Red
    if dispatch_status == "QUEUED": status_color = (0, 165, 255) # Orange
    
    cv2.putText(img, f"STATUS: {dispatch_status}", (w-240, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, status_color, 2)
    
    if dispatch_status == "DISPATCHED":
        cv2.putText(img, f"TRUCK ETA: {truck_eta}", (w-240, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.rectangle(img, (w-245, 140), (w-5, 170), (0, 0, 255), 2)
        cv2.putText(img, "COLLECTION ROUTED", (w-235, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    else:
        cv2.putText(img, "Monitoring...", (w-240, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)

def draw_ar_prism(img, rvec, tvec, K, D, percent):
    # Same prism drawing logic as before
    if percent > 80: color = (0, 0, 255) 
    elif percent > 50: color = (0, 215, 255)
    else: color = (0, 255, 0)

    fill_height_m = (percent / 100.0) * CAN_HEIGHT
    half_w = CAN_WIDTH / 2
    bottom_y = CAN_HEIGHT / 2
    current_top_y = bottom_y - fill_height_m
    
    p1 = [-half_w, bottom_y, 0]
    p2 = [half_w, bottom_y, 0]
    p3 = [half_w, current_top_y, 0]
    p4 = [-half_w, current_top_y, 0]
    p5 = [-half_w, bottom_y, -CAN_DEPTH]
    p6 = [half_w, bottom_y, -CAN_DEPTH]
    p7 = [half_w, current_top_y, -CAN_DEPTH]
    p8 = [-half_w, current_top_y, -CAN_DEPTH]

    points_3d = np.array([p1, p2, p3, p4, p5, p6, p7, p8], dtype=np.float32)
    img_points, _ = cv2.projectPoints(points_3d, rvec, tvec, K, D)
    pts = np.int32(img_points).reshape(-1, 2)

    overlay = img.copy()
    cv2.fillPoly(overlay, [pts[:4]], color)
    cv2.fillPoly(overlay, [pts[4:]], color)
    cv2.fillPoly(overlay, [np.array([pts[3], pts[2], pts[6], pts[7]])], color)
    cv2.fillPoly(overlay, [np.array([pts[0], pts[1], pts[5], pts[4]])], color)
    cv2.fillPoly(overlay, [np.array([pts[0], pts[3], pts[7], pts[4]])], color)
    cv2.fillPoly(overlay, [np.array([pts[1], pts[2], pts[6], pts[5]])], color)
    alpha = 0.4
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    
    for i in range(4): cv2.line(img, tuple(pts[i]), tuple(pts[i+4]), color, 2)
    cv2.polylines(img, [pts[:4]], True, color, 2)
    cv2.polylines(img, [pts[4:]], True, color, 2)

def main():
    global running
    t = threading.Thread(target=data_fetcher)
    t.start()
    
    print("Selecting camera...")
    cam_idx = get_available_cameras()
    
    print(f"Attempting to open camera index {cam_idx}...")
    cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
    
    # --- FIX FOR DISTORTED FRAME (OBS OPTIMIZED) ---
    # OBS Virtual Camera usually outputs 16:9 (e.g. 1920x1080).
    # Forcing 640x480 (4:3) causes it to look squashed.
    # We set it to 1280x720 (16:9) to match standard OBS settings.
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    aruco_dict = cv2.aruco.getPredefinedDictionary(TAG_FAMILY)
    params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, params)

    half_tag = TAG_SIZE / 2
    obj_points = np.array([[-half_tag, half_tag, 0], [half_tag, half_tag, 0], [half_tag, -half_tag, 0], [-half_tag, -half_tag, 0]], dtype=np.float32)

    print("Project OSCAR: Supersystem Prototype Active.")

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
                if tag_id == 1:
                    success, rvec, tvec = cv2.solvePnP(obj_points, corners[i], K, D)
                    if success:
                        draw_ar_prism(frame, rvec, tvec, K, D, trash_data['percent'])

        # --- DRAW SUPERSYSTEM UI ---
        draw_supersystem_ui(frame, trash_data['percent'])
        
        cv2.imshow('Project OSCAR - Smart City Node', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break

    running = False
    t.join()
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()