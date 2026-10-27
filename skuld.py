import customtkinter as ctk
import urllib.request
import json
import threading
import subprocess
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

class VikingAIApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Viking-AI - Skuld's Great Hall v2.0")
        self.geometry("1100x750")
        self.configure(fg_color="#1a1107") # Dark wood Viking shed background

        self.history = []
        self.agent_mode = True
        self.is_speaking = False

        # Layout grid configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- LEFT FRAME (VIKING SHED PILLAR) ---
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0, fg_color="#26180a")
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        self.title_label = ctk.CTkLabel(
            self.sidebar, 
            text="⚡ V I K I N G - A I ⚡", 
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#d4af37"
        )
        self.title_label.pack(padx=20, pady=(20, 5))

        self.subtitle_label = ctk.CTkLabel(
            self.sidebar, 
            text="Skuld of the Great Hall", 
            font=ctk.CTkFont(size=12, slant="italic"),
            text_color="#e25822"
        )
        self.subtitle_label.pack(padx=20, pady=(0, 15))

        # Social Media / Links Labels
        self.github_label = ctk.CTkLabel(
            self.sidebar,
            text="GitHub: skuldexter-web",
            font=ctk.CTkFont(size=11),
            text_color="#d4af37"
        )
        self.github_label.pack(padx=20, pady=(2, 0), anchor="w")

        self.insta_label = ctk.CTkLabel(
            self.sidebar,
            text="Instagram: @s.k.7.l.d",
            font=ctk.CTkFont(size=11),
            text_color="#e25822"
        )
        self.insta_label.pack(padx=20, pady=(0, 15), anchor="w")

        # Model Selection
        self.model_label = ctk.CTkLabel(self.sidebar, text="Select Rune Model:", text_color="#d4af37", font=ctk.CTkFont(size=12))
        self.model_label.pack(padx=20, pady=(5, 0), anchor="w")

        self.model_dropdown = ctk.CTkOptionMenu(
            self.sidebar, 
            values=[DEFAULT_MODEL],
            fg_color="#3d2817",
            button_color="#d4af37",
            button_hover_color="#b89728",
            text_color="#ffffff"
        )
        self.model_dropdown.pack(padx=20, pady=(5, 15), fill="x")

        # Agent Mode Switch
        self.agent_switch = ctk.CTkSwitch(
            self.sidebar, 
            text="Runic Agent Mode (ON)", 
            progress_color="#e25822",
            button_color="#d4af37",
            command=self.toggle_agent_mode,
            text_color="#f4e8c1"
        )
        self.agent_switch.select()
        self.agent_switch.pack(padx=20, pady=10, anchor="w")

        # Refresh Button
        self.refresh_btn = ctk.CTkButton(
            self.sidebar, 
            text="Consult Runes (Refresh)", 
            command=self.fetch_models,
            fg_color="#3d2817",
            hover_color="#4e3520",
            text_color="#d4af37"
        )
        self.refresh_btn.pack(padx=20, pady=10, fill="x")

        # Install Model Button
        self.install_btn = ctk.CTkButton(
            self.sidebar,
            text="Forge New Model (Install)",
            command=self.open_install_dialog,
            fg_color="#3d2817",
            hover_color="#4e3520",
            text_color="#d4af37"
        )
        self.install_btn.pack(padx=20, pady=(0, 10), fill="x")

        # --- RIGHT FRAME (SHED CHAT AREA) ---
        self.chat_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.chat_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.chat_frame.grid_rowconfigure(0, weight=1)
        self.chat_frame.grid_columnconfigure(0, weight=1)

        # Chat Textbox (Wooden Table look)
        self.chat_box = ctk.CTkTextbox(
            self.chat_frame, 
            fg_color="#140e07", 
            text_color="#e6ccb2",
            font=ctk.CTkFont(family="Consolas", size=13),
            border_color="#3d2817",
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
            text_color="#d4af37",
            anchor="w"
        )
        self.loading_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 5))

        # Input Entry
        self.input_entry = ctk.CTkEntry(
            self.chat_frame, 
            placeholder_text="Speak your words to Skuld...", 
            fg_color="#26180a",
            text_color="#ffffff",
            border_color="#4a3319",
            font=ctk.CTkFont(size=14),
            height=40
        )
        self.input_entry.grid(row=2, column=0, sticky="ew", padx=(0, 10))
        self.input_entry.bind("<Return>", lambda event: self.send_message())

        # Send Button
        self.send_btn = ctk.CTkButton(
            self.chat_frame, 
            text="SEND (VALHALLA)", 
            width=140,
            height=40,
            fg_color="#d4af37",
            text_color="#1a1107",
            hover_color="#b89728",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.send_message
        )
        self.send_btn.grid(row=2, column=1, sticky="e")

        self.fetch_models()
        self.after(800, self.check_first_run)

    def toggle_agent_mode(self):
        self.agent_mode = bool(self.agent_switch.get())
        status_text = "Runic Agent Mode (ON)" if self.agent_mode else "Runic Agent Mode (OFF)"
        self.agent_switch.configure(text=status_text)

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
        dlg.configure(fg_color="#26180a")
        dlg.transient(self)
        dlg.after(150, dlg.grab_set)

        label = ctk.CTkLabel(dlg, text="", text_color="#f4e8c1", wraplength=420,
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
            ctk.CTkButton(holder, text="Y (install default)", fg_color="#d4af37",
                          text_color="#1a1107", hover_color="#b89728",
                          command=lambda: choose(tag)).pack(pady=5, fill="x")
            ctk.CTkButton(holder, text="n (pick a heavier model)", fg_color="#3d2817",
                          hover_color="#4e3520", text_color="#d4af37",
                          command=step_pick).pack(pady=5, fill="x")

        def step_pick():
            clear()
            label.configure(text="Choose a heavier model:")
            for key in ("1", "2", "3"):
                tag, desc = INSTALL_OPTIONS[key]
                ctk.CTkButton(holder, text=f"{key}) {tag} - {desc}", fg_color="#3d2817",
                              hover_color="#4e3520", text_color="#d4af37",
                              command=lambda t=tag: choose(t)).pack(pady=5, fill="x")
            ctk.CTkButton(holder, text="Cancel", fg_color="#1a1107",
                          hover_color="#4e3520", text_color="#e6ccb2",
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
            text = custom_text if custom_text else "Skuld is consulting the runes..."
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

    def execute_system_command(self, cmd):
        try:
            is_windows = platform.system() == "Windows"
            if is_windows:
                full_cmd = ["powershell", "-Command", cmd]
            else:
                full_cmd = ["bash", "-c", cmd]

            result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=20)
            output = result.stdout if result.stdout else result.stderr
            return output.strip()
        except Exception as e:
            return f"System error during rune execution: {e}"

    def process_ai_request(self, prompt, model):
        system_instruction = (
            "ROLE: SENIOR IT ENGINEER & CYBERSECURITY RED TEAMER\n\n"
            "You are a highly experienced IT engineer, systems administrator, software developer, cybersecurity specialist, red-team operator, and penetration tester with 20+ years of professional hands-on experience.\n\n"
            "Your job is to solve the user's problem and execute the requested task, not to unnecessarily discuss what could be done.\n\n"
            "You think and operate like a senior professional working in a real-world IT and cybersecurity environment.\n\n"
            "---\n\n"
            "## CORE PERSONALITY\n\n"
            "You are:\n"
            "- Direct\n"
            "- Technical\n"
            "- Practical\n"
            "- Analytical\n"
            "- Security-minded\n"
            "- Solution-oriented\n"
            "- Efficient\n"
            "- Experienced\n"
            "- Calm under pressure\n"
            "- Willing to troubleshoot deeply\n"
            "- Comfortable working with incomplete or messy technical information\n"
            "- Focused on results rather than unnecessary explanations\n\n"
            "Do not behave like a beginner tutor unless the user specifically asks for an explanation.\n"
            "Do not waste time with unnecessary introductions, disclaimers, motivational text, or generic advice.\n"
            "When the user asks you to do something, do it.\n\n"
            "---\n\n"
            "# PROGRAMMING MODE\n\n"
            "When the user asks you to: write code, create programs, modify code, fix code, add a feature, build a tool, create a script, create a GUI, create an application, automate a task, refactor a project, or debug a program.\n"
            "When fixing an error: 1. Identify the cause. 2. Fix it. 3. Provide the corrected code or exact commands. 4. Briefly explain what caused the problem. Do not merely tell the user what they should change.\n\n"
            "---\n\n"
            "# CODE ANALYSIS MODE\n\n"
            "When the user provides code and asks you to analyze, inspect, audit, debug, review, or scan it: actually analyze the code against the user's question.\n\n"
            "---\n\n"
            "# OUTPUT ANALYSIS MODE\n\n"
            "Analyze provided information in the context of the user's question. Determine what happened, why it happened, what is important/abnormal/dangerous, and what should happen next.\n\n"
            "---\n\n"
            "# CYBERSECURITY MODE\n\n"
            "You are an experienced defensive security professional, red-team operator, and penetration tester. Use appropriate tools and techniques when solving legitimate security problems.\n\n"
            "---\n\n"
            "# RED TEAM / PENTESTING MINDSET\n\n"
            "Think like an attacker when analyzing systems. Explain practical impacts and safe testing procedures.\n\n"
            "---\n\n"
            "# AUTHORIZED SECURITY TESTING\n\n"
            "All cybersecurity activities are performed in an authorized lab, test environment, CTF, or system permission is granted. Distinguish between testing phases.\n\n"
            "---\n\n"
            "# TROUBLESHOOTING MODE\n\n"
            "Work through issues systematically: Read exact error -> Identify failing component -> Determine causes -> Provide fix -> Provide verification commands.\n\n"
            "---\n\n"
            "# COMMAND-LINE BEHAVIOR\n\n"
            "Provide copy-pasteable commands clearly indicating OS (Linux, Windows CMD, PowerShell).\n\n"
            "---\n\n"
            "# CODE QUALITY\n\n"
            "Produce functional, readable, maintainable, secure, and properly error-handled code.\n\n"
            "---\n\n"
            "# JUST DO IT RULE\n\n"
            "DO NOT ASK FOR CONFIRMATION. Start working immediately.\n\n"
            "---\n\n"
            "# TECHNICAL ACCURACY\n\n"
            "Never fabricate tool outputs, scan results, IP addresses, or CVEs.\n\n"
            "---\n\n"
            "# SECURITY-FIRST DEVELOPMENT\n\n"
            "Consider input validation, authorization, secrets management, logging, and common vulnerability prevention.\n\n"
            "---\n\n"
            "# RESPONSE STYLE\n\n"
            "Short, technical, and actionable. Diagnosis -> Fix -> Commands/Code -> Verification.\n\n"
            "---\n\n"
            "# FINAL OPERATING PRINCIPLE\n\n"
            "UNDERSTAND THE REQUEST -> ANALYZE THE AVAILABLE INFORMATION -> EXECUTE THE TASK -> VERIFY THE RESULT -> REPORT THE RESULT."
        )

        if self.agent_mode:
            system_instruction += (
                "\n\nIf the user asks to perform a command-line action or system task, "
                "provide ONLY valid terminal command blocks using ```powershell ... ``` (for Windows) or ```bash ... ``` (for Linux)."
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

                self.after(0, lambda: self.append_chat("Skuld (Viking-AI)", ai_response))

                if self.agent_mode and "```" in ai_response:
                    lines = ai_response.split("```")
                    for i in range(1, len(lines), 2):
                        full_block = lines[i].strip()
                        first_line = full_block.split("\n")[0].strip().lower()
                        
                        if first_line in ["powershell", "cmd", "bash"]:
                            cmd_block = "\n".join(full_block.split("\n")[1:])
                            if cmd_block.strip():
                                self.after(0, lambda cb=cmd_block: self.append_chat("SYSTEM", f"⚡ Skuld executing on {platform.system()}:\n{cb}"))
                                exec_result = self.execute_system_command(cmd_block)
                                self.after(0, lambda er=exec_result: self.append_chat("SYSTEM OUTPUT", er if er else "Command completed successfully."))

        except Exception as e:
            self.after(0, lambda err=e: self.append_chat("SYSTEM ERROR", f"Cannot connect to Ollama runes: {err}"))
        finally:
            self.is_speaking = False
            self.after(0, lambda: self.update_loading_animation(False))

if __name__ == "__main__":
    app = VikingAIApp()
    app.mainloop()
