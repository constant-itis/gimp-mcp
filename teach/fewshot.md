# gimp-mcp — worked examples (Opus-authored, verified against live GIMP)

Prompt a local model with these: given the tool set, this is *how* to compose a
sequence to satisfy a design brief. Only verified traces are included.

## On a fresh 1200x400 dark canvas, set a centered gold title 'APOLLO' with a heavy dark outline.
```
new_image(width=1200, height=400)
fill(image_id=144, color='#14141f')
outline_text(image_id=144, text='APOLLO', x=250, y=110, size=180, fill_color='#ffce5a', outline_color='#160a04', outline_width=8)
```
## Weathered/distressed amber headline 'RENEGADE' centered on a dark canvas.
```
new_image(width=1200, height=400)
fill(image_id=146, color='#101018')
add_text(image_id=146, text='RENEGADE', size=150, color='#ffb020', anchor='center')
apply_recipe(name='distressed-text', image_id=146, params='{"grit": 78}')
```
## A round Apollo-style mission patch: a blue planet in the centre with 'THE EAGLE HAS LANDED' arched over the top and 'APOLLO XI' along the bottom.
```
new_image(width=1000, height=1000)
fill(image_id=148, color='#0b0b14')
select(image_id=148, shape='ellipse', x=320, y=320, width=360, height=360)
fill(image_id=148, color='#3a5f9f')
select(image_id=148, shape='none')
arc_text(image_id=148, text='THE EAGLE HAS LANDED', radius=430, size=66, center_angle=90, step_deg=7.4, color='#ffce5a')
arc_text(image_id=148, text='APOLLO XI', radius=430, size=64, center_angle=270, step_deg=9, flip=True, color='#ffce5a')
```
## Turn a solid-white-background graphic into a trimmed transparent PNG (cut it out).
```
new_image(width=600, height=600)
select(image_id=150, shape='ellipse', x=160, y=150, width=300, height=300)
fill(image_id=150, color='#c0392b')
select(image_id=150, shape='none')
color_to_alpha(image_id=150, color='#ffffff')
trim_to_content(image_id=150)
export_image(image_id=150, path='/tmp/teach_cutout.png')
```
## Give a colourful gradient an aged, faded vintage-photo treatment.
```
new_image(width=800, height=600)
gradient_fill(image_id=153, color1='#8fb0d0', color2='#d08040', direction='diagonal')
apply_recipe(name='vintage', image_id=153)
```
## Make a die-cut sticker: a coloured blob on transparency with a thick white edge and soft shadow.
```
new_image(width=600, height=600)
select(image_id=155, shape='ellipse', x=140, y=160, width=320, height=260)
fill(image_id=155, color='#2d7dd2')
select(image_id=155, shape='none')
color_to_alpha(image_id=155, color='#ffffff')
apply_recipe(name='sticker-outline', image_id=155)
```
## Add a subtle bottom-right copyright watermark over a gradient.
```
new_image(width=1000, height=600)
gradient_fill(image_id=157, color1='#20303a', color2='#4a6a7a', direction='vertical')
add_text(image_id=157, text='© STUDIO', size=44, color='#ffffff', anchor='bottom-right')
set_layer(image_id=157, layer_id=1496, opacity=32)
```
## A glowing neon title 'NEON' centered on near-black.
```
new_image(width=1000, height=420)
fill(image_id=159, color='#0a0a12')
text_with_shadow(image_id=159, text='NEON', size=190, color='#38f0e0', anchor='center', blur=22)
```
## Concentric ring seal: gold outer ring, deep-green field, white compass-star center, 'EXPLORERS GUILD' arched top, 'EST MCMXII' along bottom.
```
new_image(width=1000, height=1000)
fill(image_id=161, color='#0c1410')
select(image_id=161, shape='ellipse', x=90, y=90, width=820, height=820)
fill(image_id=161, color='#caa63a')
select(image_id=161, shape='ellipse', x=130, y=130, width=740, height=740)
fill(image_id=161, color='#12402c')
select(image_id=161, shape='ellipse', x=300, y=300, width=400, height=400)
fill(image_id=161, color='#0c1410')
select(image_id=161, shape='none')
add_text(image_id=161, text='✦', x=500, y=500, size=240, color='#f4ecd6', font='Sans Bold', anchor='center')
arc_text(image_id=161, text='EXPLORERS GUILD', radius=415, size=62, font='Serif Bold', center_angle=90, step_deg=8.5, color='#f4ecd6')
arc_text(image_id=161, text='EST MCMXII', radius=415, size=58, font='Serif Bold', center_angle=270, step_deg=9.5, flip=True, color='#caa63a')
```
## Retro-futurist NASA-console mission patch: dark gradient sky, red planet disc, orbit ring, 'ORBITAL COMMAND' arched top, 'FLIGHT 07' bottom.
```
new_image(width=1000, height=1000)
gradient_fill(image_id=163, color1='#0a0d1c', color2='#1c2740', direction='vertical')
select(image_id=163, shape='ellipse', x=120, y=120, width=760, height=760)
fill(image_id=163, color='#0f1424')
select(image_id=163, shape='ellipse', x=250, y=300, width=340, height=340)
fill(image_id=163, color='#c0492f')
select(image_id=163, shape='ellipse', x=300, y=350, width=240, height=240)
fill(image_id=163, color='#e07a52')
select(image_id=163, shape='none')
add_text(image_id=163, text='07', x=650, y=430, size=150, color='#f2c14e', font='Monospace Bold', anchor='center')
arc_text(image_id=163, text='ORBITAL COMMAND', radius=400, size=60, font='Sans Bold', center_angle=90, step_deg=8, color='#e6ecff')
arc_text(image_id=163, text='FLIGHT 07', radius=400, size=58, font='Monospace Bold', center_angle=270, step_deg=9.5, flip=True, color='#f2c14e')
vignette(image_id=163, strength=0.5, feather=0.6)
```
## Navy monogram medallion: cream disc on navy, ringed border, large serif 'H' centered, 'HARBOR & CO' arched top, 'SINCE 1899' bottom.
```
new_image(width=1000, height=1000)
fill(image_id=165, color='#14243c')
select(image_id=165, shape='ellipse', x=110, y=110, width=780, height=780)
fill(image_id=165, color='#c9a24b')
select(image_id=165, shape='ellipse', x=135, y=135, width=730, height=730)
fill(image_id=165, color='#14243c')
select(image_id=165, shape='ellipse', x=250, y=250, width=500, height=500)
fill(image_id=165, color='#f3ecd8')
select(image_id=165, shape='none')
add_text(image_id=165, text='H', x=500, y=500, size=300, color='#14243c', font='Serif Bold', anchor='center')
arc_text(image_id=165, text='HARBOR & CO', radius=415, size=60, font='Serif Bold', center_angle=90, step_deg=9, color='#f3ecd8')
arc_text(image_id=165, text='SINCE 1899', radius=415, size=56, font='Serif Bold', center_angle=270, step_deg=10, flip=True, color='#c9a24b')
```
## Geometric mountain crest: hex-shield feel via layered rectangles, teal-to-white sky, diamond peak, 'SUMMIT SOCIETY' arched top, 'ELEVATE' banner text.
```
new_image(width=1000, height=1000)
fill(image_id=167, color='#0e2b2e')
select(image_id=167, shape='ellipse', x=140, y=140, width=720, height=720)
fill(image_id=167, color='#123c40')
select(image_id=167, shape='none')
gradient_fill(image_id=167, color1='#123c40', color2='#123c40', direction='vertical')
draw_rect(image_id=167, x=300, y=500, width=400, height=6, color='#7fd6c9', fill_shape=True, line_width=1)
add_text(image_id=167, text='▲', x=500, y=470, size=220, color='#7fd6c9', font='Sans Bold', anchor='center')
add_text(image_id=167, text='▲', x=420, y=500, size=120, color='#4a9c92', font='Sans Bold', anchor='center')
add_text(image_id=167, text='▲', x=585, y=505, size=130, color='#4a9c92', font='Sans Bold', anchor='center')
add_text(image_id=167, text='ELEVATE', x=500, y=660, size=66, color='#f2f7f5', font='Sans Bold', anchor='center')
arc_text(image_id=167, text='SUMMIT SOCIETY', radius=400, size=62, font='Sans Bold', center_angle=90, step_deg=8.5, color='#e8f4f1')
add_border(image_id=167, size=14, color='#7fd6c9')
```
## Rustic coffee roaster stamp: kraft-brown field, cream double ring, bean/cup mark, 'MIDNIGHT ROASTERS' arched top, 'SMALL BATCH' bottom, distressed grit.
```
new_image(width=1000, height=1000)
fill(image_id=169, color='#3a2416')
select(image_id=169, shape='ellipse', x=100, y=100, width=800, height=800)
fill(image_id=169, color='#e8dcc0')
select(image_id=169, shape='ellipse', x=128, y=128, width=744, height=744)
fill(image_id=169, color='#3a2416')
select(image_id=169, shape='ellipse', x=155, y=155, width=690, height=690)
fill(image_id=169, color='#e8dcc0')
select(image_id=169, shape='ellipse', x=300, y=300, width=400, height=400)
fill(image_id=169, color='#3a2416')
select(image_id=169, shape='none')
add_text(image_id=169, text='☕', x=500, y=500, size=210, color='#e8dcc0', font='Sans Bold', anchor='center')
arc_text(image_id=169, text='MIDNIGHT ROASTERS', radius=400, size=54, font='Serif Bold', center_angle=90, step_deg=7.5, color='#3a2416')
arc_text(image_id=169, text='SMALL BATCH', radius=400, size=52, font='Serif Bold', center_angle=270, step_deg=9.5, flip=True, color='#8a5a30')
apply_recipe(name='distressed-text', image_id=169, params='{"grit":65}')
```
## Aviation badge: dark navy sky, gold laurel ring, central star, chevron wings text, 'AERO CORPS' arched top, 'PILOT' bottom, drop shadow.
```
new_image(width=1000, height=1000)
gradient_fill(image_id=171, color1='#0a1226', color2='#182a4d', direction='radial')
select(image_id=171, shape='ellipse', x=130, y=130, width=740, height=740)
fill(image_id=171, color='#b8912f')
select(image_id=171, shape='ellipse', x=158, y=158, width=684, height=684)
fill(image_id=171, color='#0d1730')
select(image_id=171, shape='none')
add_text(image_id=171, text='★', x=500, y=440, size=200, color='#f0c34a', font='Sans Bold', anchor='center')
add_text(image_id=171, text='✈', x=500, y=620, size=110, color='#dfe6f2', font='Sans Bold', anchor='center')
arc_text(image_id=171, text='AERO CORPS', radius=400, size=64, font='Sans Bold', center_angle=90, step_deg=9, color='#f0c34a')
arc_text(image_id=171, text='PILOT', radius=400, size=62, font='Sans Bold', center_angle=270, step_deg=11, flip=True, color='#dfe6f2')
drop_shadow(image_id=171, offset_x=0, offset_y=8, blur=18, color='#000000', opacity=60)
```
## Framed Art-Deco cinema poster (portrait): black field, gold frame, radiating sunburst rectangles, 'THE GRAND' large title, 'A MOTION PICTURE EVENT' subtitle, arc tagline bottom.
```
new_image(width=800, height=1100)
gradient_fill(image_id=173, color1='#1a1206', color2='#000000', direction='vertical')
draw_rect(image_id=173, x=360, y=60, width=80, height=460, color='#3a2c0e', fill_shape=True, line_width=1)
draw_rect(image_id=173, x=260, y=90, width=40, height=420, color='#2c220b', fill_shape=True, line_width=1)
draw_rect(image_id=173, x=500, y=90, width=40, height=420, color='#2c220b', fill_shape=True, line_width=1)
draw_rect(image_id=173, x=160, y=130, width=30, height=360, color='#241b08', fill_shape=True, line_width=1)
draw_rect(image_id=173, x=610, y=130, width=30, height=360, color='#241b08', fill_shape=True, line_width=1)
add_text(image_id=173, text='★', x=400, y=300, size=160, color='#e8b93a', font='Serif Bold', anchor='center')
add_text(image_id=173, text='THE GRAND', x=400, y=640, size=96, color='#f4d97a', font='Serif Bold', anchor='center')
add_text(image_id=173, text='A MOTION PICTURE EVENT', x=400, y=730, size=34, color='#c9a24b', font='Sans Bold', anchor='center')
arc_text(image_id=173, text='IN GLORIOUS TECHNICOLOR', radius=300, size=40, font='Serif Bold', center_angle=270, step_deg=8.5, flip=True, color='#e8b93a')
add_border(image_id=173, size=18, color='#c9a24b')
```
## Build a two-tone circular badge with arced text, knock the white background to alpha, and export a die-cut transparent sticker.
```
new_image(width=700, height=700)
select(image_id=175, shape='ellipse', x=90, y=90, width=520, height=520)
fill(image_id=175, color='#1b7a5a')
select(image_id=175, shape='ellipse', x=160, y=160, width=380, height=380)
fill(image_id=175, color='#f4d35e')
select(image_id=175, shape='none')
add_text(image_id=175, text='EST 2130', x=350, y=350, size=54, color='#1b7a5a', font='Sans Bold', anchor='center')
arc_text(image_id=175, text='RESTORATION GUILD', radius=210, size=40, font='Sans Bold', color='#ffffff', center_angle=270, step_deg=18, flip=False)
color_to_alpha(image_id=175, color='#ffffff')
trim_to_content(image_id=175)
export_image(image_id=175, path='/tmp/teach_diecut_circle_badge.png')
```
## Create a bold wordmark over a gradient panel, knock out the white, and export a transparent logo.
```
new_image(width=900, height=400)
select(image_id=178, shape='rectangle', x=60, y=120, width=780, height=160)
gradient_fill(image_id=178, color1='#ff5f6d', color2='#ffc371', direction='horizontal')
select(image_id=178, shape='none')
outline_text(image_id=178, text='TERRA', x=450, y=200, size=120, font='Sans Bold', anchor='center', fill_color='#ffffff')
color_to_alpha(image_id=178, color='#ffffff')
trim_to_content(image_id=178)
export_image(image_id=178, path='/tmp/teach_knockout_gradient_wordmark.png')
```
## Draw a colored disc, trim it to alpha, then apply the sticker-outline recipe to give it a die-cut white edge and shadow.
```
new_image(width=600, height=600)
select(image_id=181, shape='ellipse', x=150, y=150, width=300, height=300)
fill(image_id=181, color='#8e44ad')
select(image_id=181, shape='none')
add_text(image_id=181, text='GO', x=300, y=300, size=110, color='#ffffff', font='Sans Bold', anchor='center')
color_to_alpha(image_id=181, color='#ffffff')
trim_to_content(image_id=181)
apply_recipe(name='sticker-outline', image_id=181, params='{"outline":16,"outline_color":"#ffffff","shadow":20}')
export_image(image_id=181, path='/tmp/teach_sticker_outline_star.png')
```
## Stack two hex-like squares rotated visually via nested rectangles into a layered emblem, knock white to alpha, and export a trimmed transparent badge.
```
new_image(width=640, height=640)
draw_rect(image_id=184, x=140, y=140, width=360, height=360, color='#0f4c81', fill_shape=True, line_width=0)
draw_rect(image_id=184, x=200, y=200, width=240, height=240, color='#2a9d8f', fill_shape=True, line_width=0)
draw_rect(image_id=184, x=200, y=200, width=240, height=240, color='#e9f5db', fill_shape=False, line_width=8)
add_text(image_id=184, text='B', x=320, y=320, size=150, color='#f4d35e', font='Serif Bold', anchor='center')
color_to_alpha(image_id=184, color='#ffffff')
trim_to_content(image_id=184)
export_image(image_id=184, path='/tmp/teach_transparent_hex_emblem.png')
```
## Compose a rounded price-tag shape with text, knock out the white, add a soft drop shadow, and export a print-ready transparent PNG.
```
new_image(width=800, height=500)
draw_rect(image_id=187, x=120, y=150, width=560, height=200, color='#d62828', fill_shape=True, line_width=0)
select(image_id=187, shape='ellipse', x=90, y=180, width=120, height=140)
fill(image_id=187, color='#d62828')
select(image_id=187, shape='ellipse', x=120, y=230, width=40, height=40)
fill(image_id=187, color='#ffffff')
select(image_id=187, shape='none')
add_text(image_id=187, text='SALE', x=430, y=250, size=90, color='#ffffff', font='Sans Bold', anchor='center')
color_to_alpha(image_id=187, color='#ffffff')
trim_to_content(image_id=187)
drop_shadow(image_id=187, offset_x=8, offset_y=8, blur=18, color='#000000', opacity=55)
export_image(image_id=187, path='/tmp/teach_print_ready_tag_shadow.png')
```
## Make a feathered soft-edged colored orb on white, knock out the white to leave a glowing transparent blob, and export it trimmed.
```
new_image(width=600, height=600)
select(image_id=190, shape='ellipse', x=170, y=170, width=260, height=260)
feather_selection(image_id=190, radius=40)
fill(image_id=190, color='#00b4d8')
select(image_id=190, shape='ellipse', x=240, y=240, width=120, height=120)
feather_selection(image_id=190, radius=20)
fill(image_id=190, color='#caf0f8')
select(image_id=190, shape='none')
color_to_alpha(image_id=190, color='#ffffff')
trim_to_content(image_id=190)
export_image(image_id=190, path='/tmp/teach_feathered_glow_cutout.png')
```
## Build an outlined ring stamp with arced text, grit it with the distressed-text recipe, knock out white, and export a worn transparent stamp PNG.
```
new_image(width=700, height=700)
select(image_id=193, shape='ellipse', x=110, y=110, width=480, height=480)
fill(image_id=193, color='#7f5539')
select(image_id=193, shape='ellipse', x=150, y=150, width=400, height=400)
fill(image_id=193, color='#ffffff')
select(image_id=193, shape='none')
arc_text(image_id=193, text='APPROVED ORIGINAL', radius=250, size=42, font='Serif Bold', color='#7f5539', center_angle=270, step_deg=15, flip=False)
add_text(image_id=193, text='OK', x=350, y=350, size=130, color='#7f5539', font='Serif Bold', anchor='center')
apply_recipe(name='distressed-text', image_id=193, params='{"grit":78}')
color_to_alpha(image_id=193, color='#ffffff')
trim_to_content(image_id=193)
export_image(image_id=193, path='/tmp/teach_distressed_transparent_stamp.png')
```
## High-contrast teal-to-magenta duotone over overlapping ellipse shapes.
```
new_image(width=800, height=600)
gradient_fill(image_id=196, color1='#303040', color2='#c0c0d0', direction='vertical')
select(image_id=196, shape='ellipse', x=120, y=140, width=360, height=360)
fill(image_id=196, color='#e8e4d8')
select(image_id=196, shape='ellipse', x=360, y=220, width=320, height=320)
fill(image_id=196, color='#404050')
select(image_id=196, shape='none')
desaturate(image_id=196, mode='luminosity')
curves_adjust(image_id=196, channel='red', points='0,20 128,90 255,235')
curves_adjust(image_id=196, channel='blue', points='0,60 128,150 255,210')
brightness_contrast(image_id=196, brightness=0, contrast=40)
```
## Gritty grunge treatment via oilify plus emboss over a mottled gradient base.
```
new_image(width=768, height=768)
gradient_fill(image_id=198, color1='#6b5a3e', color2='#2a2622', direction='diagonal')
select(image_id=198, shape='rectangle', x=80, y=120, width=300, height=420)
fill(image_id=198, color='#8a7550')
select(image_id=198, shape='rectangle', x=400, y=220, width=280, height=360)
fill(image_id=198, color='#3a3430')
select(image_id=198, shape='none')
oilify(image_id=198, mask_size=9, intensity=6)
emboss(image_id=198, azimuth=135, elevation=30, depth=3, bumpmap=True)
brightness_contrast(image_id=198, brightness=-10, contrast=30)
```
## Brushed embossed-metal look with motion-streaked highlights and a dark border.
```
new_image(width=800, height=600)
gradient_fill(image_id=200, color1='#9a9aa2', color2='#4a4a52', direction='vertical')
select(image_id=200, shape='ellipse', x=250, y=150, width=300, height=300)
fill(image_id=200, color='#c8c8d0')
select(image_id=200, shape='none')
motion_blur(image_id=200, length=40, angle=0, kind='linear')
emboss(image_id=200, azimuth=30, elevation=45, depth=4, bumpmap=False)
desaturate(image_id=200, mode='value')
brightness_contrast(image_id=200, brightness=10, contrast=35)
add_border(image_id=200, size=18, color='#1a1a1e')
```
## Chunky pixel-mosaic treatment over a vivid sunset gradient with a sun disc.
```
new_image(width=800, height=600)
gradient_fill(image_id=202, color1='#ffcf5c', color2='#7a2a6a', direction='vertical')
select(image_id=202, shape='ellipse', x=300, y=180, width=200, height=200)
fill(image_id=202, color='#ff6a3c')
select(image_id=202, shape='none')
hue_saturation(image_id=202, hue=0, saturation=45, lightness=0)
pixelize(image_id=202, block=22)
brightness_contrast(image_id=202, brightness=5, contrast=20)
```
## Zoom-burst sunburst with a lens flare over a warm radial-feeling gradient.
```
new_image(width=800, height=800)
gradient_fill(image_id=204, color1='#1a2038', color2='#d8863c', direction='diagonal')
select(image_id=204, shape='ellipse', x=330, y=330, width=140, height=140)
fill(image_id=204, color='#fff2c0')
select(image_id=204, shape='none')
motion_blur(image_id=204, length=60, angle=0, kind='zoom')
lens_flare(image_id=204, x=400, y=400)
brightness_contrast(image_id=204, brightness=8, contrast=25)
vignette(image_id=204, strength=45, feather=60)
```
## High-contrast posterized pop-art look with inverted psychedelic hues.
```
new_image(width=800, height=600)
gradient_fill(image_id=206, color1='#204080', color2='#e0e0e0', direction='horizontal')
select(image_id=206, shape='ellipse', x=150, y=120, width=260, height=360)
fill(image_id=206, color='#c02040')
select(image_id=206, shape='rectangle', x=440, y=160, width=240, height=300)
fill(image_id=206, color='#20a060')
select(image_id=206, shape='none')
curves_adjust(image_id=206, channel='value', points='0,0 64,10 128,128 192,245 255,255')
brightness_contrast(image_id=206, brightness=0, contrast=60)
invert(image_id=206)
hue_saturation(image_id=206, hue=0, saturation=40, lightness=0)
```
## Soft faded film-grain portrait treatment with vignette over a muted gradient.
```
new_image(width=700, height=800)
gradient_fill(image_id=208, color1='#b8a890', color2='#5c6a6e', direction='vertical')
select(image_id=208, shape='ellipse', x=210, y=220, width=280, height=340)
fill(image_id=208, color='#d8c4a8')
select(image_id=208, shape='none')
gaussian_blur(image_id=208, radius=4)
curves_adjust(image_id=208, channel='value', points='0,30 128,135 255,225')
apply_recipe(name='vintage', image_id=208, params='{"desat":30,"grain":28,"vignette":50}')
```
## A collegiate varsity emblem: 'BRUINS' arched over the year 1924 in stacked athletic lettering on a navy field with a cream outline.
```
new_image(width=1000, height=1000)
fill(image_id=210, color='#0d1b3e')
arc_text(image_id=210, text='BRUINS', radius=300, size=130, font='Serif Bold', color='#f4e9c1', center_angle=90, step_deg=9)
outline_text(image_id=210, text='1924', x=500, y=520, size=200, fill_color='#c9a227', outline_color='#f4e9c1', outline_width=7, font='Serif Bold', anchor='center')
arc_text(image_id=210, text='ATHLETIC CLUB', radius=300, size=70, font='Sans Bold', color='#f4e9c1', center_angle=270, step_deg=12, flip=True)
```
## A 1970s layered 3D title 'SUNSET' where cyan and magenta offset copies stack behind a white face on a warm cream backdrop.
```
new_image(width=1300, height=600)
fill(image_id=212, color='#f6ead0')
add_text(image_id=212, text='SUNSET', x=690, y=320, size=210, color='#e0407a', font='Sans Bold', anchor='center')
add_text(image_id=212, text='SUNSET', x=670, y=305, size=210, color='#3ec6d8', font='Sans Bold', anchor='center')
outline_text(image_id=212, text='SUNSET', x=650, y=290, size=210, fill_color='#fffdf7', outline_color='#26304a', outline_width=5, font='Sans Bold', anchor='center')
```
## A weathered military stencil label 'CARGO 07' spray-painted onto an olive-drab crate, distressed to look worn.
```
new_image(width=1200, height=500)
fill(image_id=214, color='#4b5320')
add_border(image_id=214, size=14, color='#2f3416')
add_text(image_id=214, text='CARGO 07', x=600, y=250, size=150, color='#e8e4d0', font='Monospace Bold', anchor='center')
apply_recipe(name='distressed-text', image_id=214, params='{"grit": 82}')
add_text(image_id=214, text='FRAGILE - THIS SIDE UP', x=600, y=410, size=46, color='#e8e4d0', font='Monospace Bold', anchor='center')
```
## An Old West saloon headline 'GOLD RUSH' in tuscan serif with a hard black shadow on a dusty tan poster, framed by a dark border.
```
new_image(width=1200, height=700)
gradient_fill(image_id=216, color1='#e6cfa0', color2='#c39a5e', direction='vertical')
add_border(image_id=216, size=20, color='#3a2413')
text_with_shadow(image_id=216, text='GOLD', x=600, y=250, size=190, color='#7c1f1f', font='Serif Bold', dx=8, dy=8, blur=2, anchor='center')
text_with_shadow(image_id=216, text='RUSH', x=600, y=470, size=190, color='#7c1f1f', font='Serif Bold', dx=8, dy=8, blur=2, anchor='center')
add_text(image_id=216, text='★ EST. 1849 ★', x=600, y=620, size=44, color='#3a2413', font='Serif Bold', anchor='center')
```
## An elegant interlocking monogram 'V&M' in gold on a black roundel with a thin gold border and a curved luxury tagline.
```
new_image(width=900, height=900)
fill(image_id=218, color='#101014')
add_border(image_id=218, size=8, color='#c8a24a')
outline_text(image_id=218, text='V&M', x=450, y=420, size=300, fill_color='#1a1a20', outline_color='#d9b45a', outline_width=6, font='Serif Bold', anchor='center')
arc_text(image_id=218, text='VILLA MARINA', radius=320, size=60, font='Serif Bold', color='#d9b45a', center_angle=270, step_deg=11, flip=True)
```
## Kinetic stacked typography where the word 'MOTION' repeats down the canvas fading from bright to dark to suggest speed, on a deep purple background.
```
new_image(width=900, height=1200)
gradient_fill(image_id=220, color1='#2a0f4a', color2='#0c0518', direction='vertical')
add_text(image_id=220, text='MOTION', x=450, y=220, size=150, color='#ff5edb', font='Sans Bold', anchor='center')
add_text(image_id=220, text='MOTION', x=450, y=420, size=150, color='#b93fb0', font='Sans Bold', anchor='center')
add_text(image_id=220, text='MOTION', x=450, y=620, size=150, color='#7a2c85', font='Sans Bold', anchor='center')
add_text(image_id=220, text='MOTION', x=450, y=820, size=150, color='#4d1f5c', font='Sans Bold', anchor='center')
add_text(image_id=220, text='MOTION', x=450, y=1020, size=150, color='#2e1638', font='Sans Bold', anchor='center')
```
## A vintage transom-window shop sign reading 'APOTHECARY' in gold serif caps with a drop shadow, arched shop name above and street number below on a frosted teal panel.
```
new_image(width=1400, height=600)
gradient_fill(image_id=222, color1='#2c5f5a', color2='#173432', direction='diagonal')
add_border(image_id=222, size=16, color='#0e211f')
arc_text(image_id=222, text='WEST END', radius=360, size=58, font='Serif Bold', color='#e7d8a8', center_angle=90, step_deg=10)
text_with_shadow(image_id=222, text='APOTHECARY', x=700, y=340, size=140, color='#e9c766', font='Serif Bold', dx=4, dy=5, blur=4, anchor='center')
add_text(image_id=222, text='Nº 214', x=700, y=500, size=56, color='#e7d8a8', font='Serif Bold', anchor='center')
```
