# OpenClaw in Docker (Beginner-Friendly)

This guide helps you run OpenClaw quickly and safely with Docker.

## 0) Quick Environment Check

Before You Start, make sure your machine has:

* [Docker installed](https://docs.docker.com/get-started/introduction/get-docker-desktop/)
* Bash v4+ (For example, MacOS with bash v3 only, you need upgrade with command
```
brew install bash
```
## 1) Clone this repository (HTTPS)

Use HTTPS so you don’t need to configure SSH or `git://`.

```bash
git clone https://github.com/ozbillwang/openclaw-in-docker.git
cd openclaw-in-docker
```

## 2) Set the OpenClaw Docker image

Default:

```bash
export OPENCLAW_IMAGE="alpine/openclaw:latest"
```

> Note: recently, `latest` has had issues for some users, no models you can choice.
> If you hit problems, switch to:

```bash
export OPENCLAW_IMAGE="alpine/openclaw:main"
```

## 3) Run the setup script

```bash
./docker-setup.sh
```

This script will:

* pull openclaw gateway image
* Launch an onboarding wizard
* Start the gateway via Docker Compose
* Generate a gateway token and store it in .env
---

## Onboarding screenshots (for beginners)

You can use the onboarding screenshots from this blog post:

- https://medium.com/towardsdev/run-openclaw-moltbot-clawdbot-safely-with-docker-a-practical-guide-for-beginners-94112a9b57be

---

## Quick troubleshooting

- If startup fails with `latest`, switch to `main` and rerun setup.
- Make sure Docker is running before executing `./docker-setup.sh`.
- Re-run the script after changing `OPENCLAW_IMAGE`.
