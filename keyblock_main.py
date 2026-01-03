import keyboard
import json
import sys
import os
import time
import ctypes
import threading
from pystray import Icon as TrayIcon, MenuItem as Item
from PIL import Image, ImageDraw


PROFILE_FILE = "profiles.json"
SAFE_KEYS = ['esc', 'enter', 'ctrl', 'shift', 'alt', 'caps lock', 'win', 'delete', 'backspace']
KILL_SWITCH = 'ctrl+alt+c'  # Changed from ctrl+c 

class GhostKeyBlocker:
    def __init__(self):
        self.ensure_admin()
        self.active_profile = None
        self.blocked_keys = set()
        self.is_running = True
        self.tray_icon = None

    def ensure_admin(self):
        """ Checks for admin rights and restarts if necessary. (Req #10) """
        try:
            is_admin = os.getuid() == 0
        except AttributeError:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0

        if not is_admin:
            print("[!] Requesting Administrator Privileges...")
            #re-run the program with admin rights
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            sys.exit()

    def hide_console(self):
        """ Hides the terminal window completely """
        print("\n[i] Hiding terminal in 3 seconds... (Check System Tray)")
        time.sleep(3) # Give user a moment to read
        
        kernel32 = ctypes.WinDLL('kernel32')
        user32 = ctypes.WinDLL('user32')
        
        hWnd = kernel32.GetConsoleWindow()
        if hWnd:
            user32.ShowWindow(hWnd, 0) # 0 = SW_HIDE
            
    def load_profiles(self):
        if not os.path.exists(PROFILE_FILE):
            return {}
        try:
            with open(PROFILE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}

    def save_profiles(self, profiles):
        with open(PROFILE_FILE, 'w') as f:
            json.dump(profiles, f, indent=4)

    def create_icon_image(self, color="blue"):
        """ Generates a simple icon for the system tray """
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), (255, 255, 255))
        dc = ImageDraw.Draw(image)
        dc.rectangle((0, 0, width, height), fill=color)
        dc.rectangle((16, 16, 48, 48), fill="white")
        return image

    def kill_app(self):
        """ The Emergency Kill Switch (Req #7) """
        print("\n[!!!] KILL SWITCH ACTIVATED. Unblocking all keys and exiting.")
        self.unblock_all()
        if self.tray_icon:
            self.tray_icon.stop()
        os._exit(0) # Force kill

    def unblock_all(self):
        keyboard.unhook_all()
        self.blocked_keys.clear()

    def create_new_profile(self):
        print("\n" + "="*50)
        print(" NEW PROFILE CREATION - GHOST KEY TRAP")
        print("="*50)
        print("INSTRUCTIONS:")
        print("1. Press the keys that are 'ghosting' (pressing themselves).")
        print("2. They will be DISABLED immediately upon press.")
        print("3. Press 'ESC' when you are finished detecting keys.")
        print("-" * 50)

        temp_blocked = set()

        # Inner hook to catch keys during setup
        def detector(event):
            key = event.name
            
            if event.event_type == 'down':
                if key == 'esc':
                    return # loop handle the exit
                
                if key in SAFE_KEYS:
                    print(f"[!] Cannot block safe key: {key}")
                    return

                if key in temp_blocked:
                    # Visual feedback restriction (Req #8)
                    print(f"[*] Key '{key}' already selected/blocked.")
                else:
                    print(f"[+] DETECTED & BLOCKED: {key}")
                    try:
                        keyboard.block_key(key)
                        temp_blocked.add(key)
                    except Exception as e:
                        print(f"[Error] Could not block {key}: {e}")

        # Start listening
        hook = keyboard.hook(detector)
        
        # Wait for ESC to be pressed to finish recording
        keyboard.wait('esc')
        
        # Cleanup detection hook
        keyboard.unhook(hook) 
        
        # Unblock temporarily so user can type the profile name
        #  re-block them when the profile runs
        for k in temp_blocked:
            try:
                keyboard.unblock_key(k)
            except:
                pass

        if not temp_blocked:
            print("\n[!] No keys detected. Profile creation cancelled.")
            return

        print(f"\n[OK] Captured keys: {', '.join(temp_blocked)}")
        name = input("Enter a name for this profile (e.g., 'BrotherLaptop'): ").strip()
        
        if name:
            profiles = self.load_profiles()
            profiles[name] = list(temp_blocked)
            self.save_profiles(profiles)
            print(f"[Success] Profile '{name}' saved!")
        else:
            print("[!] No name entered. Discarded.")

    def run_profile_mode(self, profile_name, keys_to_block):
        print(f"\n[!!!] ACTIVATING PROFILE: {profile_name}")
        print(f"[i] Blocking: {', '.join(keys_to_block)}")
        print(f"[i] Press {KILL_SWITCH} to emergency stop.")
        print("[i] Minimizing to System Tray...")

        # 1. Apply Blocks
        self.unblock_all()
        for k in keys_to_block:
            try:
                keyboard.block_key(k)
                self.blocked_keys.add(k)
            except Exception as e:
                print(f"Failed to block {k}: {e}")

        # 2. Register Kill Switch
        keyboard.add_hotkey(KILL_SWITCH, self.kill_app)

        self.hide_console()
        
        # 3. Tray Logic
        def on_quit(icon, item):
            self.unblock_all()
            icon.stop()
            print("\n[i] Stopped via Tray.")
            # We don't exit the app, we just return to menu (or exit completely if preferred)
            os._exit(0) 

        image = self.create_icon_image("red")
        menu = (Item('Stop Blocking & Exit', on_quit),)
        
        self.tray_icon = TrayIcon("GhostBlocker", image, f"Blocking: {profile_name}", menu)
        
        # Hide Console (Optional - simple way is usually via file extension .pyw, 
        # but here we just let the tray run blocking the main thread)
        import time
        print("\nAPP IS RUNNING IN TRAY. Check bottom right icons.")
        self.tray_icon.run() 

    def main_menu(self):
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"=== GHOST KEY BLOCKER v1.0 ===")
            print(f"[Kill Switch: {KILL_SWITCH}]")
            print("1. Load Profile & Start Blocking")
            print("2. Create New Profile")
            print("3. Delete Profile")
            print("4. Exit")
            
            choice = input("\nSelection: ").strip()

            if choice == '1':
                profiles = self.load_profiles()
                if not profiles:
                    print("\n[!] No profiles found. Create one first.")
                    time.sleep(2)
                    continue
                
                print("\nAvailable Profiles:")
                p_names = list(profiles.keys())
                for i, name in enumerate(p_names):
                    print(f"{i+1}. {name} ({len(profiles[name])} keys)")
                
                sel = input("\nSelect Profile # to Load: ")
                try:
                    idx = int(sel) - 1
                    if 0 <= idx < len(p_names):
                        target = p_names[idx]
                        self.run_profile_mode(target, profiles[target])
                        break # Exit loop as tray takes over
                except ValueError:
                    pass

            elif choice == '2':
                self.create_new_profile()
                time.sleep(2)

            elif choice == '3':
                profiles = self.load_profiles()
                if not profiles:
                    print("\n[!] No profiles to delete.")
                    time.sleep(2)
                    continue
                
                print("\nAvailable Profiles:")
                p_names = list(profiles.keys())
                for i, name in enumerate(p_names):
                    print(f"{i+1}. {name}")
                
                sel = input("\nSelect Profile # to DELETE: ")
                try:
                    idx = int(sel) - 1
                    if 0 <= idx < len(p_names):
                        del profiles[p_names[idx]]
                        self.save_profiles(profiles)
                        print("[Deleted]")
                        time.sleep(1)
                except ValueError:
                    pass

            elif choice == '4':
                print("Exiting...")
                sys.exit()

if __name__ == "__main__":
    app = GhostKeyBlocker()
    app.main_menu()