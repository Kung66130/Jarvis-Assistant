import os
import time
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_html_template(title: str, content: str, badge: str, theme_color: str) -> str:
    # Map theme_color to tailwind/modern CSS styling configurations
    theme_map = {
        "cyan": {
            "border": "from-sky-400 to-blue-600",
            "badge_bg": "bg-sky-500/10",
            "badge_border": "border-sky-500/30",
            "badge_text": "text-sky-400",
            "bullet": "text-sky-400",
            "glow": "rgba(56, 189, 248, 0.15)"
        },
        "green": {
            "border": "from-emerald-400 to-teal-600",
            "badge_bg": "bg-emerald-500/10",
            "badge_border": "border-emerald-500/30",
            "badge_text": "text-emerald-400",
            "bullet": "text-emerald-400",
            "glow": "rgba(52, 211, 153, 0.15)"
        },
        "violet": {
            "border": "from-purple-400 to-indigo-600",
            "badge_bg": "bg-purple-500/10",
            "badge_border": "border-purple-500/30",
            "badge_text": "text-purple-400",
            "bullet": "text-purple-400",
            "glow": "rgba(167, 139, 250, 0.15)"
        },
        "gold": {
            "border": "from-amber-400 to-orange-600",
            "badge_bg": "bg-amber-500/10",
            "badge_border": "border-amber-500/30",
            "badge_text": "text-amber-400",
            "bullet": "text-amber-400",
            "glow": "rgba(251, 191, 36, 0.15)"
        }
    }
    
    theme = theme_map.get(theme_color.lower(), theme_map["cyan"])
    
    # Process text content to HTML list items with bullet points formatting
    lines = content.split('\n')
    content_html = ""
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            content_html += "<div class='h-2'></div>"
            continue
            
        # Format bullet list items
        if line_strip.startswith('•') or line_strip.startswith('-'):
            cleaned = line_strip.lstrip('•-').strip()
            content_html += f'<li class="flex items-start gap-3 my-2.5 text-slate-200 text-lg leading-relaxed"><span class="{theme["badge_text"]} font-bold select-none text-xl leading-none">•</span><span>{cleaned}</span></li>'
        else:
            content_html += f'<p class="text-slate-300 text-lg my-2.5 leading-relaxed pl-1">{line_strip}</p>'
            
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700&display=swap');
            body {{
                font-family: 'Prompt', sans-serif;
                background-color: #030712;
                margin: 0;
                overflow: hidden;
            }}
        </style>
    </head>
    <body class="w-[1200px] h-[800px] flex items-center justify-center p-[60px] relative select-none">
        <!-- Deep Space Cyber Gradient Background -->
        <div class="absolute inset-0 bg-gradient-to-br from-slate-950 via-gray-950 to-neutral-950"></div>
        <div class="absolute top-[-100px] right-[-100px] w-[550px] h-[550px] rounded-full blur-[130px] pointer-events-none opacity-25" style="background: {theme["glow"]};"></div>
        
        <!-- Premium Glassmorphic Frosted Card Outer Frame -->
        <div class="relative w-full h-full bg-slate-900/50 backdrop-blur-2xl border border-white/10 rounded-[32px] shadow-[0_30px_70px_-15px_rgba(0,0,0,0.9)] overflow-hidden flex flex-col justify-between p-12">
            <!-- Neon Accent Top Edge Highlight -->
            <div class="absolute top-0 inset-x-12 h-[3px] bg-gradient-to-r {theme["border"]} rounded-b-full"></div>
            
            <div class="flex flex-col gap-6">
                <!-- Header Badge -->
                <div class="inline-flex self-start px-4.5 py-1.5 rounded-lg border {theme["badge_border"]} {theme["badge_bg"]} {theme["badge_text"]} text-xs font-bold tracking-widest uppercase shadow-[0_2px_10px_rgba(0,0,0,0.2)]">
                    {badge}
                </div>
                
                <!-- Title -->
                <h1 class="text-4xl font-bold text-white tracking-tight leading-tight mt-1">
                    {title}
                </h1>
                
                <!-- Styled Subtle Divider -->
                <div class="w-full h-[1px] bg-gradient-to-r from-white/10 via-white/5 to-transparent"></div>
                
                <!-- Content Area (Scroll/Flow Safe) -->
                <div class="max-h-[430px] overflow-hidden pr-2">
                    <ul class="flex flex-col">
                        {content_html}
                    </ul>
                </div>
            </div>
            
            <!-- Spaced Cyberpunk Footer -->
            <div class="flex justify-between items-center text-[10px] font-bold text-white/20 tracking-[0.25em] border-t border-white/5 pt-6 mt-4">
                <span>JARVIS INTELLECTUAL COGNITION SYSTEM • COMPLETED SUCCESSFULLY</span>
                <span class="opacity-60">v3.0_PLAYWRIGHT</span>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def render_report_card(
    title: str,
    content: str,
    output_path: str = "report_card.png",
    badge: str = "📢 JARVIS REPORT",
    theme_color: str = "cyan"
) -> str:
    """Renders a stunning modern glassmorphic card using HTML/CSS and Playwright."""
    html_content = get_html_template(title, content, badge, theme_color)
    
    # Save the rendered HTML in standard temp folder or workspace absolute path
    temp_html_path = os.path.join(BASE_DIR, "scratch", "temp_report.html")
    os.makedirs(os.path.dirname(temp_html_path), exist_ok=True)
    
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # Create page with exact matching high-resolution 1.5x retina-like scale viewport
        page = browser.new_page(viewport={"width": 1200, "height": 800})
        # Load local HTML file
        page.goto(f"file:///{temp_html_path.replace(chr(92), '/')}", wait_until="networkidle")
        time.sleep(0.5)  # Let external tailwind and google fonts load completely
        
        # Take high-quality snapshot
        page.screenshot(path=output_path, type="png")
        browser.close()
        
    try:
        os.remove(temp_html_path)
    except Exception:
        pass
        
    print(f"[Renderer] Rendered Playwright report card to {output_path}", flush=True)
    return output_path

if __name__ == "__main__":
    test_title = "สรุปประเด็นข่าวด่วนเช้านี้"
    test_content = (
        "• ราคาน้ำมันโลกปรับตัวสูงขึ้นอีก 2% หลังความขัดแย้งในตะวันออกกลางตึงเครียดมากขึ้น\n"
        "• ดัชนีตลาดหุ้นดาวโจนส์ปิดบวก 150 จุด ขานรับตัวเลขค้าปลีกสหรัฐฯ ออกมาดีกว่าคาด\n"
        "• ค่าเงินบาทเช้านี้เปิดแข็งค่าขึ้นเล็กน้อยที่ 36.45 บาทต่อดอลลาร์สหรัฐ\n"
        "• ธปท. ส่งสัญญาณคงอัตราดอกเบี้ยนโยบายที่ 2.50% ต่อไปเนื่องจากกังวลเงินเฟ้อระยะยาว\n"
        "• นักลงทุนต่างชาติซื้อสุทธิตลาดพันธบัตรไทยกว่า 2,400 ล้านบาทในวันทำการล่าสุด"
    )
    render_report_card(test_title, test_content, os.path.join(BASE_DIR, "test_report_card.png"), badge="📢 MORNING BRIEF", theme_color="violet")
