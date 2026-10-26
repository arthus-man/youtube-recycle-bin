import json
import urllib.request
import urllib.error
import threading
import webbrowser
import time
from datetime import datetime, timedelta

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.image import AsyncImage
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.progressbar import ProgressBar
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.window import Window

INNERTUBE_URL = "https://www.youtube.com/youtubei/v1/search"
INNERTUBE_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_VIEWS = 50
TURBO_LIMIT = 300

SORT_PARAMS = {
    "relevance": "EgIQAQ%3D%3D",
}

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
    parts = [f'"{query}"']
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
        parsed.append({
            "id": vid, "title": title, "views": views, 
            "duration": duration, "author": author, "pub_date": pub_date
        })
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
    if video["views"] is None: return True
    return video["views"] < MAX_VIEWS

def is_zero(video):
    return video["views"] is None or video["views"] == 0

class VideoRow(BoxLayout):
    def __init__(self, video, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(110), **kwargs)
        self.video = video
        self.padding = dp(4)
        self.spacing = dp(6)

        img = AsyncImage(
            source=f"https://i.ytimg.com/vi/{video['id']}/hqdefault.jpg",
            size_hint=(None, 1), width=dp(120),
            allow_stretch=True, keep_ratio=True,
        )
        self.add_widget(img)

        text_box = BoxLayout(orientation="vertical", size_hint_x=1)
        
        pub_text = video.get("pub_date") or "—"
        date_lbl = Label(
            text=f"[color=777777]{pub_text}[/color]", markup=True,
            halign="left", valign="top", size_hint_y=0.2, font_size=dp(11)
        )
        date_lbl.bind(size=lambda l, *_: setattr(l, "text_size", (l.width, None)))
        
        title = video["title"] or "(no title)"
        title_lbl = Label(
            text=f"[color=0645AD][u]{title}[/u][/color]", markup=True,
            halign="left", valign="top", size_hint_y=0.5, font_size=dp(13)
        )
        title_lbl.bind(size=lambda l, *_: setattr(l, "text_size", (l.width, None)))

        def open_video(instance, touch):
            if instance.collide_point(*touch.pos):
                webbrowser.open(f"https://youtube.com/watch?v={video['id']}")
                return True
            return False

        title_lbl.bind(on_touch_down=open_video)

        views_str = "None" if video["views"] is None else str(video["views"])
        color = "008000" if video["views"] == 0 else "555555"
        dur = video.get("duration") or "—"
        author = video.get("author") or "—"

        meta_text = (
            f"[color={color}]views: {views_str}[/color]  "
            f"[color=777777]•  {dur}[/color]  "
            f"[color=885522]•  {author}[/color]"
        )

        meta_lbl = Label(
            text=meta_text, markup=True,
            halign="left", valign="bottom", size_hint_y=0.3, font_size=dp(11)
        )
        meta_lbl.bind(size=lambda l, *_: setattr(l, "text_size", (l.width, None)))

        text_box.add_widget(date_lbl)
        text_box.add_widget(title_lbl)
        text_box.add_widget(meta_lbl)
        self.add_widget(text_box)

