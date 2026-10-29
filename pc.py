import json
import urllib.request
import urllib.error
import threading
import webbrowser
import time
import io
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from PIL import Image, ImageTk
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

INNERTUBE_URL = "https://www.youtube.com/youtubei/v1/search"
INNERTUBE_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_VIEWS = 50
TURBO_LIMIT = 500
SORT_PARAMS = {"relevance": "EgIQAQ%3D%3D"}

# ---------- Date logic ----------
def parse_date_token(s):
    s = s.strip()
    if not s.isdigit(): return None
    if len(s) == 4:
        year = int(s)
        if year < 2005 or year > 2100: return None
        return f"{year:04d}-01-01", f"{year + 1:04d}-01-01"
    if len(s) == 6:
        year, month = int(s[0:4]), int(s[4:6])
        if year < 2005 or year > 2100 or month < 1 or month > 12: return None
        start = f"{year:04d}-{month:02d}-01"
        end = f"{year + 1:04d}-01-01" if month == 12 else f"{year:04d}-{month + 1:02d}-01"
        return start, end
    if len(s) == 8:
        start = f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
        try: datetime.strptime(start, "%Y-%m-%d")
        except ValueError: return None
        end = (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        return start, end
    return None

def build_query(query, extra_query, date_from, date_to):
    parts = []
    if query: parts.append(f'"{query}"')
    if extra_query: parts.append(extra_query)
    if date_from and date_to:
        parts.append(f"after:{date_from}")
        parts.append(f"before:{date_to}")
    elif date_from:
        parts.append(f"after:{date_from}")
    return " ".join(parts)

def duration_to_seconds(dur_str):
    if not dur_str: return 0
    try:
        parts = dur_str.split(":")
        parts = [int(p) for p in parts]
        if len(parts) == 2: return parts[0] * 60 + parts[1]
        elif len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
    except Exception: pass
    return 0

# ---------- InnerTube ----------
def _parse_response(raw, max_results):
    results, continuations = [], []
    def walk(node):
        if isinstance(node, dict):
            if "videoRenderer" in node: results.append(node["videoRenderer"])
            if "continuationCommand" in node:
                tok = node["continuationCommand"].get("token")
                if tok: continuations.append(tok)
            for v in node.values(): walk(v)
        elif isinstance(node, list):
            for v in node: walk(v)
    walk(raw)

    parsed = []
    for r in results[:max_results]:
        vid = r.get("videoId")
        title = r.get("title", {}).get("runs", [{}])[0].get("text", "")
        vt = r.get("viewCountText", {}).get("simpleText", "")
        views = 0 if vt.lower().startswith("no views") else int("".join(ch for ch in vt if ch.isdigit()) or 0)
        duration = r.get("lengthText", {}).get("simpleText", "—")
        author = r.get("ownerText", {}).get("runs", [{}])[0].get("text", "—")
        pub_date = r.get("publishedTimeText", {}).get("simpleText", "—")
        parsed.append({"id": vid, "title": title, "views": views, "duration": duration, "author": author, "pub_date": pub_date})
    return parsed, (continuations[-1] if continuations else None)

def innertube_search(query, sort_key="relevance", max_results=30):
    payload = {
        "context": {"client": {"clientName": "WEB", "clientVersion": "2.20240101.00.00", "hl": "en", "gl": "US"}},
        "query": query, "params": SORT_PARAMS.get(sort_key, "EgIQAQ%3D%3D"),
    }
    url = f"{INNERTUBE_URL}?key={INNERTUBE_KEY}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return _parse_response(json.load(resp), max_results)
    except Exception as e:
        print("Search error:", e)
        return [], None

def innertube_continue(token, max_results=30):
    payload = {
        "context": {"client": {"clientName": "WEB", "clientVersion": "2.20240101.00.00", "hl": "en", "gl": "US"}},
        "continuation": token,
    }
    url = f"{INNERTUBE_URL}?key={INNERTUBE_KEY}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return _parse_response(json.load(resp), max_results)
    except Exception as e:
        print("Continuation error:", e)
        return [], None

def is_recyclable(video):
    return video["views"] is None or video["views"] < MAX_VIEWS

def is_zero(video):
    return video["views"] is None or video["views"] == 0

# ---------- GUI ----------
class App:
    def __init__(self, root):
        self.root = root
        root.title("YouTube Recycle Bin - PC")
        root.geometry("1050x700")

        self.is_searching = False
        self.stop_event = threading.Event()
        self.seen_ids = set()
        self.current_search_word = ""
        self.all_videos = {}
        self.img_queue = []
        self.photos = {}

        frm = ttk.Frame(root, padding=10)
        frm.pack(fill="x")
        
        ttk.Label(frm, text="Query (in quotes):").grid(row=0, column=0, sticky="w")
        self.e_query = ttk.Entry(frm, width=30)
        self.e_query.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(frm, text="Extra query:").grid(row=0, column=2, sticky="w")
        self.e_extra = ttk.Entry(frm, width=20)
        self.e_extra.grid(row=0, column=3, padx=5, pady=2)

        ttk.Label(frm, text="Date:").grid(row=1, column=0, sticky="w")
        self.e_date = ttk.Entry(frm, width=30)
        self.e_date.grid(row=1, column=1, padx=5, pady=2)
        self.add_placeholder(self.e_date, "2012 | 201209 | 20120901 | 2012 2014")

        ttk.Label(frm, text="Sort by:").grid(row=1, column=2, sticky="w")
        self.c_sort = ttk.Combobox(frm, values=["Relevance", "Duration (desc)"], state="readonly")
        self.c_sort.current(0)
        self.c_sort.grid(row=1, column=3, padx=5, pady=2)

        btn_frm = ttk.Frame(root, padding=(10, 0))
        btn_frm.pack(fill="x")
        self.btn_search = ttk.Button(btn_frm, text="Turbo Search", command=self.start_search)
        self.btn_search.pack(side="left")
        
        self.lbl_status = ttk.Label(root, text="Ready.", padding=10)
        self.lbl_status.pack(fill="x")

        self.progress = ttk.Progressbar(root, mode="determinate", maximum=TURBO_LIMIT)
        self.progress.pack(fill="x", padx=10, pady=(0, 10))

        cols = ("views", "date", "duration", "author", "title")
        if HAVE_PIL:
            style = ttk.Style()
            style.configure("Treeview", rowheight=75)
            self.tree = ttk.Treeview(root, columns=cols, show="tree headings", selectmode="browse")
            self.tree.heading("#0", text="Thumbnail")
            self.tree.column("#0", width=130, stretch=False)
        else:
            self.tree = ttk.Treeview(root, columns=cols, show="headings", selectmode="browse")

        self.tree.heading("views", text="Views")
        self.tree.heading("date", text="Date")
        self.tree.heading("duration", text="Duration")
        self.tree.heading("author", text="Author")
        self.tree.heading("title", text="Title (double-click to open)")
        
        self.tree.column("views", width=80, anchor="center")
        self.tree.column("date", width=100, anchor="center")
        self.tree.column("duration", width=60, anchor="center")
        self.tree.column("author", width=150)
        self.tree.column("title", width=450)

        scroll = ttk.Scrollbar(root, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scroll.pack(side="right", fill="y", padx=(0, 10), pady=10)

        self.tree.bind("<Double-1>", self.open_video)
        self.tree.tag_configure("zero", foreground="green")

        if HAVE_PIL:
            self.root.after(100, self.update_images)

    def add_placeholder(self, entry, text):
        entry.insert(0, text)
        entry.config(foreground="grey")
        def on_focus_in(e):
            if entry.get() == text:
                entry.delete(0, "end")
                entry.config(foreground="black")
        def on_focus_out(e):
            if not entry.get():
                entry.insert(0, text)
                entry.config(foreground="grey")
        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

    def start_search(self):
        if self.is_searching: return
        
        query = self.e_query.get().strip()
        extra = self.e_extra.get().strip()
        if not query and not extra:
            messagebox.showwarning("Warning", "Please enter a query or extra query!")
            return

        self.current_search_word = query.lower()
        
        self.tree.delete(*self.tree.get_children())
        self.seen_ids.clear()
        self.all_videos.clear()
        self.photos.clear()
        self.progress["value"] = 0
        self.is_searching = True
        self.stop_event.clear()
        self.btn_search.config(state="disabled")
        self.lbl_status.config(text="Searching...")

        date_raw = self.e_date.get().strip()
        if date_raw == "2012 | 201209 | 20120901 | 2012 2014":
            date_raw = ""

        date_from, date_to = None, None
        if date_raw:
            parts = date_raw.split()
            if len(parts) == 1:
                parsed = parse_date_token(parts[0])
                if parsed: date_from, date_to = parsed
            elif len(parts) == 2:
                p1, p2 = parse_date_token(parts[0]), parse_date_token(parts[1])
                if p1 and p2: date_from, date_to = p1[0], p2[1]

        full_query = build_query(query, extra, date_from, date_to)
        
        threading.Thread(target=self.worker_turbo, args=(full_query,), daemon=True).start()

    def worker_turbo(self, query):
        videos, token = innertube_search(query)
        self.root.after(0, self.process_page, videos, token, 1)

        checked = len(videos)
        
        while checked < TURBO_LIMIT and token and not self.stop_event.is_set():
            time.sleep(0.5)
            videos, token = innertube_continue(token)
            
            if not videos and not token:
                time.sleep(1.0)
                videos, token = innertube_continue(token)
                if not videos:
                    break
            
            checked += len(videos)
            self.root.after(0, self.process_page, videos, token, 0)
        
        self.root.after(0, self.finish_search)

    def process_page(self, videos, token, page):
        self.progress["value"] = min(len(self.seen_ids), TURBO_LIMIT)
        added_new = False
        
        for v in videos:
            if v["id"] in self.seen_ids: continue
            self.seen_ids.add(v["id"])
            
            if not is_recyclable(v): continue

            if self.current_search_word:
                if self.current_search_word not in v["title"].lower():
                    continue

            self.all_videos[v["id"]] = v
            added_new = True
            
            if HAVE_PIL:
                threading.Thread(target=self.load_thumb, args=(v["id"],), daemon=True).start()
        
        if added_new:
            self.rebuild_table()
        
        self.lbl_status.config(text=f"Checked: {len(self.seen_ids)}/{TURBO_LIMIT}. Found: {len(self.all_videos)}")

    def rebuild_table(self):
        sort_mode = self.c_sort.get()
        
        if sort_mode == "Duration (desc)":
            sorted_videos = sorted(
                self.all_videos.values(), 
                key=lambda v: (0 if v["views"] == 0 else 1, -duration_to_seconds(v["duration"]))
            )
        else:
            sorted_videos = sorted(
                self.all_videos.values(), 
                key=lambda v: (0 if v["views"] == 0 else 1, v["views"])
            )
        
        self.tree.delete(*self.tree.get_children())
        
        for v in sorted_videos:
            tag = ("zero",) if v["views"] == 0 else ()
            photo = self.photos.get(v["id"], "")
            self.tree.insert("", "end", values=(
                v["views"], v["pub_date"], v["duration"], v["author"], v["title"]
            ), iid=v["id"], tags=tag, image=photo)

    def load_thumb(self, vid):
        try:
            url = f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"
            req = urllib.request.Request(url, headers={"User-Agent": HEADERS["User-Agent"]})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
            img = Image.open(io.BytesIO(data)).convert("RGB")
            img = img.resize((120, 68), Image.LANCZOS)
            self.img_queue.append((vid, img))
        except Exception:
            pass

    def update_images(self):
        while self.img_queue:
            vid, img = self.img_queue.pop(0)
            if self.tree.exists(vid):
                photo = ImageTk.PhotoImage(img)
                self.photos[vid] = photo
                self.tree.item(vid, image=photo)
        
        self.root.after(100, self.update_images)

    def finish_search(self):
        self.is_searching = False
        self.btn_search.config(state="normal")
        self.lbl_status.config(text=f"Completed. Checked: {len(self.seen_ids)}. Found: {len(self.all_videos)}.")

    def open_video(self, event):
        sel = self.tree.focus()
        if sel:
            webbrowser.open(f"https://www.youtube.com/watch?v={sel}")

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()