# VIKING-AI — Skuld's Great Hall v2.0

> A local AI assistant forged in Valhalla for senior IT engineers, software developers, and cybersecurity red teamers.

---

## Features

- **Viking-Inspired Interface:** Dark, wood-themed CustomTkinter UI.
- **Model Manager:** Select, download, and install supported Ollama models, including `qwen2.5-coder` variants.
- **Live Thinking Indicator:** Real-time visual feedback while the AI processes your requests.
- **Cybersecurity & Coding Focus:** Designed for scripting, debugging, IT administration, and red-team operations.

---

## Installation Guide

### Prerequisites

Before installing VIKING-AI, ensure you have:

- Python 3.10 or newer.
- [Ollama](https://ollama.com) installed and running.
- Git installed to clone the repository.

## Install Ollama

### Linux & Mac

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Windows
```powershell
irm https://ollama.com/install.ps1 | iex
```

---

## Windows Installation

### 1. Clone the Repository

Open PowerShell and run:

```powershell
git clone https://github.com/skuldexter-web/viking-ai.git
cd viking-ai
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Download the Default AI Model

```powershell
ollama pull qwen2.5-coder:1.5b-base
```

### 4. Start VIKING-AI

```powershell
python skuld.py
```

---

## Linux Installation

**Supported distributions:** Debian, Ubuntu, Kali Linux, Linux Mint, and other Debian-based distributions.

### 1. Install the Required Packages

Open a terminal and run:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv python3-tk git -y
```

### 2. Clone the Repository

```bash
git clone https://github.com/skuldexter-web/viking-ai.git
cd viking-ai
```

### 3. Create and Activate a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 5. Download the Default AI Model

```bash
ollama pull qwen2.5-coder:1.5b-base
```

### 6. Start VIKING-AI

```bash
python3 skuld.py
```

---

## Author

- **GitHub:** [skuldexter-web](https://github.com/skuldexter-web)
- **Instagram:** [@s.k.7.l.d](https://www.instagram.com/s.k.7.l.d/)
