# OPAL application video, unified cut (problem and proof, ~2:05)

One video: the existing v5 application cut with a proof section spliced in.
Everything marked KEEP is already on the UEMCP_Demo_v5 timeline and needs no
re-recording. Only the NEW VO lines and three screen captures are new work.

Spoken pace assumed ~2.4 words/sec. New VO is ~75 words (~30s of narration).

| # | Time | Source | AUDIO (Owen) | VIDEO |
|---|------|--------|--------------|-------|
| 1 | 0:00-0:13 | KEEP | Hi. Thanks for reviewing our application. I'm Owen and I'm introducing the Open Accessibility Layer for Unreal Engine. As a developer with a disability, | On camera; OPAL title sting at "Open Accessibility Layer" |
| 2 | 0:13-0:31 | KEEP | ...unfortunately, much of Unreal Engine is inaccessible to me. I interact with my computer with a lip joystick you can see me using here. And sadly, Unreal Engine does not integrate well with on-screen keyboards, | Desktop b-roll over the splice; wide on the joystick line; W-mash footage (s11_oskey) on the keyboards line |
| 3 | 0:31-0:51 | KEEP | ...and even worse, when you press the play button, it locks your mouse and the cursor control, which I can't get back without the help of a caregiver. | Stuck demo insert (s17) with live "Can you hit escape?" audio; camera cutaway |
| 4 | 0:51-1:00 | KEEP | So, we built an MCP server, which I can use with my voice. But we feel this is just the beginning. | Dictation-widget b-roll on the voice line |
| 5 | 1:00-1:05 | NEW VO | In fact, we've already started fixing these problems ourselves. | On camera, tight punch-in |
| 6 | 1:05-1:16 | NEW VO + CAPTURE A | Now when the engine traps my mouse, I just say so. "Stop play" works over the wire, even while the mouse is captured. | Screen rec: genuinely captured in play mode, Claude panel visible, say "stop play", session ends, cursor free. Real time, live sound |
| 7 | 1:16-1:28 | NEW VO + CAPTURE B | Games read the keyboard differently, so our own on-screen keyboard now holds every key the way a game expects. W finally means forward. | Screen rec: Alpha OSK clicks W, viewport or rover actually moves. Optional before/after split with the old W-mash shot |
| 8 | 1:28-1:38 | NEW VO + CAPTURE C | And one engine setting lets my mouse drive Unreal's built-in touch joysticks. Each of these fixes took a day, not a year. | Screen rec: possessed play, virtual thumbsticks, mouse-drag drives the rover |
| 9 | 1:38-1:49 | KEEP | This work came out of our ARPA-H funded simulation project to simulate environments for robotic power wheelchairs. | Take-2 sim passage, first half only; rover orbit + crowd overlays (s12, s13) |
| 10 | 1:49-2:05 | KEEP | I was so excited to collaborate directly with the Unreal Engine to make the engine accessible to developers regardless of disability. So thank you for reviewing our application, and we look forward to hearing from you. | On camera; showcase overlay on the transition; OPAL endcard |

## What this changes against v5

- Rows 5-8 are a new ~38s proof section inserted after "just the beginning",
  where the sim passage currently sits.
- The sim passage (row 9) keeps only its first sentence ("...robotic power
  wheelchairs") and drops "the applications extend far beyond..." to hold the
  total near two minutes. If runtime does not matter, keep the full passage
  (+9s).
- Everything else on the v5 timeline is untouched, including flub cuts, zoom
  alternation, and the camera cutaway.

## To record (one sitting)

**Prerequisites, in order:**
1. Restart Alpha OSK (picks up the game key-hold fix).
2. Restart the UEMCP MCP server (ue_stop_play fix, ue_release_mouse).
3. Editor Preferences > Level Editor > Viewports > Flight Camera Control Type >
   "Use WASD for Camera Controls" (the one setting scripts cannot set).

**Captures (screen rec, real time, keep UI sound):**
- A: play mode, click into the viewport so capture engages, say "stop play".
  Optionally also "release the mouse" as a second beat; the edit picks one.
- B: viewport focused, Alpha OSK W/A/S/D flies the camera; then possessed PIE,
  same keys move the pawn.
- C: press Play as player (not Simulate), thumbsticks appear, drag to drive.

**Narration (webcam, same seat and light as take 3):**
Read rows 5-8 straight through twice. Flubs are fine; cuts land on word gaps.

## Edit plan (for the timeline build)

New take becomes th_take4; captures conform like s17 (full frame, PCM audio
where live sound plays). Proof section replaces the sim insert at the v5
splice point; sim first-sentence re-enters after row 8. QA as always:
audio-only render, transcript diff, splice scan before anything is reported.
