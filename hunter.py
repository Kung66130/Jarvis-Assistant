import pygetwindow as gw
import psutil
import os

def hunt_holograms():
    print("Hunting for hologram windows...")
    windows = gw.getAllWindows()
    found_count = 0
    for win in windows:
        # Look for our unique ID or any python-based windows that might be holograms
        title = win.title
        if "JARVIS" in title.upper() or "UI_QT" in title.upper():
            print(f"Found suspicious window: '{title}'")
            try:
                win.close()
                found_count += 1
            except:
                print(f"Could not close '{title}' directly, attempting to find process...")
    
    print(f"Closed {found_count} windows by title.")
    
    # Also kill all python processes again just in case
    python_killed = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = " ".join(proc.info['cmdline']) if proc.info['cmdline'] else ""
            if "ui_qt.py" in cmd or "python" in proc.info['name'].lower():
                if os.getpid() != proc.info['pid']: # Don't kill myself
                    proc.kill()
                    python_killed += 1
        except:
            continue
    
    print(f"Killed {python_killed} python processes.")

if __name__ == "__main__":
    try:
        hunt_holograms()
    except Exception as e:
        print(f"Hunter error: {e}")
