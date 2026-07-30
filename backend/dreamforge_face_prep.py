import os
import cv2

def get_face_cascade():
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    return cv2.CascadeClassifier(cascade_path)

def preprocess_reference_face(image_path: str, output_path: str, margin_ratio: float = 0.5):
    """
    Detects the primary face in the reference image and crops it with a margin.
    This ensures ComfyUI IP-Adapter FaceID receives a perfectly aligned face,
    greatly improving face consistency.
    """
    image_path = str(image_path)
    output_path = str(output_path)
    if not os.path.exists(image_path):
        return {"ok": False, "cropped_path": None, "error": f"Input image not found: {image_path}"}

    # Read image
    img = cv2.imread(image_path)
    if img is None:
        return {"ok": False, "cropped_path": None, "error": f"Could not read image: {image_path}"}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    face_cascade = get_face_cascade()
    
    # Detect faces
    faces = face_cascade.detectMultiScale(
        gray, 
        scaleFactor=1.1, 
        minNeighbors=5, 
        minSize=(30, 30)
    )
    
    if len(faces) == 0:
        # Fallback: if no face detected, just return original or centered crop
        # We'll just save the original image if no face is found
        cv2.imwrite(output_path, img)
        return {"ok": True, "cropped_path": output_path, "message": "No face detected, using original image."}
    
    # Find the largest face (most likely the primary subject)
    largest_face = max(faces, key=lambda f: f[2] * f[3])
    x, y, w, h = largest_face
    
    # Add margin
    margin_w = int(w * margin_ratio)
    margin_h = int(h * margin_ratio)
    
    # Calculate bounding box with margin, clamped to image dimensions
    img_h, img_w = img.shape[:2]
    
    x1 = max(0, x - margin_w)
    y1 = max(0, y - margin_h)
    x2 = min(img_w, x + w + margin_w)
    y2 = min(img_h, y + h + margin_h)
    
    # Crop face
    face_crop = img[y1:y2, x1:x2]
    
    # Save cropped face
    cv2.imwrite(output_path, face_crop)
    return {"ok": True, "cropped_path": output_path, "message": f"Face cropped and saved to {output_path}."}

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="DreamForge Face Prep")
    parser.add_argument("input", help="Path to input image")
    parser.add_argument("output", help="Path to save cropped face image")
    parser.add_argument("--margin", type=float, default=0.5, help="Margin ratio around face")
    args = parser.parse_args()
    
    res = preprocess_reference_face(args.input, args.output, args.margin)
    print(res.get("message", res.get("error", "Unknown result")))
