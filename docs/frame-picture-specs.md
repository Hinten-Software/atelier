# Pictures for the Frame: what works best

The Frame is a Fraimic 31.5" e-paper panel with six inks (Spectra 6), hung wide. This is what to make a picture like
so it arrives on the wall as intended. (From the Frame's own project, 2026-11-22; Studio IV's standing requirements,
`deploy/commissions/standing.md`, say the same to a painter.)

## Size and shape

| | |
|---|---|
| Shape | 16:9, wide (landscape) |
| Pixels | 2560 × 1440 is exactly the panel. Bigger in the same shape is fine and loses nothing (5120 × 2880, 3840 × 2160): the server scales it down. |
| Smallest worth sending | 2560 wide. Smaller is enlarged and goes soft. |
| Picture area on the wall | about 70 × 39 cm (27.5 × 15.4 in), about 93 pixels per inch |
| File | JPG at quality 90 or more, or PNG. Colour space sRGB, 8 bits. No transparency (see-through parts become white). |
| File size | whatever it comes to; 1-6 MB is typical. No upper limit that matters. |

Another shape still works, but something gives:

- Wide but not 16:9 (3:2, 4:3, 5:4): the picture fills the frame and the top and bottom are cut off. A 3:2 picture
  loses 16% of its height, a 4:3 picture 25%, a 5:4 picture 30%, half from each edge. If that shape is wanted, keep
  everything that matters out of the top and bottom eighth.
- Tall (portrait): shown whole, with white bars left and right. It uses less than a third of the frame.

Both are settings on the server's web page (Settings → Hanging and pictures) and can be changed; the above is how
they stand now.

## What the six inks can and cannot do

The panel has no in-between colours. Every pixel is black, white, yellow, red, blue or green; all other tones are dot
patterns of those, which mix at viewing distance (about 2 m and up). Measured on this frame (2026-11-22, photograph
against white paper):

| Ink | How it really looks |
|---|---|
| White | a light grey: about half as bright as white paper |
| Black | a dark blue-grey, 13 times darker than the panel's white |
| Yellow | bright and clean, the only bright colour |
| Red | dark and dull, a brick red |
| Blue | dark, a navy |
| Green | very dark, close to a blackish bottle green |

What follows from that:

- Works well: clear shapes, strong light-against-dark, real blacks, warm light (yellows, ochres, golds, warm greys),
  black-and-white and near-monochrome pictures, bold flat areas.
- Comes out darker and duller than painted: bright reds, sky blues, fresh greens, pinks, purples, turquoise. They are
  mixed from dark inks plus white dots, so they lose brilliance. Expect a muted, print-like version.
- Risky: large pale areas with a slight tint (fog, haze, pale skies, cream walls). There is nothing between white and
  the strong inks, so a faint warm tint becomes a scatter of yellow dots and can read as yellow. Either keep such
  areas a neutral grey or make the colour decided.
- Lost: detail finer than about 3 pixels at 2560 × 1440 (hairlines, small text, fine cross-hatching) and very gentle
  gradients, which turn to grain. Lettering in a picture should be at least 40 pixels high.
- Contrast: use the whole range, with something truly black and something truly white in the picture. Low-contrast
  pictures look grey and grainy.

## What the server does to a picture

Nothing needs preparing for the inks; send an ordinary picture. The server scales it to 2560 × 1440, applies the
chosen Tones setting and turns it into dots. Do not send pictures that are already dithered or reduced to six
colours: scaling ruins the dot pattern.

## Getting pictures onto the frame

- Atelier paintings (`final-f.jpg` in a studio's painting folder) are collected by themselves.
- Anything else: the server's web page → Frame → Art → add a picture.
- The frame gets a different picture each morning at its wake time; "Show" on the web page plus a tap on the frame
  brings a chosen one straight away.
