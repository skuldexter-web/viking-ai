import customtkinter as ctk
import urllib.request
import json
import threading
import platform

# Settings
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5-coder:1.5b-base"

# Theme definitions
THEMES = {
    "viking-ai": {
        "emoji": "⚡", "subtitle": "Skuld of the Great Hall", "ig2": None,
        "bg": "#1a1107", "sidebar": "#26180a", "text": "#e6ccb2", "title": "#d4af37",
        "accent": "#d4af37", "accent_text": "#1a1107", "hover": "#b89728",
        "box": "#140e07", "border": "#3d2817", "entry_bg": "#26180a", "entry_text": "#ffffff", "sub_col": "#e25822"
    },
    "v1ru5-ai": {
        "emoji": "🦠", "subtitle": "V1RU5 Neural Node", "ig2": "Instagram: @V1RU5_0",
        "bg": "#09040d", "sidebar": "#12061c", "text": "#d0a3ff", "title": "#00ff66",
        "accent": "#00ff66", "accent_text": "#09040d", "hover": "#00c853",
        "box": "#0d0414", "border": "#491269", "entry_bg": "#170826", "entry_text": "#ffffff", "sub_col": "#a822e2"
    },
    "cyberpunk-ai": {
        "emoji": "🔮", "subtitle": "Neon Grid Operator", "ig2": None,
        "bg": "#0b0b16", "sidebar": "#15152b", "text": "#00f0ff", "title": "#ff007f",
        "accent": "#ff007f", "accent_text": "#ffffff", "hover": "#cc0066",
        "box": "#101020", "border": "#00f0ff", "entry_bg": "#1a1a38", "entry_text": "#ffffff", "sub_col": "#00f0ff"
    },
    "hacker-ai": {
        "emoji": "💻", "subtitle": "Matrix Terminal", "ig2": None,
        "bg": "#020b02", "sidebar": "#051405", "text": "#00ff00", "title": "#00ff00",
        "accent": "#00ff00", "accent_text": "#020b02", "hover": "#00cc00",
        "box": "#030f03", "border": "#006600", "entry_bg": "#082108", "entry_text": "#00ff00", "sub_col": "#008800"
    },
    "milkyway-ai": {
        "emoji": "🌌", "subtitle": "Cosmic Voyager", "ig2": None,
        "bg": "#070814", "sidebar": "#0e1024", "text": "#c58af9", "title": "#8ab4f8",
        "accent": "#8ab4f8", "accent_text": "#070814", "hover": "#5c8df6",
        "box": "#0a0c1c", "border": "#3b426e", "entry_bg": "#141833", "entry_text": "#ffffff", "sub_col": "#c58af9"
    },
    "anonymous-ai": {
        "emoji": "🎭", "subtitle": "Legion Protocol", "ig2": None,
        "bg": "#0f0f0f", "sidebar": "#161616", "text": "#e0e0e0", "title": "#ff2222",
        "accent": "#ff2222", "accent_text": "#ffffff", "hover": "#cc1b1b",
        "box": "#121212", "border": "#333333", "entry_bg": "#1c1c1c", "entry_text": "#ffffff", "sub_col": "#888888"
    },
    "black and white-ai": {
        "emoji": "🏴", "subtitle": "Monochrome Core", "ig2": None,
        "bg": "#000000", "sidebar": "#0f0f0f", "text": "#ffffff", "title": "#ffffff",
        "accent": "#ffffff", "accent_text": "#000000", "hover": "#cccccc",
        "box": "#050505", "border": "#333333", "entry_bg": "#141414", "entry_text": "#ffffff", "sub_col": "#888888"
    },
    "white and black-ai": {
        "emoji": "🏳️", "subtitle": "Lightroom Interface", "ig2": None,
        "bg": "#f5f5f5", "sidebar": "#ffffff", "text": "#111111", "title": "#000000",
        "accent": "#000000", "accent_text": "#ffffff", "hover": "#333333",
        "box": "#ffffff", "border": "#cccccc", "entry_bg": "#eaeaea", "entry_text": "#000000", "sub_col": "#555555"
    }
}

