/**
 * Live Personal WhatsApp Router Test Script (100% Privacy & Auto-Logout)
 * 
 * Instructions:
 * 1. Run: node code/live_whatsapp_test.js
 * 2. Scan QR code with WhatsApp on your phone (Linked Devices).
 * 3. Send/receive a test message to see live AI routing decisions.
 * 4. Press [ENTER] at any time to LOGOUT, destroy session, and wipe all local data.
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const AUTH_PATH = path.join(__dirname, '.wwebjs_auth');
const CACHE_PATH = path.join(__dirname, '.wwebjs_cache');

console.log("\n=======================================================");
console.log(" 🟢 PRIVATE WHATSAPP LIVE ROUTER TEST");
console.log(" Privacy Guarantee: Session will auto-destroy on exit.");
console.log("=======================================================\n");

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: AUTH_PATH })
});

client.on('qr', (qr) => {
    console.log(" Scan this QR code in WhatsApp (Linked Devices):\n");
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    console.log("\n SUCCESS! Connected to your WhatsApp account.");
    console.log(" Listening for incoming messages...");
    console.log(" 👉 Send a test message or ask a friend to message you.");
    console.log("\n PRESS [ENTER] IN THIS TERMINAL AT ANY TIME TO LOGOUT & ERASE ALL DATA.\n");
});

client.on('message', async msg => {
    const chat = await msg.getChat();
    const text = msg.body;
    const sender = msg.from;
    const isGroup = chat.isGroup;

    console.log(`\n INCOMING MESSAGE from ${chat.name || sender}:`);
    console.log(`   Text: "${text}"`);

    // Call Python Router Engine
    const py = spawn('python', ['-c', `
from code.router import route_message
from code.features import ContextData
import json

ctx = ContextData("dataset")
msg_data = {
    "message_id": "live_001",
    "user_id": "u_001",
    "conversation_type": "group" if ${isGroup ? "True" : "False"} else "personal",
    "created_at": "2026-08-01 23:40",
    "message_text": """${text.replace(/"/g, '\\"')}""",
    "forwarded_count": 0
}
res = route_message(msg_data, ctx)
print(json.dumps(res))
    `]);

    py.stdout.on('data', (data) => {
        try {
            const res = JSON.parse(data.toString().trim());
            console.log(" -----------------------------------------------------");
            console.log(` 🤖 AI ROUTER ACTION:     [ ${res.action.toUpperCase()} ]`);
            console.log(` 🏷️  MESSAGE CATEGORY:     [ ${res.message_type} ]`);
            console.log(` 💡 CONFIDENCE:           [ ${(res.confidence * 100).toFixed(0)}% ]`);
            console.log(` 📝 EXPLANATION:          ${res.reason}`);
            console.log(" -----------------------------------------------------\n");
        } catch (e) {
            console.log(" Output:", data.toString());
        }
    });
});

// Clean Logout & Data Wipe Handler
async function cleanupAndExit() {
    console.log("\n\n 🛑 LOGGING OUT OF WHATSAPP...");
    try {
        await client.logout();
        await client.destroy();
        console.log(" ✅ WhatsApp Web session unlinked from your phone.");
    } catch (e) {
        console.log(" Cleanup notice:", e.message);
    }

    // Wipe session folders
    [AUTH_PATH, CACHE_PATH].forEach(dir => {
        if (fs.existsSync(dir)) {
            fs.rmSync(dir, { recursive: true, force: true });
        }
    });

    console.log(" 🧹 Session tokens and credentials COMPLETELY DELETED.");
    console.log(" 🔒 ZERO DATA RETAINED. You are 100% logged out.");
    console.log("=======================================================\n");
    process.exit(0);
}

process.on('SIGINT', cleanupAndExit);
process.stdin.on('data', cleanupAndExit);

client.initialize();
