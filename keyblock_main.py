import keyboard
import json
import sys
import os
import time
import ctypes
import threading
from pystray import Icon as TrayIcon, MenuItem as Item
from PIL import Image, ImageDraw

# --- CONFIGURATION ---
PROFILE_FILE = "profiles.json"
SAFE_KEYS = ['esc', 'ctrl', 'shift', 'alt', 'caps lock', 'win', 'delete', 'backspace']
KILL_SWITCH = 'ctrl+alt+c'

class GhostKeyBlocker:
    def __init__(self):
        self.ensure_admin()
        self.active_profile = None
        self.blocked_keys = set()
        self.is_running = True
        self.tray_icon = None

    def ensure_admin(self):
        try:
            is_admin = os.getuid() == 0
        except AttributeError:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0

        if not is_admin:
            print("[!] Requesting Administrator Privileges...")
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            sys.exit()

    def hide_console(self):
        print("\n[i] Hiding terminal in 3 seconds... (Check System Tray)")
        time.sleep(3)
        
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
                data = json.load(f)
                clean_data = {}
                for name, content in data.items():
                    if isinstance(content, list):
                        clean_data[name] = {"blocked": content, "remapped": {}}
                    else:
                        clean_data[name] = content
                return clean_data
        except:
            return {}

    def save_profiles(self, profiles):
        with open(PROFILE_FILE, 'w') as f:
            json.dump(profiles, f, indent=4)

    def create_icon_image(self, color="blue"):
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), (255, 255, 255))
        dc = ImageDraw.Draw(image)
        dc.rectangle((0, 0, width, height), fill=color)
        dc.rectangle((16, 16, 48, 48), fill="white")
        return image

    def kill_app(self):
        print("\n[!!!] KILL SWITCH ACTIVATED. Unblocking all keys and exiting.")
        self.unblock_all()
        if self.tray_icon:
            self.tray_icon.stop()
        os._exit(0)

    def unblock_all(self):
        try:
            keyboard.unhook_all()
        except:
            pass
        self.blocked_keys.clear()

    # --- FIXED LOGIC HERE ---
    def create_new_profile(self):
        print("\n" + "="*50)
        print(" NEW PROFILE CREATION (Fixed)")
        print("="*50)
        print("INSTRUCTIONS:")
        print("1. Wait for the 'Ghost Key' to press itself.")
        print("2. The script will BLOCK it immediately.")
        print("3. You will be asked Y/N to remap it (Instant, No Enter needed).")
        print("4. Press 'ESC' at any time to FINISH.")
        print("-" * 50)

        temp_blocked = set()
        temp_remapped = {}

        while True:
            print("\n[Waiting for Ghost Key...] (Press ESC to Finish)")
            
            # Step 1: Wait for a key press event
            event = keyboard.read_event(suppress=True)
            
            # Only care about key DOWN events
            if event.event_type != 'down':
                continue
            
            key = event.name
            
            if key == 'esc':
                break

            if key in SAFE_KEYS and key != 'enter':
                print(f"[!] '{key}' is a SAFE KEY. Cannot block.")
                continue

            if key in temp_blocked:
                # If key is already blocked, we ignore it to prevent spam
                continue

            # Step 2: Block it instantly
            try:
                keyboard.block_key(key)
                temp_blocked.add(key)
                print(f"[+] BLOCKED: '{key}'")
            except Exception as e:
                print(f"[!] Error blocking {key}: {e}")
                continue

            # Step 3: Instant Y/N Prompt (No input() buffer!)
            print(f"   -> Do you want to remap '{key}'? (Press Y or N)")
            
            remap_choice = None
            
            # Mini-loop to wait specifically for Y, N, or ESC
            while True:
                decide_event = keyboard.read_event(suppress=True)
                if decide_event.event_type == 'down':
                    if decide_event.name == 'y':
                        remap_choice = 'y'
                        break
                    elif decide_event.name == 'n':
                        remap_choice = 'n'
                        break
                    elif decide_event.name == 'esc':
                        # Treat ESC here as "No, I'm done"
                        remap_choice = 'done' 
                        break
            
            if remap_choice == 'done':
                break

            if remap_choice == 'y':
                print(f"   -> Press the NEW key you want to act as '{key}':")
                
                # Wait for the replacement key
                while True:
                    src_event = keyboard.read_event(suppress=True)
                    if src_event.event_type == 'down':
                        new_src = src_event.name
                        
                        if new_src == 'esc':
                            print("   [!] Cancelled remap.")
                            break

                        temp_remapped[new_src] = key
                        print(f"   [OK] Remapped! Pressing [{new_src}] will now type [{key}]")
                        break
            else:
                print("   -> OK, key blocked only.")
            
            # Brief pause to let you lift your finger before loop restarts
            time.sleep(0.3)

        # --- SAVE SECTION ---
        # Unblock everything so user can type the name
        self.unblock_all()

        if not temp_blocked and not temp_remapped:
            print("\n[!] No keys detected. Cancelled.")
            return

        print(f"\n[SUMMARY]")
        print(f"Blocked: {list(temp_blocked)}")
        print(f"Remapped: {temp_remapped}")
        
        name = input("\nEnter Profile Name to Save: ").strip()
        
        if name:
            profiles = self.load_profiles()
            profiles[name] = {
                "blocked": list(temp_blocked),
                "remapped": temp_remapped
            }
            self.save_profiles(profiles)
            print(f"[Success] Profile '{name}' saved!")
        else:
            print("[!] No name entered. Discarded.")

    def run_profile_mode(self, profile_name, profile_data):
        print(f"\n[!!!] ACTIVATING PROFILE: {profile_name}")
        
        keys_to_block = profile_data.get("blocked", [])
        keys_to_remap = profile_data.get("remapped", {})

        print(f"[i] Blocking: {len(keys_to_block)} keys")
        print(f"[i] Remapping: {len(keys_to_remap)} keys")
        print(f"[i] Press {KILL_SWITCH} to emergency stop.")
        
        # 1. Apply Blocks
        self.unblock_all()
        for k in keys_to_block:
            try:
                keyboard.block_key(k)
                self.blocked_keys.add(k)
            except Exception as e:
                print(f"Failed block {k}: {e}")

        # 2. Apply Remaps
        for src, dst in keys_to_remap.items():
            try:
                keyboard.remap_key(src, dst)
                print(f"   -> Remapped [{src}] -> [{dst}]")
            except Exception as e:
                print(f"Failed remap {src}->{dst}: {e}")

        # 3. Register Kill Switch
        keyboard.add_hotkey(KILL_SWITCH, self.kill_app)
        
        self.hide_console()

        # 4. Tray Logic
        def on_quit(icon, item):
            self.unblock_all()
            icon.stop()
            print("\n[i] Stopped via Tray.")
            os._exit(0) 

        image = self.create_icon_image("red")
        menu = (Item('Stop Blocking & Exit', on_quit),)
        self.tray_icon = TrayIcon("GhostBlocker", image, f"Active: {profile_name}", menu)
        print("\nAPP IS RUNNING IN TRAY.")
        self.tray_icon.run() 

    def toggle_startup(self):
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "GhostKeyBlocker"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            try:
                winreg.QueryValueEx(key, app_name)
                winreg.DeleteValue(key, app_name)
                print("\n[-] Removed from Windows Startup.")
            except FileNotFoundError:
                if getattr(sys, 'frozen', False):
                    path_to_run = f'"{sys.executable}"'
                else:
                    path_to_run = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, path_to_run)
                print("\n[+] Added to Windows Startup!")
            winreg.CloseKey(key)
        except Exception as e:
            print(f"\n[!] Error toggling startup: {e}")

    def main_menu(self):
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"=== GHOST KEY BLOCKER v2.1 ===")
            print(f"[Kill Switch: {KILL_SWITCH}]")
            print("1. Load Profile")
            print("2. Create New Profile")
            print("3. Delete Profile")
            print("4. Toggle Auto-Start")
            print("5. Exit")
            
            choice = input("\nSelection: ").strip()

            if choice == '1':
                profiles = self.load_profiles()
                if not profiles:
                    print("\n[!] No profiles found.")
                    time.sleep(2)
                    continue
                
                print("\nAvailable Profiles:")
                p_names = list(profiles.keys())
                for i, name in enumerate(p_names):
                    p_data = profiles[name]
                    if isinstance(p_data, list):
                        b_count = len(p_data)
                        r_count = 0
                    else:
                        b_count = len(p_data.get("blocked", []))
                        r_count = len(p_data.get("remapped", {}))
                    print(f"{i+1}. {name} [Blocked: {b_count} | Remapped: {r_count}]")
                
                sel = input("\nSelect Profile #: ")
                try:
                    idx = int(sel) - 1
                    if 0 <= idx < len(p_names):
                        target = p_names[idx]
                        p_data = profiles[target]
                        if isinstance(p_data, list):
                            p_data = {"blocked": p_data, "remapped": {}}
                        self.run_profile_mode(target, p_data)
                        break
                except ValueError: pass

            elif choice == '2':
                self.create_new_profile()
                time.sleep(2)

            elif choice == '3':
                profiles = self.load_profiles()
                if not profiles:
                    print("\n[!] No profiles.")
                    time.sleep(2)
                    continue
                p_names = list(profiles.keys())
                for i, name in enumerate(p_names): print(f"{i+1}. {name}")
                sel = input("\nDelete #: ")
                try:
                    idx = int(sel) - 1
                    if 0 <= idx < len(p_names):
                        del profiles[p_names[idx]]
                        self.save_profiles(profiles)
                        print("[Deleted]")
                        time.sleep(1)
                except: pass

            elif choice == '4':
                self.toggle_startup()
                time.sleep(2)
            
            elif choice == '5':
                sys.exit()

if __name__ == "__main__":
    app = GhostKeyBlocker()
    app.main_menu()