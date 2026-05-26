# Deployment Guide

## Before Your First Push

Run this checklist:

```bash
# 1. Make sure you're in the right directory
cd gitlane

# 2. Check what will be committed
git status

# 3. Verify sensitive files are NOT staged
git status | grep -E '.env|settings.json'
# If these appear, run:
git rm --cached .env settings.json 2>/dev/null || true

# 4. Make sure .gitignore is in place
cat .gitignore | head -5

# 5. Check if any credentials are in your staged files
git diff --cached | grep -i "api_key\|token\|password" || echo "✓ No credentials found"
```

## Initializing Git Repository

If you haven't already:

```bash
# Initialize git
git init

# Add GitHub remote
git remote add origin https://github.com/ZalakRajvanshi/gitlane.git

# Create initial commit
git add .
git commit -m "Initial commit: Gitlane AI assistant"

# Push to GitHub
git branch -M main
git push -u origin main
```

## On GitHub

After pushing, verify:

1. ✅ `.env` is NOT in the repository
2. ✅ `settings.json` is NOT in the repository
3. ✅ `.gitignore` and `.gitattributes` are present
4. ✅ `LICENSE`, `README.md`, `INSTALLATION.md` are visible
5. ✅ No API keys appear in any file

## For Contributors

Create a CONTRIBUTING.md workflow:
```bash
# Fork on GitHub, then:
git clone https://github.com/yourfork/gitlane.git
cd gitlane
git checkout -b feature/your-feature-name
# Make changes
git add .
git commit -m "feat: description of your change"
git push origin feature/your-feature-name
# Create Pull Request on GitHub
```
