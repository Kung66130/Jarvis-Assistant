import speech_recognition as sr
import sys
import io
import os
import pyaudio
import numpy as np
import argparse
import time
import json

# Force UTF-8 Output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
DEFAULT_THRESHOLD = 3000
QUEUE_FILE = os.path.join(os.path.dirname(__file__), "agent_queue.json")
TELEGRAM_CMD_FILE = os.path.join(os.path.dirname(__file__), "telegram_cmd.json")


def find_input_device() -> int | None:
    p = pyaudio.PyAudio()
    try:
        for i in range(p.get_device_count()):
            dev_info = p.get_device_info_by_index(i)
            name = dev_info.get('name', '')
            if dev_info.get('maxInputChannels') > 0 and "EDIFIER" in name.upper():
                return i
    finally:
        p.terminate()
    return None


def pop_agent_report() -> str | None:
    if not os.path.exists(QUEUE_FILE):
        return None
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            data_json = f.read()
        os.remove(QUEUE_FILE)
        return data_json
    except Exception:
        return None


def pop_telegram_command() -> str | None:
    if not os.path.exists(TELEGRAM_CMD_FILE):
        return None
    try:
        with open(TELEGRAM_CMD_FILE, "r", encoding="utf-8") as f:
            data_json = f.read()
        try:
            os.remove(TELEGRAM_CMD_FILE)
        except Exception:
            pass
        return data_json
    except Exception:
        return None


def _open_input_stream(p: pyaudio.PyAudio, device_index: int | None):
    return p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        input_device_index=device_index,
        frames_per_buffer=CHUNK,
    )


def _read_rms(stream) -> float:
    try:
        # Check if there are enough frames to read without blocking
        if stream.get_read_available() < CHUNK:
            return 0.0
    except Exception:
        # Fallback if get_read_available is not supported
        pass
    data = stream.read(CHUNK, exception_on_overflow=False)
    audio_data = np.frombuffer(data, dtype=np.int16)
    return float(np.sqrt(np.mean(audio_data.astype(np.float32) ** 2)))


def wait_for_wake_activity(
    device_index: int | None,
    *,
    threshold: int = DEFAULT_THRESHOLD,
) -> str | None:
    p = pyaudio.PyAudio()
    stream = None
    try:
        try:
            stream = _open_input_stream(p, device_index)
            print("Listening for wake word...", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Microphone input is unavailable ({e}). Running in Remote/Telegram-only mode...", file=sys.stderr)
            stream = None

        while True:
            # 1. Check for Telegram commands first
            tg_cmd = pop_telegram_command()
            if tg_cmd:
                if stream:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except Exception:
                        pass
                return f"TELEGRAM_CMD:{tg_cmd}"

            # 2. Check for Agent reports
            report = pop_agent_report()
            if report:
                if stream:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except Exception:
                        pass
                return f"AGENT_REPORT:{report}"

            # 3. Check for voice wake word
            if stream:
                try:
                    if _read_rms(stream) > threshold:
                        stream.stop_stream()
                        stream.close()
                        return "WAKE"
                except Exception as e:
                    print(f"Error reading audio stream: {e}. Disabling voice input stream...", file=sys.stderr)
                    try:
                        stream.stop_stream()
                        stream.close()
                    except Exception:
                        pass
                    stream = None
            
            # Tiny sleep to avoid pegging CPU at 100% while polling
            time.sleep(0.05)
    finally:
        p.terminate()


def recognize_command(
    device_index: int | None,
    *,
    timeout: int = 5,
    phrase_time_limit: int = 8,
) -> str:
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone(device_index=device_index) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            print("Woke up! Recording...", file=sys.stderr)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            return recognizer.recognize_google(audio, language="th-TH")
    except sr.UnknownValueError:
        print("Speech recognition: Could not understand audio", file=sys.stderr)
        return ""
    except sr.RequestError as e:
        print(f"Speech recognition service error: {e}", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"Speech recognition error: {e}", file=sys.stderr)
        return ""


def detect_interrupt(
    device_index: int | None,
    *,
    threshold: int = 4500,
    windows: int = 2,
    window_ms: int = 180,
) -> bool:
    p = pyaudio.PyAudio()
    hits = 0
    deadline = time.time() + (windows * window_ms / 1000.0)
    stream = None
    try:
        try:
            stream = _open_input_stream(p, device_index)
        except Exception as e:
            # If microphone is unavailable, we cannot detect interrupt by voice
            return False

        while time.time() < deadline:
            try:
                if _read_rms(stream) > threshold:
                    hits += 1
                    if hits >= windows:
                        stream.stop_stream()
                        stream.close()
                        return True
            except Exception:
                break
        if stream:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        return False
    finally:
        p.terminate()


def listen() -> str:
    device_index = find_input_device()
    if device_index is None:
        print("EDIFIER mic not found, using default.", file=sys.stderr)

    wake_result = wait_for_wake_activity(device_index)
    if wake_result and wake_result.startswith("AGENT_REPORT:"):
        return wake_result

    return recognize_command(device_index)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["default", "command", "interrupt"], default="default")
    args = parser.parse_args()

    device_index = find_input_device()
    if device_index is None:
        print("EDIFIER mic not found, using default.", file=sys.stderr)

    try:
        if args.mode == "command":
            result = recognize_command(device_index)
            print(f"RESULT:{result or 'NONE'}")
            return
        if args.mode == "interrupt":
            print("INTERRUPT" if detect_interrupt(device_index) else "NONE")
            return

        result = listen()
        if result.startswith("ERROR"):
            print(result)
        elif result.startswith("AGENT_REPORT:"):
            print(result)
        elif result:
            print(f"RESULT:{result}")
        else:
            print("RESULT:NONE")
    except Exception as e:
        print(f"ERROR:{e}")


if __name__ == "__main__":
    main()
