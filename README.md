# Toneii - DnD Edition (Real-time Soundboard)

ยินดีต้อนรับสู่ Toneii โปรเจกต์ Soundboard สำหรับเกม Tabletop RPG (D&D) ที่สามารถซิงค์เสียงผ่าน WebSockets ให้ผู้เล่นทุกคนได้ยินพร้อมกัน!

## 📦 การติดตั้งและการรันใช้งานเบื้องต้น (เล่นในวง LAN หรือเครื่องตัวเอง)
1. เปิด Terminal / Command Prompt ในโฟลเดอร์นี้
2. ติดตั้งไลบรารี: `pip install -r requirements.txt`
3. รันเซิร์ฟเวอร์: `uvicorn main:app --reload`
4. เปิดเบราว์เซอร์:
   - **สำหรับ DM (คุณ):** `http://localhost:8000/static/host.html`
   - **สำหรับ Player:** `http://localhost:8000/static/guest.html`

---

## 🌍 คู่มือการเปิดให้เพื่อนใน Discord เข้ามาเล่นด้วย (Online Play)
1. เปิด Command Prompt ตัวใหม่ เข้าไปที่โฟลเดอร์ที่เก็บ `ngrok.exe` แล้วพิมพ์คำสั่ง:
   `ngrok http 8000`
2. ส่งลิงก์ Forwarding ที่ได้ให้เพื่อน! (เช่น `https://xxx.ngrok-free.app/static/guest.html`)
