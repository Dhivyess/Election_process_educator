"""
rag/google_services.py
Google Cloud integrations — Vision API for booth accessibility detection.
"""

import os
import base64
from typing import Optional
from google.cloud import vision
from google.cloud.vision_v1 import Feature, ImageContext
import logging

logger = logging.getLogger(__name__)

# ── Google Vision API ─────────────────────────────────────────────────────

class AccessibilityDetector:
    """
    Uses Google Cloud Vision API to analyze polling booth photos
    and detect accessibility features (ramps, wheelchair spaces, signage).
    """
    
    def __init__(self):
        try:
            self.client = vision.ImageAnnotatorClient()
            self.available = True
            logger.info("Google Vision API client initialized.")
        except Exception as e:
            logger.warning(f"Vision API unavailable: {e}")
            self.available = False
    
    def analyze_booth_accessibility(self, image_base64: str) -> dict:
        """
        Analyze a polling booth photo for accessibility features.
        
        Returns:
        {
            "accessibility_score": 0-100,
            "features_detected": ["wheelchair_ramp", "accessible_seating", ...],
            "barriers_detected": ["stairs", "crowded", ...],
            "recommendation": "This booth is accessible for PwD voters"
        }
        """
        if not self.available:
            return {"error": "Vision API not available"}
        
        try:
            image = vision.Image(content=base64.b64decode(image_base64))
            
            # Request: label detection + object detection
            features = [
                Feature(type_=Feature.Type.LABEL_DETECTION),
                Feature(type_=Feature.Type.OBJECT_LOCALIZATION),
            ]
            request = vision.AnnotateImageRequest(image=image, features=features)
            response = self.client.annotate_image(request)
            
            # Extract relevant labels
            features_detected = []
            barriers_detected = []
            confidence = 0
            
            for label in response.label_annotations:
                label_desc = label.description.lower()
                label_conf = label.score
                
                # Accessibility features
                if any(x in label_desc for x in ["ramp", "wheelchair", "accessible", "disabled", "barrier-free"]):
                    if label_conf > 0.6:
                        features_detected.append(label_desc)
                        confidence += label_conf * 20
                
                # Barriers
                if any(x in label_desc for x in ["stairs", "step", "crowded", "steep"]):
                    if label_conf > 0.6:
                        barriers_detected.append(label_desc)
            
            # Clamp confidence to 0-100
            accessibility_score = min(100, int(confidence + 30))  # Base 30 for all booths
            
            recommendation = self._generate_recommendation(
                accessibility_score, features_detected, barriers_detected
            )
            
            return {
                "accessibility_score": accessibility_score,
                "features_detected": features_detected,
                "barriers_detected": barriers_detected,
                "recommendation": recommendation,
                "image_width": response.full_text if hasattr(response, 'full_text') else 0
            }
        
        except Exception as e:
            logger.error(f"Vision API error: {e}")
            return {
                "error": str(e),
                "accessibility_score": 0,
                "recommendation": "Unable to assess. Contact booth officer."
            }
    
    def _generate_recommendation(self, score: int, features: list, barriers: list) -> str:
        """Generate human-readable recommendation."""
        if score >= 80:
            return "✅ This booth is accessible for voters with disabilities. Ramp and seating detected."
        elif score >= 60:
            return "⚠️ This booth has some accessibility features but may have barriers. Call 1950 to confirm."
        elif score >= 40:
            return "⚠️ Accessibility status unclear. Contact the booth officer or call 1950."
        else:
            return "❌ This booth may not be fully accessible. Request assistance from booth staff."


# ── Utility function ──────────────────────────────────────────────────────

accessibility_detector = AccessibilityDetector()


def detect_booth_accessibility(image_base64: str) -> dict:
    """Wrapper function for easy use in main.py endpoints."""
    return accessibility_detector.analyze_booth_accessibility(image_base64)
