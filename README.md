# morning-dispatcher

This branch holds no code. It is checked out by the "SpicyStock morning
dispatcher" session, whose only job is to start `.github/workflows/morning.yml`
on `main` (with `dry_run` off) when the owner's weekday 8:21 AM Chicago
scheduled task fires into it. Keeping this branch empty keeps that session's
context, and its cost, small. Nothing here is built, tested or published; the
product lives on `main`.
