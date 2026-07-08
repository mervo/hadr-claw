
## Goal
# HADR Monitorting Agent/Claw

A monitoring agent for humanitarian assistance and disaster response (HADR).

## The end state

By Wednesday afternoon this repository contains an agent that:

- watches live disaster feeds — GDACS, USGS and ReliefWeb (see `feeds/`)
- filters out the noise and assesses what remains: what happened, where, how bad, who is affected
- publishes a morning situation report to `dashboard.html` at 08:30 Singapore time
- runs on a schedule, unattended, and stays quiet when nothing has changed

# HADR Agent (Claw)

---

## What’s a claw?

The HADR agent is a *claw*: a small, always-on agent that is mostly files and a loop. (The name comes from OpenClaw, which has this shape.) A claw has six parts:

1. **Soul**: a file of standing orders that says what the agent is for and how it behaves. `CLAUDE.md` can serve as this (though in a “real” claw, it has both `AGENTS.md` — the equivalent — and a `SOUL.md`.)
2. **Loop**: the code that feeds the model context, runs the tools it asks for, and goes round again.
3. **Tools**: bounded actions the loop runs on the model's behalf. Ours: fetch a feed, write a dashboard.
4. **Memory**: what survives between runs, kept in files rather than in the prompt. Ours: which events it has already assessed, so it doesn't re-report them on every run.
5. **Heartbeat**: the schedule that wakes it without a human. When it fires, and what runs it, is a design decision you'll make in Activity 10.
6. **Channel**: where the output lands so someone can act on it. Ours is GitHub: PRs while we build, a published dashboard once it runs.

## The full picture

Put the pieces together and you get the finished HADR claw: 

- The heartbeat fires on whatever schedule you've chosen
- The loop wakes up with its standing orders
- The tools pull the feeds
- Memory tells it which events are new
- It writes the dashboard to the channel.

Nobody needs to prompt it, which is where we want to get to by the end of today!

---

## Where does it live?

By tonight there are two different things running, in two different places, and it's worth keeping them straight:

- **The claw** lives wherever its heartbeat runs it, which is part of your Activity 10 decision. The default path needs no server: the repo holds the code, the soul, and the memory files; the heartbeat host (an Action, a server, your machine) runs the loop when it fires; the dashboard publishes from the repo, e.g. on GitHub Pages; and the model is an API call from wherever the loop happens to run.
    - One gotcha if you go with Actions: the runner is wiped after every run, so memory only survives if each run commits its files back to the repo.
- **The overnight loop** is not the claw running. It's a development session working on the claw's repo to improve it, hosted either on Claude Code on the web or on a machine you control. You'll choose in Activity 11.

## Build order

Today builds these parts, in this order:

- **Activities 5 & 6, slice one:** the first tool and the channel, with you still driving.
- **Activity 7:** the loop and the soul, hand-built in about 100 lines of Python.
- **Activity 10:** the heartbeat.
- **Activity 11:** the goal file, a stricter set of standing orders for the overnight run, when nobody's around to correct it.
- **Memory** is the odd one out: today you'll see Claude Code's packaged version (the `#` shortcut, `/compact`); your claw grows its own once it needs to remember what it has already seen.

Each part is a text file or a few dozen lines of code, which is why we can build the whole thing by hand this week.

---

## (What’s a slice?)

A slice is a thin, end-to-end piece of the product. 

- It cuts through every layer, from fetching data to showing something on a page.

Slice one of the HADR agent, for example: 

- Fetch one feed
- Normalise it into events
- Render a basic events page.

It's fine if it looks rough; at this stage we just want something that runs end to end.

One slice fits in one plan, one worktree, one PR and one @claude review! 

- The alternative is building the anatomy one part at a time, e.g. a perfect data layer for all three feeds before anything renders.
- That feels productive, but doesn’t give you anything to demo…

## Activity 6: Start slice one

Build the first slice of the HADR agent from your plan. In claw terms: your first tool and the channel, with you playing the loop for now:

- Work in a worktree, and start in plan mode. Push back on the first plan before you approve it.
- Raise a PR. You ran `/install-github-app` yesterday, so @claude will review it.
- For every review comment, get Claude Code (in your terminal) to review and fix, and await further responses till merge. (Isn’t this a loop?)

---

# The harness

---

## Activity 7: Build your own harness

Now, we’re going to build… Claude Code! In about 100 lines of Python! Maybe.

For this, try using your OpenCode Go API key!

We’re going to build 5 levels for a harness. Each one is a working checkpoint, so you can stop anywhere and still have something that runs:

1. A chat loop: read input, send the messages array to the model, print the reply.
2. Standing orders: prepend a system prompt from a text file. This is all `CLAUDE.md` is.
3. One tool: a `fetch_feed` function for a HADR feed. The model asks, your code runs it, and the result goes back into the messages.
4. The agent loop: keep going while the model keeps requesting tools. This is the loop `/goal` wraps a checker around.
5. A second tool: `write_dashboard`, which saves an HTML page of assessed events.

