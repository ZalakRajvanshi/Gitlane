# Security Policy

## Reporting Security Issues

⚠️ **Do not open a public GitHub issue for security vulnerabilities.**

Instead, please email your findings to the maintainer or use GitHub's private vulnerability reporting feature.

## Safe Practices

When using Gitlane:

- **Never commit `.env` files** — they contain API keys
- **Keep `settings.json` local** — contains personal preferences
- **Don't share your Groq or GitHub tokens** — treat them like passwords
- **Use strong API keys** — regenerate compromised ones immediately

## What We Protect

- Your GitHub activity data remains local
- API keys never leave your `.env` file
- Local database files are not synced publicly

## Updates

Keep Gitlane updated to receive security patches:
```bash
git pull origin main
pip install -r requirements.txt --upgrade
```
