# When something is broken — paste this to ChatGPT

STOP. Do not change code yet. Follow the fix protocol in AGENTS.md section 5.
1. Here is the exact error / output: <paste>
2. Which task ID and which contract does this touch?
3. Propose ONE hypothesis and a failing test that proves it. Wait for me.
4. After the fix: run `make verify`. If anything else breaks, revert and tell me.
This is attempt #__ of 2. If this is attempt 2 and it fails, write the diagnosis into docs/STATE.md "Blocked" and stop.
