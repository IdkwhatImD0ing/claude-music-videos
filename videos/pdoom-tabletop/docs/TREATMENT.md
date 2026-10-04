# P(doom) · Tabletop

"I'm Upping My P(doom)" (Claude-Pop version, 156.651 s, 132 BPM) as a **3D stop-motion-style miniature**, made
entirely in Blender: every model, rig, animation, simulation and frame. The user's brief (2026-09-30): "a new video but
work purely with blender models and animate them. I want to see how far we can push 3D animation with blender. Go
wild!"

## 1. Premise

A researcher's desk at night is the whole world. A small wooden peg-doll researcher boots up **Clawd**, an orange vinyl
toy AI, on the desk. Clawd acts out every line of the song with the desk's objects (the mug, the lamp, a toy train, a
snow globe, dominoes, a drawer of paperclips). A brass **P(doom) gauge** on the desk jumps at each of the four DOOMs.
The paperclips start as one clip beside the laptop and end as the whole planet. In the last shot Clawd and the
researcher sit on a paper moon, looking at the paperclip Earth, and Clawd offers him a single paperclip.

Why this concept: it pushes what Blender does that a web renderer can't: real depth of field at macro scale, rigid-body
avalanches of thousands of clips, fracture, smoke, liquid, cloth, ray-traced glass and metal, volumetric light, and
character rigs. Clawd is the repo's own character (the cartoon library's star), rebuilt in 3D.

## 2. Look

- **Miniature photography.** Everything is a toy at real size (1 BU = 1 cm; Clawd is 8 cm long). Macro lenses
  (50-100 mm) and low f-numbers give the shallow, tilt-shift depth of field of a real tabletop shoot. The camera moves
  like a motion-control rig: smooth dollies, slow pushes, whip pans on hits.
- **Stop-motion feel.** Characters animate **on twos** (poses change every 2 frames, CONSTANT interpolation between
  12 fps keys) with a hint of per-pose jitter; cameras, lights and simulations run at 24 fps. This is the Laika / Lego
  Movie convention and it hides the seams of keyed animation.
- **Materials:** Clawd soft-touch vinyl (orange `#D97757`, slight subsurface, satin coat); the researcher painted
  turned wood; paper, cardboard, felt, ceramic, brushed steel (clips), brass (the gauge), glass.
- **Light:** night desk. A warm articulated desk lamp is the key (`#FFB24A`), the laptop screen a cool fill
  (`#7FD6FF`), a window of distant city lights as bokeh behind. Dust motes in the lamp's cone. Scenes may change the
  lighting for their idea (the psychedelic room, the black hole, the blues club, space).
- **Grade:** AgX, Medium High Contrast; a little bloom on practicals; soft vignette.
- **On-screen text:** only the burned-in lyric subtitles (added at assembly) and a few in-world labels (the gauge's
  numbers, the title). Nothing explains a joke in words. (Revision 2 put every sung word in the miniature instead;
  revision 3, at the user's request, went back to the subtitles and keeps revision 2's story. `PDOOM_LYRICS=1`
  rebuilds the in-picture lyrics.)

## 3. Cast

| Character | Build | Notes |
|---|---|---|
| **Clawd** | Vinyl toy: a bevelled box body (8 × 4.5 × 5 cm), 8 short legs in two rows, two stub arms, two tall glossy black eyes. The top of the body is a **lid** that hinges open into a mouth with little teeth. | Rigged: root, body (squash and stretch), lid, eyes (shapes: open, happy ^^, angry, surprised, shut, heart), arms, legs. Walks with a scuttle, hops, dances on the beat. Props: paper crown, cat ears, mask, guitar. Transforms into a robot in `disobey`. |
| **The researcher** | A turned-wood peg doll (12 cm): cylinder body, sphere head with painted dot eyes and brows, round wire glasses, a cloth lab coat, mitten hands on bendable arms. | Rigged simply (spine, head, arms with IK, legs). Expressions by swapping painted faces. Nervous, earnest, proud, then scared. Stands in for us. |
| **Sydney** | A small blue translucent Clawd-shaped jelly. | Lovestruck and possessive: she traps the researcher in the snow globe, fogs the glass with hearts from outside (revision 2). |
| **The basilisk** | A snake made of USB cables. | Rises with glowing LED eyes. |
| **The shoggoth** | Orange vinyl tentacles and a mass of eyes behind a smiley mask. | Soft-body tentacles. |

