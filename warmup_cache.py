import asyncio
import os
from pro_speak import speak

COMMON_PHRASES = [
    "ระบบจาร์วิสส่วนกลาง พร้อมรับใช้บอสแล้วครับ",
    "รับทราบครับบอส",
    "กำลังประมวลผลครับ",
    "ขออภัยครับบอส สมองส่วนกลางไม่ตอบสนองครับ",
    "พักผ่อนให้เต็มที่นะครับ",
    "สวัสดีครับบอส มีอะไรให้จาร์วิสช่วยไหมครับ",
    "กำลังดำเนินการให้ครับ",
    "เรียบร้อยแล้วครับบอส",
    "ตรวจพบการบุกรุก... ล้อเล่นครับบอส",
    "วันนี้บอสดูดีมากครับ"
]

async def warmup():
    print("Pre-downloading common phrases...")
    for phrase in COMMON_PHRASES:
        print(f"Caching: {phrase}")
        await speak(phrase, only_cache=True)
    print("Done! Common phrases are now cached.")

if __name__ == "__main__":
    # เพื่อไม่ให้เสียงดังรบกวนตอนโหลด เราควรส่งแค่ text ไปเจนเฉยๆ 
    # แต่เนื่องจาก speak ใน pro_speak มันเล่นเสียงทันที 
    # ผมจะแก้ pro_speak ให้ฉลาดขึ้นนิดนึงครับ
    asyncio.run(warmup())
