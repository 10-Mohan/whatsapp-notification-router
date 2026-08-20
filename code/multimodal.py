import os
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("multimodal")

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "cache")
AUDIO_CACHE = os.path.join(CACHE_DIR, "audio_transcripts.json")
IMAGE_CACHE = os.path.join(CACHE_DIR, "image_ocr.json")

def ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)

def get_audio_transcripts(dataset_dir):
    ensure_cache_dir()
    if os.path.exists(AUDIO_CACHE):
        try:
            with open(AUDIO_CACHE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load audio cache: {e}")

    transcripts = {}
    audio_dir = os.path.join(dataset_dir, "media", "audio")
    if not os.path.exists(audio_dir):
        logger.warning(f"Audio directory not found: {audio_dir}")
        return transcripts

    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_dir = os.path.dirname(ffmpeg_exe)
        if ffmpeg_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
            logger.info(f"Added ffmpeg path: {ffmpeg_dir}")
    except Exception as e:
        logger.warning(f"Could not setup imageio-ffmpeg path: {e}")

    try:
        import whisper
        logger.info("Loading Whisper model for voice note transcription...")
        model = whisper.load_model("tiny")
        for fname in sorted(os.listdir(audio_dir)):
            if fname.endswith(".mp3"):
                vn_id = os.path.splitext(fname)[0]
                fpath = os.path.join(audio_dir, fname)
                try:
                    res = model.transcribe(fpath)
                    text = res.get("text", "").strip()
                    transcripts[vn_id] = text
                    logger.info(f"Transcribed {vn_id}: {text}")
                except Exception as ex:
                    logger.error(f"Error transcribing {fname}: {ex}")
                    transcripts[vn_id] = ""
    except Exception as e:
        logger.warning(f"Whisper not available or error: {e}")

    with open(AUDIO_CACHE, "w", encoding="utf-8") as f:
        json.dump(transcripts, f, indent=2, ensure_ascii=False)

    return transcripts

def get_image_ocr(dataset_dir):
    ensure_cache_dir()
    if os.path.exists(IMAGE_CACHE):
        try:
            with open(IMAGE_CACHE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load image cache: {e}")

    ocr_results = {}
    image_dir = os.path.join(dataset_dir, "media", "images")
    if not os.path.exists(image_dir):
        logger.warning(f"Image directory not found: {image_dir}")
        return ocr_results

    try:
        import easyocr
        logger.info("Loading EasyOCR reader for image text extraction...")
        reader = easyocr.Reader(['en'], gpu=False)
        for fname in sorted(os.listdir(image_dir)):
            if fname.endswith((".jpg", ".png", ".jpeg")):
                img_id = os.path.splitext(fname)[0]
                fpath = os.path.join(image_dir, fname)
                try:
                    results = reader.readtext(fpath, detail=0)
                    text = " ".join(results).strip()
                    ocr_results[img_id] = text
                    logger.info(f"OCR {img_id}: {text}")
                except Exception as ex:
                    logger.error(f"Error OCR on {fname}: {ex}")
                    ocr_results[img_id] = ""
    except Exception as e:
        logger.warning(f"EasyOCR not available or error: {e}")

    with open(IMAGE_CACHE, "w", encoding="utf-8") as f:
        json.dump(ocr_results, f, indent=2, ensure_ascii=False)

    return ocr_results