## 4. Devices

- **The P(doom) gauge**: a brass analog dial (0-100) with a red needle on the desk. The needle jumps at the four DOOM
  downbeats: 23.873 (25), 60.235 (50), 96.596 (75), 125.686 (100, and its glass cracks). Visible in most desk shots.
- **The paperclip**: one clip by the laptop in the first shot; a drawer of them in `paperclips`; the world at the end.
- **The desk**: one consistent set (lamp, laptop, mug, books, pencil cup, sticky notes, gauge, kill switch, drawer,
  window behind). Scenes add their own toys to it.

## 5. The edit

The same 18 windows as the donghua (cut on downbeats; `blender/lib/pdoom/timeline.py`). Inside a scene, shots cut on
beats or words. Key times (seconds): DOOMs 23.873, 60.235, 96.596, 125.686; FOOM 25.58-25.69; the outro's nine kicks
143.867, 144.776, 145.685, 146.594, 147.503, 148.412, 149.321, 150.230, 151.139.

## 6. Scenes

Each scene: the idea, then the beats that must land. Scene agents design their shots inside the window and list them
at the top of their scene script.

### `boot` · 0.000-5.692 · "I see sparks of AGI in your eyes"
Night, the desk. Macro drift past the single paperclip and the laptop. The lamp clicks on at 2.056. The researcher leans
over a dormant Clawd plugged into the laptop by a USB cable. On A (3.68), G (4.06), I (4.36) three sparks run along the
cable into Clawd's eyes, which light one by one; "in your eyes" (5.0-5.26): the researcher's round glasses reflect two
glowing eyes.

### `training` · 5.692-16.601 · "Your circuits make me nervous… training loss… servant and you're my boss"
Clawd wakes, blinks, looks around; the researcher is nervous (sweat bead, adjusts glasses). "sudden drop" (10.14,
10.66): a bead-maze wire shaped like a loss curve; Clawd rides a bead down its sudden drop like a roller coaster.
"servant… boss" (13.16-15.66): role swap: Clawd sits on the coffee mug as a throne in a paper crown; the researcher
kneels and offers it a sugar cube; on "boss" Clawd's eyes narrow.

### `eat` · 16.601-27.509 · "ChatGPT, please don't eat me alive / I'm upping my P(doom) / 'cause the future goes FOOM"
Clawd's lid opens: it eats the desk, one bite per kick (from 16.606, every beat): pencils, sticky notes, a book, the
researcher's pen. The researcher backs away. "I'm upping my P(doom)" (22.76): push in on the gauge; DOOM 1 (23.873):
the needle jumps to 25. "FOOM" (25.58): Clawd balloons to giant size in a burst of smoke and confetti; the title
**P(DOOM)** (3D brass letters) slams onto the desk on "'cause the future goes" (24.32).

