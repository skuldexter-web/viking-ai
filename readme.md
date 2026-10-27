# ⚡ Viking-AI (Skuld's Great Hall v2.0) ⚡

A custom GUI application built with Python and CustomTkinter that acts as your local Senior IT Engineer & Cybersecurity Red Teamer assistant, powered by **Ollama**.

## Features
- **Custom Viking Aesthetic:** Dark wood-themed UI interface.
- **Dynamic Model Manager:** Select or forge/install models directly via Ollama (`qwen2.5-coder` variants).
- **Live Thinking Indicator:** Spinner/loading notifications while querying the local model.

---

## 🛠️ Installation Guide

### Prerequisites (All OS)
1. **Python 3.10+** installed on your system.
2. **Ollama** installed and running. Download and install it from [ollama.com](https://ollama.com).

---

### 🪟 Windows Users

1. **Install Python & Git:** Ensure Python is added to your system PATH during installation.
2. **Clone or download** this repository:
   ```powershell
   git clone [https://github.com/skuldexter-web/viking-ai.git](https://github.com/skuldexter-web/viking-ai.git)
   cd viking-ai
Install the required Python packages:

PowerShell
pip install -r requirements.txt
Pull the default model via Ollama:

PowerShell
ollama pull qwen2.5-coder:1.5b-base
Run the application:

PowerShell
python skuld.py

---

### 🐧 Debian / Linux Users (Ubuntu, Kali, Mint, Debian)

Install Tkinter and Pip (required for CustomTkinter on Linux):
```bash
sudo apt update
sudo apt install python3-tk python3-pip -y
Clone or download this repository:

Bash
git clone [https://github.com/skuldexter-web/viking-ai.git](https://github.com/skuldexter-web/viking-ai.git)
cd viking-ai
Install the required Python packages:

Bash
pip install -r requirements.txt --break-system-packages
# Tip: Alternatively, use a virtual environment: python3 -m venv venv && source venv/bin/activate
Pull the default model via Ollama:

Bash
ollama pull qwen2.5-coder:1.5b-base
Run the application:

Bash
python3 skuld.py

---

### Author
GitHub: skuldexter-web

Instagram: @s.k.7.l.d
