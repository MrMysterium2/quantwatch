# Contributing

Thanks for your interest in QuantWatch! This is primarily a personal
learning/homelab project I maintain on my own, but contributions and feedback
are still welcome.

## Reporting Bugs

Please open an [Issue](https://github.com/MrMysterium2/quantwatch/issues) with:

- A short description of the problem
- Steps to reproduce
- Expected vs. actual behavior
- Relevant logs (`docker logs quantwatch-backend`), if available

**Please never** post real API keys, passwords, or `.env` contents in issues
or pull requests.

## Proposing Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes with a meaningful commit message
4. Open a pull request describing what changed and why

## Local Setup

See [README.md](README.md) for the Docker Compose setup and `.env.example`.

## Style

- Python: PEP 8, meaningful variable names
- Comments/docstrings in English, consistent within a file
- No secret is ever hardcoded — always via `os.getenv(...)`
