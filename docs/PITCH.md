# Practice game pitch

_Fill in at the start of each practice jam. Practice 1 (Sat Nov 7): remake a tiny arcade game we both know.
Practice 2 (Sun Nov 8): a random theme. Overwrite this file for each one; Git keeps the history._

**Practice round:** 1 (Sat Nov 7) — remake a tiny arcade game

**Theme:** Frogger, in 3D

**One-sentence pitch:** Hop your character across lanes of traffic and a river of floating logs to reach the goal, as many times as you can before you run out of lives.

**Core mechanic (the one thing that has to feel great):** The hop. Each button press moves exactly one tile forward, back, left or right with a quick, snappy jump. It should feel instant, readable and fair, so every death feels like your mistake.

**How you win / how you lose:**
- Win: fill all 3 lily pads on each of 3 levels.
- Lose: run out of lives. You start with 3; cars, water and running out of time each cost one; each new level gives +1.
- Score: +10 per new row, +50 per lily pad, +2 per second left on the clock, +100 for the bonus fly, +100 per level.

**The twist — Sundown (added Nov 3):** every lily pad you fill moves the day on: afternoon → sunset → night. The sun sinks
and turns orange, then street lamps, headlight beams, glowing lily pads and fireflies take over, and the cars speed up
each time. You read danger by light by the last crossing.

**Full-game update (Nov 3, morning):**
- Title screen (PLAY / QUIT, best score) over a bird's-eye view of the live board.
- 3 levels: filling all three pads brings sunrise, fireworks and the next level (faster cars and faster logs, +1 life).
- 30-second crossing timer; spare seconds become bonus points, and the last 5 seconds tick and blink.
- Bonus fly: hops to a random empty pad every 7 seconds, worth +100.
- Pause on P or Esc, best score saved between sessions, Play Again skips the title.

**Length of a playthrough:** 3–5 minutes

**Art style in a few words:** Chunky, bright, toy-like blocks (grey-box shapes with bold colors), top-down-ish camera angled from behind.

**Cut list (things we will NOT build):**
- No crocodiles, diving turtles, or new maps (the 3 levels reuse one board)
- No settings menu (volume, key rebinding)
- No multiplayer or online leaderboard (the best score is local only)
- _Originally cut, then added on Nov 3 when we had spare time: crossing timer, bonus fly, levels, best-score saving, a
  title screen. The frog is our own sphere model, not the template mannequin._