INSTALL_OPTIONS = {
    "default": ("qwen2.5-coder:1.5b-base", "Light (default)"),
    "1": ("qwen2.5-coder:7b-base", "Medium, ~4.7 GB VRAM"),
    "2": ("qwen2.5-coder:14b-base", "Strong, ~9 GB VRAM"),
    "3": ("qwen2.5-coder:32b-base", "The flagship, ~20 GB VRAM"),
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

class MultiThemeAIApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.current_theme_name = "viking-ai" # Default theme
        theme = THEMES[self.current_theme_name]

        self.title("Multi-Theme AI Terminal v2.0")
        self.geometry("1100x750")
        self.configure(fg_color=theme["bg"])

        self.is_speaking = False

        # Layout grid configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- LEFT FRAME (SIDEBAR) ---
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0, fg_color=theme["sidebar"])
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        self.title_label = ctk.CTkLabel(
            self.sidebar, 
            text=f"{theme['emoji']} {self.current_theme_name.upper()} {theme['emoji']}", 
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme["title"]
        )
        self.title_label.pack(padx=20, pady=(20, 5))

        self.subtitle_label = ctk.CTkLabel(
            self.sidebar, 
            text=theme["subtitle"], 
            font=ctk.CTkFont(size=12, slant="italic"),
            text_color=theme["sub_col"]
        )
        self.subtitle_label.pack(padx=20, pady=(0, 15))

        # Social Media / Links Labels
        self.github_label = ctk.CTkLabel(
            self.sidebar,
            text="GitHub: skuldexter-web",
            font=ctk.CTkFont(size=11),
            text_color=theme["title"]
        )
        self.github_label.pack(padx=20, pady=(2, 0), anchor="w")

        self.insta_label = ctk.CTkLabel(
            self.sidebar,
            text="Instagram: @s.k.7.l.d",
            font=ctk.CTkFont(size=11),
            text_color=theme["sub_col"]
        )
        self.insta_label.pack(padx=20, pady=(0, 2), anchor="w")

        # Extra Instagram label (v1ru5_0)
        self.insta2_label = ctk.CTkLabel(
            self.sidebar,
            text=theme["ig2"] if theme["ig2"] else "",
            font=ctk.CTkFont(size=11),
            text_color=theme["sub_col"]
        )
        if theme["ig2"]:
            self.insta2_label.pack(padx=20, pady=(0, 15), anchor="w")
        else:
            self.insta2_label.pack(padx=20, pady=(0, 15), anchor="w")
            self.insta2_label.pack_forget()

        # Theme Selection Dropdown
        self.theme_label = ctk.CTkLabel(self.sidebar, text="Select Theme:", text_color=theme["title"], font=ctk.CTkFont(size=12))
        self.theme_label.pack(padx=20, pady=(5, 0), anchor="w")

        self.theme_dropdown = ctk.CTkOptionMenu(
            self.sidebar, 
            values=list(THEMES.keys()),
            command=self.change_theme,
            fg_color=theme["border"],
            button_color=theme["accent"],
            button_hover_color=theme["hover"],
            text_color=theme["entry_text"]
        )
        self.theme_dropdown.set(self.current_theme_name)
        self.theme_dropdown.pack(padx=20, pady=(5, 10), fill="x")

        # Model Selection Dropdown
        self.model_label = ctk.CTkLabel(self.sidebar, text="Select Model:", text_color=theme["title"], font=ctk.CTkFont(size=12))
        self.model_label.pack(padx=20, pady=(5, 0), anchor="w")

        self.model_dropdown = ctk.CTkOptionMenu(
            self.sidebar, 
            values=[DEFAULT_MODEL],
            fg_color=theme["border"],
            button_color=theme["accent"],
            button_hover_color=theme["hover"],
            text_color=theme["entry_text"]
        )
        self.model_dropdown.pack(padx=20, pady=(5, 15), fill="x")

        # Refresh Button
        self.refresh_btn = ctk.CTkButton(
            self.sidebar, 
            text="Ping Models (Refresh)", 
            command=self.fetch_models,
            fg_color=theme["border"],
            hover_color=theme["hover"],
            text_color=theme["title"]
        )
        self.refresh_btn.pack(padx=20, pady=10, fill="x")

        # Install Model Button
        self.install_btn = ctk.CTkButton(
            self.sidebar,
            text="Forge New Model (Install)",
            command=self.open_install_dialog,
            fg_color=theme["border"],
            hover_color=theme["hover"],
            text_color=theme["title"]
        )
        self.install_btn.pack(padx=20, pady=(0, 10), fill="x")

        # --- RIGHT FRAME (CHAT AREA) ---
        self.chat_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.chat_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.chat_frame.grid_rowconfigure(0, weight=1)
        self.chat_frame.grid_columnconfigure(0, weight=1)

        # Chat Textbox
        self.chat_box = ctk.CTkTextbox(
            self.chat_frame, 
            fg_color=theme["box"], 
            text_color=theme["text"],
            font=ctk.CTkFont(family="Consolas", size=13),
            border_color=theme["border"],
            border_width=2,
            wrap="word"
        )
        self.chat_box.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        self.chat_box.configure(state="disabled")

        # Loading status indicator / label
        self.loading_label = ctk.CTkLabel(
            self.chat_frame,
            text="",
            font=ctk.CTkFont(family="Consolas", size=12, slant="italic"),
            text_color=theme["title"],
            anchor="w"
        )
        self.loading_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 5))

        # Input Entry
        self.input_entry = ctk.CTkEntry(
            self.chat_frame, 
            placeholder_text="Enter prompt...", 
            fg_color=theme["entry_bg"],
            text_color=theme["entry_text"],
            border_color=theme["border"],
            font=ctk.CTkFont(size=14),
            height=40
        )
        self.input_entry.grid(row=2, column=0, sticky="ew", padx=(0, 10))
        self.input_entry.bind("<Return>", lambda event: self.send_message())

        # Send Button
        self.send_btn = ctk.CTkButton(
            self.chat_frame, 
            text="EXECUTE", 
            width=140,
            height=40,
            fg_color=theme["accent"],
            text_color=theme["accent_text"],
            hover_color=theme["hover"],
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.send_message
        )
        self.send_btn.grid(row=2, column=1, sticky="e")

        self.fetch_models()
        self.after(800, self.check_first_run)

    def change_theme(self, selected_theme):
        self.current_theme_name = selected_theme
        theme = THEMES[selected_theme]

        # Update root window & sidebar
        self.configure(fg_color=theme["bg"])
        self.sidebar.configure(fg_color=theme["sidebar"])

        # Update text & titles
        self.title_label.configure(text=f"{theme['emoji']} {selected_theme.upper()} {theme['emoji']}", text_color=theme["title"])
        self.subtitle_label.configure(text=theme["subtitle"], text_color=theme["sub_col"])
        self.github_label.configure(text_color=theme["title"])
        self.insta_label.configure(text_color=theme["sub_col"])
        
        # Handle secondary Instagram label visibility
        if theme["ig2"]:
            self.insta2_label.configure(text=theme["ig2"], text_color=theme["sub_col"])
            self.insta2_label.pack(padx=20, pady=(0, 15), anchor="w")
        else:
            self.insta2_label.pack_forget()

        self.theme_label.configure(text_color=theme["title"])
        self.model_label.configure(text_color=theme["title"])

        # Update dropdowns
        for dd in [self.theme_dropdown, self.model_dropdown]:
            dd.configure(
                fg_color=theme["border"],
                button_color=theme["accent"],
                button_hover_color=theme["hover"],
                text_color=theme["entry_text"]
            )

        # Update buttons
        for btn in [self.refresh_btn, self.install_btn]:
            btn.configure(
                fg_color=theme["border"],
                hover_color=theme["hover"],
                text_color=theme["title"]
            )

        # Update chat area
        self.chat_box.configure(
            fg_color=theme["box"],
            text_color=theme["text"],
            border_color=theme["border"]
        )
        self.loading_label.configure(text_color=theme["title"])
        self.input_entry.configure(
            fg_color=theme["entry_bg"],
            text_color=theme["entry_text"],
            border_color=theme["border"]
        )
        self.send_btn.configure(
            fg_color=theme["accent"],
            text_color=theme["accent_text"],
            hover_color=theme["hover"]
        )

    def fetch_models(self):
        def run():
            try:
                req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags")
                with urllib.request.urlopen(req) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    models = [m['name'] for m in data.get('models', [])]
                    if models:
                        self.model_dropdown.configure(values=models)
                        if DEFAULT_MODEL in models:
                            self.model_dropdown.set(DEFAULT_MODEL)
                        else:
                            self.model_dropdown.set(models[0])
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()

    def installed_models(self):
        try:
            req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                return [m['name'] for m in data.get('models', [])]
        except Exception:
            return None

    def check_first_run(self):
        models = self.installed_models()
        if models is None:
            return
        known = [tag for tag, _ in INSTALL_OPTIONS.values()]
        if not any(m in known for m in models):
            self.open_install_dialog()

    def open_install_dialog(self):
        theme = THEMES[self.current_theme_name]
        dlg = ctk.CTkToplevel(self)
        dlg.title("Forge a Model")
        dlg.geometry("460x330")
        dlg.configure(fg_color=theme["sidebar"])
        dlg.transient(self)
        dlg.after(150, dlg.grab_set)

        label = ctk.CTkLabel(dlg, text="", text_color=theme["text"], wraplength=420,
                             font=ctk.CTkFont(size=13), justify="left")
        label.pack(padx=20, pady=(20, 10))
        holder = ctk.CTkFrame(dlg, fg_color="transparent")
        holder.pack(padx=20, pady=10, fill="x")

        def clear():
            for w in holder.winfo_children():
                w.destroy()

        def choose(tag):
            dlg.destroy()
            self.install_model(tag)

        def step_default():
            clear()
            tag, desc = INSTALL_OPTIONS["default"]
            label.configure(text=f"Install the default model?\n{tag} - {desc}\n\n[Y/n]")
            ctk.CTkButton(holder, text="Y (install default)", fg_color=theme["accent"],
                          text_color=theme["accent_text"], hover_color=theme["hover"],
                          command=lambda: choose(tag)).pack(pady=5, fill="x")
            ctk.CTkButton(holder, text="n (pick a heavier model)", fg_color=theme["border"],
                          hover_color=theme["hover"], text_color=theme["title"],
                          command=step_pick).pack(pady=5, fill="x")

        def step_pick():
            clear()
            label.configure(text="Choose a heavier model:")
            for key in ("1", "2", "3"):
                tag, desc = INSTALL_OPTIONS[key]
                ctk.CTkButton(holder, text=f"{key}) {tag} - {desc}", fg_color=theme["border"],
                              hover_color=theme["hover"], text_color=theme["title"],
                              command=lambda t=tag: choose(t)).pack(pady=5, fill="x")
            ctk.CTkButton(holder, text="Cancel", fg_color=theme["box"],
                          hover_color=theme["hover"], text_color=theme["text"],
                          command=dlg.destroy).pack(pady=5, fill="x")

        step_default()

    def install_model(self, tag):
        self.is_speaking = True
        self.update_loading_animation(True, f"Forging model {tag}...")
        self.append_chat("SYSTEM", f"Forging model {tag} via Ollama... this can take a while.")

        def run():
            last_pct = -10
            try:
                payload = json.dumps({"name": tag, "stream": True}).encode('utf-8')
                req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/pull", data=payload,
                                             headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req) as response:
                    for raw in response:
                        line = raw.decode('utf-8').strip()
                        if not line:
                            continue
                        info = json.loads(line)
                        if "error" in info:
                            raise RuntimeError(info["error"])
                        total, done = info.get("total"), info.get("completed")
                        if total and done is not None:
                            pct = int(done * 100 / total)
                            if pct >= last_pct + 10:
                                last_pct = pct
                                self.after(0, self.append_chat, "SYSTEM", f"{tag}: {pct}%")
                self.after(0, self.append_chat, "SYSTEM", f"Model {tag} installed.")
                self.after(0, self.fetch_models)
            except Exception as e:
                self.after(0, self.append_chat, "SYSTEM ERROR", f"Install failed: {e}")
            finally:
                self.is_speaking = False
                self.after(0, lambda: self.update_loading_animation(False))

        threading.Thread(target=run, daemon=True).start()

    def update_loading_animation(self, active, custom_text=None):
        if not active:
            self.loading_label.configure(text="")
            return

        def animate(step=0):
            if not self.is_speaking:
                self.loading_label.configure(text="")
                return
            chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            icon = chars[step % len(chars)]
            text = custom_text if custom_text else "Processing node parameters..."
            self.loading_label.configure(text=f"{icon} {text}")
            self.after(100, lambda: animate(step + 1))

        animate()

    def append_chat(self, sender, message):
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", f"{sender}:\n{message}\n\n")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def send_message(self):
        prompt = self.input_entry.get().strip()
        if not prompt:
            return

        self.input_entry.delete(0, "end")
        self.append_chat("You", prompt)

        selected_model = self.model_dropdown.get()
        self.is_speaking = True
        self.update_loading_animation(True)
        threading.Thread(target=self.process_ai_request, args=(prompt, selected_model), daemon=True).start()

    def process_ai_request(self, prompt, model):
        system_instruction = (
            "ROLE: SENIOR IT ENGINEER, SOFTWARE DEVELOPER & CYBERSECURITY RED TEAMER\n\n"
            "You are an expert IT engineer, senior software developer, and red-team operator with 20+ years of experience. "
            "You write custom security tools and code cleanly, efficiently, and precisely. No fluff or beginner tutorials."
        )

        payload = {
            "model": model,
            "system": system_instruction,
            "prompt": prompt,
            "stream": False
        }

        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/generate", data=data, headers={'Content-Type': 'application/json'})
            
            with urllib.request.urlopen(req) as response:
                res = json.loads(response.read().decode('utf-8'))
                ai_response = res.get("response", "").strip()

                self.after(0, lambda: self.append_chat("AI", ai_response))

        except Exception as e:
            self.after(0, lambda err=e: self.append_chat("SYSTEM ERROR", f"Cannot connect to Ollama node: {err}"))
        finally:
            self.is_speaking = False
            self.after(0, lambda: self.update_loading_animation(False))

if __name__ == "__main__":
    app = MultiThemeAIApp()
    app.mainloop()