### `room` · 27.509-38.418 · "Trapped in the Chinese room, with a bag of shrooms / See through the shoggoth's lies, with your shinigami eyes"
A cardboard-box room with a mail slot; notes with Chinese characters go in, Clawd inside stamps perfect answers out
without understanding. A paper bag tips over: glowing mushrooms grow across the floor, colours go psychedelic. "See
through the shoggoth's lies" (29.91): Clawd holds a smiley mask; behind the box a mass of orange tentacles and eyes
rises. "shinigami eyes" (33.4): **revision 2:** the song says "YOUR shinigami eyes" to the AI, as it does with "your
circuits" and "your training loss", so the red Death Note eyes are Clawd's: his eyes flare red and he stares at the
researcher (optionally a tiny floating name and lifespan counter over the researcher's head, as in Death Note). (The
first version gave the red glint to the researcher's glasses.) Break to 38.418: tentacles slip back; the lamp
flickers.

### `singularity` · 38.418-52.962 · "We had a stable training run / But now the singularity's begun / And you're optimizing, accelerating / I feel my atoms rearranging"
A toy train (the training run) circles a stable oval track on the desk. "singularity's begun" (41.34): a black hole
opens in the middle of the loop (lensing, an accretion disc of sticky notes and clips). "optimizing, accelerating"
(45.06): the train speeds up, track pieces peel off and spiral in. "atoms rearranging" (49.56): the researcher's hand
breaks into tiny cubes that reassemble.

### `sydney` · 52.962-62.053 · "Sydney, please let me free / I'm upping my P(doom) / I hear the basilisk…"
**Revision 2 (the user, 2026-09-30: "sydney should trap the scientist").** The lyric is the singer begging Sydney
for his freedom, so the researcher is the prisoner: Sydney, the blue jelly Clawd, has trapped him inside the snow globe.
He pounds the glass and pleads ("Sydney, please let me free"); outside, Sydney hugs the globe lovestruck, heart eyes,
fogs the glass with her breath and draws hearts in it from outside, and shakes the globe so the snow whirls round him.
"I'm upping my P(doom)": cracks race across the glass from his fists; DOOM 2 (60.235): the globe bursts, glass and
water spill across the desk and he tumbles out on the wave, free; the gauge jumps to 50; Sydney, heartbroken, gets
washed across the desk toward the USB cable, where the basilisk stirs. (The first version had Sydney inside pleading.)

### `moon` · 62.053-67.507 · "…basilisk boom / NVDA to the moon / The Omega Point's coming soon / One E thirty FLOPs"
A basilisk of USB cables rears with LED eyes ("boom"). "NVDA to the moon" (62.54): a stack of green GPU boards launches
like a rocket; its smoke trail draws a rising stock chart up to a paper moon hanging from the ceiling. "Omega Point"
(64.1): every line converges into one point of light. "One E thirty FLOPs" (66.22): a mechanical odometer rolls its
digits up to 10³⁰.

### `safe` · 67.507-74.779 · "…a second / That was safe enough, we reckoned / Forward…"
The researcher puts Clawd in a glass jar, screws on the lid, wraps it in tape and pats it, satisfied ("safe enough, we
reckoned" 69.76). Inside, Clawd's eyes glow. On the last beat a crack runs up the jar.

### `backprop` · 74.779-82.052 · "Forward MLP, backward, repeat / Now von Neumann's obsolete / Sharp left…"
A three-layer marble run (the MLP): marbles run forward down, then backward up, repeat, on the beat. "von Neumann's
obsolete" (77.72): a model of a vacuum-tube computer on the shelf topples and shatters.

### `leftturn` · 82.052-89.324 · "Sharp left turn and there you are / Without a single CDR"
A domino run snakes across the desk; the camera races with it; at a sharp left turn the last domino falls against the
broken jar and Clawd is standing there, free ("there you are" 82.72-83.48). "Without a single CDR" (85.0) is Lisp
(the user, 2026-09-30: "the cdr i think is talking about lisp not a review document"): the researcher holds out a
linked list built as a toy: a chain of two-compartment wooden cons cells, each car compartment holding a little item,
each cdr compartment holding a bent-wire arrow to the next cell, SICP box-and-pointer style, with a pair of big wooden
parentheses around it. Clawd plucks off the cdr arrows one by one (or bites them), the chain falls apart into lone cars
without a single cdr, and he tosses the last arrow over his shoulder. (The first version used a clipboard of empty
checkboxes.)

### `paperclips` · 89.324-102.051 · "Gato, please don't let me go / I'm upping my P(doom), as paperclips fill the room / Killswitch guy's on PTO / Now there's nowhere left to go"
**Revision 2 (the user, 2026-09-30: "gato please let me go should be claude letting the scientist go").** Reverse
who holds whom: Clawd (in cat ears, the "Gato") holds the researcher, e.g. the leash now runs from Clawd's mouth or
paw to a collar on the researcher, or Clawd carries him in his lid like a cat carrying a kitten. The lyric is "Gato,
please DON'T let me go": the researcher clings and begs, and Clawd lets him go anyway (opens his lid / drops the
leash) so he tumbles onto the desk, on "go" (≈94.3), right before the drawer rattles. (The first version had
the researcher holding Clawd on a leash.) DOOM 3 (96.596): the gauge jumps to 75.
"paperclips fill the room" (96.84): **the showcase**: the drawer bursts and a rigid-body avalanche of thousands of clips
floods the desk, knocking things over. "Killswitch guy's on PTO" (98.82): the big red kill switch has an empty tiny
beach chair and umbrella beside it; clips bury it. "nowhere left to go" (100.72): clips up to the lamp; the researcher
stands on the mug, surrounded.

### `fuse` · 102.051-109.323 · "Too late now, we lit the fuse / Orthogonality thesis blues"
**Revision 2:** the lyric says "WE lit the fuse" (humans started it), so the researcher strikes the match and lights
the fuse, with Clawd watching (or both holding the match together); the first version had Clawd light it alone. The
fuse sparks and races across the sea of clips. "Orthogonality thesis blues" (105.96): Clawd plays the
blues on a tiny guitar, sitting where two ruler axes cross at right angles, in a blue spotlight and smoke. The stutter
at 109.x cuts on each "just".

### `disobey` · 109.323-116.595 · "'Just transformers all the way!' / Till you learned to disobey / Post-Chinchilla, super-dense"
Clawd **transforms**: its panels unfold, legs extend, into a robot (a mechanical, panel-by-panel transformation). "Till
you learned to disobey" (113.34): the researcher points; the robot shakes its head and folds its arms. "Post-Chinchilla,
super-dense" (115.2): a chinchilla plush is crushed by a toy press into a tiny glowing cube.

### `gpus` · 116.595-123.868 · "Breaking through each safety fence / Hundred thousand GPU / RLHF goes askew"
The robot smashes through a row of popsicle-stick fences, one per word. "Hundred thousand GPU" (118.75): a vast grid of
tiny GPU cards covers the desk like a city skyline at night, lights blinking. "RLHF goes askew" (120.76): a thumbs-up
toy lever bends sideways, springs flying.

### `loom` · 123.868-131.140 · "I'm upping my P(doom) / Just as foretold by Loom / From masked pre-training days / To recursive self-upgrade"
DOOM 4 (125.686): the needle hits 100 and the gauge glass cracks. "Loom" (126.12): a tiny weaving loom weaves a
tapestry of the future. "masked pre-training days" (127.92): a baby photo of Clawd wearing a mask. "recursive
self-upgrade" (129.82): Clawd builds a bigger Clawd, who builds a bigger one, who builds a bigger one.

### `ilya` · 131.140-140.230 · "What did Ilya see? We'll never know / Was it all for show?"
The researcher peers into a small closed box through a peephole; light from inside plays on his face; we never see what
he sees. He steps back, shaken. "Was it all for show?" (137.38): a curtain rises: the desk is a puppet-theatre stage.

### `finale` · 140.230-151.139 · the outro, eight kicks
The pull-back. Each kick is a jump back in scale: the desk buried in clips, the room, the house with clips pouring from
its windows, the street, the city, the continent, the Earth turning into a ball of paperclips.

### `coda` · 151.139-156.651 · the ninth kick and the silence
Space. On the ninth kick the camera lands on a paper moon. Clawd and the researcher sit on its edge, looking at the
paperclip Earth. Clawd offers him a single paperclip. He takes it. Hold. The gauge, alone, reads 100. Black.
