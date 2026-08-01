import os
import subprocess
import sys

def setup_and_run():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root_dir)

    print("\n=======================================================")
    print(" 🛡️ PRIVACY-FIRST LIVE WHATSAPP TEST LAUNCHER")
    print("=======================================================\n")

    # Install whatsapp-web.js and qrcode-terminal locally if missing
    if not os.path.exists(os.path.join(root_dir, "node_modules", "whatsapp-web.js")):
        print(" Installing temporary WhatsApp Web helper packages (whatsapp-web.js, qrcode-terminal)...")
        subprocess.run(["npm", "install", "whatsapp-web.js", "qrcode-terminal", "--no-save"], shell=True)

    print("\n Launching Live Test Engine...")
    print(" Press ENTER at any time during the test to LOGOUT & ERASE ALL SESSION DATA.\n")

    js_file = os.path.join(root_dir, "code", "live_whatsapp_test.js")
    subprocess.run(["node", js_file], shell=True)

if __name__ == "__main__":
    setup_and_run()