class VideoApp(App):
    def build(self):
        Window.clearcolor = (1, 1, 1, 1)
        root = BoxLayout(orientation="vertical", padding=dp(6), spacing=dp(6))

        form = GridLayout(cols=2, size_hint_y=None, height=dp(210), spacing=dp(4))
        
        form.add_widget(Label(text="Query (in quotes):", size_hint_x=0.4))
        self.query_input = TextInput(multiline=False, hint_text="e.g. bandicam 2013")
        self.query_input.bind(text=self.check_changes)
        form.add_widget(self.query_input)

        form.add_widget(Label(text="Extra word:", size_hint_x=0.4))
        self.extra_input = TextInput(multiline=False, hint_text="e.g. skype")
        self.extra_input.bind(text=self.check_changes)
        form.add_widget(self.extra_input)

        form.add_widget(Label(text="Date:", size_hint_x=0.4))
        self.date_input = TextInput(multiline=False, hint_text="2012 | 201209 | 20120901 | 2012 2014")
        self.date_input.bind(text=self.check_changes)
        form.add_widget(self.date_input)

        form.add_widget(Label(text="Sort by:", size_hint_x=0.4))
        self.sort_spinner = Spinner(
            text='Relevance', values=('Relevance', 'Duration (desc)'), size_hint_x=0.6,
        )
        self.sort_spinner.bind(text=self.check_changes)
        form.add_widget(self.sort_spinner)

        root.add_widget(form)

        self.status = Label(text="Ready.", size_hint_y=None, height=dp(20), color=(0.2, 0.2, 0.2, 1), font_size=dp(12))
        root.add_widget(self.status)
        
        self.progress = ProgressBar(max=100, value=0, size_hint_y=None, height=dp(10))
        root.add_widget(self.progress)

        self.search_btn = Button(text="Turbo Search (300 items)", size_hint_y=None, height=dp(48), on_release=self.on_search)
        root.add_widget(self.search_btn)

        self.scroll = ScrollView()
        self.list_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(2))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        self.scroll.add_widget(self.list_box)
        root.add_widget(self.scroll)

        self.last_query = None
        self.current_sort_mode = 'relevance'
        self.continuation_token = None
        self.seen_ids = set()
        self.pages_loaded = 0
        self.token_history = []
        self.empty_streak = 0
        self.discarded = 0
        self.all_videos = []
        self.total_checked = 0
        self.is_searching = False
        self.last_search_params = None
        self.current_search_word = ""
        return root

    def get_current_params(self):
        return f"{self.query_input.text.strip()}|{self.extra_input.text.strip()}|{self.date_input.text.strip()}|{self.sort_spinner.text}"

    def check_changes(self, *args):
        if self.is_searching or self.last_search_params is None: return
        current = self.get_current_params()
        if current != self.last_search_params:
            if self.search_btn.disabled:
                self.search_btn.disabled = False
                self.search_btn.text = "Turbo Search (300 items)"
                self.status.text = "Parameters changed. Ready for new search."
        else:
            if not self.search_btn.disabled:
                self.search_btn.disabled = True
                self.search_btn.text = "Search Completed"
                self.status.text = "This query has already been executed."

    def _build_query(self):
        query = self.query_input.text.strip()
        extra = self.extra_input.text.strip()
        dates_raw = self.date_input.text.strip()

        if not query:
            self._popup("Please enter a query.")
            return None

        date_from = date_to = None
        if dates_raw:
            parts = dates_raw.split()
            if len(parts) == 1:
                parsed = parse_date_token(parts[0])
                if not parsed:
                    self._popup("Invalid date format.")
                    return None
                date_from, date_to = parsed
            elif len(parts) == 2:
                p1 = parse_date_token(parts[0])
                p2 = parse_date_token(parts[1])
                if not p1 or not p2:
                    self._popup("Invalid date format.")
                    return None
                date_from = p1[0]
                date_to = p2[1]
                if date_from > date_to:
                    date_from, date_to = date_to, date_from
            else:
                self._popup("Too many date arguments.")
                return None

        return build_query(query, extra, date_from, date_to)

    def _popup(self, text):
        Popup(title="Error", content=Label(text=text), size_hint=(0.8, 0.3)).open()

    def on_search(self, *args):
        if self.is_searching: return
            
        full_query = self._build_query()
        if not full_query: return

        self.current_search_word = self.query_input.text.strip().lower()

        if self.sort_spinner.text == 'Duration (desc)':
            self.current_sort_mode = 'duration'
        else:
            self.current_sort_mode = 'relevance'

        self.last_search_params = self.get_current_params()

        self.status.text = f"Searching: {full_query}"
        self.progress.value = 0
        self.search_btn.disabled = True
        self.search_btn.text = "Searching..."
        self.list_box.clear_widgets()
        self.seen_ids.clear()
        self.all_videos = []
        self.last_query = full_query
        self.continuation_token = None
        self.pages_loaded = 0
        self.token_history = []
        self.empty_streak = 0
        self.discarded = 0
        self.total_checked = 0
        self.is_searching = True
        
        threading.Thread(target=self._worker_search, args=(full_query, 'relevance'), daemon=True).start()

    def _worker_search(self, query, sort_key):
        videos, token = innertube_search(query, sort_key=sort_key, max_results=30)
        Clock.schedule_once(lambda dt: self._render(videos, token, True, 1), 0)

    def _worker_continue(self, token, target_page):
        time.sleep(0.5)
        videos, next_token = innertube_continue(token, max_results=30)
        fresh = [v for v in videos if v["id"] not in self.seen_ids]

        if fresh:
            self.empty_streak = 0
            Clock.schedule_once(lambda dt: self._render(fresh, next_token, False, target_page), 0)
        else:
            self.empty_streak += 1
            if self.empty_streak < 2:
                recovered = self._recover_token(target_page)
                if recovered:
                    rec_videos, rec_token = recovered
                    rec_fresh = [v for v in rec_videos if v["id"] not in self.seen_ids]
                    if rec_fresh:
                        self.empty_streak = 0
                        Clock.schedule_once(lambda dt: self._render(rec_fresh, rec_token, False, target_page), 0)
                        return
                self.empty_streak += 1
            Clock.schedule_once(lambda dt: self._render([], None, False, target_page), 0)

    def _recover_token(self, target_page):
        last_token = None
        for page_idx, tok in reversed(self.token_history):
            if page_idx == target_page - 1:
                last_token = tok
                break
        if not last_token: return None

        time.sleep(0.5)
        videos, fresh_token = innertube_continue(last_token, max_results=30)
        if not videos: return None

        self.token_history.append((target_page, fresh_token))
        return videos, fresh_token

    def _render(self, videos, next_token, is_new, page_index):
        if is_new:
            self.total_checked = len(videos)
        else:
            self.total_checked += len(videos)

        if is_new:
            self.list_box.clear_widgets()
            self.seen_ids.clear()
            self.all_videos = []
            self.pages_loaded = 1
        else:
            self.pages_loaded = max(self.pages_loaded, page_index)

        unique = [v for v in videos if v["id"] not in self.seen_ids]

        recyclable = []
        for v in unique:
            if not is_recyclable(v):
                self.discarded += 1
                continue
            if self.current_search_word:
                if self.current_search_word not in v["title"].lower():
                    self.discarded += 1
                    continue
            recyclable.append(v)

        for v in recyclable:
            self.seen_ids.add(v["id"])
            self.all_videos.append(v)

        if next_token:
            self.token_history.append((page_index, next_token))

        if self.current_sort_mode == 'duration':
            sorted_videos = sorted(self.all_videos, key=lambda v: (0 if is_zero(v) else 1, -duration_to_seconds(v.get("duration"))))
        else:
            sorted_videos = sorted(self.all_videos, key=lambda v: (0 if is_zero(v) else 1, v["views"] if v["views"] is not None else -1))

        self.list_box.clear_widgets()
        for v in sorted_videos:
            self.list_box.add_widget(VideoRow(v))

        zero_count = sum(1 for v in self.all_videos if is_zero(v))
        self.status.text = f"Checked: {self.total_checked}/{TURBO_LIMIT}. Found: {len(self.all_videos)} (0 views: {zero_count})."
        self.progress.value = min(100, (self.total_checked / TURBO_LIMIT) * 100)

        self.continuation_token = next_token

        if self.total_checked < TURBO_LIMIT and next_token:
            target_page = self.pages_loaded + 1
            threading.Thread(target=self._worker_continue, args=(next_token, target_page), daemon=True).start()
        else:
            if self.total_checked >= TURBO_LIMIT:
                self.status.text += " (Limit reached)"
            else:
                self.status.text += " (End of results)"
            
            self.search_btn.text = "Search Completed"
            self.search_btn.disabled = True
            self.is_searching = False

if __name__ == "__main__":
    VideoApp().run()