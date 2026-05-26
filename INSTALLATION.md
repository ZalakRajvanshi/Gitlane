# Installation & Setup

## Prerequisites

- Python 3.9+
- Git
- A free [Groq API key](https://console.groq.com)
- (Optional) GitHub token for enhanced file stats

## Quick Start

### Windows

```bash
# Clone the repo
git clone https://github.com/ZalakRajvanshi/gitlane.git
cd gitlane

# Run setup (requires Admin)
.\setup.ps1

# Or manual setup:
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Copy environment template
copy .env.example .env

# Edit .env with your API keys
notepad .env
```

### Linux / macOS

```bash
# Clone the repo
git clone https://github.com/ZalakRajvanshi/gitlane.git
cd gitlane

# Run setup
bash setup.sh

# Or manual setup:
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env
```

## Getting API Keys

### Groq API Key (Free)
1. Visit https://console.groq.com
2. Sign up or log in
3. Create an API key
4. Copy it to `.env` as `GROQ_API_KEY=your_key_here`

### GitHub Token (Optional)
1. Go to https://github.com/settings/tokens
2. Click "Generate new token"
3. Select `repo` scope for read access
4. Copy it to `.env` as `GITHUB_TOKEN=your_token_here`

## First Run

```bash
# On Windows
python main.py

# On Linux/macOS
python main.py
```

Gitlane will guide you through initial configuration.

## Troubleshooting

**"No module named 'groq'"**
- Ensure you've activated the virtual environment
- Run `pip install groq`

**"GROQ_API_KEY not found"**
- Make sure `.env` exists and has your key
- Restart the application

**Import errors**
- Reinstall dependencies: `pip install -r requirements.txt --force-reinstall`
