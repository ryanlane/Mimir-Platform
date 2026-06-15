"""Video processing service using OpenCV for frame extraction."""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("mimir.channels.slowmovie.video")

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    logger.warning("[SlowMovie] opencv-python-headless not installed – frame extraction unavailable")
    _CV2_AVAILABLE = False

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    logger.warning("[SlowMovie] Pillow not installed – image conversion unavailable")
    _PIL_AVAILABLE = False


class VideoService:
    """Handles video introspection and frame extraction."""

    @staticmethod
    def is_available() -> bool:
        return _CV2_AVAILABLE and _PIL_AVAILABLE

    @staticmethod
    def get_video_info(video_path: Path) -> dict:
        """Return total_frames, fps, width, height, duration_seconds for a video file."""
        if not _CV2_AVAILABLE:
            return {"total_frames": 0, "fps": 0.0, "width": 0, "height": 0, "duration_seconds": 0.0}
        cap = cv2.VideoCapture(str(video_path))
        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = total_frames / fps if fps > 0 else 0.0
            return {
                "total_frames": total_frames,
                "fps": round(fps, 3),
                "width": width,
                "height": height,
                "duration_seconds": round(duration, 2),
            }
        finally:
            cap.release()

    @staticmethod
    def extract_frame(
        video_path: Path,
        frame_number: int,
        target_size: Optional[Tuple[int, int]] = None,
    ) -> Optional[bytes]:
        """Extract a single frame from a video, returning JPEG bytes.

        Args:
            video_path: Path to the video file.
            frame_number: Zero-based frame index to extract.
            target_size: Optional (width, height) to resize the frame to.

        Returns:
            JPEG bytes, or None on failure.
        """
        if not _CV2_AVAILABLE or not _PIL_AVAILABLE:
            return None

        cap = cv2.VideoCapture(str(video_path))
        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            if not ret or frame is None:
                logger.warning("[SlowMovie] Could not read frame %d from %s", frame_number, video_path)
                return None

            # Convert BGR (OpenCV) → RGB (Pillow)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)

            if target_size:
                img = _resize_letterbox(img, target_size)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=92, optimize=True)
            return buf.getvalue()
        except Exception as exc:
            logger.error("[SlowMovie] Frame extraction failed: %s", exc)
            return None
        finally:
            cap.release()

    @staticmethod
    def extract_frame_to_file(
        video_path: Path,
        frame_number: int,
        output_path: Path,
        target_size: Optional[Tuple[int, int]] = None,
    ) -> bool:
        """Extract a frame and save it to disk. Returns True on success."""
        data = VideoService.extract_frame(video_path, frame_number, target_size)
        if data is None:
            return False
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)
        return True


def _resize_letterbox(img: "Image.Image", target: Tuple[int, int]) -> "Image.Image":
    """Resize image to fit within target while preserving aspect ratio (letterbox)."""
    tw, th = target
    iw, ih = img.size
    scale = min(tw / iw, th / ih)
    new_w = int(iw * scale)
    new_h = int(ih * scale)
    resized = img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (tw, th), (0, 0, 0))
    offset_x = (tw - new_w) // 2
    offset_y = (th - new_h) // 2
    canvas.paste(resized, (offset_x, offset_y))
    return canvas
