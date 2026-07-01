# "I want to do X" — quick index

Fast lookup from intent → the tool or Scheme to reach for. Deep version of each is in
the linked cookbook. MCP wrapper tools (from `server.py`) are in `code font`; raw
Scheme is shown where no wrapper exists.

## Open / create / save
| want | do | more |
|------|-----|------|
| open a file | `load_image(path)` | 01-images-io |
| blank canvas | `new_image(w,h)` | 01 |
| export PNG/JPG/WebP | `export_image(img,path)` (ext picks format) | 01 |
| keep layers editable | `save_xcf(img,path)` | 01 |
| dump each layer to its own PNG | `export_layers(img,dir)` | 01/02 |
| free an image from memory | `close_image(img)` | 01 |

## See what you're doing
| want | do | more |
|------|-----|------|
| look at the image | `render_preview(img)` then Read the PNG | 00-overview |
| list open images | `list_images()` | 01 |
| list the layer stack | `list_layers(img)` | 02 |

## Layers
| want | do | more |
|------|-----|------|
| add blank layer | `new_layer(img,name)` | 02-layers-masks |
| drop a logo/photo on top | `add_layer_from_file(img,path,x,y)` | 02 |
| opacity / blend mode / move | `set_layer(img,lid,opacity=,mode=,x=,y=)` | 02 |
| flatten to one layer | `gimp_eval("(gimp-image-flatten IMG)")` | 02 |
| merge only visible | `merge_visible(img)` | 02 |

## Text
| want | do | more |
|------|-----|------|
| add text | `add_text(img,text,x,y,size,color,font)` | 03-text-fonts |
| center text | compute from `gimp-text-get-extents-fontname` | 03 |
| available fonts | `list_fonts(keyword)` | 03 |
| NOTHING renders | server launched with `-f` → restart without it | 03 |

## Color / tone
| want | do | more |
|------|-----|------|
| brightness/contrast | `brightness_contrast(img,b,c)` | 04-color-tone |
| auto-fix contrast | `auto_levels(img)` | 04 |
| hue / saturation | `hue_saturation(img,h,s,l)` | 04 |
| black & white | `desaturate(img,mode)` | 04 |
| curves | `curves_adjust(img,channel,points)` | 04 |
| invert | `invert(img)` | 04 |

## Transform
| want | do | more |
|------|-----|------|
| resize content | `scale_image(img,w,h)` | 06-transforms-canvas |
| crop | `crop(img,w,h,x,y)` | 06 |
| trim borders | `autocrop(img)` | 06 |
| rotate 90/180/270 | `rotate(img,deg)` | 06 |
| flip | `flip(img,'horizontal')` | 06 |
| bigger canvas, same content | `resize_canvas(img,w,h,x,y)` | 06 |

## Selections / paint / effects
| want | do | more |
|------|-----|------|
| select a region | `select(img,'rectangle',x,y,w,h)` | 05-selections |
| fill selection | `fill(img,color)` | 05/07 |
| draw a box | `draw_rect(img,x,y,w,h,color)` | 07-paint-draw |
| blur | `gaussian_blur(img,radius)` | 08-filters-fx |
| sharpen | `sharpen(img,amount,radius)` | 08 |
| pixelate/censor | `pixelize(img,block)` (select first to scope) | 08 |
| drop shadow | `drop_shadow(img,dx,dy,blur,color,opacity)` | 08 |
| any other filter | `pdb_query("blur")` → `pdb_help(name)` → `gimp_eval` | 08 |

## When there's no wrapper
Anything in GIMP is reachable: `pdb_query("keyword")` to find the procedure,
`pdb_help("name")` for its exact args, then `gimp_eval("(the-call …)")`.
See `cookbook/00-overview.md` for the calling conventions.

## Batch many files
Loop in Python, edit in Scheme, `gimp-image-delete` each when done. See
`cookbook/11-automation.md`.
