"""pack: color — brightness/contrast, hue/sat, desaturate, invert, auto-levels, curves."""
from _core import mcp, bridge, _drawable, _flush


@mcp.tool
def brightness_contrast(image_id: int, brightness: int = 0, contrast: int = 0) -> str:
    """Adjust brightness and contrast (-127..127 each) on the active drawable."""
    d = _drawable(image_id)
    bridge.eval(f"(gimp-brightness-contrast {d} {int(brightness)} {int(contrast)})")
    _flush()
    return f"applied brightness={brightness} contrast={contrast} to image {image_id}"


@mcp.tool
def hue_saturation(image_id: int, hue: float = 0, saturation: float = 0, lightness: float = 0) -> str:
    """Shift hue (-180..180), saturation (-100..100), lightness (-100..100) on the active drawable."""
    d = _drawable(image_id)
    bridge.eval(f"(gimp-drawable-hue-saturation {d} HUE-RANGE-ALL {float(hue)} {float(lightness)} {float(saturation)} 0)")
    _flush()
    return f"hue/sat adjusted image {image_id}"


@mcp.tool
def desaturate(image_id: int, mode: str = "luminosity") -> str:
    """Convert the active drawable to grayscale-in-RGB. mode: lightness|luma|average|luminosity|value."""
    d = _drawable(image_id)
    m = {"lightness": "DESATURATE-LIGHTNESS", "luma": "DESATURATE-LUMA",
         "average": "DESATURATE-AVERAGE", "luminosity": "DESATURATE-LUMINOSITY",
         "value": "DESATURATE-VALUE"}.get(mode.lower(), "DESATURATE-LUMINOSITY")
    bridge.eval(f"(gimp-drawable-desaturate {d} {m})")
    _flush()
    return f"desaturated image {image_id} ({mode})"


@mcp.tool
def invert(image_id: int) -> str:
    """Invert the colors of the active drawable."""
    bridge.eval(f"(gimp-drawable-invert {_drawable(image_id)} FALSE)")
    _flush()
    return f"inverted image {image_id}"


@mcp.tool
def auto_levels(image_id: int) -> str:
    """Auto-stretch contrast (white-balance-ish) on the active drawable."""
    d = _drawable(image_id)
    bridge.eval(f"(gimp-levels-stretch {d})")
    _flush()
    return f"auto-leveled image {image_id}"


@mcp.tool
def curves_adjust(image_id: int, channel: str = "value", points: str = "0,0 255,255") -> str:
    """Apply a curves adjustment. channel: value|red|green|blue|alpha. points: 'x,y x,y ...' (0-255).

    Example to brighten mids: '0,0 128,160 255,255'.
    """
    d = _drawable(image_id)
    ch = {"value": "HISTOGRAM-VALUE", "red": "HISTOGRAM-RED", "green": "HISTOGRAM-GREEN",
          "blue": "HISTOGRAM-BLUE", "alpha": "HISTOGRAM-ALPHA"}.get(channel.lower(), "HISTOGRAM-VALUE")
    raw = []
    for pair in points.split():
        x, y = pair.split(",")
        raw.append(str(int(float(x))))
        raw.append(str(int(float(y))))
    bridge.eval(f"(gimp-curves-spline {d} {ch} {len(raw)} #({' '.join(raw)}))")
    _flush()
    return f"applied curves on {channel} for image {image_id}"
