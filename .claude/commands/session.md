---
description: Start a planned work package from docs/sessions (usage: /session 01)
argument-hint: <session number, e.g. 01>
---

Start Duck Gambit session $ARGUMENTS.

1. Open `docs/sessions/README.md` and find the brief whose number is `$ARGUMENTS`. Read that brief in full, then follow its "Prompt" section as your instructions.
2. Check its dependencies are done (look at `git log` and the code they produce). If not, stop and say which are missing.
3. If the brief is marked ⚑, list the questions for John in one message before building anything that depends on the answers. Build what does not depend on them meanwhile.
4. Work on a branch named `session-$ARGUMENTS-<slug>` unless John says otherwise.
5. Finish with `/check`, try the change in the running app, and report: what changed, how to try it, open questions.
