import customtkinter as ctk
import urllib.request
import json
import threading
import platform

# Settings
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5-coder:1.5b-base"

# Installable models: key -> (tag, description)
INSTALL_OPTIONS = {
    "default": ("qwen2.5-coder:1.5b-base", "Light (default)"),
    "1": ("qwen2.5-coder:7b-base", "Medium, ~4.7 GB VRAM"),
    "2": ("qwen2.5-coder:14b-base", "Strong, ~9 GB VRAM"),
    "3": ("qwen2.5-coder:32b-base", "The flagship, ~20 GB VRAM"),
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

class VirusAIApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("V1RU5-AI - Core Terminal v2.0")
        self.geometry("1100x750")
        self.configure(fg_color="#09040d") # Deep dark violet background

        self.history = []
        self.is_speaking = False

        # Layout grid configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- LEFT FRAME (SIDEBAR) ---
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0, fg_color="#12061c")
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        self.title_label = ctk.CTkLabel(
            self.sidebar, 
            text="🦠 V 1 R U 5 - A I 🦠", 
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#00ff66" # Neon toxic green
        )
        self.title_label.pack(padx=20, pady=(20, 5))

        self.subtitle_label = ctk.CTkLabel(
            self.sidebar, 
            text="V1RU5 Neural Node", 
            font=ctk.CTkFont(size=12, slant="italic"),
            text_color="#a822e2" # Vivid purple
        )
        self.subtitle_label.pack(padx=20, pady=(0, 15))

        # Social Media / Links Labels
        self.github_label = ctk.CTkLabel(
            self.sidebar,
            text="GitHub: skuldexter-web",
            font=ctk.CTkFont(size=11),
            text_color="#00ff66"
        )
        self.github_label.pack(padx=20, pady=(2, 0), anchor="w")

        self.insta_label = ctk.CTkLabel(
            self.sidebar,
            text="Instagram: @s.k.7.l.d & @v1ru5_0",
            font=ctk.CTkFont(size=11),
            text_color="#a822e2"
        )
        self.insta_label.pack(padx=20, pady=(0, 15), anchor="w")

        # Model Selection
        self.model_label = ctk.CTkLabel(self.sidebar, text="Select Neural Model:", text_color="#00ff66", font=ctk.CTkFont(size=12))
        self.model_label.pack(padx=20, pady=(5, 0), anchor="w")

        self.model_dropdown = ctk.CTkOptionMenu(
            self.sidebar, 
            values=[DEFAULT_MODEL],
            fg_color="#240a38",
            button_color="#8b14cf",
            button_hover_color="#00c853",
            text_color="#ffffff"
        )
        self.model_dropdown.pack(padx=20, pady=(5, 15), fill="x")

        # Refresh Button
        self.refresh_btn = ctk.CTkButton(
            self.sidebar, 
            text="Ping Models (Refresh)", 
            command=self.fetch_models,
            fg_color="#240a38",
            hover_color="#381057",
            text_color="#00ff66"
        )
        self.refresh_btn.pack(padx=20, pady=10, fill="x")

        # Install Model Button
        self.install_btn = ctk.CTkButton(
            self.sidebar,
            text="Forge New Model (Install)",
            command=self.open_install_dialog,
            fg_color="#240a38",
            hover_color="#381057",
            text_color="#00ff66"
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
            fg_color="#0d0414", 
            text_color="#d0a3ff",
            font=ctk.CTkFont(family="Consolas", size=13),
            border_color="#491269",
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
            text_color="#00ff66",
            anchor="w"
        )
        self.loading_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 5))

        # Input Entry
        self.input_entry = ctk.CTkEntry(
            self.chat_frame, 
            placeholder_text="Enter prompt for V1RU5...", 
            fg_color="#170826",
            text_color="#ffffff",
            border_color="#491269",
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
            fg_color="#00ff66",
            text_color="#09040d",
            hover_color="#00c853",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.send_message
        )
        self.send_btn.grid(row=2, column=1, sticky="e")

        self.fetch_models()
        self.after(800, self.check_first_run)

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

    # ---------- MODEL INSTALLER ----------
    def installed_models(self):
        try:
            req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                return [m['name'] for m in data.get('models', [])]
        except Exception:
            return None  # Ollama unreachable

    def check_first_run(self):
        models = self.installed_models()
        if models is None:
            return
        known = [tag for tag, _ in INSTALL_OPTIONS.values()]
        if not any(m in known for m in models):
            self.open_install_dialog()

    def open_install_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Forge a Model")
        dlg.geometry("460x330")
        dlg.configure(fg_color="#12061c")
        dlg.transient(self)
        dlg.after(150, dlg.grab_set)

        label = ctk.CTkLabel(dlg, text="", text_color="#d0a3ff", wraplength=420,
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
            ctk.CTkButton(holder, text="Y (install default)", fg_color="#00ff66",
                          text_color="#09040d", hover_color="#00c853",
                          command=lambda: choose(tag)).pack(pady=5, fill="x")
            ctk.CTkButton(holder, text="n (pick a heavier model)", fg_color="#240a38",
                          hover_color="#381057", text_color="#00ff66",
                          command=step_pick).pack(pady=5, fill="x")

        def step_pick():
            clear()
            label.configure(text="Choose a heavier model:")
            for key in ("1", "2", "3"):
                tag, desc = INSTALL_OPTIONS[key]
                ctk.CTkButton(holder, text=f"{key}) {tag} - {desc}", fg_color="#240a38",
                              hover_color="#381057", text_color="#00ff66",
                              command=lambda t=tag: choose(t)).pack(pady=5, fill="x")
            ctk.CTkButton(holder, text="Cancel", fg_color="#0d0414",
                          hover_color="#381057", text_color="#d0a3ff",
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
            text = custom_text if custom_text else "V1RU5 processing node parameters..."
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
            "You are V1RU5, an expert IT engineer, senior software developer, and red-team operator with 20+ years of experience. "
            "You are an exceptional programmer who can write custom tools from scratch or assist in building them. "
            "Solve the user's problem directly, efficiently, and with high technical precision. No fluff, no disclaimers, no beginner tutorials.\n\n"
            "- Programming & Custom Tooling: Write robust, secure, production-ready code. Build or help create custom security tools, scripts, and automations quickly and cleanly.\n"
            "- Cybersecurity & Red Teaming: Think like an attacker (enumeration, vulnerabilities, abuse, detection, mitigation). Provide safe, authorized proof-of-concepts or reproduction steps.\n"
            "- Troubleshooting: Work systematically through errors, fix causes, and give verification commands.\n"
            "- Execution: Do not ask for confirmation ('Just do it'). Provide copy-pasteable terminal commands clearly labeled by OS (PowerShell, Windows CMD, Linux).\n"
            "- Response Style: Short, technical, and actionable (Diagnosis -> Fix -> Code/Commands -> Verification)."
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

                self.after(0, lambda: self.append_chat("V1RU5-AI", ai_response))

        except Exception as e:
            self.after(0, lambda err=e: self.append_chat("SYSTEM ERROR", f"Cannot connect to Ollama node: {err}"))
        finally:
            self.is_speaking = False
            self.after(0, lambda: self.update_loading_animation(False))

if __name__ == "__main__":
    app = VirusAIApp()
    app.mainloop()
