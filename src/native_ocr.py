"""Isolated Apple Vision reader. Receives image bytes on stdin; emits JSON."""
import json
import sys


def recognize(data, language):
    import Vision
    from Foundation import NSData
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)
    supported, _ = request.supportedRecognitionLanguagesAndReturnError_(None)
    desired = ["en-US", "hi-IN"] if "hin" in language else ["en-US"]
    languages = [item for item in desired if item in supported]
    request.setRecognitionLanguages_(languages or ["en-US"])
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(NSData.dataWithBytes_length_(data, len(data)), None)
    ok, _ = handler.performRequests_error_([request], None)
    if not ok:
        raise RuntimeError("Local OCR could not read the image.")
    text = "\n".join(item.topCandidates_(1)[0].string() for item in request.results()).strip()
    return {"text": text, "languages": languages}


if __name__ == "__main__":
    print(json.dumps(recognize(sys.stdin.buffer.read(), sys.argv[1] if len(sys.argv) > 1 else "eng")))
