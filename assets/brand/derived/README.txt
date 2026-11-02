Logos made from the kit one directory up, for two things it does not do.
The drawings are the kit's: each file here is a kit file with one or two
elements deleted and nothing else changed. frontend/test_brand.py compares them,
so a new kit fails that test until these are made again from it.

  simba-logo-stacked-dark.svg           the kit's, without its background
  simba-logo-horizontal-dark.svg        the kit's, without its background
  simba-logo-horizontal-small.svg       the kit's horizontal, without the tagline
  simba-logo-horizontal-small-dark.svg  the same, without background or tagline

Why:
  Background  The kit's dark logos sit on a filled rectangle, #0F1A19. The app's
              dark canvas is #0b1817 (#14100c in palette A), so each stood in a
              visible box, and on GitHub's dark page too.
  Tagline     26 units tall in a logo 300 units tall. At the 48px the home
              screen's corner has room for, that is about 4px, a grey smear on a
              screen where nothing else is under 20px.

The kit's own files are unchanged, and are still the ones for slides, the report
cover and anywhere the logo is large or on its own background.