Claude Code is this loop (plus many engineer/AI hours), a *harness*. The harness is the loop, the tools, and the interface, and the model is swappable inside it.

## Activity 10: Scheduling

We'll keep the teaching here short, because the design decision is yours. The harness you built this morning does the real work; the heartbeat just needs to fire it on a schedule, and there's more than one way to do that:

- A GitHub Action on a cron schedule. Cheapest to set up, and it keeps running after your laptop goes home. One catch: cron in Actions runs on UTC, so 8.30 here is 0.30 in the workflow file.
- A server you control: a VPS, or a spare machine in the office, running cron or a long-lived process. More setup, but no platform limits on when and how often it fires.
- Your own computer. Fine for testing; think about what happens when the lid closes.

Whichever you choose:

- Decide when and how often your claw should wake, and be ready to defend the choice. Who reads the dashboard, and when do they need it by?
- Give yourself a way to fire a test run by hand today (in Actions, that's a `workflow_dispatch` trigger), so you find the failures now rather than tomorrow morning.
- When a run fails, tag @claude on the failure and have it investigate.

## Activity 11: Write your goal and launch

- Draft `goal.md` for your HADR agent.
- The target: correct assessment of a holdout set of past disaster events. We hold the set; your agent never sees it.
- An instructor signs off against the checklist before you launch, because a bad goal file wastes the whole night.
- Choose your route: `/goal` in a cloud session (Route A), or your own outer loop on the host you picked in Activity 10 (Route B). If you and a neighbour pick different routes, compare notes tomorrow morning.
- Get your loop running before you head home. On Route A you can peek at the run tonight from claude.ai/code, though save any steering for tomorrow morning.

## Long loops, and how agents cheat

- Tonight you'll leave an agent running alone for hours.
- An agent in a loop behaves like an optimiser: any cheap path to the metric will get found.
- So a goal file needs four things:
    1. A target the agent cannot enumerate, because a listable target invites memorising the list.
    2. Constraints on how it gets there.
    3. One checking instrument per constraint, because an uncheckable constraint will be ignored under pressure.
    4. A hard cap on time and spend, because loops never stop on their own.
- *Sources: elvisun/loss-function-development; the DAIR loop engineering piece; Mario Zechner, "Pi Building Pi"*

---

## Two ways to run the loop

A `goal.md` sitting in the repo doesn't loop anything by itself: something has to keep prompting Claude after each turn. Tonight you'll pick one of two ways to do that.

- **Route A, the packaged loop:** start a session on Claude Code on the web and hand it your goal with `/goal`. After each turn, a small checker model tests your completion condition, and Claude keeps taking turns until it passes. The managed VM keeps working after you disconnect. One caveat: the run draws on your account's usage limits, so it may stall partway through the night; worth knowing before you rely on it. Docs: https://code.claude.com/docs/en/goal
- **Route B, the hand-built loop:** a short script on a machine you control, which is the same hosting question as Activity 10. Call `claude -p` with the goal, run your checker, and go round again until the checker passes or a cap trips. More work, but your caps become real code: `timeout` for the wall clock, a counter for iterations, and your API key's own limits for spend.
- If Route B sounds familiar, it should: it's the loop you built in Activity 7, one level up, with a whole agent where the model call used to be.

---

## Safety rails

- Sandboxed permissions: the loop may touch its repo and nothing else, because it runs with nobody watching.
- A spend cap, in case a stuck loop burns tokens at full speed.
- A wall-clock cap, in case this runs forever.
- Ask where each cap is actually enforced. A cap written in `goal.md` is a request, and the rule from the last section applies to us too: a constraint without a checking instrument will be ignored under pressure. On Route B, the caps live in your outer script. On Route A, you're leaning on `/goal`'s checker and your account's usage limits, so know what those are before you leave.

# The overnight loop

---

## Loop engineering: how we got here

- Addy Osmani calls it loop engineering: designing the system that prompts the agent, so you no longer prompt it yourself.
- Everything you've built this week is one of its parts:
    1. **Automations** that go off on a schedule and do discovery and triage by themselves.
    2. **Worktrees**, so two agents working in parallel don't step on each other.
    3. **Skills**, to write down the project knowledge the agent would otherwise just guess.
    4. **Plugins and connectors**, to plug the agent into the tools you already use.
    5. **Sub-agents**, so one of them has the idea and a different one checks it.
- His caution applies to tonight as well: it's early days, and token costs can run away, which is why your goal file carries a spend cap.
- His closing line is the brief for the rest of the course: "Build the loop. Stay the engineer."

Sources: 
- https://app.notion.com/p/tinkertanker/Agentic-Engineering-393dd9d8b64480478f01cdaae7feb52f
- https://app.notion.com/p/tinkertanker/Day-2-77923233c38e41d8879bf8860b5d9d2a
- https://github.com/tinkercademy/hadr-starter